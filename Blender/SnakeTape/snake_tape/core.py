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
    wrap_mode: str = 'BOTH'
    wrap_edge: str = 'A'
    wrap_depth_mm: float = 3
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
    mesh_detail: str = 'OPTIMIZED'
    mesh_error_mm: float = .02
    paper_bump_mm: float = .003
    stage: str = 'FOLDED'
    reverse: bool = False

    def validate(self):
        for key, value in asdict(self).items():
            if isinstance(value, (int, float)) and not math.isfinite(value):
                raise ValueError(f'{key} must be finite')
        for key in ('thickness_mm','width_mm','wrap_depth_mm','spacing_mm','wave_length_mm','resolution_mm'):
            if getattr(self,key) <= 0:
                raise ValueError(f'{key} must be positive')
        for key in ('variation','wave_strength'):
            if not 0 <= getattr(self,key) <= .8:
                raise ValueError(f'{key} must be between 0 and 0.8')
        if not 0 <= self.angle_deg <= 45:
            raise ValueError('Cut angle must be between 0 and 45 degrees')
        if min(self.fold_radius_mm,self.clearance_mm,self.cut_gap_mm,
               self.cut_stop_mm,self.cut_stop_variation_mm,self.paper_bump_mm) < 0:
            raise ValueError('Radius, clearance, gap, cut-stop and paper-bump distances cannot be negative')
        if self.width_mode not in ('PER_SIDE','TOTAL') or self.stage not in ('BASE','EXTENDED','CUT','FOLDED'):
            raise ValueError('Unknown width mode or preview stage')
        if self.cut_gap_mm >= self.spacing_mm*.25:
            raise ValueError('Cut gap must be smaller than one quarter of spacing')
        if self.mesh_detail not in ('OPTIMIZED','DETAILED'):
            raise ValueError('Unknown mesh detail')
        if self.wrap_mode not in ('BOTH','ONE_EDGE') or self.wrap_edge not in ('A','B'):
            raise ValueError('Unknown wrap mode or edge')
        if not 0 < self.mesh_error_mm <= .1:
            raise ValueError('Shape tolerance must be positive and at most 0.1 mm')
        return self

    def overhang(self, band_width):
        value = self.width_mm if self.width_mode == 'PER_SIDE' else (self.width_mm-band_width)/2
        if value <= 0:
            raise ValueError('Total tape width must exceed the selected band width')
        return value

    def one_edge_dimensions(self,available_width):
        """Allocate flat tape width to a finished wrap depth and its quarter bend."""
        self.validate()
        mid=self.thickness_mm*.5+self.clearance_mm
        if self.wrap_depth_mm<=self.thickness_mm+.2:
            raise ValueError('Wrap depth is too short to bend and settle; increase wrap depth')
        minimum=max(mid,self.thickness_mm*1.5)
        radius=max(mid,self.fold_radius_mm) if self.fold_radius_mm else minimum
        if not self.fold_radius_mm:
            for _ in range(6):
                flat=self.width_mm-self.wrap_depth_mm-radius*math.pi/2
                preferred=max(minimum,min(2*self.thickness_mm,min(available_width,flat)*.4))
                radius=max(minimum,min(preferred,(self.wrap_depth_mm-self.thickness_mm)/3))
        overhang=self.wrap_depth_mm+radius*math.pi/2
        flat=self.width_mm-overhang
        if flat<=2*self.thickness_mm:
            raise ValueError('Overall width must leave a flat part wider than twice the tape thickness after the wrap and bend')
        if flat>available_width+max(1e-4,available_width*1e-6):
            raise ValueError(f'Overall width {self.width_mm:.4g} mm and wrap depth {self.wrap_depth_mm:.4g} mm need '
                             f'{flat:.4g} mm on the selected faces; only {available_width:.4g} mm is available. '
                             'Reduce overall width, increase wrap depth or select a wider face strip.')
        if self.wrap_depth_mm<self.thickness_mm+max(.2,3*radius)-1e-7:
            raise ValueError(f'Wrap depth {self.wrap_depth_mm:.4g} mm is too short for a {radius:.4g} mm fold radius; '
                             'increase wrap depth or reduce fold radius/thickness')
        return {'flat_width_mm':flat,'overhang_mm':overhang,'bend_allowance_mm':radius*math.pi/2,
                'fold_radius_mm':radius,'wrap_depth_mm':self.wrap_depth_mm}


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
