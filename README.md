# Probe Basic Lathe — Bantam Lathe Config

LinuxCNC 2.9 configuration for a Bantam lathe running
[Probe Basic Lathe](https://github.com/kcjengr/probe_basic).

**Hardware:** Mesa 5i25 / 7i76, closed-loop stepgen with encoder feedback,
XHC WHB04B-6 wireless pendant, VFD spindle.

---

## Repository contents

| Path | Description |
|------|-------------|
| `probe_basic_lathe.ini` | Main config — machine units, limits, PID, homing |
| `hallib/Bantam_v1.hal` | Hardware HAL (Mesa stepgen, spindle, I/O, estop) |
| `hallib/xhc-whb04b-6.hal` | Wireless pendant HAL |
| `hallib/probe_basic_lathe_postgui.hal` | PBL postgui connections |
| `hallib/shutdown.hal` | Shutdown script (empty) |
| `subroutines/` | Conversational macro subroutines (see below) |
| `python/` | Remap scripts for tool change |
| `archive/` | Superseded simulation files and change logs |

---

## For other Probe Basic Lathe users — conversational macro fixes

The PBL lathe conversational macros (Turning, Boring, Facing, etc.) have
several bugs and missing files in the default installation. The fixed
subroutines in this repo can be dropped into any PBL lathe config.

### What is fixed

| File | Problem | Fix |
|------|---------|-----|
| `subroutines/turning.ngc` | **Missing** from PBL install | Created from Andy Pugh gmoccapy originals |
| `subroutines/boring.ngc` | **Missing** from PBL install | Created from Andy Pugh gmoccapy originals |
| `subroutines/chamfer.ngc` | Three missing `#` caused parse errors on rear chamfer | Fixed |
| `subroutines/radius.ngc` | Wrong `o`-word numbers in elseif/endif; undefined variable | Fixed |
| `subroutines/threading.ngc` | `threading_feed` used as spindle speed (should be `threading_ss`); changed to G97 constant-RPM | Fixed |
| All subroutines | Zero depth-of-cut causes infinite while loop, locking machine in MDI | Guard added |
| All subroutines | Hardcoded G21 (metric) | Correct for metric machines |

### Step 1 — copy the subroutine files

Copy the fixed `.ngc` files from `subroutines/` into your PBL config's
`subroutines/` folder, replacing the originals:

```
turning.ngc    boring.ngc     facing.ngc     chamfer.ngc
radius.ngc     threading.ngc  drill.ngc      tapping.ngc
```

> **Note on threading:** the `threading_ss` field is used as spindle **RPM**
> (not surface speed) because G76 threading requires constant RPM. Enter
> the desired RPM there (e.g. 200–400 for metric threads).

### Step 2 — fix the conversational macro defaults in PBL

The default values in PBL's conversational tabs are wrong out of the box
(feed rates of 5 mm/rev, surface speed of 1 m/min, etc.). PBL loads its
UI directly from the XML `.ui` file so the fix must go there.

Run this **once** in a terminal (requires sudo). Values are based on
Andy Pugh's original gmoccapy lathe macro defaults:

```bash
sudo python3 << 'PYEOF'
import xml.etree.ElementTree as ET

f = '/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.ui'
tree = ET.parse(f)
root = tree.getroot()

# (widget_name, value, xml_type)
# xml_type is 'number' for QSpinBox, 'double' for VCPSettingsDoubleSpinBox
defaults = [
    # Units fields — default to G21 (metric)
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
    ('threading_ss',     50,    'number'),
    ('threading_maxrpm', 200,   'number'),
    ('drill_ss',         100,   'number'),
    ('drill_maxrpm',     2000,  'number'),
    ('tapping_ss',       30,    'number'),
    ('tapping_maxrpm',   200,   'number'),
    # Feed rates and depth of cut
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
            print('Updated', name, '->', val)
        else:
            prop = ET.SubElement(widget, 'property')
            prop.set('name', 'value')
            ET.SubElement(prop, xtype).text = text
            print('Added  ', name, '->', val)

tree.write(f, encoding='unicode', xml_declaration=False)
print('Done.')
PYEOF
```

Then delete PBL's widget state cache and restart:

```bash
rm -f ~/linuxcnc/configs/<your-config-dir>/.vcp_persistent_data.pickle
```

> **Warning:** these changes will be overwritten if the `probe_basic_lathe`
> package is updated via `apt`. Re-run the script after any PBL update.

### Step 3 — clear the notification banner

PBL shows a "5/30/2025 ACTION REQUIRED" banner on the main screen. The
required `stdglue.py` change is already included in current installs.
To remove the banner:

```bash
sudo python3 -c "
f = '/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe_ui.py'
import re
txt = open(f).read()
txt = re.sub(r'self\.label_5\.setText\(_translate\(\"Form\", \"<html>.*?</html>\"\)\)',
             'self.label_5.setText(_translate(\"Form\", \"\"))', txt)
open(f, 'w').write(txt)
print('done')
"
```

---

## Machine-specific configuration

The HAL files and INI settings in this repo are specific to this machine.
They are provided as a reference, not a drop-in replacement. Key values
to adapt for your own machine:

**`probe_basic_lathe.ini`**
- `[JOINT_0/1]` — INPUT_SCALE, STEP_SCALE, PID values, limits, home offsets
- `[SPINDLE_0]` — ENCODER_SCALE, OUTPUT_SCALE, OUTPUT_MAX_LIMIT
- `[AXIS_X/Z]` — MIN_LIMIT, MAX_LIMIT, MAX_VELOCITY

**`hallib/Bantam_v1.hal`**
- Mesa card config string (`num_encoders`, `num_stepgens`, `sserial_port_0`)
- Limit/home switch input pin numbers
- Spindle at-speed and fault input pin numbers

**`hallib/xhc-whb04b-6.hal`**
- Works as-is for XHC WHB04B-6 pendant on a 2-axis XZ lathe

---

## Workflow notes

- **Homing:** home once per session before using conversational macros
- **After aborting a macro:** POWER off → POWER on → MAN → continue
- **Units:** all subroutines hardcode G21 (metric); inch machines would
  need the `o106` conditional block reinstated
- **Threading ss field:** enter RPM, not surface speed
