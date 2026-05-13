# Bantam Lathe — New Machine Setup Guide

This repo contains the complete LinuxCNC configuration for the Bantam lathe
with Mesa 5i25/7i76. Follow these steps when installing on a new machine.

## Hardware
- Mesa 5i25 PCIe card + 7i76 breakout board
- Spindle encoder on 5i25 encoder input

## 1. Install LinuxCNC + Probe Basic

```bash
# Add LinuxCNC repo and install
wget -O - https://www.linuxcnc.org/tmp/GPG-KEY-linuxcnc | sudo apt-key add -
# Follow linuxcnc.org instructions for Debian Bookworm

# Install Probe Basic Lathe
sudo apt install python3-probe-basic
```

## 2. Clone this repo

```bash
cd ~/linuxcnc/configs
git clone https://github.com/Muzzerboy/linuxcnc-bantam-lathe.git pb_lathe_murray
```

## 3. Kernel boot parameters

Add to `GRUB_CMDLINE_LINUX_DEFAULT` in `/etc/default/grub`:

```
idle=poll processor.max_cstate=1 intel_idle.max_cstate=0 nmi_watchdog=0 isolcpus=3 usbcore.autosuspend=-1
```

Note: `i915.enable_rc6=0` and `i915.enable_dc=0` were needed for the Bay Trail
Q1900B-ITX board only — not required on Coffee Lake or newer.

```bash
sudo update-grub
```

## 4. Fix VTK backplot initial zoom (QtPyVCP bug)

The VTK backplot defaults to a scale of 1.0 (±1mm visible) for lathe XZ view.
Fix by adding `ResetCamera()` and proper scale after `setViewXZ()`:

```bash
# Check current line number (may change with package updates)
grep -n "def setViewXZ\b" /usr/lib/python3/dist-packages/qtpyvcp/widgets/display_widgets/vtk_backplot/vtk_backplot.py

# The fix goes at the line AFTER __doCommonSetViewWork() inside setViewXZ
# Replace the single ResetCamera() line (or add after __doCommonSetViewWork):
sudo sed -i 's/        self.renderer.ResetCamera()$/        bounds = self.machine_actor.GetBounds()\n        x_range = abs(bounds[1] - bounds[0])\n        z_range = abs(bounds[5] - bounds[4])\n        self.camera.SetParallelScale(max(x_range, z_range) \/ 6.0)/' \
    /usr/lib/python3/dist-packages/qtpyvcp/widgets/display_widgets/vtk_backplot/vtk_backplot.py
```

**Note:** This file is overwritten by package updates. Re-apply after any
`python3-qtpyvcp` upgrade.

## 5. VTK FPS setting

Already set in `probe_basic_lathe.ini` as `FPS = 10`. No extra steps needed.

## 6. Display configuration (Bay Trail only — skip on Coffee Lake+)

The following were needed for the old Q1900B-ITX board only:

```bash
# Disable XFCE compositor
xfconf-query -c xfwm4 -p /general/use_compositing -s false

# Software cursor + no GPU acceleration
sudo tee /etc/X11/xorg.conf.d/20-intel.conf << 'EOF'
Section "Device"
    Identifier "Intel Graphics"
    Driver "modesetting"
    Option "SWcursor" "true"
    Option "AccelMethod" "none"
EndSection
EOF
```

## 7. Dual monitor layout

If running two monitors with the right screen as primary:

```bash
xrandr --output HDMI-1 --pos 0x0 --output VGA-1 --pos 1920x0 --primary
```

Persist via XFCE Settings > Display.

## 8. Launch LinuxCNC

```
linuxcnc ~/linuxcnc/configs/pb_lathe_murray/probe_basic_lathe.ini
```
