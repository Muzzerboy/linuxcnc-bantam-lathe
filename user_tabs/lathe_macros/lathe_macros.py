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
import re
import base64
import io
import json
import linuxcnc

from qtpy.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QDialog, QButtonGroup,
    QRadioButton, QFrame, QScrollArea, QSizePolicy)
from qtpy.QtCore import Qt, QRectF, QPointF
from qtpy.QtGui import QPainter, QColor, QFont, QPen

try:
    from qtpy.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

TAB_DIR          = os.path.dirname(os.path.abspath(__file__))
SVG_FILE         = os.path.join(TAB_DIR, 'LatheMacro.svg')
SVG_TRANSPARENT  = os.path.join(TAB_DIR, 'LatheMacro_transparent.svg')
STATE_FILE       = os.path.join(TAB_DIR, 'state.json')


def _build_transparent_svg():
    """
    Pre-process LatheMacro.svg: make pure-black PNG backgrounds transparent.
    Cached to LatheMacro_transparent.svg. Run in a background thread on first
    use; on subsequent starts the cache is already there so this is instant.
    """
    if not os.path.exists(SVG_FILE):
        return

    # Already up to date
    if (os.path.exists(SVG_TRANSPARENT) and
            os.path.getmtime(SVG_TRANSPARENT) >= os.path.getmtime(SVG_FILE)):
        return

    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return

    txt = open(SVG_FILE, encoding='utf-8').read()

    def fix_png(m):
        try:
            raw = base64.b64decode(m.group(1))
            img = Image.open(io.BytesIO(raw)).convert('LA')
            arr = np.array(img)
            arr[:, :, 1] = np.where(arr[:, :, 0] == 0, 0, 255).astype(np.uint8)
            buf = io.BytesIO()
            Image.fromarray(arr, mode='LA').save(buf, 'PNG')
            return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return m.group(0)

    result = re.sub(r'data:image/png;base64,([A-Za-z0-9+/=]+)', fix_png, txt)
    try:
        with open(SVG_TRANSPARENT, 'w', encoding='utf-8') as f:
            f.write(result)
    except Exception:
        pass


def _svg_path():
    """Return the best SVG path: transparent version if available, else original."""
    if os.path.exists(SVG_TRANSPARENT):
        return SVG_TRANSPARENT
    return SVG_FILE


# Kick off preprocessing in background (instant if cache exists)
import threading
threading.Thread(target=_build_transparent_svg, daemon=True).start()

# Spinbox label positions from Andy's lathemacro.ui.
# Coordinates are in the SVG's 1500x1000 coordinate space.
# Format: { operation_key: [ ((svg_x, svg_y), 'Label text'), ... ] }
LABELS = {
    'turning': [
        ((1000, 654), 'Finish Diameter'),
        ((635,  687), 'Feed per Rev'),
        ((800,  230), 'End Radius'),
        ((821,  863), 'Cut per Pass'),
        ((125,  424), 'Finish Z'),
        ((520,  474), 'Taper Angle'),
    ],
    'boring': [
        ((700,  280), 'Taper Angle'),
        ((421,  520), 'Run-out Radius'),
        ((1080, 616), 'Finish Diameter'),
        ((900,  825), 'Diameter Increment'),
        ((530,  820), 'Feed per Rev'),
        ((273,  267), 'Finish Z'),
    ],
    'facing': [
        ((156,  404), 'Finish Z'),
        ((1115, 626), 'Finish Diameter'),
        ((876,  886), 'Feed per Rev'),
        ((408,  760), 'Cut per Pass'),
        ((1044, 364), 'Face Angle'),
    ],
    'radius': [
        ((1018, 674), 'Diameter at Corner'),
        ((202,  334), 'Z Position'),
        ((848,  451), 'Radius Size'),
        ((863,  629), 'Front Inside'),
        ((763,  680), 'Front Outside'),
        ((335,  448), 'Rear Outside'),
    ],
    'chamfer': [
        ((202,  334), 'Z Position'),
        ((1112, 287), 'Chamfer Size'),
        ((1033, 678), 'Diameter at Corner'),
        ((335,  448), 'Rear Outside'),
        ((763,  680), 'Front Outside'),
        ((863,  629), 'Front Inside'),
    ],
    'threading': [
        ((268,  341), 'Finish Z'),
        ((652,  737), 'External (OD)'),
        ((754,  603), 'Internal (ID)'),
        ((1010, 753), 'Thread Diameter'),
        ((192,  616), 'Thread Pitch'),
    ],
    'drill': [
        ((1200, 270), 'Drill Diameter'),
        ((260,  250), 'Drill Depth (Z)'),
        ((770,  900), 'Feed per Rev'),
        ((300,  711), 'Peck Distance'),
    ],
    'tapping': [
        ((1084, 672), 'Tap Diameter'),
        ((648,  864), 'Pitch / Feed'),
    ],
}

# SVG layer index per operation (matches Andy's GladeVCP tab order)
LAYER = {
    'turning':   0,
    'boring':    1,
    'facing':    2,
    'radius':    3,
    'chamfer':   4,
    'threading': 5,
    'drill':     7,
    'tapping':   6,   # grooving layer — closest available
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


# ---------------------------------------------------------------------------
# SVG diagram panel
# ---------------------------------------------------------------------------

class DiagramWidget(QWidget):
    """Renders one layer of Andy Pugh's LatheMacro.svg with labels."""

    SVG_W, SVG_H = 1500, 1000   # native SVG coordinate space
    _shared_renderer = None

    def __init__(self, op_key, layer_idx, parent=None):
        super().__init__(parent)
        self._layer_id = f'layer{layer_idx}'
        self._labels = LABELS.get(op_key, [])
        self.setMinimumSize(300, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet('background: #c8c8c8;')
        if HAS_SVG and DiagramWidget._shared_renderer is None:
            svg = _svg_path()
            if os.path.exists(svg):
                DiagramWidget._shared_renderer = QSvgRenderer(svg)

    def _render_rect(self):
        """Return a QRectF that fits the SVG aspect ratio centred in the widget."""
        margin = 4
        aw = self.width()  - 2 * margin
        ah = self.height() - 2 * margin
        svg_aspect = self.SVG_W / self.SVG_H
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

        BG = QColor('#c8c8c8')
        painter.fillRect(event.rect(), BG)

        r = DiagramWidget._shared_renderer
        rect = self._render_rect()

        if r and r.isValid():
            if r.elementExists(self._layer_id):
                r.render(painter, self._layer_id, rect)
            else:
                r.render(painter, rect)

            # Overlay dimension labels
            font = QFont('Sans', 8, QFont.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            for (sx, sy), text in self._labels:
                wx = rect.left() + (sx / self.SVG_W) * rect.width()
                wy = rect.top()  + (sy / self.SVG_H) * rect.height()
                tw = fm.horizontalAdvance(text) + 6
                th = fm.height() + 2
                bg = QRectF(wx - tw/2, wy - th/2, tw, th)
                painter.fillRect(bg, QColor(255, 255, 180, 220))
                painter.setPen(QPen(QColor('#111')))
                painter.drawText(bg, Qt.AlignCenter, text)
        else:
            painter.setPen(QColor('#666'))
            painter.drawText(event.rect(), Qt.AlignCenter, 'Diagram unavailable')

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
        return f'{int(v)}' if self.field_type == 'int' else f'{float(v):.4f}'

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

        splitter = QSplitter(Qt.Horizontal)

        # Left: SVG diagram
        self.diagram = DiagramWidget(self.sub_name, layer_idx)
        splitter.addWidget(self.diagram)

        # Right: fields + run button
        right = QWidget()
        right.setStyleSheet('background: #2a2a2a;')
        rl = QVBoxLayout(right)
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

        splitter.addWidget(right)
        splitter.setSizes([500, 400])
        outer.addWidget(splitter)

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
        splitter = QSplitter(Qt.Horizontal)

        self.diagram = DiagramWidget(self.sub_name, layer_idx)
        splitter.addWidget(self.diagram)

        right = QWidget(); right.setStyleSheet('background: #2a2a2a;')
        rl = QVBoxLayout(right)
        rl.setContentsMargins(10, 10, 10, 10); rl.setSpacing(4)

        for key, label, hint, unit, default, ftype in field_defs:
            f = CycleField(key, label, hint, unit, default, ftype)
            self.fields[key] = f; rl.addWidget(f)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color: #444;'); rl.addWidget(sep)

        lbl = QLabel('Corner type:')
        lbl.setStyleSheet('color: #aaa; font-size: 11pt;')
        rl.addWidget(lbl)
        for i, (key, label) in enumerate(self._radio_defs):
            rb = QRadioButton(label)
            if i == 0: rb.setChecked(True)
            self.radio_group.addButton(rb, i)
            self.radios[key] = rb; rl.addWidget(rb)

        rl.addStretch()
        self.status = QLabel(''); self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #f90; font-size: 10pt;')
        rl.addWidget(self.status)

        run = QPushButton(f'  RUN {self.sub_name.upper()}  ')
        run.setObjectName('run'); run.clicked.connect(self._run)
        rl.addWidget(run)

        splitter.addWidget(right)
        splitter.setSizes([500, 400])
        outer.addWidget(splitter)

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
            ('x',     'Thread Diameter', 'Nominal OD (external) or bore (internal)', 'mm',    20.0, 'length'),
            ('z',     'Finish Z',        'End of threaded section',                  'mm',     0.0, 'length'),
            ('pitch', 'Pitch',           'Distance between thread crests',           'mm',     1.0, 'pitch'),
            ('ss',    'Speed',           'Spindle RPM (not surface speed)',          'RPM',   50.0, 'int'),
            ('maxrpm','Max RPM',         'RPM limit',                                'RPM',  200.0, 'int'),
            ('tool',  'Tool Number',     '',                                         '',       5.0, 'int'),
            ('coolant','Coolant',        '0 = off, 1 = on',                         '',       0.0, 'int'),
        ]

    def _build(self, layer_idx, field_defs):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)

        self.diagram = DiagramWidget(self.sub_name, layer_idx)
        splitter.addWidget(self.diagram)

        right = QWidget(); right.setStyleSheet('background: #2a2a2a;')
        rl = QVBoxLayout(right)
        rl.setContentsMargins(10, 10, 10, 10); rl.setSpacing(4)

        for key, label, hint, unit, default, ftype in field_defs:
            f = CycleField(key, label, hint, unit, default, ftype)
            self.fields[key] = f; rl.addWidget(f)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color: #444;'); rl.addWidget(sep)
        rl.addWidget(self.rb_ext); rl.addWidget(self.rb_int)
        rl.addStretch()

        self.status = QLabel(''); self.status.setWordWrap(True)
        self.status.setStyleSheet('color: #f90; font-size: 10pt;')
        rl.addWidget(self.status)

        run = QPushButton('  RUN THREADING  ')
        run.setObjectName('run'); run.clicked.connect(self._run)
        rl.addWidget(run)

        splitter.addWidget(right)
        splitter.setSizes([500, 400])
        outer.addWidget(splitter)

    def _call(self, f):
        tid = 1.0 if self.rb_int.isChecked() else 0.0
        return (f"O<threading> call [{f['ss']}] [{f['maxrpm']}] [1.0] [0.1] "
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
            f"[{f['feed']}] [{f['z']}] [0] [0] "
            f"[{f['tool']}] [{f['coolant']}] [{f['maxrpm']}]")

def _bore_call(f):
    return (f"O<boring> call [{f['x']}] [{f['ss']}] [{f['doc']}] "
            f"[{f['feed']}] [{f['z']}] [0] [0] "
            f"[{f['tool']}] [{f['coolant']}] [{f['maxrpm']}]")

def _face_call(f):
    return (f"O<facing> call [{f['ss']}] [{f['maxrpm']}] [{f['feed']}] "
            f"[{f['doc']}] [{f['tool']}] [{f['coolant']}] [0] "
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

def _tapping_call(f):
    return (f"O<tapping> call [{f['dia']}] [{f['z']}] [{f['ss']}] "
            f"[{f['pitch']}] [{f['tool']}] [{f['coolant']}] [{f['ramp']}]")


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
            ('ss',     'Surface Speed',      'Cutting speed at tool tip',          'm/min', 100.0,'length'),
            ('maxrpm', 'Max RPM',            'RPM limit (G96 D parameter)',        'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per spindle revolution',        'mm/rev', 0.15,'feed'),
            ('doc',    'Depth of Cut',       'Material removed per pass (radius)', 'mm',     1.0, 'length'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _turn_call, 'Turning')

        add('boring', LAYER['boring'], [
            ('x',      'Finish Bore Dia',    'Target bore diameter',               'mm',     0.0, 'length'),
            ('z',      'Finish Z',           'Z coordinate of bore end',           'mm',     0.0, 'length'),
            ('ss',     'Surface Speed',      'Cutting speed at tool tip',          'm/min', 100.0,'length'),
            ('maxrpm', 'Max RPM',            'RPM limit',                          'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per revolution',                'mm/rev', 0.15,'feed'),
            ('doc',    'Depth of Cut',       'Material removed per pass (radius)', 'mm',     1.0, 'length'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _bore_call, 'Boring')

        add('facing', LAYER['facing'], [
            ('x',      'Finish Diameter',    'Outer diameter of face',             'mm',     0.0, 'length'),
            ('z',      'Finish Z',           'Final face Z position',              'mm',     0.0, 'length'),
            ('ss',     'Surface Speed',      'Cutting speed at tool tip',          'm/min', 100.0,'length'),
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
            ('ss',     'Surface Speed',      'Cutting speed',                     'm/min', 100.0,'length'),
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
            ('ss',     'Surface Speed',      'Cutting speed',                     'm/min', 100.0,'length'),
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
            ('ss',     'Surface Speed',      'Cutting speed at drill tip',         'm/min', 100.0,'length'),
            ('maxrpm', 'Max RPM',            'RPM limit',                          'RPM',  2000.0,'int'),
            ('feed',   'Feed Rate',          'Feed per revolution',                'mm/rev', 0.05,'feed'),
            ('tool',   'Tool Number',        '',                                   '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                  '',       0.0, 'int'),
        ], _drill_call, 'Drilling')

        add('tapping', LAYER['tapping'], [
            ('dia',   'Tap Diameter',        'Nominal tap diameter',               'mm',    10.0, 'length'),
            ('z',     'Tap Depth (Z)',       'Z coordinate of tap bottom',        'mm',     0.0, 'length'),
            ('pitch', 'Thread Pitch',        'Distance between thread crests',    'mm',     1.0, 'pitch'),
            ('ss',    'Spindle Speed',       'RPM (low — typically 30-100)',      'RPM',   30.0, 'int'),
            ('tool',  'Tool Number',         '',                                  '',       1.0, 'int'),
            ('coolant','Coolant',            '0 = off,  1 = on',                 '',       0.0, 'int'),
            ('ramp',  'Ramp Distance',       'Spindle acceleration allowance',    'mm',     5.0, 'length'),
        ], _tapping_call, 'Tapping')

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
