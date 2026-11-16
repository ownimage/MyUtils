"""Visual template editing using the exact renderer used for saved slides."""
from __future__ import annotations
import copy
import hashlib
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal, QSignalBlocker, QElapsedTimer
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import (QWidget, QApplication, QComboBox as NativeComboBox, QHBoxLayout, QVBoxLayout, QFormLayout,
    QLabel, QFileDialog, QColorDialog, QMessageBox)
from qfluentwidgets import CheckBox, qconfig, isDarkTheme
from photo_tools.fluent import QPushButton, PrimaryPushButton, QComboBox, DoubleSpinBox
from template_render import (ROOT, ensure_fonts, render_image, load_photo, layer_rect,
                             default_template, validate_template, missing_fonts, user_default_template, save_user_default)


class TemplateCanvas(QWidget):
    changed = Signal()
    selectionChanged = Signal(str)

    def __init__(self, template, photo, title, date, parent=None):
        super().__init__(parent)
        self.template = template
        self.photo, self.title, self.date = photo, title, date
        self.selected = 'title'
        self._drag = None
        self.setMinimumSize(460, 300)
        self.setMouseTracking(True)
        self.setAccessibleName('Template preview: drag text to move, drag square handle to resize')
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.refresh)
        self.rendered = None
        self.refresh()

    def refresh(self):
        self.rendered = render_image(self.photo, self.title, self.date, self.template)
        self.update()

    def schedule(self):
        self.timer.start()
        self.update()

    def image_rect(self):
        area = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        scale = min(area.width()/1920, area.height()/1080)
        return QRectF(area.center().x()-960*scale, area.center().y()-540*scale, 1920*scale, 1080*scale)

    def canvas_point(self, point):
        rect = self.image_rect()
        return QPointF((point.x()-rect.x())*1920/rect.width(), (point.y()-rect.y())*1080/rect.height())

    def bounds(self, name):
        return layer_rect(self.title if name == 'title' else self.date, self.template[name])

    def handle_point(self, name):
        rect = self.bounds(name)
        return rect.bottomLeft() if self.template[name]['align'] == 'right' else rect.bottomRight()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#202020'))
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        rect = self.image_rect()
        if self.rendered is not None:
            painter.drawImage(rect, self.rendered)
        painter.save()
        painter.translate(rect.topLeft())
        scale = rect.width()/1920
        painter.scale(scale, scale)
        painter.setClipRect(QRectF(0,0,1920,1080))
        for name in ('title', 'date'):
            if not self.template[name]['enabled']:
                continue
            selected = name == self.selected
            pen = QPen(QColor('#4cc2ff') if selected else QColor('#ffffff'), 1.5/scale)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.bounds(name))
            if selected:
                point = self.handle_point(name)
                half = 5/scale
                painter.fillRect(QRectF(point.x()-half, point.y()-half, half*2, half*2), QColor('#4cc2ff'))
        painter.restore()
        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self.canvas_point(event.position())
        tolerance = 12*1920/self.image_rect().width()
        for name in (self.selected, 'date' if self.selected == 'title' else 'title'):
            if not self.template[name]['enabled']:
                continue
            handle = self.handle_point(name)
            resize = (point-handle).manhattanLength() < tolerance
            if resize or self.bounds(name).contains(point):
                self.selected = name
                self.selectionChanged.emit(name)
                layer = self.template[name]
                self._drag = (point, copy.deepcopy(layer), resize)
                self.setCursor(Qt.CursorShape.SizeFDiagCursor if resize else Qt.CursorShape.ClosedHandCursor)
                self.update()
                event.accept()
                return

    def mouseMoveEvent(self, event):
        if self._drag is None:
            return
        point = self.canvas_point(event.position())
        start, original, resize = self._drag
        layer = self.template[self.selected]
        if resize:
            anchor = QPointF(original['x'], original['y'])
            initial = max(20, (start-anchor).manhattanLength())
            ratio = max(.05, (point-anchor).manhattanLength()/initial)
            layer['size_pt'] = max(1, min(160, original['size_pt']*ratio))
        else:
            delta = point-start
            layer['x'] = max(0, min(1920, original['x']+delta.x()))
            layer['y'] = max(0, min(1080, original['y']+delta.y()))
        self.changed.emit()
        self.schedule()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            self._drag = None
            self.unsetCursor()
            self.refresh()
            event.accept()


class FontPicker(NativeComboBox):
    """Native type-ahead and arrow navigation, including live popup highlighting."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('fontPicker')
        self._typing = QElapsedTimer()
        self.setAccessibleName('Font: type a name or use arrow keys to preview')
        self.setEditable(False)
        self.setMaxVisibleItems(16)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.highlighted.connect(self.setCurrentIndex)
        qconfig.themeChanged.connect(self.refresh_style)
        self.refresh_style()

    def keyPressEvent(self, event):
        text = event.text()
        typing = self._typing.isValid() and self._typing.elapsed() < QApplication.keyboardInputInterval()
        plain = not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier))
        if plain and text and text.isprintable() and (text != ' ' or typing):
            # Reuse Qt's native incremental search, including repeated-letter
            # cycling and its timeout, rather than Space opening mid-name.
            self.view().keyboardSearch(text)
            index = self.view().currentIndex().row()
            if index >= 0:
                self.setCurrentIndex(index)
            self._typing.start()
            event.accept()
            return
        super().keyPressEvent(event)

    def refresh_style(self, *_):
        dark = isDarkTheme()
        background, foreground, border = ('#2b2b2b','#ffffff','#555555') if dark else ('#ffffff','#202020','#d0d0d0')
        self.setStyleSheet(f"""
            QComboBox#fontPicker {{ background: {background}; color: {foreground};
                border: 1px solid {border}; border-radius: 5px; padding: 6px 10px;
                font-family: 'Segoe UI'; font-size: 14px; min-height: 20px; }}
            QComboBox#fontPicker:focus {{ border: 1px solid #0078d4; }}
            QComboBox#fontPicker QAbstractItemView {{ background: {background};
                color: {foreground}; selection-background-color: #0078d4;
                selection-color: white; border: 1px solid {border}; outline: 0; }}
            QComboBox#fontPicker QAbstractItemView::item {{ min-height: 26px; }}
        """)


class TemplateEditor(QWidget):
    accepted = Signal()
    rejected = Signal()

    def __init__(self, template, image_path=None, title='Title', date='2026 06 15', parent=None):
        super().__init__(parent)
        ensure_fonts()
        self.value = validate_template(template)
        self.initial_value = copy.deepcopy(self.value)
        self.setWindowTitle('Edit slideshow template')
        self.setObjectName('templateEditor')
        photo = None
        if image_path:
            try:
                photo = load_photo(image_path)
            except ValueError:
                pass
        outer = QVBoxLayout(self)
        heading = QLabel('Make the slide your own')
        heading.setObjectName('title')
        outer.addWidget(heading)
        hint = QLabel('Drag a title or date to move it. Drag its blue square to resize. The preview uses the same layout as the saved JPEG.')
        hint.setWordWrap(True)
        outer.addWidget(hint)
        defaults = QHBoxLayout()
        self.load_user = QPushButton('Load user default')
        self.load_user.clicked.connect(self.load_user_default)
        defaults.addWidget(self.load_user)
        self.load_system = QPushButton('Load system default')
        self.load_system.clicked.connect(self.load_system_default)
        defaults.addWidget(self.load_system)
        self.save_default = QPushButton('Save user default')
        self.save_default.clicked.connect(self.save_as_default)
        defaults.addWidget(self.save_default)
        defaults.addStretch()
        outer.addLayout(defaults)
        self.default_status = QLabel('Event changes are saved separately from your reusable default.')
        self.default_status.setWordWrap(True)
        outer.addWidget(self.default_status)
        body = QHBoxLayout()
        self.canvas = TemplateCanvas(self.value, photo, title or 'Title', date or '2026 06 15')
        body.addWidget(self.canvas, 1)
        panel = QWidget()
        panel.setFixedWidth(290)
        form = QFormLayout(panel)
        form.setContentsMargins(12,0,0,0)
        self.layer = QComboBox()
        self.layer.addItem('Title', 'title')
        self.layer.addItem('Date', 'date')
        form.addRow('Edit', self.layer)
        self.visible = CheckBox('Show this text')
        form.addRow(self.visible)
        self.font = FontPicker()
        self.font.setMinimumWidth(160)
        self.font.setMaximumWidth(195)
        self._populate_fonts()
        form.addRow('Font', self.font)
        self.import_font = QPushButton('Add font file…')
        self.import_font.clicked.connect(self.add_font)
        form.addRow(self.import_font)
        self.size = DoubleSpinBox()
        self.size.setRange(1,160)
        self.size.setDecimals(2)
        self.size.setSuffix(' pt')
        form.addRow('Size', self.size)
        self.x = DoubleSpinBox()
        self.x.setRange(0,1920)
        self.x.setDecimals(1)
        form.addRow('Horizontal', self.x)
        self.y = DoubleSpinBox()
        self.y.setRange(0,1080)
        self.y.setDecimals(1)
        form.addRow('Vertical', self.y)
        self.align = QComboBox()
        for text, value in (('Left','left'),('Centre','center'),('Right','right')):
            self.align.addItem(text,value)
        form.addRow('Align',self.align)
        self.text_color = QPushButton('Text colour…')
        self.text_color.clicked.connect(lambda: self.pick_color('color'))
        form.addRow(self.text_color)
        self.glow = DoubleSpinBox()
        self.glow.setRange(0,60)
        self.glow.setDecimals(1)
        form.addRow('Glow size',self.glow)
        self.glow_color = QPushButton('Glow colour…')
        self.glow_color.clicked.connect(lambda: self.pick_color('glow_color'))
        form.addRow(self.glow_color)
        dimensions = QLabel('1920 × 1080 · 300 dpi\nSize uses print points at 300 dpi.\nVertical position is the text baseline.')
        dimensions.setWordWrap(True)
        form.addRow(dimensions)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        form.addRow(self.warning)
        body.addWidget(panel)
        outer.addLayout(body,1)
        buttons = QHBoxLayout()
        reset = QPushButton('Reset to default')
        reset.clicked.connect(self.reset)
        buttons.addWidget(reset)
        buttons.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        apply = PrimaryPushButton('Apply template')
        apply.clicked.connect(self.accept)
        buttons.addWidget(apply)
        outer.addLayout(buttons)
        self.layer.currentIndexChanged.connect(self.sync_controls)
        self.canvas.selectionChanged.connect(self.select_layer)
        self.canvas.changed.connect(self.sync_controls)
        self.visible.stateChanged.connect(self.apply_controls)
        self.font.currentIndexChanged.connect(self.apply_controls)
        self.align.currentIndexChanged.connect(self.apply_controls)
        for spin in (self.size,self.x,self.y,self.glow):
            spin.valueChanged.connect(self.apply_controls)
        self.sync_controls()
        self.cancel_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape),self)
        self.cancel_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.cancel_shortcut.activated.connect(self.reject)

    def _populate_fonts(self):
        self.font.clear()
        for family in sorted(QFontDatabase.families(), key=str.casefold):
            self.font.addItem(family,family)

    def select_layer(self, name):
        self.layer.setCurrentIndex(self.layer.findData(name))
        self.sync_controls()

    def sync_controls(self, *_):
        name = self.layer.currentData() or 'title'
        self.canvas.selected = name
        layer = self.value[name]
        controls = (self.visible,self.font,self.size,self.x,self.y,self.align,self.glow)
        blockers = [QSignalBlocker(widget) for widget in controls]
        self.visible.setChecked(layer['enabled'])
        self.font.setCurrentIndex(self.font.findData(layer['font_family']))
        self.size.setValue(layer['size_pt'])
        self.x.setValue(layer['x'])
        self.y.setValue(layer['y'])
        self.align.setCurrentIndex(self.align.findData(layer['align']))
        self.glow.setValue(layer['glow_size'])
        del blockers
        absent = missing_fonts(self.value)
        self.warning.setText('Missing font: '+', '.join(absent) if absent else 'Changes apply to every photo in this event. Apply template saves them to highlight/template.json.')
        self.canvas.update()

    def apply_controls(self, *_):
        layer = self.value[self.layer.currentData()]
        family = self.font.currentData()
        if family:
            if family != layer['font_family']:
                layer['font_file'] = ''
            layer['font_family'] = family
        layer.update(size_pt=self.size.value(), x=self.x.value(), y=self.y.value(),
                     align=self.align.currentData(), enabled=self.visible.isChecked(),glow_size=self.glow.value())
        self.canvas.schedule()
        absent = missing_fonts(self.value)
        if not absent:
            self.warning.setText('Changes apply to every photo in this event. Apply template saves them to highlight/template.json.')

    def pick_color(self, key):
        layer = self.value[self.layer.currentData()]
        color = QColorDialog.getColor(QColor(layer[key]), self, 'Choose colour')
        if color.isValid():
            layer[key] = color.name()
            self.canvas.schedule()

    def add_font(self):
        filename, _ = QFileDialog.getOpenFileName(self,'Add a font file','','Fonts (*.ttf *.otf)')
        if not filename:
            return
        try:
            source = Path(filename)
            target = ROOT / source.name
            if target.exists() and target.read_bytes() != source.read_bytes():
                target = ROOT / (source.stem+'-'+hashlib.sha256(source.read_bytes()).hexdigest()[:8]+source.suffix)
            if source.resolve() != target.resolve():
                shutil.copy2(source,target)
            identifier = QFontDatabase.addApplicationFont(str(target))
            families = QFontDatabase.applicationFontFamilies(identifier)
            if not families:
                raise ValueError('This file could not be loaded as a font.')
            blocker = QSignalBlocker(self.font)
            self._populate_fonts()
            del blocker
            layer = self.value[self.layer.currentData()]
            layer['font_family'], layer['font_file'] = families[0], target.name
            self.sync_controls()
            self.canvas.schedule()
        except Exception as error:
            QMessageBox.warning(self,'Could not add font',str(error))

    def is_dirty(self):
        return self.value != self.initial_value

    def mark_clean(self):
        self.initial_value = copy.deepcopy(self.value)

    def _set_template(self, value):
        self.value = validate_template(value)
        self.canvas.template = self.value
        self.sync_controls()
        self.canvas.refresh()

    def load_user_default(self):
        try:
            self._set_template(user_default_template())
            self.default_status.setText('Loaded user default from Slideshow/template.json. Apply to use it for this event.')
        except (OSError, ValueError) as error:
            self.default_status.setText(str(error))

    def load_system_default(self):
        try:
            self._set_template(default_template())
            self.default_status.setText('Loaded system default. Your saved user default is unchanged.')
        except (OSError, ValueError) as error:
            self.default_status.setText(str(error))

    def reset(self):
        self.load_system_default()

    def _validate(self):
        validate_template(self.value)
        absent = missing_fonts(self.value)
        if absent:
            raise ValueError('Choose an available font: '+', '.join(absent))

    def save_as_default(self):
        try:
            self._validate()
            save_user_default(self.value)
            self.default_status.setText('Saved user default to Slideshow/template.json. New events will use this layout.')
        except (OSError, ValueError) as error:
            self.default_status.setText('Could not save user default: '+str(error))

    def accept(self):
        try:
            self._validate()
        except ValueError as error:
            self.default_status.setText(str(error))
            return
        self.accepted.emit()

    def reject(self):
        self.rejected.emit()
