"""Shared native preview and JPEG renderer. Coordinates are canvas pixels."""
from __future__ import annotations
import copy
import json
import math
import os
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QImageReader,
                          QPainter, QPainterPath, QFontMetricsF, QPen)
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent
SYSTEM_DEFAULT_PATH = ROOT / 'default_template.json'
USER_DEFAULT_PATH = ROOT / 'template.json'
_app = None
_registered = set()


def ensure_fonts():
    global _app
    if QApplication.instance() is None:
        _app = QApplication([])
    # Register local Windows fonts for headless previews; never copy them.
    system_fonts = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'Fonts'
    candidates = [*ROOT.glob('*.ttf'), *ROOT.glob('*.otf')]
    candidates += [system_fonts / 'segoesc.ttf', system_fonts / 'segoeui.ttf']
    for path in sorted(path for path in candidates if path.is_file()):
        if str(path) not in _registered:
            if QFontDatabase.addApplicationFont(str(path)) >= 0:
                _registered.add(str(path))


def default_template():
    return validate_template(json.loads(SYSTEM_DEFAULT_PATH.read_text(encoding='utf-8')))


def user_default_template():
    try:
        value = json.loads(USER_DEFAULT_PATH.read_text(encoding='utf-8-sig'))
    except FileNotFoundError as error:
        raise ValueError('No user default saved yet. Use Save user default first.') from error
    except (OSError, ValueError) as error:
        raise ValueError(f'Could not load user default: {error}') from error
    return validate_template(value)


def preferred_template():
    return user_default_template() if USER_DEFAULT_PATH.exists() else default_template()


def save_user_default(value):
    template = validate_template(value)
    descriptor, filename = tempfile.mkstemp(dir=USER_DEFAULT_PATH.parent,
                                             prefix='.template-',suffix='.tmp')
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump(template,stream,ensure_ascii=False,indent=2)
            stream.write('\n')
        os.replace(filename,USER_DEFAULT_PATH)
    finally:
        Path(filename).unlink(missing_ok=True)


def validate_template(value):
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('Unsupported slideshow template format.')
    result = copy.deepcopy(value)
    if (result.get('width'), result.get('height'), result.get('dpi')) != (1920, 1080, 300):
        raise ValueError('Slideshow templates must use 1920 x 1080 at 300 dpi.')
    for color in [result.get('background')]:
        if not isinstance(color, str) or not QColor(color).isValid():
            raise ValueError('Invalid template background colour.')
    for name in ('title', 'date'):
        layer = result.get(name)
        if not isinstance(layer, dict):
            raise ValueError('Missing template layer: ' + name)
        for key, low, high in (('x', 0, 1920), ('y', 0, 1080), ('size_pt', 1, 160), ('glow_size', 0, 60)):
            number = layer.get(key)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not low <= number <= high:
                raise ValueError(f'Invalid {name} {key}.')
        if layer.get('align') not in ('left', 'center', 'right'):
            raise ValueError('Invalid text alignment.')
        if not isinstance(layer.get('font_family'), str) or not layer['font_family']:
            raise ValueError('Choose a font for ' + name)
        file = layer.get('font_file', '')
        if not isinstance(file, str) or (file and (Path(file).name != file or '/' in file or '\\' in file)):
            raise ValueError('Font files must be in the Slideshow folder.')
        for key in ('color', 'glow_color'):
            if not isinstance(layer.get(key), str) or not QColor(layer[key]).isValid():
                raise ValueError('Invalid text colour.')
        if not isinstance(layer.get('enabled'), bool):
            raise ValueError('Invalid text visibility.')
    return result


def missing_fonts(template):
    ensure_fonts()
    available = {family.casefold() for family in QFontDatabase.families()}
    return sorted({template[name]['font_family'] for name in ('title', 'date')
                   if template[name]['enabled'] and template[name]['font_family'].casefold() not in available})


def text_path(text, layer, dpi=300):
    font = QFont(layer['font_family'])
    font.setPixelSize(max(1, round(layer['size_pt'] * dpi / 72)))
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    advance = QFontMetricsF(font).horizontalAdvance(text)
    x = layer['x'] - advance * {'left': 0, 'center': .5, 'right': 1}[layer['align']]
    path = QPainterPath()
    path.addText(QPointF(x, layer['y']), font, text)
    return path


def layer_rect(text, layer, dpi=300):
    bounds = text_path(text or ' ', layer, dpi).boundingRect()
    if bounds.isEmpty():
        bounds = QRectF(layer['x'] - 20, layer['y'] - 40, 40, 40)
    margin = max(7, layer['glow_size'])
    return bounds.adjusted(-margin, -margin, margin, margin)


def load_photo(path):
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and (size.width() > 1920 or size.height() > 1080):
        reader.setScaledSize(size.scaled(QSize(1920, 1080), Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ValueError('Could not read image: ' + Path(path).name)
    return image


def render_image(photo, title, date, template):
    ensure_fonts()
    image = QImage(1920, 1080, QImage.Format.Format_RGB32)
    image.fill(QColor(template['background']))
    image.setDotsPerMeterX(round(300 / .0254))
    image.setDotsPerMeterY(round(300 / .0254))
    painter = QPainter(image)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    try:
        if photo is not None and not photo.isNull():
            size = photo.size().scaled(QSize(1920,1080), Qt.AspectRatioMode.KeepAspectRatio)
            painter.drawImage(QRectF((1920-size.width())/2, (1080-size.height())/2,
                                     size.width(), size.height()), photo)
        for name, text in (('title', title), ('date', date)):
            layer = template[name]
            if not layer['enabled'] or not text:
                continue
            path = text_path(text, layer)
            radius = layer['glow_size']
            # Layered soft strokes produce the soft outer glow.
            if radius:
                for step in range(12, 0, -1):
                    color = QColor(layer['glow_color'])
                    color.setAlphaF(.10 + .24 * (1-step/12))
                    painter.setPen(QPen(color, max(.5, radius*2*step/12),
                                        Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(layer['color']))
            painter.drawPath(path)
    finally:
        painter.end()
    return image


def render_file(path, title, date, template):
    template = validate_template(template)
    absent = missing_fonts(template)
    if absent:
        raise ValueError('Missing font: ' + ', '.join(absent) + '. Choose another font in Edit template.')
    image = render_image(load_photo(path), title, date, template)
    if not image.save(str(path), 'JPEG', 100):
        raise OSError('Could not save slide: ' + str(path))
