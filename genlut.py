#!/usr/bin/env python3
import numpy as np

# ------------------------------------------------------------
# User-adjustable parameters
# ------------------------------------------------------------

BUS_MIN = 0.0
BUS_MAX = 16.0

ADC_MAX = 1023
PWM_MAX = 255

CENTER = 12.0          # Expanded region center (V)

SIGMA = 1.4            # Width of expansion

BASE_GAIN = 0.25       # Sensitivity away from center
PEAK_GAIN = 1.60       # Additional sensitivity at center

# ------------------------------------------------------------
# Gaussian sensitivity
# ------------------------------------------------------------

def sensitivity(v):
    return (
        BASE_GAIN
        + PEAK_GAIN *
        np.exp(-0.5 * ((v - CENTER) / SIGMA) ** 2)
    )

# ------------------------------------------------------------
# Integrate sensitivity
# ------------------------------------------------------------

resolution = 10000

voltage = np.linspace(BUS_MIN, BUS_MAX, resolution)

gain = sensitivity(voltage)

# Numerical integration

position = np.cumsum(gain)

# Normalize to 0...1

position -= position[0]
position /= position[-1]

# ------------------------------------------------------------
# Convert every ADC code into PWM
# ------------------------------------------------------------

table = []

for adc in range(ADC_MAX + 1):

    # Convert ADC reading back into bus voltage.
    #
    # Assumes your resistor divider is calibrated so:
    #
    # ADC=0     -> 0.0V
    # ADC=1023  ->16.0V
    #
    bus_voltage = adc * BUS_MAX / ADC_MAX

    meter_position = np.interp(
        bus_voltage,
        voltage,
        position
    )

    pwm = round(meter_position * PWM_MAX)

    table.append(pwm)

# ------------------------------------------------------------
# Print Arduino array
# ------------------------------------------------------------

print("const uint8_t meterTable[1024] PROGMEM = {")

for i in range(0, len(table), 16):

    row = ", ".join(f"{x:3d}" for x in table[i:i+16])

    end = "," if i + 16 < len(table) else ""

    print("    " + row + end)

print("};")
