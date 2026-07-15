#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

BUS_MIN, BUS_MAX = 0.0, 16.0
ADC_MAX, PWM_MAX = 1023, 255
CENTER, SIGMA = 12.0, 1.4
BASE_GAIN, PEAK_GAIN = 0.25, 1.60

def sensitivity(v):
    return BASE_GAIN + PEAK_GAIN * np.exp(-0.5 * ((v - CENTER) / SIGMA) ** 2)

resolution = 10000
voltage = np.linspace(BUS_MIN, BUS_MAX, resolution)
gain = sensitivity(voltage)
position = np.cumsum(gain)
position -= position[0]
position /= position[-1]

def volt_to_position(v):
    return np.interp(v, voltage, position)

arc_start_deg = 145
arc_end_deg = 35
arc_span = arc_start_deg - arc_end_deg

radius = 1.0
cx, cy = 0.0, 0.0

def pos_to_angle_rad(pos):
    deg = arc_start_deg - pos * arc_span
    return np.radians(deg)

fig, ax = plt.subplots(figsize=(10, 5), facecolor='#fcfcfb')
ax.set_facecolor('#fcfcfb')
ax.set_aspect('equal')

# Colored range bands (drawn first so ticks sit on top)
BAND_WIDTH = 8
r_band = radius + 0.04
ranges = [
    (0.0,  5.0,  '#555555'),  # gray   — device off (too low to start)
    (5.0,  10.5, '#7a2020'),  # maroon — brownout zone (corruption / disk damage)
    (10.5, 11.4, '#e8a020'),  # amber  — brownout risk
    (11.4, 12.6, '#2e9e3e'),  # green  — Synology safe range (±5%)
    (12.6, 13.2, '#e8a020'),  # amber  — overvoltage warning (errors observed)
    (13.2, 16.0, '#cc3333'),  # red    — overvoltage damage
]
for v_lo, v_hi, color in ranges:
    p0 = volt_to_position(v_lo)
    p1 = volt_to_position(v_hi)
    th = np.linspace(pos_to_angle_rad(p0), pos_to_angle_rad(p1), 300)
    ax.plot(cx + r_band * np.cos(th), cy + r_band * np.sin(th),
            color=color, linewidth=BAND_WIDTH, solid_capstyle='butt')

# Main arc
theta = np.linspace(np.radians(arc_end_deg), np.radians(arc_start_deg), 500)
ax.plot(cx + radius * np.cos(theta), cy + radius * np.sin(theta),
        color='#0b0b0b', linewidth=1.5)

# Minor ticks (0.25 V)
major_volts = np.arange(0, 17, 1)
minor_volts = np.arange(0, 16.25, 0.25)

for v in minor_volts:
    if v in major_volts or v % 0.5 == 0:
        continue
    pos = volt_to_position(v)
    ang = pos_to_angle_rad(pos)
    r_inner = radius - 0.04
    ax.plot([cx + r_inner * np.cos(ang), cx + radius * np.cos(ang)],
            [cy + r_inner * np.sin(ang), cy + radius * np.sin(ang)],
            color='#52514e', linewidth=0.6)

# Half-volt ticks
half_volts = np.arange(0.5, 16, 1)
for v in half_volts:
    pos = volt_to_position(v)
    ang = pos_to_angle_rad(pos)
    r_inner = radius - 0.07
    ax.plot([cx + r_inner * np.cos(ang), cx + radius * np.cos(ang)],
            [cy + r_inner * np.sin(ang), cy + radius * np.sin(ang)],
            color='#52514e', linewidth=0.8)

# Major ticks + labels
for v in major_volts:
    pos = volt_to_position(v)
    ang = pos_to_angle_rad(pos)
    r_inner = radius - 0.12
    ax.plot([cx + r_inner * np.cos(ang), cx + radius * np.cos(ang)],
            [cy + r_inner * np.sin(ang), cy + radius * np.sin(ang)],
            color='#0b0b0b', linewidth=1.4)

    r_label = radius - 0.20
    ax.text(cx + r_label * np.cos(ang), cy + r_label * np.sin(ang),
            f'{int(v)}', ha='center', va='center', fontsize=9,
            fontfamily='sans-serif', color='#0b0b0b')

ax.text(cx, 0.50, 'Vdc', ha='center', va='center', fontsize=11,
        fontfamily='sans-serif', color='#52514e')

fig.suptitle('Non-linear Meter Scale (expanded around 12 V)',
             fontsize=13, fontfamily='sans-serif', color='#0b0b0b',
             fontweight='bold', y=0.98)

ax.set_xlim(-1.15, 1.15)
ax.set_ylim(0.30, 1.18)
ax.axis('off')
fig.tight_layout(rect=[0, 0, 1, 0.93])
out_path = Path(__file__).parent / 'concept_scale.png'
fig.savefig(out_path, dpi=180,
            bbox_inches='tight', facecolor='#fcfcfb')
print(f'Saved {out_path}')
