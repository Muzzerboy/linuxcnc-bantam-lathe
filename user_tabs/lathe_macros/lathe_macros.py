#!/usr/bin/env python3
"""
Lathe Cycles user tab for Probe Basic Lathe.

Two-panel layout matching PBL's conversational tab:
  Left  — Andy Pugh's SVG diagram for the selected operation,
           showing which dimension is which (Finish Diameter, Z, etc.)
  Right — Numeric input fields with touchscreen numpad and
           unit conversion (in->mm, tpi->pitch)

Operations: Turning, Boring, Facing, Chamfer, Radius,
            Threading, Drilling, Tapping
"""

import os
import json
import linuxcnc

from qtpy.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QDialog, QButtonGroup,
    QRadioButton, QFrame, QScrollArea, QSizePolicy)
from qtpy.QtCore import Qt, QRectF, QPointF
from qtpy.QtGui import QPainter, QColor, QFont, QPen, QPixmap

try:
    from qtpy.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

TAB_DIR    = os.path.dirname(os.path.abspath(__file__))
SVG_FILE   = os.path.join(TAB_DIR, 'LatheMacro_vector.svg')
STATE_FILE = os.path.join(TAB_DIR, 'state.json')

# Pre-rendered PNGs for all 8 operations via librsvg
# Vector ops rendered at ~600px wide (display resolution) so dimension
# lines stay at the correct stroke weight without bilinear thinning.
# Format: {op_key: (filename, label_coord_w, label_coord_h)}
OP_PNGS = {
    'turning':   ('turning_rendered.png',   888,  686),
    'boring':    ('boring_rendered.png',    888,  686),
    'facing':    ('facing_rendered.png',    888,  686),
    'chamfer':   ('chamfer_rendered.png',   888,  686),
    'radius':    ('radius_rendered.png',    888,  686),
    'threading': ('threading_rendered.png', 888,  686),
    'groove':    ('groove_rendered.png',   1500, 1000),
    'drill':     ('drill_rendered.png',    1500, 1000),
}

# Spinbox label positions in the SVG's 888×686 coordinate space.
# Derived from Andy Pugh's original lathemacro.ui, scaled to viewBox coords.
LABELS = {
    'turning': [
        ((720, 590), 'Finish Diameter'),
        (( 50, 400), 'Finish Z'),
        ((550, 160), 'End Radius'),
        ((330, 380), 'Taper Angle'),
        ((390, 510), 'Feed Rate'),
        ((500, 610), 'Depth of Cut'),
    ],
    'boring': [
        ((720, 570), 'Finish Bore Dia'),
        (( 60, 350), 'Finish Z'),
        ((500, 350), 'Run-out Radius'),
        ((340, 350), 'Taper Angle'),
        ((400, 500), 'Feed Rate'),
        ((550, 650), 'Depth of Cut'),
    ],
    'facing': [
        ((680, 520), 'Finish Diameter'),
        (( 85, 320), 'Finish Z'),
        ((485, 446), 'Face Angle'),
        ((370, 580), 'Feed Rate'),
        ((570, 590), 'Depth of Cut'),
    ],
    'radius': [
        ((680, 440), 'Diameter at Corner'),
        ((110, 300), 'Z at Corner'),
        ((590, 300), 'Radius Size'),
        ((490, 560), '(Front Outside)'),
        ((610, 490), '(Front Inside)'),
        ((140, 429), '(Rear Outside)'),
    ],
    'chamfer': [
        ((660, 470), 'Diameter at Corner'),
        ((160, 290), 'Z at Corner'),
        ((535, 335), 'Chamfer Size'),
        ((800, 200), '(Front Outside)'),
        ((750, 350), '(Front Inside)'),
        ((140, 370), '(Rear Outside)'),
    ],
    'threading': [
        ((650, 555), 'Thread Diameter'),
        (( 65, 310), 'Finish Z'),
        ((320, 535), 'Thread Pitch'),
        ((380, 580), '(External - OD)'),
        ((525, 410), '(Internal - ID)'),
    ],
    'groove': [
        ((1050, 600), 'Groove Diameter'),
        (( 905, 100), 'Groove Z'),
        (( 680, 885), 'Feed Rate'),
    ],
    'drill': [
        ((1250, 270), 'Drill Diameter'),
        (( 370, 240), 'Drill Depth (Z)'),
        (( 770, 910), 'Feed Rate'),
        (( 300, 700), 'Peck Distance'),
    ],
}

# SVG layer index per operation
# Layers 0-5: pure vector SVG  |  Layers 6-7: transparent raster V3 SVG
LAYER = {
    'turning':   0,
    'boring':    1,
    'facing':    2,
    'radius':    3,
    'chamfer':   4,
    'threading': 5,
    'groove':    6,
    'drill':     7,
}

STYLE = """
QWidget      { background: #2a2a2a; color: white; font-size: 13pt; }
QTabWidget::pane { border: 1px solid #444; }
QTabBar::tab {
    background: #333; color: #aaa; padding: 6px 14px;
    border: 1px solid #444; border-bottom: none; font-size: 11pt;
}
QTabBar::tab:selected { background: #1a5a8a; color: white; }
QLabel       { color: #ccc; }
QLabel#unit  { color: #888; font-size: 11pt; }
QLabel#hint  { color: #888; font-size: 10pt; font-style: italic; }
QLineEdit {
    background: #1a1a1a; color: white;
    border: 1px solid #555; border-radius: 3px;
    font-size: 14pt; padding: 2px 6px; min-width: 110px;
}
QLineEdit:hover { border-color: #5555ee; }
QPushButton {
    background: #3a3a3a; color: white;
    border: 1px solid #555; border-radius: 4px;
    padding: 6px 12px; font-size: 13pt;
}
QPushButton:hover   { background: #4a4a7a; }
QPushButton:pressed { background: #5555ee; }
QPushButton#run {
    background: #1a5a1a; font-size: 16pt;
    min-height: 50px; border-radius: 6px;
}
QPushButton#run:hover { background: #2a7a2a; }
QRadioButton { color: #ccc; font-size: 12pt; spacing: 8px; }
QRadioButton::indicator { width: 18px; height: 18px; }
QSplitter::handle { background: #444; width: 3px; }
"""

PAD_STYLE = """
QDialog  { background: #222; }
QLabel#title { color: #aaa; font-size: 13pt; padding: 4px; }
QLineEdit {
    background: #111; color: white;
    border: 2px solid #555; border-radius: 4px;
    font-size: 26pt; padding: 4px 10px;
}
QPushButton {
    background: #3a3a3a; color: white;
    border: 1px solid #555; border-radius: 4px;
    font-size: 20pt; min-height: 58px; min-width: 70px;
}
QPushButton:pressed { background: #5555ee; }
QPushButton#conv { background: #2a4a2a; font-size: 13pt; min-height: 44px; }
QPushButton#ok   { background: #1a5a1a; font-size: 16pt; min-height: 50px; }
QPushButton#can  { background: #5a1a1a; font-size: 16pt; min-height: 50px; }
"""

INSTRUCTIONS = {
    'turning': (
        "1. Select a turning tool (Tool Number).\n\n"
        "2. Touch off Z=0 at the workpiece face.\n\n"
        "3. Position tool tip at the stock OD at your start Z.\n\n"
        "4. Set Finish Diameter (target OD) and Finish Z (end of cut, negative = left).\n\n"
        "5. Set Surface Speed, Feed Rate and Depth of Cut.\n\n"
        "6. Press RUN."
    ),
    'boring': (
        "1. Select a boring bar (Tool Number).\n\n"
        "2. Position tool tip inside the bore at the entry face.\n\n"
        "3. Set Finish Bore Dia (target bore diameter) and Finish Z (bore bottom, negative).\n\n"
        "4. Set Surface Speed, Feed Rate and Depth of Cut.\n\n"
        "5. Press RUN."
    ),
    'facing': (
        "1. Select a facing tool (Tool Number).\n\n"
        "2. Position tool at the outer edge of the stock, lightly touching the face.\n\n"
        "3. Set Finish Diameter (stock OD) and Finish Z (final face Z position).\n\n"
        "4. Set Surface Speed, Feed Rate and Depth of Cut.\n\n"
        "5. Press RUN."
    ),
    'chamfer': (
        "1. Select a 45° chamfering tool (Tool Number).\n\n"
        "2. Set Diameter at Corner and Z at Corner to the workpiece corner position.\n\n"
        "3. Set Chamfer Size (width along each face).\n\n"
        "4. Select corner type: Front Outside (OD/end), Front Inside (bore/end) or Rear Outside (OD/shoulder).\n\n"
        "5. Press RUN."
    ),
    'radius': (
        "1. Select a round-nose tool (Tool Number).\n\n"
        "2. Set Diameter at Corner and Z at Corner to the workpiece corner position.\n\n"
        "3. Set Radius Size.\n\n"
        "4. Select corner type: Front Outside, Front Inside or Rear Outside.\n\n"
        "5. Press RUN."
    ),
    'threading': (
        "1. Select a threading insert (Tool Number).\n\n"
        "2. Set Thread Diameter (nominal) and Finish Z (thread end, negative).\n\n"
        "3. Set Thread Pitch (mm) and Speed (constant RPM, typically 200–400).\n\n"
        "4. Select External or Internal.\n\n"
        "5. Press RUN."
    ),
    'groove': (
        "1. Select a grooving tool (Tool Number).\n\n"
        "2. Set Groove Diameter to the finished diameter at the groove bottom.\n\n"
        "3. Set Groove Z to the Z position of the groove centre.\n\n"
        "4. Use a low Feed Rate (typically 0.03–0.08 mm/rev).\n\n"
        "5. Position the tool at the stock OD.\n\n"
        "6. Press RUN."
    ),
    'drill': (
        "1. Select a drill bit (Tool Number).\n\n"
        "2. Centre-drill first if needed.\n\n"
        "3. Set Drill Diameter, Drill Depth Z (negative) and Peck Distance (0 = no pecking).\n\n"
        "4. Set Surface Speed and Feed Rate.\n\n"
        "5. Press RUN."
    ),
}


def _make_help_widget(op_key):
    w = QWidget()
    vl = QVBoxLayout(w)
    vl.setContentsMargins(12, 10, 12, 10)
    vl.setSpacing(6)
    title = QLabel('How to use')
    title.setStyleSheet('color: #8fc88f; font-weight: bold; font-size: 11pt;')
    body = QLabel(INSTRUCTIONS.get(op_key, ''))
    body.setWordWrap(True)
    body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    body.setStyleSheet('color: #bbb; font-size: 10pt;')
    vl.addWidget(title)
    vl.addWidget(body)
    vl.addStretch()
    return w


# ---------------------------------------------------------------------------
# SVG diagram panel
# ---------------------------------------------------------------------------

class DiagramWidget(QWidget):
    """Renders one layer of Andy Pugh's LatheMacro_vector.svg with labels."""

    SVG_BG = QColor(145, 145, 149)
    _shared_renderer = None   # fallback only

    def __init__(self, op_key, layer_idx, parent=None):
        super().__init__(parent)
        self._layer_id = f'layer{layer_idx}' if layer_idx >= 0 else None
        self._labels   = LABELS.get(op_key, [])
        self._pixmap   = None
        self._png_w    = 888    # label coordinate space width
        self._png_h    = 686    # label coordinate space height
        self.setMinimumSize(100, 100)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet('background: rgb(145,145,149);')
        self.setMouseTracking(True)
        self._hover = ''
        info = OP_PNGS.get(op_key)
        if info:
            fname, self._png_w, self._png_h = info
            p = os.path.join(TAB_DIR, fname)
            if os.path.exists(p):
                self._pixmap = QPixmap(p)
        if self._pixmap is None and HAS_SVG and \
                DiagramWidget._shared_renderer is None and os.path.exists(SVG_FILE):
            DiagramWidget._shared_renderer = QSvgRenderer(SVG_FILE)

    def mouseMoveEvent(self, event):
        rect = self._render_rect()
        if rect.contains(QPointF(event.pos())):
            sx = int((event.x() - rect.x()) / rect.width()  * self._png_w)
            sy = int((event.y() - rect.y()) / rect.height() * self._png_h)
            self._hover = f'{sx}, {sy}'
        else:
            self._hover = ''
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        h = event.size().height()
        if h > 20:
            target_w = int(h * self._png_w / self._png_h)
            if abs(self.width() - target_w) > 1:
                self.setFixedWidth(target_w)

    def _render_rect(self):
        """Return a QRectF that fits the SVG aspect ratio centred in the widget."""
        margin = 4
        aw = self.width()  - 2 * margin
        ah = self.height() - 2 * margin
        svg_aspect = self._png_w / self._png_h
        if aw / ah > svg_aspect:
            rw = ah * svg_aspect
            rh = ah
        else:
            rw = aw
            rh = aw / svg_aspect
        rx = margin + (aw - rw) / 2
        ry = margin + (ah - rh) / 2
        return QRectF(rx, ry, rw, rh)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        painter.fillRect(event.rect(), self.SVG_BG)

        rect = self._render_rect()

        if self._pixmap and not self._pixmap.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(rect.toRect(), self._pixmap)
        elif DiagramWidget._shared_renderer and \
                DiagramWidget._shared_renderer.isValid() and self._layer_id and \
                DiagramWidget._shared_renderer.elementExists(self._layer_id):
            DiagramWidget._shared_renderer.render(painter, self._layer_id, rect)
        else:
            painter.setPen(QColor('#666'))
            painter.drawText(event.rect(), Qt.AlignCenter, 'Diagram unavailable')

        # Yellow dimension labels
        if self._labels and (self._pixmap or DiagramWidget._shared_renderer):
            font = QFont('Sans', 8, QFont.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            for (sx, sy), text in self._labels:
                wx = rect.left() + (sx / self._png_w) * rect.width()
                wy = rect.top()  + (sy / self._png_h) * rect.height()
                tw = fm.horizontalAdvance(text) + 6
                th = fm.height() + 2
                bg = QRectF(wx - tw/2, wy - th/2, tw, th)
                painter.fillRect(bg, QColor(255, 255, 180, 220))
                painter.setPen(QPen(QColor('#111')))
                painter.drawText(bg, Qt.AlignCenter, text)


        painter.end()


# ---------------------------------------------------------------------------
# Numpad dialog
# ---------------------------------------------------------------------------

class NumpadDialog(QDialog):

    def __init__(self, label, value, field_type='length', parent=None):
        super().__init__(parent, Qt.Dialog)
        self.field_type = field_type
        self.setStyleSheet(PAD_STYLE)
        self.setWindowTitle('Enter value')
        self._build(label, str(value))

    def _build(self, label, value):
        outer = QVBoxLayout(self)
        outer.setSpacing(6)
        lbl = QLabel(label); lbl.setObjectName('title')
        lbl.setAlignment(Qt.AlignCenter); outer.addWidget(lbl)
        self.display = QLineEdit(value)
        self.display.setAlignment(Qt.AlignRight); outer.addWidget(self.display)
        grid = QHBoxLayout()
        col = [QVBoxLayout(), QVBoxLayout(), QVBoxLayout()]
        for text, c in [('7',0),('4',0),('1',0),('0',0),
                        ('8',1),('5',1),('2',1),('.',1),
                        ('9',2),('6',2),('3',2),('+/-',2)]:
            b = QPushButton(text)
            b.clicked.connect(lambda _, t=text: self._digit(t))
            col[c].addWidget(b)
        for c in col: grid.addLayout(c)
        outer.addLayout(grid)
        row = QHBoxLayout()
        bsp = QPushButton('⌫'); bsp.clicked.connect(self._bsp)
        clr = QPushButton('C'); clr.clicked.connect(lambda: self.display.setText(''))
        row.addWidget(bsp); row.addWidget(clr); outer.addLayout(row)
        if self.field_type in ('length', 'feed'):
            r = QHBoxLayout()
            for txt, fn in [('in → mm', self._in_mm), ('mm → in', self._mm_in)]:
                b = QPushButton(txt); b.setObjectName('conv')
                b.clicked.connect(fn); r.addWidget(b)
            outer.addLayout(r)
        elif self.field_type == 'pitch':
            r = QHBoxLayout()
            for txt, fn in [('tpi → mm', self._tpi_mm), ('mm → tpi', self._mm_tpi)]:
                b = QPushButton(txt); b.setObjectName('conv')
                b.clicked.connect(fn); r.addWidget(b)
            outer.addLayout(r)
        r2 = QHBoxLayout()
        can = QPushButton('Cancel'); can.setObjectName('can')
        ok  = QPushButton('OK');     ok.setObjectName('ok')
        can.clicked.connect(self.reject); ok.clicked.connect(self.accept)
        r2.addWidget(can); r2.addWidget(ok); outer.addLayout(r2)

    def _digit(self, t):
        if t == '+/-':
            c = self.display.text()
            self.display.setText(c[1:] if c.startswith('-') else '-' + c)
        else:
            self.display.setText(self.display.text() + t)

    def _bsp(self): self.display.setText(self.display.text()[:-1])

    def _convert(self, factor):
        try: self.display.setText(f'{float(self.display.text()) * factor:.4f}')
        except ValueError: pass

    def _in_mm(self):  self._convert(25.4)
    def _mm_in(self):  self._convert(1/25.4)
    def _tpi_mm(self):
        try:
            v = float(self.display.text())
            self.display.setText(f'{25.4/v:.4f}' if v else '')
        except ValueError: pass
    def _mm_tpi(self): self._tpi_mm()

    def value(self):
        try: return float(self.display.text())
        except ValueError: return 0.0


# ---------------------------------------------------------------------------
# Individual field widget
# ---------------------------------------------------------------------------

class CycleField(QWidget):

    def __init__(self, key, label, hint, unit, default, field_type='length'):
        super().__init__()
        self.key = key
        self.label_text = label
        self.field_type = field_type
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(1)
        row = QHBoxLayout()
        lbl = QLabel(label); lbl.setMinimumWidth(200)
        self.edit = QLineEdit(self._fmt(default))
        self.edit.setReadOnly(True)
        self.edit.mousePressEvent = self._open
        ulbl = QLabel(unit); ulbl.setObjectName('unit'); ulbl.setMinimumWidth(65)
        row.addWidget(lbl); row.addWidget(self.edit); row.addWidget(ulbl)
        layout.addLayout(row)
        if hint:
            h = QLabel(hint); h.setObjectName('hint'); layout.addWidget(h)

    def _fmt(self, v):
        if self.field_type == 'int':
            return f'{int(v)}'
        if self.field_type == 'speed':
            return f'{float(v):.0f}'
        if self.field_type in ('feed', 'angle'):
            return f'{float(v):.2f}'
        return f'{float(v):.3f}'   # length, pitch, everything else

    def _open(self, event):
        dlg = NumpadDialog(self.label_text, self.edit.text(),
                           self.field_type, self.window())
        dlg.setMinimumSize(380, 520)
        if dlg.exec_() == QDialog.Accepted:
            self.edit.setText(self._fmt(dlg.value()))

    def value(self):
        try: return float(self.edit.text())
        except ValueError: return 0.0

    def set_value(self, v):
        self.edit.setText(self._fmt(v))


# ---------------------------------------------------------------------------
# Base operation page  (left=diagram, right=fields)
# ---------------------------------------------------------------------------

class OpPage(QWidget):

    def __init__(self, sub_name, layer_idx, field_defs, build_call):
        super().__init__()
        self.sub_name   = sub_name
        self.build_call = build_call
        self.fields     = {}
        self._build(layer_idx, field_defs)

    def _build(self, layer_idx, field_defs):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left: SVG diagram (auto-sizes to aspect ratio)
        self.diagram = DiagramWidget(self.sub_name, layer_idx)
        outer.addWidget(self.diagram)

        # Right: fields (60%) + help text (40%)
        right = QWidget()
        right_l = QHBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)

        fields_w = QWidget()
        rl = QVBoxLayout(fields_w)
        rl.setContentsMargins(10, 10, 10, 10)
        rl.setSpacing(4)

        for key, label, hint, unit, default, ftype in field_defs:
            f = CycleField(key, label, hint, unit, default, ftype)
            self.fields[key] = f
            rl.addWidget(f)

        rl.addStretch()
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #f90; font-size: 10pt;')
        rl.addWidget(self.status)

        run = QPushButton(f'  RUN {self.sub_name.upper()}  ')
        run.setObjectName('run')
        run.clicked.connect(self._run)
        rl.addWidget(run)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet('color: #444;')

        right_l.addWidget(fields_w, 3)
        right_l.addWidget(sep)
        right_l.addWidget(_make_help_widget(self.sub_name), 2)

        outer.addWidget(right, 1)

    def _run(self):
        try:
            fvals = {k: f.value() for k, f in self.fields.items()}
            cmd_str = self.build_call(fvals)
            self.status.setText(f'→ {cmd_str}')
            c = linuxcnc.command()
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            c.mdi(cmd_str)
        except Exception as e:
            self.status.setText(f'ERROR: {e}')

    def state(self):
        return {k: f.value() for k, f in self.fields.items()}

    def restore(self, data):
        for k, v in data.items():
            if k in self.fields:
                self.fields[k].set_value(v)


# ---------------------------------------------------------------------------
# Radio-button page (Chamfer, Radius)
# ---------------------------------------------------------------------------

class RadioOpPage(OpPage):

    def __init__(self, sub_name, layer_idx, field_defs, radio_defs, build_call):
        self.radio_group = QButtonGroup()
        self.radios = {}
        self._radio_defs = radio_defs
        super().__init__(sub_name, layer_idx, field_defs, build_call)

    def _build(self, layer_idx, field_defs):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.diagram = DiagramWidget(self.sub_name, layer_idx)
        outer.addWidget(self.diagram)

        right = QWidget()
        right_l = QHBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)

        fields_w = QWidget()
        rl = QVBoxLayout(fields_w)
        rl.setContentsMargins(10, 10, 10, 10); rl.setSpacing(4)

        for key, label, hint, unit, default, ftype in field_defs:
            f = CycleField(key, label, hint, unit, default, ftype)
            self.fields[key] = f; rl.addWidget(f)

        hsep = QFrame(); hsep.setFrameShape(QFrame.HLine)
        hsep.setStyleSheet('color: #444;'); rl.addWidget(hsep)

        lbl = QLabel('Corner type:')
        lbl.setStyleSheet('color: #aaa; font-size: 11pt;')
        rl.addWidget(lbl)
        for i, (key, label) in enumerate(self._radio_defs):
            rb = QRadioButton(label)
            self.radio_group.addButton(rb, i)
            self.radios[key] = rb; rl.addWidget(rb)
        if self.radios:
            first_rb = next(iter(self.radios.values()))
            first_rb.setChecked(True)

        rl.addStretch()
        self.status = QLabel(''); self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #f90; font-size: 10pt;')
        rl.addWidget(self.status)

        run = QPushButton(f'  RUN {self.sub_name.upper()}  ')
        run.setObjectName('run'); run.clicked.connect(self._run)
        rl.addWidget(run)

        vsep = QFrame()
        vsep.setFrameShape(QFrame.VLine)
        vsep.setStyleSheet('color: #444;')

        right_l.addWidget(fields_w, 3)
        right_l.addWidget(vsep)
        right_l.addWidget(_make_help_widget(self.sub_name), 2)

        outer.addWidget(right, 1)

    def selected_radio(self):
        for key, rb in self.radios.items():
            if rb.isChecked(): return key
        return None

    def state(self):
        s = super().state(); s['_radio'] = self.selected_radio(); return s

    def restore(self, data):
        super().restore(data)
        sel = data.get('_radio')
        if sel and sel in self.radios: self.radios[sel].setChecked(True)


# ---------------------------------------------------------------------------
# Threading page
# ---------------------------------------------------------------------------

class ThreadingPage(OpPage):

    def __init__(self):
        self.radio_group = QButtonGroup()
        self.rb_ext = QRadioButton('External thread')
        self.rb_int = QRadioButton('Internal thread')
        self.rb_ext.setChecked(True)
        self.radio_group.addButton(self.rb_ext, 0)
        self.radio_group.addButton(self.rb_int, 1)
        super().__init__('threading', LAYER['threading'], self._fields(), self._call)

    def _fields(self):
        return [
            ('x',     'Thread Diameter', 'Nominal diameter — OD for external, bore for internal (not pilot hole)', 'mm', 20.0, 'length'),
            ('z',     'Finish Z',        'End of threaded section',                  'mm',     0.0, 'length'),
            ('pitch', 'Pitch',           'Distance between thread crests',           'mm',     1.0, 'pitch'),
            ('doc',   'Depth of Cut',   'First-pass depth (G76 j parameter)',       'mm',     0.1, 'length'),
            ('ss',    'Surface Speed',    'Cutting speed at tool tip',                'm/min', 100.0, 'speed'),
            ('maxrpm','Max RPM',         'RPM limit (G96 D parameter)',              'RPM',  400.0, 'int'),
            ('tool',  'Tool Number',     '',                                         '',       5.0, 'int'),
            ('coolant','Coolant',        '0 = off, 1 = on',                         '',       0.0, 'int'),
        ]

    def _build(self, layer_idx, field_defs):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.diagram = DiagramWidget(self.sub_name, layer_idx)
        outer.addWidget(self.diagram)

        right = QWidget()
        right_l = QHBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)

        fields_w = QWidget()
        rl = QVBoxLayout(fields_w)
        rl.setContentsMargins(10, 10, 10, 10); rl.setSpacing(4)

        for key, label, hint, unit, default, ftype in field_defs:
            f = CycleField(key, label, hint, unit, default, ftype)
            self.fields[key] = f; rl.addWidget(f)

        hsep = QFrame(); hsep.setFrameShape(QFrame.HLine)
        hsep.setStyleSheet('color: #444;'); rl.addWidget(hsep)
        rl.addWidget(self.rb_ext); rl.addWidget(self.rb_int)
        rl.addStretch()

        self.status = QLabel(''); self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #f90; font-size: 10pt;')
        rl.addWidget(self.status)

        run = QPushButton('  RUN THREADING  ')
        run.setObjectName('run'); run.clicked.connect(self._run)
        rl.addWidget(run)

        vsep = QFrame()
        vsep.setFrameShape(QFrame.VLine)
        vsep.setStyleSheet('color: #444;')

        right_l.addWidget(fields_w, 3)
        right_l.addWidget(vsep)
        right_l.addWidget(_make_help_widget(self.sub_name), 2)

        outer.addWidget(right, 1)

    def _call(self, f):
        tid = 1.0 if self.rb_int.isChecked() else 0.0
        return (f"O<threading> call [{f['ss']}] [{f['maxrpm']}] [1.0] [{f['doc']}] "
                f"[{f['tool']}] [{f['coolant']}] [0] [0] "
                f"[{f['x']}] [{f['z']}] [{f['pitch']}] [{tid}]")

    def state(self):
        s = super().state(); s['_internal'] = self.rb_int.isChecked(); return s

    def restore(self, data):
        super().restore(data)
        if data.get('_internal'): self.rb_int.setChecked(True)


# ---------------------------------------------------------------------------
# Call builders
# ---------------------------------------------------------------------------

def _turn_call(f):
    return (f"O<turning> call [{f['x']}] [{f['ss']}] [{f['doc']}] "
            f"[{f['feed']}] [{f['z']}] [{f.get('radius', 0)}] [{f.get('angle', 0)}] "
            f"[{f['tool']}] [{f['coolant']}] [{f['maxrpm']}]")

def _bore_call(f):
    return (f"O<boring> call [{f['x']}] [{f['ss']}] [{f['doc']}] "
            f"[{f['feed']}] [{f['z']}] [{f.get('radius', 0)}] [{f.get('angle', 0)}] "
            f"[{f['tool']}] [{f['coolant']}] [{f['maxrpm']}]")

def _face_call(f):
    return (f"O<facing> call [{f['ss']}] [{f['maxrpm']}] [{f['feed']}] "
            f"[{f['doc']}] [{f['tool']}] [{f['coolant']}] [{f.get('angle', 0)}] "
            f"[{f['x']}] [{f['z']}]")

def _chamfer_call(page):
    def _call(f):
        sel = page.selected_radio()
        fo = f['size'] if sel == 'fo' else 0.0
        fi = f['size'] if sel == 'fi' else 0.0
        bo = f['size'] if sel == 'bo' else 0.0
        return (f"O<chamfer> call [{f['x']}] [{f['ss']}] [{f['doc']}] "
                f"[{f['z']}] [{f['tool']}] [{f['feed']}] "
                f"[{fo}] [{fi}] [{bo}] [{f['coolant']}] [{f['maxrpm']}] [21]")
    return _call

def _radius_call(page):
    def _call(f):
        sel = page.selected_radio()
        fo = f['size'] if sel == 'fo' else 0.0
        fi = f['size'] if sel == 'fi' else 0.0
        bo = f['size'] if sel == 'bo' else 0.0
        return (f"O<radius> call [{f['x']}] [{f['ss']}] [{f['feed']}] "
                f"[{f['doc']}] [{f['z']}] [{f['tool']}] [0] "
                f"[{fo}] [{fi}] [{bo}] [{f['coolant']}] [{f['maxrpm']}]")
    return _call

def _drill_call(f):
    return (f"O<drill> call [{f['dia']}] [{f['depth']}] [{f['ss']}] "
            f"[{f['feed']}] [{f['tool']}] [{f['peck']}] [0] "
            f"[{f['coolant']}] [0] [0] [{f['maxrpm']}] [21]")

def _groove_call(f):
    return (f"O<grooving> call [{f['x']}] [{f['ss']}] [{f['feed']}] "
            f"[{f['tool']}] [{f['coolant']}] [{f['z']}] [{f['maxrpm']}]")


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------

class UserTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('Lathe_Cycles')
        self.setStyleSheet(STYLE)
        self.pages = {}
        self._build()
        self._load_state()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # (key, label, hint, unit, default, field_type)
        def add(name, layer, fields, call_fn, tab_label):
            p = OpPage(name, layer, fields, call_fn)
            self.pages[name] = p
            tabs.addTab(p, tab_label)

        add('turning', LAYER['turning'], [
            ('x',      'Finish Diameter',    'Target OD at end of cut',            'mm',    15.0, 'length'),
            ('z',      'Finish Z',           'Z coordinate of cut end',            'mm',     0.0, 'length'),
            ('radius', 'End Radius',         'Nose radius at end of cut (0=none)', 'mm',     0.0, 'length'),
            ('angle',  'Taper Angle',        'Taper angle in degrees (0=straight)','deg',    0.0, 'angle'),
            ('ss',     'Surface Speed',      'Cutting speed at tool tip',          'm/min', 100.0,'speed'),
            ('maxrpm', 'Max RPM',            'RPM limit (G96 D parameter)',        'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per spindle revolution',        'mm/rev', 0.15,'feed'),
            ('doc',    'Depth of Cut',       'Material removed per pass (radius)', 'mm',     1.0, 'length'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _turn_call, 'Turning')

        add('boring', LAYER['boring'], [
            ('x',      'Finish Bore Dia',    'Target bore diameter',               'mm',     0.0, 'length'),
            ('z',      'Finish Z',           'Z coordinate of bore end',           'mm',     0.0, 'length'),
            ('radius', 'Run-out Radius',     'Nose radius at bore end (0=none)',   'mm',     0.0, 'length'),
            ('angle',  'Taper Angle',        'Bore taper angle in degrees (0=straight)','deg',0.0,'angle'),
            ('ss',     'Surface Speed',      'Cutting speed at tool tip',          'm/min', 100.0,'speed'),
            ('maxrpm', 'Max RPM',            'RPM limit',                          'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per revolution',                'mm/rev', 0.15,'feed'),
            ('doc',    'Depth of Cut',       'Material removed per pass (radius)', 'mm',     1.0, 'length'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _bore_call, 'Boring')

        add('facing', LAYER['facing'], [
            ('x',      'Finish Diameter',    'Outer diameter of face',             'mm',     0.0, 'length'),
            ('z',      'Finish Z',           'Final face Z position',              'mm',     0.0, 'length'),
            ('angle',  'Face Angle',         'Angle from perpendicular (0=flat)',  'deg',    0.0, 'angle'),
            ('ss',     'Surface Speed',      'Cutting speed at tool tip',          'm/min', 100.0,'speed'),
            ('maxrpm', 'Max RPM',            'RPM limit',                          'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per revolution',                'mm/rev', 0.15,'feed'),
            ('doc',    'Depth of Cut',       'Material removed per pass (Z)',      'mm',     1.0, 'length'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _face_call, 'Facing')

        # Chamfer
        p = RadioOpPage('chamfer', LAYER['chamfer'], [
            ('x',      'Diameter at Corner', 'OD (or bore dia) at the corner',    'mm',     0.0, 'length'),
            ('z',      'Z at Corner',        'Z position of the corner',          'mm',     0.0, 'length'),
            ('size',   'Chamfer Size',       'Width of chamfer along each face',  'mm',     1.0, 'length'),
            ('ss',     'Surface Speed',      'Cutting speed',                     'm/min', 100.0,'speed'),
            ('maxrpm', 'Max RPM',            'RPM limit',                         'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per revolution',               'mm/rev', 0.15,'feed'),
            ('doc',    'Step per Pass',      'Chamfer increment each pass',       'mm',     0.5, 'length'),
            ('tool',   'Tool Number',        '',                                  '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                 '',       0.0, 'int'),
        ], [
            ('fo', 'Front Outside  (OD / end face)'),
            ('fi', 'Front Inside   (bore / end face)'),
            ('bo', 'Rear Outside   (OD / shoulder)'),
        ], None)
        p.build_call = _chamfer_call(p)
        self.pages['chamfer'] = p
        tabs.addTab(p, 'Chamfer')

        # Radius
        p = RadioOpPage('radius', LAYER['radius'], [
            ('x',      'Diameter at Corner', 'OD (or bore dia) at the corner',    'mm',     0.0, 'length'),
            ('z',      'Z at Corner',        'Z position of the corner',          'mm',     0.0, 'length'),
            ('size',   'Radius Size',        'Radius of the blend arc',           'mm',     1.0, 'length'),
            ('ss',     'Surface Speed',      'Cutting speed',                     'm/min', 100.0,'speed'),
            ('maxrpm', 'Max RPM',            'RPM limit',                         'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per revolution',               'mm/rev', 0.15,'feed'),
            ('doc',    'Step per Pass',      'Radius increment each pass',        'mm',     0.5, 'length'),
            ('tool',   'Tool Number',        '',                                  '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                 '',       0.0, 'int'),
        ], [
            ('fo', 'Front Outside  (OD / end face)'),
            ('fi', 'Front Inside   (bore / end face)'),
            ('bo', 'Rear Outside   (OD / shoulder)'),
        ], None)
        p.build_call = _radius_call(p)
        self.pages['radius'] = p
        tabs.addTab(p, 'Radius')

        # Threading
        p = ThreadingPage()
        self.pages['threading'] = p
        tabs.addTab(p, 'Threading')

        add('drill', LAYER['drill'], [
            ('dia',    'Drill Diameter',     'Drill bit diameter',                 'mm',    10.0, 'length'),
            ('depth',  'Drill Depth (Z)',    'Z coordinate of drill bottom',       'mm',     0.0, 'length'),
            ('peck',   'Peck Distance',      'Retract after each peck',            'mm',     2.0, 'length'),
            ('ss',     'Surface Speed',      'Cutting speed at drill tip',         'm/min', 100.0,'speed'),
            ('maxrpm', 'Max RPM',            'RPM limit',                          'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per revolution',                'mm/rev', 0.05,'feed'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _drill_call, 'Drilling')

        add('groove', LAYER['groove'], [
            ('x',      'Groove Diameter',    'Finished diameter at groove bottom', 'mm',     0.0, 'length'),
            ('z',      'Groove Z',           'Z position of groove centre',        'mm',     0.0, 'length'),
            ('ss',     'Surface Speed',      'Cutting speed at tool tip',          'm/min', 100.0,'speed'),
            ('maxrpm', 'Max RPM',            'RPM limit',                          'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per rev (typically 0.03–0.08)', 'mm/rev', 0.05,'feed'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _groove_call, 'Grooving')

        self.tabs = tabs

    def _load_state(self):
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            for name, page in self.pages.items():
                if name in data:
                    page.restore(data[name])
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_state(self):
        data = {name: page.state() for name, page in self.pages.items()}
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def hideEvent(self, event):
        self._save_state(); super().hideEvent(event)

    def closeEvent(self, event):
        self._save_state(); super().closeEvent(event)
