#!/usr/bin/env python3
"""Regenerate groove_rendered.png from LatheMacro.svg (gmoccapy V3)."""
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import cairo, xml.etree.ElementTree as ET, io, math, os

SVG_PATH = os.path.join(os.path.dirname(__file__),
    '..', '..', '..', 'gmoccapy_lathe', 'lathe_macros_V3', 'LatheMacro.svg')
OUT_PATH = os.path.join(os.path.dirname(__file__), 'groove_rendered.png')
W, H = 600, 400

# ---------------------------------------------------------------------------
# Groove Z dimension paths (injected into layer6 at render time)
# Groove-wall leader : x=820 SVG,  top y=46.1,  bottom y=282.5
# End-face leader    : x=992.5 SVG, top y=150,   bottom y=375
# Span at -150° (Z-axis direction) connecting them
# ---------------------------------------------------------------------------
GX, EX = 820.0, 992.5
SPAN_EY = 150.0
SPAN_GY = SPAN_EY + (GX - EX) * (0.500 / 0.866)   # = 46.1

SPAN_S = ('fill:none;stroke:#000000;stroke-width:3;stroke-linecap:butt;'
          'stroke-linejoin:miter;stroke-opacity:1;'
          'marker-start:url(#marker15083);marker-end:url(#marker14839)')
LINE_S  = ('fill:none;stroke:#000000;stroke-width:3;stroke-linecap:butt;'
           'stroke-linejoin:miter;stroke-opacity:1')

GZ_PATHS = [
    f'<path style="{LINE_S}" d="M {GX},{SPAN_GY:.1f} {GX},282.5" id="gz_tick_groove"/>',
    f'<path style="{LINE_S}" d="M {EX},{SPAN_EY} {EX},375"       id="gz_tick_face"/>',
    f'<path style="{SPAN_S}" d="M {EX},{SPAN_EY} {GX},{SPAN_GY:.1f}" id="gz_span"/>',
]

tree = ET.parse(SVG_PATH)
root = tree.getroot()
ns_ink = 'http://www.inkscape.org/namespaces/inkscape'

for elem in root.iter():
    mode = elem.get(f'{{{ns_ink}}}groupmode', '')
    if mode == 'layer':
        elem.set('style', 'display:inline' if elem.get('id') == 'layer6' else 'display:none')

for elem in root.iter():
    if elem.get('id') == 'layer6':
        for p in GZ_PATHS:
            elem.append(ET.fromstring(p))
        break

buf = io.BytesIO()
tree.write(buf)
handle = Rsvg.Handle.new_from_data(buf.getvalue())
dim = handle.get_dimensions()

surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
ctx = cairo.Context(surface)
ctx.set_source_rgb(0.57, 0.57, 0.59)
ctx.paint()
ctx.scale(W / dim.width, H / dim.height)
handle.render_cairo(ctx)
surface.write_to_png(OUT_PATH)
print(f"Saved {OUT_PATH}")
