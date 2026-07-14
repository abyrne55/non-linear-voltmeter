#!/usr/bin/env python3
"""Generate a 1:1 physical-scale SVG of the non-linear voltmeter face
for Cricut "Print Then Cut" on the Baomain 85C1 (0-5 V) panel meter."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Wedge, Rectangle, Circle
from matplotlib.collections import PatchCollection
import matplotlib.patheffects as pe

# ── Physical dimensions (mm) ─────────────────────────────────────────
PLATE_W       = 60.0
PLATE_H       = 35.5
PIVOT_X       = PLATE_W / 2        # 30.0
PIVOT_Y       = 39.0               # below plate top (3.5 mm below bottom edge)
ARC_RADIUS    = 31.0
DEFLECTION    = 90.0               # degrees of needle sweep

MOUNT_HOLE_DIA   = 2.0
MOUNT_HOLE_INSET = 3.0             # from bottom-left / bottom-right corner
NOTCH_W          = 14.0
NOTCH_H          = 6.0

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
LABEL_OFFSET   = ARC_RADIUS * 0.20

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
ax.add_patch(Rectangle((0, 0), PLATE_W, PLATE_H,
                        facecolor='white', edgecolor='none', zorder=0))

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
                fontsize=5, fontfamily='sans-serif', color='#0b0b0b', zorder=4)

# ── "Vdc" label ─────────────────────────────────────────────────────
vdc_y = cy + ARC_RADIUS * 0.42
ax.text(PIVOT_X, vdc_y, 'Vdc', ha='center', va='center',
        fontsize=5.5, fontfamily='sans-serif', color='#52514e', zorder=4)

# ── Cut outline (magenta) ───────────────────────────────────────────
CUT_COLOR = '#ff00ff'
CUT_LW = mm_to_pts(0.25)

notch_left  = (PLATE_W - NOTCH_W) / 2
notch_right = notch_left + NOTCH_W

outline_x = [0, 0, notch_left, notch_left, notch_right, notch_right, PLATE_W, PLATE_W, 0]
outline_y = [PLATE_H, 0, 0, NOTCH_H, NOTCH_H, 0, 0, PLATE_H, PLATE_H]
ax.plot(outline_x, outline_y, color=CUT_COLOR, linewidth=CUT_LW,
        solid_joinstyle='miter', zorder=10)

hole_y = MOUNT_HOLE_INSET
hole_r = MOUNT_HOLE_DIA / 2
for hx in [MOUNT_HOLE_INSET, PLATE_W - MOUNT_HOLE_INSET]:
    circle = plt.Circle((hx, hole_y), hole_r,
                         fill=False, edgecolor=CUT_COLOR,
                         linewidth=CUT_LW, zorder=10)
    ax.add_patch(circle)

# ── Save ─────────────────────────────────────────────────────────────
svg_path = '/home/abyrne/tmp/meter/meter_scale_cricut.svg'
png_path = '/home/abyrne/tmp/meter/meter_scale_cricut.png'

fig.savefig(svg_path, format='svg', transparent=False)
fig.savefig(png_path, format='png', dpi=300, transparent=False)
print(f'Saved {svg_path}')
print(f'Saved {png_path}')
