"""Deterministic, UI-independent dimensions and cutting patterns (millimetres)."""
from dataclasses import asdict, dataclass
import math
import random


def mm_to_units(mm, scene_scale):
    if scene_scale <= 0:
        raise ValueError('Scene scale must be positive')
    return mm / (1000 * scene_scale)


@dataclass
class Settings:
    thickness_mm: float = .1
    width_mode: str = 'PER_SIDE'
    width_mm: float = 10
    spacing_mm: float = 3
    variation: float = .25
    angle_deg: float = 10
    cut_stop_mm: float = 0
    cut_stop_variation_mm: float = 0
    wave_strength: float = .2
    wave_length_mm: float = 25
    seed: int = 1
    fold_radius_mm: float = 0
    clearance_mm: float = .01
    cut_gap_mm: float = .06
    resolution_mm: float = .65
    stage: str = 'FOLDED'
    reverse: bool = False

    def validate(self):
        for key, value in asdict(self).items():
            if isinstance(value, (int, float)) and not math.isfinite(value):
                raise ValueError(f'{key} must be finite')
        for key in ('thickness_mm','width_mm','spacing_mm','wave_length_mm','resolution_mm'):
            if getattr(self,key) <= 0:
                raise ValueError(f'{key} must be positive')
        for key in ('variation','wave_strength'):
            if not 0 <= getattr(self,key) <= .8:
                raise ValueError(f'{key} must be between 0 and 0.8')
        if not 0 <= self.angle_deg <= 45:
            raise ValueError('Cut angle must be between 0 and 45 degrees')
        if min(self.fold_radius_mm,self.clearance_mm,self.cut_gap_mm,
               self.cut_stop_mm,self.cut_stop_variation_mm) < 0:
            raise ValueError('Radius, clearance, gap and cut-stop distances cannot be negative')
        if self.width_mode not in ('PER_SIDE','TOTAL') or self.stage not in ('BASE','EXTENDED','CUT','FOLDED'):
            raise ValueError('Unknown width mode or preview stage')
        if self.cut_gap_mm >= self.spacing_mm*.25:
            raise ValueError('Cut gap must be smaller than one quarter of spacing')
        return self

    def overhang(self, band_width):
        value = self.width_mm if self.width_mode == 'PER_SIDE' else (self.width_mm-band_width)/2
        if value <= 0:
            raise ValueError('Total tape width must exceed the selected band width')
        return value


def cuts(length, settings, closed=False):
    settings.validate()
    if length <= 0:
        raise ValueError('The rim must have positive length')
    count = max(1,round(length/settings.spacing_mm))
    if count > 4000:
        raise ValueError('Too many cuts; increase Cut spacing')
    rng = random.Random(settings.seed)
    cycles = max(1, round(length/settings.wave_length_mm)) if closed else length/settings.wave_length_mm
    phase = rng.uniform(0, math.tau)
    weights = [max(.2,1 + rng.uniform(-settings.variation,settings.variation)
                   + settings.wave_strength*math.sin(math.tau*cycles*(i+.5)/count+phase)) for i in range(count)]
    normalizer = length/sum(weights)
    positions = [0.0]
    for weight in weights:
        positions.append(positions[-1]+weight*normalizer)
    positions[-1] = length
    angles = [math.radians(settings.angle_deg)*(.45*rng.uniform(-1,1)+.55*math.sin(math.tau*cycles*s/length+phase)) for s in positions]
    if closed:
        angles[-1] = angles[0]
    else:
        angles[0] = angles[-1] = 0
    return positions, angles


def cut_stops(positions,settings,closed=False,side=0,max_stop=None):
    """Distance left uncut from the fold line at each slit, in millimetres.

    An independent random stream preserves the existing cut positions/angles.
    A zero mean with positive variation deliberately mixes full and shorter cuts.
    """
    settings.validate()
    if max_stop is not None and max_stop<0:
        raise ValueError('Maximum cut-stop distance cannot be negative')
    rng=random.Random(settings.seed ^ 0x43555444 ^ (side*0x9e3779b9))
    result=[]
    for _ in positions:
        value=max(0,settings.cut_stop_mm+rng.uniform(-settings.cut_stop_variation_mm,
                                                    settings.cut_stop_variation_mm))
        result.append(min(value,max_stop) if max_stop is not None else value)
    if closed and result:
        result[-1]=result[0]
    return result
