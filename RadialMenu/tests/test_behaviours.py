import tempfile
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from photo_tools.shell import SuiteContext
from radial_gui import RadialService
from button_profiles import default_button


class BehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.context = SuiteContext(self.app, settings_path=self.tmp.name+'/settings.ini')
        with patch.object(RadialService, 'start'), patch.object(RadialService, 'install_tray'):
            self.service = RadialService(self.context)
        self.backend = self.service.input = Mock()
        self.target = (123, 456, 789)
        self.backend.capture.return_value = self.target
        self.backend.application.return_value = 'C:/Test.exe'
        self.backend.valid.return_value = True
        self.backend.focused.return_value = True
        self.backend.gesture_safe.return_value = True
        self.backend.begin_gesture.return_value = True
        self.backend.end_gesture.return_value = True
        self.backend.gesture_state.return_value = 'waiting'
        self.backend.gesture_presses.return_value = 0
        self.backend.begin_hold.return_value = True
        self.backend.repeat_sequence.return_value = True

    def tearDown(self):
        self.service.stop()
        self.app.aboutToQuit.disconnect(self.service.stop)
        self.tmp.cleanup()

    def arm(self, mode):
        buttons = [default_button(i) for i in range(26)]
        buttons[0].update(sequence='Shift+F24', behaviour=mode)
        self.service.profiles.save('C:/Test.exe', buttons)
        self.service.toggle_popup()
        self.service.select_letter(1)
        self.service.send_timer.stop()
        self.assertFalse(self.service.popup.isVisible())
        self.assertIsNotNone(self.service.armed)
        self.backend.begin_gesture.assert_called_once_with(self.service.key)

    def test_hold_toggles_on_fresh_presses_and_survives_release(self):
        self.arm('hold')
        self.service.deliver_letter()
        self.backend.begin_hold.assert_not_called()
        self.backend.gesture_state.return_value = 'ready'
        self.service.deliver_letter()
        self.backend.begin_hold.assert_not_called()
        # A quick press/release can finish between timer ticks.
        self.backend.gesture_state.return_value = 'ready'
        self.backend.gesture_presses.return_value = 1
        self.service.deliver_letter()
        self.service.deliver_letter()
        self.backend.begin_hold.assert_called_once_with(self.target, 'Shift+F24', toggle=True)
        self.backend.gesture_safe.assert_called_with(self.target, allow_mouse=True)
        self.backend.gesture_state.return_value = 'ready'
        self.service.deliver_letter()
        self.assertIsNotNone(self.service.armed)
        self.backend.end_gesture.assert_not_called()
        self.backend.gesture_presses.return_value = 2
        self.service.deliver_letter()
        self.backend.end_gesture.assert_called_once()
        self.assertIsNone(self.service.armed)
        self.service.toggle_popup()
        self.assertTrue(self.service.popup.isVisible())

    def test_repeat_stop_keeps_menu_hidden_until_the_following_press(self):
        self.arm('repeat')
        self.backend.gesture_state.return_value = 'ready'
        self.backend.gesture_presses.return_value = 1
        with patch('radial_gui.time.monotonic', return_value=100):
            self.service.deliver_letter()
            self.service.deliver_letter()
        self.backend.repeat_sequence.assert_called_once_with(self.target, 'Shift+F24', toggle=True)
        with patch('radial_gui.time.monotonic', return_value=100.11):
            self.service.deliver_letter()
        self.assertEqual(self.backend.repeat_sequence.call_count, 2)
        self.assertIsNotNone(self.service.armed)
        self.backend.gesture_presses.return_value = 2
        self.service.deliver_letter()
        self.assertIsNone(self.service.armed)
        self.assertFalse(self.service.popup.isVisible())
        self.service.toggle_popup()
        self.assertTrue(self.service.popup.isVisible())
        self.assertEqual(self.backend.repeat_sequence.call_count, 2)
        self.backend.end_gesture.assert_called_once()

    def test_focus_loss_cancellation_and_send_failure_release_input(self):
        for mode in ('hold', 'repeat'):
            for reason in ('focus', 'escape', 'failure', 'preview', 'stop'):
                with self.subTest(mode=mode, reason=reason):
                    self.backend.reset_mock()
                    self.backend.focused.return_value = True
                    self.backend.gesture_state.return_value = 'waiting'
                    self.backend.gesture_presses.return_value = 0
                    self.backend.begin_hold.return_value = True
                    self.backend.repeat_sequence.return_value = True
                    self.arm(mode)
                    self.backend.gesture_state.return_value = 'down'
                    self.backend.gesture_presses.return_value = 1
                    if reason == 'failure':
                        self.backend.begin_hold.return_value = False
                        self.backend.repeat_sequence.return_value = False
                    self.service.deliver_letter()
                    if reason == 'focus':
                        self.backend.focused.return_value = False
                        self.service.deliver_letter()
                    elif reason == 'escape':
                        self.backend.gesture_state.return_value = 'cancelled'
                        self.service.deliver_letter()
                    elif reason == 'preview':
                        self.service.preview()
                        self.service.popup.hide()
                    elif reason == 'stop':
                        self.service.stop()
                    self.assertIsNone(self.service.armed)
                    self.backend.end_gesture.assert_called_once()
                    self.assertFalse(self.service.send_timer.isActive())

    def test_registration_is_suspended_and_restored_and_hook_failure_does_not_arm(self):
        with patch('radial_gui.ctypes.windll.user32.UnregisterHotKey', return_value=1) as unregister, \
                patch('radial_gui.ctypes.windll.user32.RegisterHotKey', return_value=1) as register:
            self.service.registered = True
            self.arm('hold')
            unregister.assert_called_once()
            self.assertFalse(self.service.registered)
            self.service.cancel_delivery()
            register.assert_called_once()
            self.assertTrue(self.service.registered)
            self.backend.begin_gesture.return_value = False
            self.service.toggle_popup()
            self.service.select_letter(1)
            self.assertIsNone(self.service.armed)
            self.assertIn('Could not capture', self.service.status)
            self.assertEqual(unregister.call_count, 1)
            self.service.registered = False

    def test_mode_markers_have_distinct_rendered_pixels(self):
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QFontDatabase
        from radial_gui import RadialPopup
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        popup = RadialPopup()
        popup.resize(360, 360)
        try:
            for dark in (False, True):
                popup.dark = dark
                images = []
                for mode in ('normal', 'hold', 'repeat'):
                    popup.buttons[0]['behaviour'] = mode
                    images.append(popup.grab().toImage().copy(QRect(164, 6, 32, 24)))
                self.assertNotEqual(images[0], images[1])
                self.assertNotEqual(images[1], images[2])
                self.assertNotEqual(images[0], images[2])
        finally:
            popup.close()

    def test_focus_timeout_and_preview_never_arm(self):
        self.arm('hold')
        self.backend.focused.return_value = False
        with patch('radial_gui.time.monotonic', return_value=10**12):
            self.service.deliver_letter()
        self.assertIsNone(self.service.armed)
        self.backend.begin_hold.assert_not_called()
        self.service.preview()
        self.service.select_letter(1)
        self.assertIsNone(self.service.armed)


class PhysicalInputTests(unittest.TestCase):
    def test_capture_waits_for_initial_release_swallows_trigger_and_ignores_injected(self):
        import ctypes
        from activation_monitor import ActivationMonitor, KBDLLHOOKSTRUCT, INPUT_TAG
        monitor = ActivationMonitor('Ctrl+Alt+Space')
        monitor.api = Mock()
        monitor.api.CallNextHookEx.return_value = 0
        monitor.physical = {17, 18, 162, 164, 32}
        def event(vk, down, injected=False):
            data = KBDLLHOOKSTRUCT(vk, 0, 0x10 if injected else 0, 0, INPUT_TAG if injected else 0)
            return monitor.key_event(0, 0x100 if down else 0x101, ctypes.addressof(data))
        self.assertEqual(monitor.state(), 'waiting')
        self.assertEqual(event(32, False), 0)
        # Once Space releases, modifier releases belong to armed capture.
        for vk in (162, 164):
            self.assertEqual(event(vk, False), 1)
        self.assertEqual(monitor.state(), 'ready')
        for vk in (162, 164, 32):
            self.assertEqual(event(vk, True), 1)
        self.assertEqual(monitor.state(), 'down')
        self.assertEqual(event(32, False, injected=True), 0)
        self.assertEqual(monitor.state(), 'down')
        self.assertEqual(event(160, True), 0)
        self.assertFalse(monitor.safe())
        event(160, False)
        self.assertTrue(monitor.safe())
        self.assertEqual(event(32, False), 1)
        self.assertEqual(monitor.state(), 'ready')
        self.assertEqual(event(27, True), 1)
        self.assertEqual(monitor.state(), 'cancelled')

    def test_remapped_hotkey_events_work_and_own_output_does_not_retrigger(self):
        import ctypes
        from activation_monitor import ActivationMonitor, KBDLLHOOKSTRUCT, INPUT_TAG
        monitor = ActivationMonitor('Ctrl+Alt+Space')
        monitor.ready = True
        monitor.api = Mock()
        monitor.api.CallNextHookEx.return_value = 0
        def event(vk, down, tag=0):
            data = KBDLLHOOKSTRUCT(vk, 0, 0x10, 0, tag)
            return monitor.key_event(0, 0x100 if down else 0x101, ctypes.addressof(data))
        # Software remappers inject untagged input; these must activate Repeat.
        for vk in (162, 164, 32):
            self.assertEqual(event(vk, True), 1)
        self.assertEqual(monitor.state(), 'down')
        self.assertEqual(monitor.press_count, 1)
        from activation_monitor import INPUT_TAG
        for vk in (162, 164, 32):
            self.assertEqual(event(vk, False, INPUT_TAG), 0)
        self.assertEqual(monitor.state(), 'down')
        self.assertEqual(monitor.press_count, 1)
        for vk in (32, 164, 162):
            event(vk, False)
        self.assertEqual(monitor.state(), 'ready')
        for vk in (162, 164, 32):
            event(vk, True)
        event(32, True)  # typematic repeat is not a fresh press
        self.assertEqual(monitor.press_count, 2)

    def test_first_post_selection_hotkey_counts_when_ctrl_alt_stay_held(self):
        import ctypes
        from activation_monitor import ActivationMonitor, KBDLLHOOKSTRUCT
        api, kernel = Mock(), Mock()
        api.SetWindowsHookExW.return_value = 1
        api.CallNextHookEx.return_value = 0
        api.GetAsyncKeyState.side_effect = lambda vk: 0x8000 if vk in (17,18,162,164) else 0
        monitor = ActivationMonitor('Ctrl+Alt+Space')
        with patch('activation_monitor.ctypes.WinDLL', side_effect=[api, kernel]):
            self.assertTrue(monitor.start())
        # Opening Space was released before selection, but Ctrl and Alt remain
        # physically held. The very next Space tap must start the Hold.
        for down in (True, False):
            event = KBDLLHOOKSTRUCT(32, 0, 0, 0, 0)
            monitor.key_event(0, 0x100 if down else 0x101, ctypes.addressof(event))
        self.assertEqual(monitor.press_count, 1)
        self.assertEqual(monitor.state(), 'ready')
        monitor.stop()

    def backend(self):
        from windows_input import WindowsInput
        backend = WindowsInput.__new__(WindowsInput)
        backend.api = Mock()
        backend.api.GetAsyncKeyState.return_value = 0
        backend.focused = Mock(return_value=True)
        backend.monitor = Mock()
        backend.monitor.state.return_value = 'down'
        backend.monitor.safe.return_value = True
        backend.monitor.stop.return_value = True
        backend.gesture_held = []
        events = []
        def send(count, payload, size):
            from activation_monitor import INPUT_TAG
            self.assertTrue(all(payload[i].ki.dwExtraInfo == INPUT_TAG for i in range(count)))
            events.extend((payload[i].ki.wVk, payload[i].ki.dwFlags) for i in range(count))
            return count
        backend.api.SendInput.side_effect = send
        return backend, events

    def test_arming_clears_held_activation_modifiers_without_losing_physical_state(self):
        from activation_monitor import ActivationMonitor
        backend, events = self.backend()
        monitor = ActivationMonitor('Ctrl+Alt+Space')
        monitor.physical = {17,18,163,165}
        monitor.start = Mock(return_value=True)
        monitor.ready = True
        with patch('activation_monitor.ActivationMonitor', return_value=monitor):
            self.assertTrue(backend.begin_gesture('Ctrl+Alt+Space'))
        self.assertEqual(events, [(165,3), (163,3)])
        self.assertEqual(monitor.physical, {17,18,163,165})
        self.assertEqual(backend.gesture_held, [])

    def test_active_hold_allows_mouse_use_without_losing_focus_guard(self):
        backend, _ = self.backend()
        backend.api.GetAsyncKeyState.return_value = 0x8000
        self.assertFalse(backend.gesture_safe((1,2,3)))
        self.assertTrue(backend.gesture_safe((1,2,3), allow_mouse=True))
        self.assertTrue(backend.repeat_sequence((1,2,3), 'A', toggle=True))
        backend.focused.return_value = False
        self.assertFalse(backend.gesture_safe((1,2,3), allow_mouse=True))

    def test_modifiers_only_payloads_for_normal_hold_and_repeat(self):
        backend, events = self.backend()
        backend.keys_released = Mock(return_value=True)
        self.assertTrue(backend.send_sequence((1,2,3), 'Ctrl+Alt'))
        tap = [(17,0),(18,0),(18,2),(17,2)]
        self.assertEqual(events, tap)
        events.clear()
        self.assertTrue(backend.begin_hold((1,2,3), 'Ctrl+Shift'))
        self.assertEqual(events, [(17,0),(16,0)])
        self.assertTrue(backend.end_gesture())
        self.assertEqual(events, [(17,0),(16,0),(16,2),(17,2)])
        backend.monitor = Mock()
        backend.monitor.state.return_value = 'down'
        backend.monitor.safe.return_value = True
        events.clear()
        self.assertTrue(backend.repeat_sequence((1,2,3), 'Ctrl+Alt'))
        self.assertEqual(events, tap)

    def test_hold_down_and_reverse_release_survive_focus_loss(self):
        backend, events = self.backend()
        self.assertTrue(backend.begin_hold((1,2,3), 'Ctrl+Shift+Left'))
        self.assertEqual(events, [(17,0), (16,0), (37,1)])
        backend.focused.return_value = False
        self.assertTrue(backend.end_gesture())
        self.assertEqual(events[3:], [(37,3), (16,2), (17,2)])
        self.assertEqual(backend.gesture_held, [])
        backend.end_gesture()
        self.assertEqual(len(events), 6)

    def test_repeat_balances_every_chord_and_checks_physical_state(self):
        backend, events = self.backend()
        for _ in range(2):
            self.assertTrue(backend.repeat_sequence((1,2,3), 'Ctrl+C, Alt+Right'))
        batch = [(17,0), (67,0), (67,2), (17,2), (18,0), (39,1), (39,3), (18,2)]
        self.assertEqual(events, batch*2)
        self.assertEqual(backend.gesture_held, [])
        backend.monitor.state.return_value = 'ready'
        self.assertFalse(backend.repeat_sequence((1,2,3), 'A'))
        self.assertEqual(events, batch*2)

    def test_partial_send_releases_only_inserted_downs(self):
        backend, events = self.backend()
        backend.api.SendInput.side_effect = None
        backend.api.SendInput.return_value = 1
        self.assertFalse(backend.begin_hold((1,2,3), 'Ctrl+Shift+A'))
        self.assertEqual(backend.gesture_held, [17])
        released = []
        def cleanup(count, payload, size):
            released.extend((payload[i].ki.wVk, payload[i].ki.dwFlags) for i in range(count))
            return count
        backend.api.SendInput.side_effect = cleanup
        self.assertTrue(backend.end_gesture())
        self.assertEqual(released, [(17,2)])

    def test_key_release_retries_after_a_transient_send_failure(self):
        backend, events = self.backend()
        self.assertTrue(backend.begin_hold((1,2,3), 'Shift+A'))
        backend.api.SendInput.side_effect = [0, 2]
        self.assertTrue(backend.end_gesture())
        self.assertEqual(backend.gesture_held, [])
        self.assertEqual(backend.api.SendInput.call_count, 3)

    def test_capture_installs_and_uninstalls_on_windows(self):
        from activation_monitor import ActivationMonitor
        monitor = ActivationMonitor('F8')
        try:
            self.assertTrue(monitor.start())
            self.assertIsNotNone(monitor.callback)
        finally:
            self.assertTrue(monitor.stop())
        self.assertIsNone(monitor.handle)
