#!/usr/bin/env python3
"""
Lathe Cycles user tab for Probe Basic Lathe.

Replicates Andy Pugh's gmoccapy lathe macro interface with:
  - Free-text numeric entry fields (touch a field to open numpad)
  - Unit conversion buttons: in->mm, mm->in, tpi->pitch
  - Turning, Boring, Facing, Chamfer, Radius, Threading, Drilling, Tapping

Each operation calls the corresponding subroutine in the config's
subroutines/ directory via MDI.
"""

import os
import json
import linuxcnc

from qtpy.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QDialog, QButtonGroup,
    QRadioButton, QFrame, QSizePolicy)
from qtpy.QtCore import Qt
from qtpy.QtGui import QFont

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'state.json')

STYLE = """
QWidget      { background: #2a2a2a; color: white; font-size: 13pt; }
QTabWidget::pane { border: 1px solid #444; }
QTabBar::tab {
    background: #333; color: #aaa; padding: 6px 16px;
    border: 1px solid #444; border-bottom: none;
    font-size: 12pt;
}
QTabBar::tab:selected { background: #1a5a8a; color: white; }
QLabel  { color: #ccc; }
QLabel#unit { color: #888; font-size: 11pt; }
QLabel#head { color: #aaa; font-size: 11pt; border-bottom: 1px solid #444; }
QLineEdit {
    background: #1a1a1a; color: white;
    border: 1px solid #555; border-radius: 3px;
    font-size: 14pt; padding: 2px 6px;
    min-width: 110px;
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

        lbl = QLabel(label)
        lbl.setObjectName('title')
        lbl.setAlignment(Qt.AlignCenter)
        outer.addWidget(lbl)

        self.display = QLineEdit(value)
        self.display.setAlignment(Qt.AlignRight)
        outer.addWidget(self.display)

        grid = QGridLayout()
        grid.setSpacing(5)
        for text, row, col in [
            ('7',0,0),('8',0,1),('9',0,2),
            ('4',1,0),('5',1,1),('6',1,2),
            ('1',2,0),('2',2,1),('3',2,2),
            ('0',3,0),('.',3,1),('+/-',3,2),
        ]:
            b = QPushButton(text)
            b.clicked.connect(lambda _, t=text: self._digit(t))
            grid.addWidget(b, row, col)

        bsp = QPushButton('⌫')
        bsp.clicked.connect(self._bsp)
        grid.addWidget(bsp, 4, 0, 1, 2)
        clr = QPushButton('C')
        clr.clicked.connect(lambda: self.display.setText(''))
        grid.addWidget(clr, 4, 2)
        outer.addLayout(grid)

        # Conversion buttons
        if self.field_type in ('length', 'feed'):
            row = QHBoxLayout()
            for txt, fn in [('in → mm', self._in_mm), ('mm → in', self._mm_in)]:
                b = QPushButton(txt); b.setObjectName('conv')
                b.clicked.connect(fn); row.addWidget(b)
            outer.addLayout(row)
        elif self.field_type == 'pitch':
            row = QHBoxLayout()
            for txt, fn in [('tpi → mm', self._tpi_mm), ('mm → tpi', self._tpi_mm)]:
                b = QPushButton(txt); b.setObjectName('conv')
                b.clicked.connect(fn); row.addWidget(b)
            outer.addLayout(row)

        row2 = QHBoxLayout()
        can = QPushButton('Cancel'); can.setObjectName('can')
        ok  = QPushButton('OK');     ok.setObjectName('ok')
        can.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        row2.addWidget(can); row2.addWidget(ok)
        outer.addLayout(row2)

    def _digit(self, t):
        if t == '+/-':
            cur = self.display.text()
            self.display.setText(cur[1:] if cur.startswith('-') else '-' + cur)
        else:
            self.display.setText(self.display.text() + t)

    def _bsp(self):
        self.display.setText(self.display.text()[:-1])

    def _convert(self, factor):
        try:
            self.display.setText(f'{float(self.display.text()) * factor:.4f}')
        except ValueError:
            pass

    def _in_mm(self):  self._convert(25.4)
    def _mm_in(self):  self._convert(1/25.4)
    def _tpi_mm(self):
        try:
            v = float(self.display.text())
            self.display.setText(f'{25.4/v:.4f}' if v else '')
        except ValueError:
            pass

    def value(self):
        try:
            return float(self.display.text())
        except ValueError:
            return 0.0


# ---------------------------------------------------------------------------
# Individual field widget
# ---------------------------------------------------------------------------

class CycleField(QWidget):

    def __init__(self, key, label, unit, default, field_type='length'):
        super().__init__()
        self.key = key
        self.label_text = label
        self.field_type = field_type
        lbl = QLabel(label)
        lbl.setMinimumWidth(180)
        self.edit = QLineEdit(self._fmt(default))
        self.edit.setReadOnly(True)
        self.edit.mousePressEvent = self._open
        ulbl = QLabel(unit)
        ulbl.setObjectName('unit')
        ulbl.setMinimumWidth(70)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.addWidget(lbl)
        row.addWidget(self.edit)
        row.addWidget(ulbl)

    def _fmt(self, v):
        return f'{int(v)}' if self.field_type == 'int' else f'{float(v):.4f}'

    def _open(self, event):
        dlg = NumpadDialog(self.label_text, self.edit.text(),
                           self.field_type, self.window())
        dlg.setMinimumSize(380, 520)
        if dlg.exec_() == QDialog.Accepted:
            self.edit.setText(self._fmt(dlg.value()))

    def value(self):
        try:
            return float(self.edit.text())
        except ValueError:
            return 0.0

    def set_value(self, v):
        self.edit.setText(self._fmt(v))


# ---------------------------------------------------------------------------
# Base operation page
# ---------------------------------------------------------------------------

class OpPage(QWidget):

    def __init__(self, sub_name, field_defs, build_call):
        """
        sub_name   : subroutine name (e.g. 'turning')
        field_defs : list of (key, label, unit, default, field_type)
        build_call : callable(fields_dict) -> mdi string
        """
        super().__init__()
        self.sub_name   = sub_name
        self.build_call = build_call
        self.fields     = {}
        self._build(field_defs)

    def _build(self, field_defs):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(4)

        for key, label, unit, default, ftype in field_defs:
            f = CycleField(key, label, unit, default, ftype)
            self.fields[key] = f
            outer.addWidget(f)

        outer.addStretch()

        self.status = QLabel('')
        self.status.setStyleSheet('color: #f90; font-size: 11pt;')
        outer.addWidget(self.status)

        run = QPushButton(f'  RUN {self.sub_name.upper()}  ')
        run.setObjectName('run')
        run.clicked.connect(self._run)
        outer.addWidget(run)

    def _run(self):
        try:
            fvals = {k: f.value() for k, f in self.fields.items()}
            cmd_str = self.build_call(fvals)
            self.status.setText(f'→  {cmd_str}')
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
    """Operation page with radio buttons for corner-type selection."""

    def __init__(self, sub_name, field_defs, radio_defs, build_call):
        self.radio_group = QButtonGroup()
        self.radios = {}
        self._radio_defs = radio_defs
        super().__init__(sub_name, field_defs, build_call)

    def _build(self, field_defs):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(4)

        for key, label, unit, default, ftype in field_defs:
            f = CycleField(key, label, unit, default, ftype)
            self.fields[key] = f
            outer.addWidget(f)

        # Radio buttons
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color: #444;')
        outer.addWidget(sep)

        for i, (key, label) in enumerate(self._radio_defs):
            rb = QRadioButton(label)
            if i == 0:
                rb.setChecked(True)
            self.radio_group.addButton(rb, i)
            self.radios[key] = rb
            outer.addWidget(rb)

        outer.addStretch()

        self.status = QLabel('')
        self.status.setStyleSheet('color: #f90; font-size: 11pt;')
        outer.addWidget(self.status)

        run = QPushButton(f'  RUN {self.sub_name.upper()}  ')
        run.setObjectName('run')
        run.clicked.connect(self._run)
        outer.addWidget(run)

    def selected_radio(self):
        for key, rb in self.radios.items():
            if rb.isChecked():
                return key
        return None

    def state(self):
        s = super().state()
        s['_radio'] = self.selected_radio()
        return s

    def restore(self, data):
        super().restore(data)
        sel = data.get('_radio')
        if sel and sel in self.radios:
            self.radios[sel].setChecked(True)


# ---------------------------------------------------------------------------
# Threading page (has internal/external radio)
# ---------------------------------------------------------------------------

class ThreadingPage(OpPage):

    def __init__(self):
        self.radio_group = QButtonGroup()
        self.rb_ext = QRadioButton('External thread')
        self.rb_int = QRadioButton('Internal thread')
        self.rb_ext.setChecked(True)
        self.radio_group.addButton(self.rb_ext, 0)
        self.radio_group.addButton(self.rb_int, 1)
        super().__init__('threading', self._fields(), self._call)

    def _fields(self):
        return [
            ('x',      'Thread Diameter',   'mm',    20.0,  'length'),
            ('z',      'Finish Z',          'mm',     0.0,  'length'),
            ('pitch',  'Pitch',             'mm',     1.0,  'pitch'),
            ('ss',     'Speed',             'RPM',   50.0,  'int'),
            ('maxrpm', 'Max RPM',           'RPM',  200.0,  'int'),
            ('tool',   'Tool Number',       '',       5.0,  'int'),
            ('coolant','Coolant (0/1)',     '',       0.0,  'int'),
        ]

    def _build(self, field_defs):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(4)
        for key, label, unit, default, ftype in field_defs:
            f = CycleField(key, label, unit, default, ftype)
            self.fields[key] = f
            outer.addWidget(f)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color: #444;'); outer.addWidget(sep)
        outer.addWidget(self.rb_ext)
        outer.addWidget(self.rb_int)
        outer.addStretch()
        self.status = QLabel('')
        self.status.setStyleSheet('color: #f90; font-size: 11pt;')
        outer.addWidget(self.status)
        run = QPushButton('  RUN THREADING  ')
        run.setObjectName('run')
        run.clicked.connect(self._run)
        outer.addWidget(run)

    def _call(self, f):
        tid = 1.0 if self.rb_int.isChecked() else 0.0
        return (f"O<threading> call "
                f"[{f['ss']}] [{f['maxrpm']}] [1.0] [0.1] "
                f"[{f['tool']}] [{f['coolant']}] [0] [0] "
                f"[{f['x']}] [{f['z']}] [{f['pitch']}] [{tid}]")

    def state(self):
        s = super().state()
        s['_internal'] = self.rb_int.isChecked()
        return s

    def restore(self, data):
        super().restore(data)
        if data.get('_internal'):
            self.rb_int.setChecked(True)


# ---------------------------------------------------------------------------
# Build call helpers for each operation
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
        fo = f['size'] if page.selected_radio() == 'fo' else 0.0
        fi = f['size'] if page.selected_radio() == 'fi' else 0.0
        bo = f['size'] if page.selected_radio() == 'bo' else 0.0
        return (f"O<chamfer> call [{f['x']}] [{f['ss']}] [{f['doc']}] "
                f"[{f['z']}] [{f['tool']}] [{f['feed']}] "
                f"[{fo}] [{fi}] [{bo}] [{f['coolant']}] [{f['maxrpm']}] [21]")
    return _call

def _radius_call(page):
    def _call(f):
        fo = f['size'] if page.selected_radio() == 'fo' else 0.0
        fi = f['size'] if page.selected_radio() == 'fi' else 0.0
        bo = f['size'] if page.selected_radio() == 'bo' else 0.0
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
# Main tab widget
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
        layout.setContentsMargins(4, 4, 4, 4)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Turning ---
        p = OpPage('turning', [
            ('x',      'Finish Diameter',  'mm',    15.0, 'length'),
            ('z',      'Finish Z',         'mm',     0.0, 'length'),
            ('ss',     'Surface Speed',    'm/min', 100.0, 'length'),
            ('maxrpm', 'Max RPM',          'RPM',  2000.0,'int'),
            ('feed',   'Feed',             'mm/rev', 0.15, 'feed'),
            ('doc',    'Depth of Cut',     'mm',     1.0,  'length'),
            ('tool',   'Tool Number',      '',       1.0,  'int'),
            ('coolant','Coolant (0=off)',  '',       0.0,  'int'),
        ], _turn_call)
        self.pages['turning'] = p
        tabs.addTab(p, 'Turning')

        # --- Boring ---
        p = OpPage('boring', [
            ('x',      'Finish Bore Dia',  'mm',     0.0, 'length'),
            ('z',      'Finish Z',         'mm',     0.0, 'length'),
            ('ss',     'Surface Speed',    'm/min', 100.0, 'length'),
            ('maxrpm', 'Max RPM',          'RPM',  2000.0,'int'),
            ('feed',   'Feed',             'mm/rev', 0.15, 'feed'),
            ('doc',    'Depth of Cut',     'mm',     1.0,  'length'),
            ('tool',   'Tool Number',      '',       1.0,  'int'),
            ('coolant','Coolant (0=off)',  '',       0.0,  'int'),
        ], _bore_call)
        self.pages['boring'] = p
        tabs.addTab(p, 'Boring')

        # --- Facing ---
        p = OpPage('facing', [
            ('x',      'Finish Diameter',  'mm',     0.0, 'length'),
            ('z',      'Finish Z',         'mm',     0.0, 'length'),
            ('ss',     'Surface Speed',    'm/min', 100.0, 'length'),
            ('maxrpm', 'Max RPM',          'RPM',  2000.0,'int'),
            ('feed',   'Feed',             'mm/rev', 0.15, 'feed'),
            ('doc',    'Depth of Cut',     'mm',     1.0,  'length'),
            ('tool',   'Tool Number',      '',       1.0,  'int'),
            ('coolant','Coolant (0=off)',  '',       0.0,  'int'),
        ], _face_call)
        self.pages['facing'] = p
        tabs.addTab(p, 'Facing')

        # --- Chamfer ---
        p = RadioOpPage('chamfer', [
            ('x',      'Diameter at corner','mm',    0.0,  'length'),
            ('z',      'Z at corner',       'mm',    0.0,  'length'),
            ('size',   'Chamfer Size',       'mm',   1.0,  'length'),
            ('ss',     'Surface Speed',     'm/min',100.0, 'length'),
            ('maxrpm', 'Max RPM',           'RPM', 2000.0, 'int'),
            ('feed',   'Feed',              'mm/rev',0.15, 'feed'),
            ('doc',    'Step per Pass',     'mm',    0.5,  'length'),
            ('tool',   'Tool Number',       '',      1.0,  'int'),
            ('coolant','Coolant (0=off)',   '',      0.0,  'int'),
        ], [
            ('fo', 'Front Outside'),
            ('fi', 'Front Inside'),
            ('bo', 'Rear Outside'),
        ], None)
        p.build_call = _chamfer_call(p)
        self.pages['chamfer'] = p
        tabs.addTab(p, 'Chamfer')

        # --- Radius ---
        p = RadioOpPage('radius', [
            ('x',      'Diameter at corner','mm',    0.0,  'length'),
            ('z',      'Z at corner',       'mm',    0.0,  'length'),
            ('size',   'Radius Size',        'mm',   1.0,  'length'),
            ('ss',     'Surface Speed',     'm/min',100.0, 'length'),
            ('maxrpm', 'Max RPM',           'RPM', 2000.0, 'int'),
            ('feed',   'Feed',              'mm/rev',0.15, 'feed'),
            ('doc',    'Step per Pass',     'mm',    0.5,  'length'),
            ('tool',   'Tool Number',       '',      1.0,  'int'),
            ('coolant','Coolant (0=off)',   '',      0.0,  'int'),
        ], [
            ('fo', 'Front Outside'),
            ('fi', 'Front Inside'),
            ('bo', 'Rear Outside'),
        ], None)
        p.build_call = _radius_call(p)
        self.pages['radius'] = p
        tabs.addTab(p, 'Radius')

        # --- Threading ---
        p = ThreadingPage()
        self.pages['threading'] = p
        tabs.addTab(p, 'Threading')

        # --- Drilling ---
        p = OpPage('drill', [
            ('dia',    'Drill Diameter',    'mm',    10.0, 'length'),
            ('depth',  'Drill Depth (Z)',   'mm',     0.0, 'length'),
            ('peck',   'Peck Distance',     'mm',     2.0, 'length'),
            ('ss',     'Surface Speed',    'm/min', 100.0, 'length'),
            ('maxrpm', 'Max RPM',          'RPM',  2000.0,'int'),
            ('feed',   'Feed',             'mm/rev', 0.05, 'feed'),
            ('tool',   'Tool Number',      '',        1.0, 'int'),
            ('coolant','Coolant (0=off)',  '',        0.0, 'int'),
        ], _drill_call)
        self.pages['drill'] = p
        tabs.addTab(p, 'Drilling')

        # --- Tapping ---
        p = OpPage('tapping', [
            ('dia',   'Tap Diameter',      'mm',    10.0, 'length'),
            ('z',     'Tap Depth (Z)',     'mm',     0.0, 'length'),
            ('pitch', 'Pitch',             'mm',     1.0, 'pitch'),
            ('ss',    'Speed',             'RPM',   30.0, 'int'),
            ('tool',  'Tool Number',       '',       1.0, 'int'),
            ('coolant','Coolant (0=off)', '',        0.0, 'int'),
            ('ramp',  'Ramp Distance',     'mm',     5.0, 'length'),
        ], _tapping_call)
        self.pages['tapping'] = p
        tabs.addTab(p, 'Tapping')

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
        self._save_state()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)
