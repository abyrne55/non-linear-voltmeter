#!/usr/bin/env python3
import math
import tkinter as tk
import numpy as np

# ── Defaults ──
BUS_MIN, BUS_MAX = 0.0, 16.0
PWM_MAX = 255
DEFAULT_CENTER = 12.0
DEFAULT_SIGMA = 1.4
DEFAULT_BASE_GAIN = 0.25
DEFAULT_PEAK_GAIN = 1.60

# ── Geometry (90° arc matching physical scale) ──
ARC_START = 135
ARC_END = 45
ARC_SPAN = ARC_START - ARC_END

W, H = 500, 340
CX, CY = W // 2, 320
RADIUS = 300
NEEDLE_LEN = RADIUS - 30

RESOLUTION = 10000
voltage = np.linspace(BUS_MIN, BUS_MAX, RESOLUTION)


def compute_position(center, sigma, base_gain, peak_gain):
    gain = base_gain + peak_gain * np.exp(-0.5 * ((voltage - center) / sigma) ** 2)
    pos = np.cumsum(gain)
    pos -= pos[0]
    pos /= pos[-1]
    return pos


def volt_to_position(v, position):
    return float(np.interp(v, voltage, position))


def pos_to_angle(pos):
    return math.radians(ARC_START - pos * ARC_SPAN)


def endpoint(angle, r, cx=CX, cy=CY):
    return cx + r * math.cos(angle), cy - r * math.sin(angle)


BAND_R = RADIUS + 8
BAND_W = 10
ranges = [
    (0.0,  5.0,  '#555555'),
    (5.0,  10.5, '#7a2020'),
    (10.5, 11.4, '#e8a020'),
    (11.4, 12.6, '#2e9e3e'),
    (12.6, 13.2, '#e8a020'),
    (13.2, 16.0, '#cc3333'),
]

# ── App ──
root = tk.Tk()
root.title("Meter Simulator")
root.resizable(False, False)

canvas = tk.Canvas(root, width=W, height=H, bg="#fcfcfb", highlightthickness=0)
canvas.pack()

readout = tk.Label(root, text="0.00 V  |  PWM 0  |  0.0%",
                   font=("monospace", 12), bg="#fcfcfb", fg="#0b0b0b")
readout.pack(pady=(0, 4))

voltage_var = tk.DoubleVar(value=0.0)
center_var = tk.DoubleVar(value=DEFAULT_CENTER)
sigma_var = tk.DoubleVar(value=DEFAULT_SIGMA)
base_gain_var = tk.DoubleVar(value=DEFAULT_BASE_GAIN)
peak_gain_var = tk.DoubleVar(value=DEFAULT_PEAK_GAIN)

canvas_items = []


def draw_meter():
    for item in canvas_items:
        canvas.delete(item)
    canvas_items.clear()

    position = compute_position(center_var.get(), sigma_var.get(),
                                base_gain_var.get(), peak_gain_var.get())

    # Colored range bands
    for v_lo, v_hi, color in ranges:
        pts = []
        p0 = volt_to_position(v_lo, position)
        p1 = volt_to_position(v_hi, position)
        steps = max(int(abs(p1 - p0) * 500), 20)
        for i in range(steps + 1):
            p = p0 + (p1 - p0) * i / steps
            a = pos_to_angle(p)
            pts.extend(endpoint(a, BAND_R))
        canvas_items.append(
            canvas.create_line(pts, fill=color, width=BAND_W, smooth=True))

    # Main arc
    pts = []
    for i in range(501):
        a = math.radians(ARC_END + i * (ARC_START - ARC_END) / 500)
        pts.extend(endpoint(a, RADIUS))
    canvas_items.append(
        canvas.create_line(pts, fill="#0b0b0b", width=2, smooth=True))

    # Ticks and labels
    for v in np.arange(0, 16.25, 0.25):
        pos = volt_to_position(v, position)
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
        canvas_items.append(
            canvas.create_line(x0, y0, x1, y1,
                               fill="#0b0b0b" if is_major else "#52514e",
                               width=width))

        if is_major:
            lx, ly = endpoint(a, RADIUS - 30)
            canvas_items.append(
                canvas.create_text(lx, ly, text=str(int(v)),
                                   font=("sans-serif", 10), fill="#0b0b0b"))

    canvas_items.append(
        canvas.create_text(CX, 160, text="Vdc",
                           font=("sans-serif", 11), fill="#52514e"))

    # Pivot dot
    canvas_items.append(
        canvas.create_oval(CX - 5, CY - 5, CX + 5, CY + 5,
                           fill="#0b0b0b", outline="#0b0b0b"))

    # Needle
    v = voltage_var.get()
    pos = volt_to_position(v, position)
    a = pos_to_angle(pos)
    nx, ny = endpoint(a, NEEDLE_LEN)
    canvas_items.append(
        canvas.create_line(CX, CY, nx, ny, fill="#cc2222", width=2))

    # Readout
    pwm = round(pos * PWM_MAX)
    duty = pwm / PWM_MAX * 100
    readout.config(text=f"{v:5.2f} V  |  PWM {pwm:3d}  |  {duty:5.1f}%")


def on_voltage_change(_=None):
    draw_meter()


def on_tuning_change(_=None):
    draw_meter()


voltage_slider = tk.Scale(root, from_=0, to=16, resolution=0.01,
                           orient=tk.HORIZONTAL, length=W - 40,
                           variable=voltage_var, command=on_voltage_change,
                           label="Input Voltage (V)",
                           bg="#fcfcfb", highlightthickness=0,
                           troughcolor="#d0d0d0")
voltage_slider.pack(padx=20, pady=(0, 6))

# ── Tuning controls ──
tuning_frame = tk.LabelFrame(root, text="LUT Tuning", bg="#fcfcfb",
                              font=("sans-serif", 10), padx=8, pady=4)
tuning_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

tuning_params = [
    ("CENTER",    center_var,    6.0,  16.0, 0.1),
    ("SIGMA",     sigma_var,     0.1,  5.0,  0.05),
    ("BASE_GAIN", base_gain_var, 0.01, 2.0,  0.01),
    ("PEAK_GAIN", peak_gain_var, 0.01, 4.0,  0.01),
]
for label_text, var, from_, to_, res in tuning_params:
    row = tk.Frame(tuning_frame, bg="#fcfcfb")
    row.pack(fill=tk.X, pady=1)
    tk.Label(row, text=f"{label_text}:", width=12, anchor="w",
             bg="#fcfcfb", font=("monospace", 9)).pack(side=tk.LEFT)
    tk.Scale(row, from_=from_, to=to_, resolution=res,
             orient=tk.HORIZONTAL, length=300, variable=var,
             command=on_tuning_change, bg="#fcfcfb",
             highlightthickness=0, troughcolor="#d0d0d0",
             showvalue=True).pack(side=tk.LEFT, fill=tk.X, expand=True)

draw_meter()
root.mainloop()
