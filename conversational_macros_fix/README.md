# Probe Basic Lathe — Conversational Macro Fixes

This folder contains fixed and completed conversational macro subroutines
for **Probe Basic Lathe**, along with the system file changes needed to
make the conversational tabs work correctly.

Assumes Probe Basic Lathe is already installed and running on your machine.

---

## What is fixed

| File | Problem | Fix |
|------|---------|-----|
| `turning.ngc` | **Missing** from PBL install | Written from scratch (Andy Pugh gmoccapy originals) |
| `boring.ngc` | **Missing** from PBL install | Written from scratch |
| `chamfer.ngc` | Three missing `#` symbols caused parse error on rear chamfer | Fixed |
| `radius.ngc` | Wrong G7/G8 mode + incorrect arc centre (I=0 K=temp) caused arc radius mismatch error | Fixed: G8 mode, I=±temp K=0 |
| `threading.ngc` | `threading_feed` used as spindle speed; should be constant RPM for threading | Fixed: G97 S#<threading_ss> |
| `tapping.ngc` | G33.1 (rigid tapping) hangs on VFD spindles; G33 works with encoder feedback | Fixed: G33 spindle-sync |
| All subroutines | Zero depth-of-cut causes infinite while loop, machine locks in MDI | Guard added: doc must be > 0 |
| All subroutines | G21 (metric) hardcoded | Correct for metric machines |
| `backup_restore.ngc` | Noisy DEBUG messages cluttered notification panel | Removed |

---

## Step 1 — copy subroutine files

Copy all `.ngc` files from the `subroutines/` folder here into your PBL
config's `subroutines/` directory, replacing any existing files:

```bash
cp subroutines/*.ngc ~/linuxcnc/configs/<your-config>/subroutines/
```

---

## Step 2 — add G21 to INI startup code

In your `probe_basic_lathe.ini`, find `RS274NGC_STARTUP_CODE` and ensure
`G21` is included:

```ini
RS274NGC_STARTUP_CODE = G21 G7 G18
```

---

## Step 3 — fix default values in the PBL UI

PBL's conversational tabs have wrong default values out of the box (feed
rates of 5 mm/rev, surface speeds of 1 m/min, tool steps of 10, etc.).
These are set in the XML `.ui` file that PBL loads directly.

Run this **once** in a terminal (requires sudo). Values are based on
Andy Pugh's original gmoccapy lathe macro defaults:

```bash
sudo python3 << 'PYEOF'
import xml.etree.ElementTree as ET

f = '/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.ui'
tree = ET.parse(f)
root = tree.getroot()

# (widget_name, value, xml_type)
defaults = [
    # Units fields -- default to G21 (metric). Toggle between 20/21.
    ('turning_units',    21,    'number'),
    ('chamfer_units',    21,    'number'),
    ('threads_units',    21,    'number'),
    ('drilling_units',   21,    'number'),
    ('tapping_units',    21,    'number'),
    # Surface speed (m/min) and max RPM
    ('turning_ss',       100,   'number'),
    ('turning_maxrpm',   2000,  'number'),
    ('boring_ss',        100.0, 'double'),
    ('boring_maxrpm',    2000.0,'double'),
    ('facing_ss',        100.0, 'double'),
    ('facing_maxrpm',    2000,  'number'),
    ('chamfer_ss',       100,   'number'),
    ('chamfer_maxrpm',   2000,  'number'),
    ('radius_ss',        100,   'number'),
    ('radius_maxrpm',    2000,  'number'),
    ('threading_ss',     50,    'number'),   # RPM, not surface speed
    ('threading_maxrpm', 200,   'number'),
    ('drill_ss',         100,   'number'),
    ('drill_maxrpm',     2000,  'number'),
    ('tapping_ss',       30,    'number'),
    ('tapping_maxrpm',   200,   'number'),
    # Feed rates and depth of cut (Andy Pugh originals)
    ('turning_feed',     0.15,  'double'),
    ('turning_doc',      1.0,   'double'),
    ('boring_feed',      0.15,  'double'),
    ('boring_doc',       1.0,   'double'),
    ('facing_feed',      0.15,  'double'),
    ('facing_doc',       1.0,   'double'),
    ('chamfer_feed',     0.15,  'double'),
    ('chamfer_doc',      1.0,   'double'),
    ('radius_feed',      0.15,  'double'),
    ('radius_doc',       1.0,   'double'),
    ('threading_feed',   1.0,   'double'),
    ('threading_doc',    0.1,   'double'),
    ('drill_feed',       0.05,  'double'),
    ('drill_peck',       2.0,   'double'),
    ('drill_doc',        1.0,   'double'),
    ('tapping_pitch',    1.0,   'double'),
    ('tapping_rampdistance', 5.0, 'double'),
]

for name, val, xtype in defaults:
    for widget in root.iter('widget'):
        if widget.get('name') != name:
            continue
        existing = next((p for p in widget.findall('property')
                         if p.get('name') == 'value'), None)
        text = str(int(val)) if xtype == 'number' else '{:.15f}'.format(val)
        if existing is not None:
            existing[0].text = text
        else:
            prop = ET.SubElement(widget, 'property')
            prop.set('name', 'value')
            ET.SubElement(prop, xtype).text = text
        print('{} = {}'.format(name, val))

tree.write(f, encoding='unicode', xml_declaration=False)
print('Done.')
PYEOF
```

---

## Step 4 — fix spinbox step sizes

Tool number and depth-of-cut spinboxes have wrong step sizes (10 for
tool numbers, bad values for doc). Fix with:

```bash
sudo python3 << 'PYEOF'
import xml.etree.ElementTree as ET

f = '/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.ui'
tree = ET.parse(f)
root = tree.getroot()

# Step size: (widget_name, step, xml_type)
steps = [
    # Tool numbers and coolant -- step of 1
    ('turning_tool',    1,    'number'),
    ('boring_tool',     1,    'number'),
    ('facing_tool',     1,    'number'),
    ('chamfer_tool',    1,    'number'),
    ('radius_tool',     1,    'number'),
    ('threading_tool',  1,    'number'),
    ('drill_tool',      1,    'number'),
    ('tapping_tool',    1,    'number'),
    ('turning_coolant', 1,    'number'),
    ('boring_coolant',  1,    'number'),
    ('facing_coolant',  1,    'number'),
    ('chamfer_coolant', 1,    'number'),
    ('radius_coolant',  1,    'number'),
    ('threading_coolant',1,   'number'),
    ('drill_coolant',   1,    'number'),
    ('tapping_coolant', 1,    'number'),
    # Depth of cut and feed -- fine steps
    ('turning_doc',     0.05, 'double'),
    ('turning_feed',    0.01, 'double'),
    ('boring_doc',      0.05, 'double'),
    ('boring_feed',     0.01, 'double'),
    ('facing_doc',      0.05, 'double'),
    ('facing_feed',     0.01, 'double'),
    ('chamfer_doc',     0.05, 'double'),
    ('chamfer_feed',    0.01, 'double'),
    ('radius_doc',      0.05, 'double'),
    ('radius_feed',     0.01, 'double'),
    ('threading_doc',   0.05, 'double'),
    ('threading_feed',  0.01, 'double'),
    ('drill_doc',       0.05, 'double'),
    ('drill_feed',      0.01, 'double'),
    ('drill_peck',      0.05, 'double'),
    ('tapping_pitch',   0.01, 'double'),
    ('tapping_rampdistance', 0.1, 'double'),
]

for name, step, xtype in steps:
    for widget in root.iter('widget'):
        if widget.get('name') != name:
            continue
        existing = next((p for p in widget.findall('property')
                         if p.get('name') == 'singleStep'), None)
        text = str(int(step)) if xtype == 'number' else '{:.15f}'.format(step)
        if existing is not None:
            existing[0].text = text
        else:
            prop = ET.SubElement(widget, 'property')
            prop.set('name', 'singleStep')
            ET.SubElement(prop, xtype).text = text
        print('{} step = {}'.format(name, step))

tree.write(f, encoding='unicode', xml_declaration=False)
print('Done.')
PYEOF
```

---

## Step 5 — clear PBL widget state cache

PBL caches widget values in a pickle file which overrides system defaults.
Delete it so the new defaults take effect on next start:

```bash
rm -f ~/linuxcnc/configs/<your-config>/.vcp_persistent_data.pickle
```

---

## Step 6 — optional: remove the update notification banner

PBL shows a "5/30/2025 ACTION REQUIRED" banner. The required `stdglue.py`
change is already included in current installs. To remove the banner:

```bash
sudo python3 -c "
import re
f = '/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe_ui.py'
txt = open(f).read()
txt = re.sub(r'self\.label_5\.setText\(_translate\(\"Form\", \"<html>.*?</html>\"\)\)',
             'self.label_5.setText(_translate(\"Form\", \"\"))', txt)
open(f, 'w').write(txt)
print('done')
"
```

---

## Usage notes

### Z coordinates are absolute
The Z field in all macros takes an **absolute Z coordinate**, not a length.
If your workpiece face is at Z=0 and you want to turn 50mm, enter **Z = -50**.

### Threading surface speed field
The `threading_ss` field controls spindle **RPM** (not surface speed) because
G76 threading requires constant RPM. Enter the desired RPM directly —
typically 200–400 RPM for metric threads.

### Tapping
Uses G33 (spindle-encoder-synchronized motion) with M4 reversal. Requires:
- Spindle encoder connected in HAL
- A tension-compression (floating) tap holder for best results, as the
  spindle and Z axis do not start/stop simultaneously

### Workflow after aborting a macro
If you press STOP to abort a running macro:
`POWER off → POWER on → MAN mode → continue`

### Units
All subroutines hardcode G21 (metric). The units spinbox (20/21) is present
in the UI but has no effect on machine behaviour — it is cosmetic only.

---

## Important: changes will be lost on PBL package update

The system file changes (Steps 3, 4, 6) modify files in
`/usr/lib/python3/dist-packages/probe_basic_lathe/`. These will be
overwritten if `probe_basic_lathe` is updated via `apt`. Re-run the
sudo scripts after any PBL update.

The subroutine files (Step 1) live in your config directory and are
not affected by package updates.
