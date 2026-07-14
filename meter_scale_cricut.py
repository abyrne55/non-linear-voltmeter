#!/usr/bin/env python3
"""Generate a 1:1 physical-scale SVG of the non-linear voltmeter face
for Cricut "Print Then Cut" on the Baomain 85C1 (0-5 V) panel meter."""

import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import Arc, Wedge, Rectangle, Circle, PathPatch
from matplotlib.collections import PatchCollection
import matplotlib.patheffects as pe

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ruler', action='store_true',
                    help='Draw mm ruler ticks along the edges')
args = parser.parse_args()

# ── Physical dimensions (mm) ─────────────────────────────────────────
PLATE_W       = 60.0
PLATE_H       = 35.5
PIVOT_X       = PLATE_W / 2        # 30.0
PIVOT_Y       = 39.0               # below plate top (3.5 mm below bottom edge)
ARC_RADIUS    = 31.0
DEFLECTION    = 90.0               # degrees of needle sweep

MOUNT_HOLE_DIA   = 2.5
MOUNT_HOLE_X     = 14.0            # center distance from left/right edges
MOUNT_HOLE_Y     = 3.0             # center distance from bottom edge
NOTCH_W          = 22.0            # width of semicircular cutout
NOTCH_H          = 6.0             # height of cutout (arc peak from bottom edge)

# ── Voltage / sensitivity (same as meter_scale.py) ───────────────────
BUS_MIN, BUS_MAX = 0.0, 16.0
CENTER, SIGMA    = 12.0, 1.4
BASE_GAIN        = 0.25
PEAK_GAIN        = 1.60

def sensitivity(v):
    return BASE_GAIN + PEAK_GAIN * np.exp(-0.5 * ((v - CENTER) / SIGMA) ** 2)

resolution = 10000
voltage    = np.linspace(BUS_MIN, BUS_MAX, resolution)
gain       = sensitivity(voltage)
position   = np.cumsum(gain)
position  -= position[0]
position  /= position[-1]

def volt_to_position(v):
    return np.interp(v, voltage, position)

arc_start_deg = 90 + DEFLECTION / 2   # 135
arc_end_deg   = 90 - DEFLECTION / 2   # 45

def pos_to_angle_rad(pos):
    deg = arc_start_deg - pos * DEFLECTION
    return np.radians(deg)

# ── Color bands ──────────────────────────────────────────────────────
RANGES = [
    (0.0,  5.0,  '#555555'),
    (5.0,  10.5, '#7a2020'),
    (10.5, 11.4, '#e8a020'),
    (11.4, 12.6, '#2e9e3e'),
    (12.6, 13.2, '#e8a020'),
    (13.2, 16.0, '#cc3333'),
]

# ── Tick geometry ────────────────────────────────────────────────────
MAJOR_TICK_LEN = ARC_RADIUS * 0.12
HALF_TICK_LEN  = ARC_RADIUS * 0.07
MINOR_TICK_LEN = ARC_RADIUS * 0.04
LABEL_OFFSET   = ARC_RADIUS * 0.18

BAND_INNER = ARC_RADIUS
BAND_OUTER = ARC_RADIUS + MAJOR_TICK_LEN + 0.1275

# ── Matplotlib setup ────────────────────────────────────────────────
MM_PER_INCH = 25.4
plt.rcParams['svg.fonttype'] = 'path'

fig = plt.figure(
    figsize=(PLATE_W / MM_PER_INCH, PLATE_H / MM_PER_INCH),
    dpi=96,
    facecolor='white',
)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, PLATE_W)
ax.set_ylim(0, PLATE_H)
ax.set_aspect('equal')
ax.axis('off')

cy = PLATE_H - PIVOT_Y  # pivot in axes coords (y=0 is bottom)

# ── White background ────────────────────────────────────────────────
bg_rect = Rectangle((0, 0), PLATE_W, PLATE_H,
                     facecolor='white', edgecolor='none', zorder=0)
ax.add_patch(bg_rect)

# ── Helper: mm linewidth ────────────────────────────────────────────
def mm_to_pts(mm):
    return mm * (72.0 / MM_PER_INCH)

# ── Color band fills (tach-style: fills the tick region) ────────────
for v_lo, v_hi, color in RANGES:
    p0 = volt_to_position(v_lo)
    p1 = volt_to_position(v_hi)
    th = np.linspace(pos_to_angle_rad(p0), pos_to_angle_rad(p1), 300)
    # Build closed annular wedge: outer arc forward, inner arc back
    xs = np.concatenate([PIVOT_X + BAND_OUTER * np.cos(th),
                         PIVOT_X + BAND_INNER * np.cos(th[::-1])])
    ys = np.concatenate([cy + BAND_OUTER * np.sin(th),
                         cy + BAND_INNER * np.sin(th[::-1])])
    ax.fill(xs, ys, facecolor=color, edgecolor='none', zorder=1)

# ── Main arc ────────────────────────────────────────────────────────
theta = np.linspace(np.radians(arc_end_deg), np.radians(arc_start_deg), 500)
ax.plot(PIVOT_X + ARC_RADIUS * np.cos(theta), cy + ARC_RADIUS * np.sin(theta),
        color='#0b0b0b', linewidth=mm_to_pts(0.35), zorder=2)

# ── Ticks and labels ────────────────────────────────────────────────
major_volts = np.arange(0, 17, 1)
minor_volts = np.arange(0, 16.25, 0.25)

for v in minor_volts:
    if v in major_volts or v % 0.5 == 0:
        continue
    pos = volt_to_position(v)
    ang = pos_to_angle_rad(pos)
    r_outer = ARC_RADIUS + MINOR_TICK_LEN
    ax.plot([PIVOT_X + ARC_RADIUS * np.cos(ang), PIVOT_X + r_outer * np.cos(ang)],
            [cy + ARC_RADIUS * np.sin(ang), cy + r_outer * np.sin(ang)],
            color='#0b0b0b', linewidth=mm_to_pts(0.15), zorder=3)

half_volts = np.arange(0.5, 16, 1)
for v in half_volts:
    pos = volt_to_position(v)
    ang = pos_to_angle_rad(pos)
    r_outer = ARC_RADIUS + HALF_TICK_LEN
    ax.plot([PIVOT_X + ARC_RADIUS * np.cos(ang), PIVOT_X + r_outer * np.cos(ang)],
            [cy + ARC_RADIUS * np.sin(ang), cy + r_outer * np.sin(ang)],
            color='#0b0b0b', linewidth=mm_to_pts(0.20), zorder=3)

LABELED_VOLTS = {0, 5, 10, 11, 12, 13, 14, 16}

for v in major_volts:
    pos = volt_to_position(v)
    ang = pos_to_angle_rad(pos)
    r_outer = ARC_RADIUS + MAJOR_TICK_LEN
    ax.plot([PIVOT_X + ARC_RADIUS * np.cos(ang), PIVOT_X + r_outer * np.cos(ang)],
            [cy + ARC_RADIUS * np.sin(ang), cy + r_outer * np.sin(ang)],
            color='#0b0b0b', linewidth=mm_to_pts(0.25), zorder=3)

    if v in LABELED_VOLTS:
        r_label = ARC_RADIUS + LABEL_OFFSET
        ax.text(PIVOT_X + r_label * np.cos(ang), cy + r_label * np.sin(ang),
                f'{int(v)}', ha='center', va='center',
                fontsize=6.5, fontfamily='Montserrat', color='#0b0b0b', zorder=4)

# ── "Vdc" label ─────────────────────────────────────────────────────
ax.text(PLATE_W / 2, PLATE_H / 2 + 1.5, 'V', ha='center', va='center',
        fontsize=16, fontweight='bold', fontfamily='Montserrat',
        color='#0b0b0b', zorder=4)

# DC symbol: solid line over dashed line, centered below V
dc_cx = PLATE_W / 2
dc_y = PLATE_H / 2 - 3.5
dc_w = 5.0
dc_lw = mm_to_pts(0.4)
ax.plot([dc_cx - dc_w/2, dc_cx + dc_w/2], [dc_y + 0.8, dc_y + 0.8],
        color='#0b0b0b', linewidth=dc_lw, solid_capstyle='butt', zorder=4)
dash_len = 0.8
gap_len = 0.6
x = dc_cx - dc_w / 2
while x + dash_len <= dc_cx + dc_w / 2 + 0.01:
    x_end = min(x + dash_len, dc_cx + dc_w / 2)
    ax.plot([x, x_end], [dc_y, dc_y],
            color='#0b0b0b', linewidth=dc_lw, solid_capstyle='butt', zorder=4)
    x += dash_len + gap_len

# ── Cut outline (magenta) ───────────────────────────────────────────
CUT_COLOR = '#ff00ff'
CUT_LW = mm_to_pts(0.25)

notch_cx = PLATE_W / 2
notch_left = notch_cx - NOTCH_W / 2
notch_right = notch_cx + NOTCH_W / 2

# Circular arc: chord = NOTCH_W, sagitta = NOTCH_H
arc_half_chord = NOTCH_W / 2
arc_r = (arc_half_chord**2 + NOTCH_H**2) / (2 * NOTCH_H)
arc_cy = -(arc_r - NOTCH_H)
arc_angle = np.arcsin(arc_half_chord / arc_r)
arc_th = np.linspace(np.pi - arc_angle, arc_angle, 80)

outline_x = np.concatenate([
    [0, 0],
    [notch_left],
    notch_cx + arc_r * np.cos(arc_th),
    [notch_right],
    [PLATE_W, PLATE_W, 0],
])
outline_y = np.concatenate([
    [PLATE_H, 0],
    [0],
    arc_cy + arc_r * np.sin(arc_th),
    [0],
    [0, PLATE_H, PLATE_H],
])
(cut_line,) = ax.plot(outline_x, outline_y, color=CUT_COLOR, linewidth=CUT_LW,
                      solid_joinstyle='miter', zorder=10)

hole_r = MOUNT_HOLE_DIA / 2
cut_circles = []
for hx in [MOUNT_HOLE_X, PLATE_W - MOUNT_HOLE_X]:
    circle = plt.Circle((hx, MOUNT_HOLE_Y), hole_r,
                         fill=False, edgecolor=CUT_COLOR,
                         linewidth=CUT_LW, zorder=10)
    ax.add_patch(circle)
    cut_circles.append(circle)

# ── Ruler (optional) ────────────────────────────────────────────────
if args.ruler:
    RULER_COLOR = '#888888'
    GRID_COLOR = '#cccccc'
    RULER_TICK = 1.5
    RULER_LW = mm_to_pts(0.1)
    GRID_LW = mm_to_pts(0.05)
    for x in range(int(PLATE_W) + 1):
        is_10 = x % 10 == 0
        is_5 = x % 5 == 0
        tick = RULER_TICK * (2 if is_10 else 1.4 if is_5 else 1)
        grid_lw = GRID_LW * (2 if is_10 else 1.4 if is_5 else 1)
        ax.plot([x, x], [0, PLATE_H],
                color=GRID_COLOR, linewidth=grid_lw, zorder=0.5)
        ax.plot([x, x], [PLATE_H, PLATE_H - tick],
                color=RULER_COLOR, linewidth=RULER_LW, zorder=5)
        ax.plot([x, x], [0, tick],
                color=RULER_COLOR, linewidth=RULER_LW, zorder=5)
        if is_10:
            ax.text(x, PLATE_H - tick - 0.6, str(x), ha='center', va='top',
                    fontsize=3, color=RULER_COLOR, fontfamily='sans-serif', zorder=5)
            ax.text(x, tick + 0.6, str(x), ha='center', va='bottom',
                    fontsize=3, color=RULER_COLOR, fontfamily='sans-serif', zorder=5)
    for y in range(int(PLATE_H) + 1):
        is_10 = y % 10 == 0
        is_5 = y % 5 == 0
        tick = RULER_TICK * (2 if is_10 else 1.4 if is_5 else 1)
        grid_lw = GRID_LW * (2 if is_10 else 1.4 if is_5 else 1)
        ax.plot([0, PLATE_W], [y, y],
                color=GRID_COLOR, linewidth=grid_lw, zorder=0.5)
        ax.plot([0, tick], [y, y],
                color=RULER_COLOR, linewidth=RULER_LW, zorder=5)
        ax.plot([PLATE_W, PLATE_W - tick], [y, y],
                color=RULER_COLOR, linewidth=RULER_LW, zorder=5)
        if is_10:
            ax.text(tick + 0.6, y, str(y), ha='left', va='center',
                    fontsize=3, color=RULER_COLOR, fontfamily='sans-serif', zorder=5)
            ax.text(PLATE_W - tick - 0.6, y, str(y), ha='right', va='center',
                    fontsize=3, color=RULER_COLOR, fontfamily='sans-serif', zorder=5)

# ── Save ─────────────────────────────────────────────────────────────
svg_path = '/home/abyrne/tmp/meter/meter_scale_cricut.svg'
fig.savefig(svg_path, format='svg', transparent=False)
print(f'Saved {svg_path}')

# ── PNG: transparent notch & holes, no cut marks ─────────────────────
cut_line.remove()
for c in cut_circles:
    c.remove()
bg_rect.remove()

def _circle_hole(cx, cy, r, n=64):
    th = np.linspace(2 * np.pi, 0, n, endpoint=False)
    verts = [(cx + r * np.cos(t), cy + r * np.sin(t)) for t in th]
    verts.append(verts[0])
    codes = [Path.MOVETO] + [Path.LINETO] * (n - 1) + [Path.CLOSEPOLY]
    return verts, codes

plate_verts = list(zip(outline_x, outline_y))
plate_codes = ([Path.MOVETO] + [Path.LINETO] * (len(plate_verts) - 2)
               + [Path.CLOSEPOLY])
h1v, h1c = _circle_hole(MOUNT_HOLE_X, MOUNT_HOLE_Y, hole_r)
h2v, h2c = _circle_hole(PLATE_W - MOUNT_HOLE_X, MOUNT_HOLE_Y, hole_r)
compound = Path(plate_verts + h1v + h2v, plate_codes + h1c + h2c)
ax.add_patch(PathPatch(compound, facecolor='white', edgecolor='none', zorder=0))

w_mm = int(round(PLATE_W))
h_mm = int(round(PLATE_H))
png_path = f'/home/abyrne/tmp/meter/meter_scale_cricut_{w_mm}x{h_mm}mm.png'
fig.savefig(png_path, format='png', dpi=300, transparent=True)
print(f'Saved {png_path}')
