#!/usr/bin/env python3
import math
import tkinter as tk
import numpy as np

# ── LUT math (from genlut.py) ──
BUS_MIN, BUS_MAX = 0.0, 16.0
PWM_MAX = 255
CENTER, SIGMA = 12.0, 1.4
BASE_GAIN, PEAK_GAIN = 0.25, 1.60

resolution = 10000
voltage = np.linspace(BUS_MIN, BUS_MAX, resolution)
gain = BASE_GAIN + PEAK_GAIN * np.exp(-0.5 * ((voltage - CENTER) / SIGMA) ** 2)
position = np.cumsum(gain)
position -= position[0]
position /= position[-1]


def volt_to_position(v):
    return float(np.interp(v, voltage, position))


# ── Geometry (shallow arc like an 85C1 panel meter) ──
ARC_START = 145
ARC_END = 35
ARC_SPAN = ARC_START - ARC_END

W, H = 500, 340
CX, CY = W // 2, 320
RADIUS = 300
NEEDLE_LEN = RADIUS - 30


def pos_to_angle(pos):
    return math.radians(ARC_START - pos * ARC_SPAN)


def endpoint(angle, r, cx=CX, cy=CY):
    return cx + r * math.cos(angle), cy - r * math.sin(angle)


# ── App ──
root = tk.Tk()
root.title("Meter Simulator")
root.resizable(False, False)

canvas = tk.Canvas(root, width=W, height=H, bg="#fcfcfb", highlightthickness=0)
canvas.pack()

# Colored range bands (drawn first so ticks sit on top)
BAND_R = RADIUS + 8
BAND_W = 10
ranges = [
    (0.0,  5.0,  '#555555'),  # gray   — device off
    (5.0,  10.5, '#7a2020'),  # maroon — brownout zone (corruption / disk damage)
    (10.5, 11.4, '#e8a020'),  # amber  — brownout risk
    (11.4, 12.6, '#2e9e3e'),  # green  — Synology safe range (±5%)
    (12.6, 13.2, '#e8a020'),  # amber  — overvoltage warning
    (13.2, 16.0, '#cc3333'),  # red    — overvoltage damage
]
for v_lo, v_hi, color in ranges:
    pts = []
    p0 = volt_to_position(v_lo)
    p1 = volt_to_position(v_hi)
    steps = max(int(abs(p1 - p0) * 500), 20)
    for i in range(steps + 1):
        p = p0 + (p1 - p0) * i / steps
        a = pos_to_angle(p)
        pts.extend(endpoint(a, BAND_R))
    canvas.create_line(pts, fill=color, width=BAND_W, smooth=True)

# Draw arc
pts = []
for i in range(501):
    a = math.radians(ARC_END + i * (ARC_START - ARC_END) / 500)
    pts.extend(endpoint(a, RADIUS))
canvas.create_line(pts, fill="#0b0b0b", width=2, smooth=True)

# Ticks and labels
for v in np.arange(0, 16.25, 0.25):
    pos = volt_to_position(v)
    a = pos_to_angle(pos)
    is_major = v == int(v)
    is_half = (v * 2) == int(v * 2) and not is_major

    if is_major:
        tick_len, width = 18, 2
    elif is_half:
        tick_len, width = 11, 1
    else:
        tick_len, width = 6, 1

    x0, y0 = endpoint(a, RADIUS)
    x1, y1 = endpoint(a, RADIUS - tick_len)
    canvas.create_line(x0, y0, x1, y1, fill="#0b0b0b" if is_major else "#52514e", width=width)

    if is_major:
        lx, ly = endpoint(a, RADIUS - 30)
        canvas.create_text(lx, ly, text=str(int(v)), font=("sans-serif", 10), fill="#0b0b0b")

canvas.create_text(CX, 160, text="Vdc", font=("sans-serif", 11), fill="#52514e")

# Needle pivot dot
canvas.create_oval(CX - 5, CY - 5, CX + 5, CY + 5, fill="#0b0b0b", outline="#0b0b0b")

needle = canvas.create_line(CX, CY, *endpoint(pos_to_angle(0), NEEDLE_LEN), fill="#cc2222", width=2)

readout = tk.Label(root, text="0.00 V  |  PWM 0  |  0.0%", font=("monospace", 12), bg="#fcfcfb", fg="#0b0b0b")
readout.pack(pady=(0, 4))

def on_slider(val):
    v = float(val)
    pos = volt_to_position(v)
    a = pos_to_angle(pos)
    nx, ny = endpoint(a, NEEDLE_LEN)
    canvas.coords(needle, CX, CY, nx, ny)
    pwm = round(pos * PWM_MAX)
    duty = pwm / PWM_MAX * 100
    readout.config(text=f"{v:5.2f} V  |  PWM {pwm:3d}  |  {duty:5.1f}%")

slider = tk.Scale(root, from_=0, to=16, resolution=0.01, orient=tk.HORIZONTAL,
                  length=W - 40, command=on_slider, label="Input Voltage (V)",
                  bg="#fcfcfb", highlightthickness=0, troughcolor="#d0d0d0")
slider.pack(padx=20, pady=(0, 10))

on_slider(0)
root.mainloop()
