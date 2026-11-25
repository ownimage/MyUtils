import math
import unittest

from snake_tape.core import Settings, cuts, mm_to_units


class SettingsTests(unittest.TestCase):
    def test_scene_scale_conversion(self):
        self.assertAlmostEqual(mm_to_units(10, 1), .01)
        self.assertAlmostEqual(mm_to_units(10, .001), 10)

    def test_width_modes_include_original_band(self):
        self.assertEqual(Settings(width_mm=10).overhang(4), 10)
        self.assertEqual(Settings(width_mode='TOTAL', width_mm=20).overhang(4), 8)

    def test_insufficient_total_width_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'width'):
            Settings(width_mode='TOTAL', width_mm=3).overhang(4)

    def test_invalid_settings_are_rejected(self):
        for values in ({'thickness_mm': 0}, {'spacing_mm': -1},
                       {'variation': 1.1}, {'wave_length_mm': 0},
                       {'width_mm': float('nan')}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Settings(**values).validate()


class CutTests(unittest.TestCase):
    def test_cut_stops_default_to_full_depth(self):
        from snake_tape.core import cut_stops
        positions,_=cuts(60,Settings(),True)
        self.assertEqual(cut_stops(positions,Settings(),True),[0]*len(positions))

    def test_cut_stop_variation_is_repeatable_bounded_and_independent(self):
        from snake_tape.core import cut_stops
        settings=Settings(cut_stop_mm=.5,cut_stop_variation_mm=.5)
        positions,_=cuts(60,settings,True)
        values=cut_stops(positions,settings,True)
        self.assertEqual(values,cut_stops(positions,settings,True))
        self.assertEqual(values[0],values[-1])
        self.assertTrue(all(0<=v<=1 for v in values))
        self.assertGreater(max(values)-min(values),.5)
        self.assertNotEqual(values,cut_stops(positions,settings,True,side=1))
        self.assertEqual(cuts(60,Settings(),True),cuts(60,settings,True))

    def test_zero_mean_can_mix_full_and_short_cuts(self):
        from snake_tape.core import cut_stops
        settings=Settings(cut_stop_variation_mm=1)
        positions,_=cuts(120,settings,True)
        values=cut_stops(positions,settings,True)
        self.assertIn(0,values)
        self.assertTrue(any(v>.1 for v in values))

    def test_cut_stop_values_are_nonnegative_and_leave_a_cut(self):
        from snake_tape.core import cut_stops
        for kwargs in ({'cut_stop_mm':-1},{'cut_stop_variation_mm':-1}):
            with self.assertRaises(ValueError):
                Settings(**kwargs).validate()
        positions,_=cuts(60,Settings(),True)
        values=cut_stops(positions,Settings(cut_stop_variation_mm=100),True,max_stop=2)
        self.assertTrue(all(0<=v<=2 for v in values))

    def test_repeatable_but_seed_changes_pattern(self):
        a = cuts(100, Settings(seed=8), False)
        self.assertEqual(a, cuts(100, Settings(seed=8), False))
        self.assertNotEqual(a, cuts(100, Settings(seed=9), False))

    def test_partition_is_positive_and_covers_length(self):
        for closed in (False, True):
            for seed in range(15):
                positions, angles = cuts(113.7, Settings(seed=seed), closed)
                self.assertEqual(positions[0], 0)
                self.assertAlmostEqual(positions[-1], 113.7)
                self.assertGreater(min(b-a for a, b in zip(positions, positions[1:])), 1)
                self.assertEqual(len(positions), len(angles))

    def test_zero_variation_and_angles(self):
        p, a = cuts(30, Settings(variation=0, wave_strength=0, angle_deg=0), False)
        self.assertTrue(all(abs((y-x)-3) < 1e-8 for x, y in zip(p, p[1:])))
        self.assertTrue(all(x == 0 for x in a))

    def test_closed_noise_and_angle_have_no_seam_jump(self):
        p, a = cuts(120, Settings(), True)
        self.assertEqual(a[0], a[-1])

    def test_wave_only_pattern_is_smooth(self):
        p, _ = cuts(120, Settings(variation=0, wave_strength=.3, wave_length_mm=40), True)
        widths = [b-a for a, b in zip(p, p[1:])]
        differences = [abs(b-a) for a, b in zip(widths, widths[1:])]
        self.assertLess(max(differences), .65)
        self.assertGreater(max(widths)-min(widths), .5)


if __name__ == '__main__':
    unittest.main()
