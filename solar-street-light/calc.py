#!/usr/bin/env python3
"""Sizing and loss budget for a 12 V / 20 W solar street light.

Both converters are run by one PIC16F1769 (see DESIGN.md).

Run: python3 calc.py
All component values match DESIGN.md. Loss models are first-order
estimates; confirm on the bench with a power analyzer.
"""
from math import sqrt

# ---------------------------------------------------------------- inputs
LED_N_SERIES = 12          # 3535 high-power LEDs, one string
LED_VF = 2.95              # V per LED at ~0.56 A, 25 C (check datasheet bin)
P_LED = 20.0               # W target

BAT_V_NOM = 12.8           # LiFePO4 4S nominal
BAT_V_MIN = 11.2           # low-voltage disconnect (2.8 V/cell)
BAT_V_MAX = 14.4           # end of charge (3.6 V/cell)
BAT_AH = 30.0

# Night profile: (hours, fraction of full power)
PROFILE = [(4, 1.0), (2, 0.5), (6, 0.3)]
STANDBY_W = 0.13           # MCU + controllers, 24 h
PSH = 4.0                  # peak sun hours, worst month (site dependent)
PANEL_DERATE = 0.80        # temperature, dust, mismatch, wiring
BAT_ROUNDTRIP = 0.96       # LiFePO4 energy round trip at 0.2 C
DOD = 0.90


def boost_losses(vin, pout, vled, f=200e3, L=68e-6):
    """Asynchronous boost LED driver (controller + NMOS + Schottky)."""
    iled = pout / vled
    vd = 0.42                       # Schottky Vf at ~0.56 A
    vout = vled + 0.1 + vd          # sense drop + diode
    d = 1 - vin / vout
    # iterate input current with efficiency
    eff = 0.95
    for _ in range(20):
        iin = pout / eff / vin
        di = vin * d / (f * L)
        irms_l = sqrt(iin**2 + di**2 / 12)
        irms_q = iin * sqrt(d)
        loss = {
            "inductor DCR (35 mOhm)": irms_l**2 * 0.035,
            "inductor core": 0.08,
            "MOSFET conduction (14 mOhm hot)": irms_q**2 * 0.014,
            "MOSFET switching (tr+tf=20 ns)": 0.5 * vout * iin * 20e-9 * f,
            "MOSFET Coss (300 pF)": 0.5 * 300e-12 * vout**2 * f,
            "gate drive (25 nC, 10 V)": 25e-9 * 10 * f,
            "Schottky diode": vd * iled,
            "LED sense resistor (0.1 Ohm, low side)": iled**2 * 0.100,
            "switch sense resistor (50 mOhm)": irms_q**2 * 0.050,
            "LED disconnect FET (20 mOhm)": iled**2 * 0.020,
            "low-side gate driver quiescent": 0.010,
            "PIC + 5 V LDO (5 mA from battery)": 0.005 * vin,
            "caps ESR + PCB copper": 0.035,
        }
        ptot = sum(loss.values())
        eff = pout / (pout + ptot)
    return eff, loss, d, iin, di, iled


def buck_losses(vin, vbat, pin, f=100e3, L=22e-6):
    """Synchronous buck MPPT charger with ideal-diode input."""
    eff = 0.97
    for _ in range(20):
        iout = pin * eff / vbat
        iin = pin / vin
        d = vbat / vin
        di = (vin - vbat) * d / (f * L)
        irms_l = sqrt(iout**2 + di**2 / 12)
        loss = {
            "high-side FET conduction (7 mOhm hot)": iout**2 * d * 0.007,
            "high-side FET switching (tr+tf=20 ns)": 0.5 * vin * iout * 20e-9 * f,
            "low-side FET conduction (7 mOhm hot)": iout**2 * (1 - d) * 0.007,
            "dead-time body diode (2x20 ns)": 2 * 20e-9 * f * 0.8 * iout,
            "inductor DCR (12 mOhm)": irms_l**2 * 0.012,
            "inductor core": 0.12,
            "gate drive (2x30 nC, 10 V)": 2 * 30e-9 * 10 * f,
            "charge sense shunt (2 mOhm)": iout**2 * 0.002,
            "ideal-diode FET (4 mOhm)": iin**2 * 0.004,
            "PIC + 5 V/10 V rails + gate driver": 0.10,
            "caps ESR + PCB copper": 0.05,
        }
        ptot = sum(loss.values())
        eff = (pin - ptot) / pin
    return eff, loss, d, iout, di


def show(title, loss, pout_or_pin, eff):
    print(f"\n{title}")
    for k, v in loss.items():
        print(f"  {k:<40s} {v*1000:7.1f} mW")
    print(f"  {'TOTAL':<40s} {sum(loss.values())*1000:7.1f} mW")
    print(f"  efficiency {eff*100:.2f} %")


vled = LED_N_SERIES * LED_VF
print("=" * 64)
print("LED STRING")
print(f"  {LED_N_SERIES}S1P, Vled = {vled:.1f} V, Iled = {P_LED/vled*1000:.0f} mA")
print(f"  Low-side sense 0.1 Ohm -> {P_LED/vled*100:.1f} mV, amplified x20 by PIC op-amp")

print("=" * 64)
print("LED DRIVER (boost), 20 W out")
for vin in (BAT_V_MIN, BAT_V_NOM, 13.3, BAT_V_MAX):
    eff, loss, d, iin, di, iled = boost_losses(vin, P_LED, vled)
    print(f"  Vin {vin:5.1f} V  D={d:.3f}  Iin={iin:.2f} A  dI={di:.2f} A  "
          f"Ipk={iin+di/2:.2f} A  eff={eff*100:.2f} %")
eff, loss, *_ = boost_losses(BAT_V_NOM, P_LED, vled)
show("  Loss breakdown at 12.8 V in, 20 W out", loss, P_LED, eff)
print("\n  Dimmed operation (DAC reference lowered, 12.8 V in):")
for frac in (0.5, 0.3):
    e, *_ = boost_losses(BAT_V_NOM, P_LED * frac, vled * (0.97 if frac < 1 else 1))
    print(f"    {frac*100:3.0f} %  ({P_LED*frac:4.1f} W)  eff={e*100:.2f} %")

print("=" * 64)
print("MPPT CHARGER (sync buck), 80 W panel, Vmp 18 V")
for pin, vin in ((80, 18.0), (80, 15.8), (40, 18.0), (16, 18.0)):
    eff, loss, d, iout, di = buck_losses(vin, 13.6, pin)
    print(f"  Pin {pin:3d} W  Vin {vin:4.1f} V  D={d:.3f}  Ichg={iout:.2f} A  "
          f"dI={di:.2f} A  eff={eff*100:.2f} %")
eff_c, loss, *_ = buck_losses(18.0, 13.6, 80)
show("  Loss breakdown at 80 W, 18 V -> 13.6 V", loss, 80, eff_c)

print("=" * 64)
print("ENERGY BUDGET")
e_led = sum(h * f * P_LED for h, f in PROFILE)
eff_drv = boost_losses(BAT_V_NOM, P_LED * 0.6, vled)[0]
e_bat = e_led / eff_drv + STANDBY_W * 24
hours = sum(h for h, _ in PROFILE)
print(f"  Night profile {PROFILE} -> {hours} h, LED energy {e_led:.0f} Wh")
print(f"  Battery draw per night incl. standby: {e_bat:.0f} Wh")
usable = BAT_V_NOM * BAT_AH * DOD
print(f"  Battery {BAT_V_NOM} V {BAT_AH:.0f} Ah, usable {usable:.0f} Wh "
      f"-> autonomy {usable/e_bat:.2f} nights")
need_in = e_bat / (0.97 * BAT_ROUNDTRIP)
print(f"  Energy needed at battery charger input: {need_in:.0f} Wh/day")
p_min = need_in / (PSH * PANEL_DERATE)
print(f"  Minimum panel at {PSH} PSH, derate {PANEL_DERATE}: {p_min:.0f} W")
for p in (60, 80):
    harvest = p * PSH * PANEL_DERATE * 0.97 * BAT_ROUNDTRIP
    surplus = harvest - e_bat
    print(f"  {p} W panel: {harvest:.0f} Wh/day stored, surplus {surplus:.0f} Wh"
          f" -> refill 2 empty nights in {2*e_bat/surplus:.1f} days")

print("=" * 64)
print("CHAIN EFFICIENCY")
eff_drv_full = boost_losses(BAT_V_NOM, P_LED, vled)[0]
mppt_track = 0.99
print(f"  Battery -> LED (driver)           {eff_drv_full*100:.1f} %")
print(f"  Panel -> battery (MPPT x buck)    {mppt_track*eff_c*100:.1f} %")
print(f"  Panel -> LED incl. battery cycle  "
      f"{mppt_track*eff_c*BAT_ROUNDTRIP*eff_drv_full*100:.1f} %")

print("=" * 64)
print("BOOST CONTROL LOOP (peak current mode, PIC comparator + PRG)")
L, f, rsw = 68e-6, 200e3, 0.050
iled = P_LED / vled
vout = vled + 0.1 * iled + 0.42
for vin in (BAT_V_MIN, BAT_V_NOM, BAT_V_MAX):
    d = 1 - vin / vout
    rload = vout / iled
    frhp = (1 - d) ** 2 * rload / (2 * 3.14159 * L)
    down = (vout - vin) / L * rsw / 1e6   # V/us at the sense resistor
    print(f"  Vin {vin:4.1f} V: D={d:.3f}  RHP zero {frhp/1e3:5.1f} kHz  "
          f"sense down-slope {down*1e3:5.1f} mV/us")
d = 1 - BAT_V_MIN / vout
down = (vout - BAT_V_MIN) / L * rsw / 1e6
print(f"  Slope compensation (PRG) >= 0.5 x worst down-slope = {0.5*down*1e3:.1f} mV/us;"
      f" use about {0.75*down*1e3:.0f} mV/us")
frhp_min = (1 - d) ** 2 * (vout / iled) / (2 * 3.14159 * L)
print(f"  Crossover target <= RHP zero / 5 = {frhp_min/5/1e3:.1f} kHz (use 1-2 kHz)")
ipk = P_LED / 0.95 / BAT_V_MIN + BAT_V_MIN * d / (f * L) / 2
print(f"  Peak switch current at 11.2 V: {ipk:.2f} A -> {ipk*rsw*1e3:.0f} mV on 50 mOhm")
print(f"  LED sense: {iled:.3f} A x 0.1 Ohm = {iled*0.1*1e3:.1f} mV; op-amp gain 20 -> "
      f"{iled*0.1*20:.2f} V at full current")

print("=" * 64)
print("CHARGER PWM RESOLUTION (firmware duty control)")
fosc, fsw = 32e6, 100e3
steps = fosc / fsw
print(f"  {fosc/1e6:.0f} MHz / {fsw/1e3:.0f} kHz = {steps:.0f} steps, "
      f"{100/steps:.2f} % duty per step")
vb = 13.6
for d in (0.70, 0.85):
    dv = vb / d - vb / (d + 1 / steps)
    print(f"  at D={d:.2f}: panel voltage step {dv*1e3:.0f} mV")
