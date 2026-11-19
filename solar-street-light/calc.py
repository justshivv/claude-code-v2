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

# ======================================================================
# SC95F8523 VERSION (see SC95F8523.md and kicad/)
# No on-chip comparator, op-amp or DAC; one PWM period shared by all
# channels (32 MHz clock); one FLT input.
# ======================================================================
print("\n" + "#" * 64)
print("SC95F8523 VERSION: both converters at 100 kHz (shared PWM period)")


# Parts in the KiCad project (kicad/): IR2104 half-bridge driver for the
# charger, UCC27511 for the boost switch, both supplied from the battery
# (VDRV); L78L05 5 V regulator; LM4040-2.5 reference for fault thresholds.
# IR2104 drive: 130/270 mA minimum (KiCad symbol lists 210/360 mA typical).
# With Qgs2+Qgd of about 10 nC that gives roughly 77 + 37 = 115 ns of
# switching edges (conservative, minimum drive). Dead time is fixed inside
# the IR2104 at about 520 ns. Check both against the IR2104 datasheet.
IR_EDGE = 115e-9
IR_DT = 520e-9
I_5V_RAIL = 0.007        # SC95F8523 4.5 mA + 2x INA181 + LM2901 + LM4040 bias, A
I_78L05_Q = 0.0045       # L78L05 quiescent current, A (about 3-6 mA)
I_DRV_Q = 0.0008         # IR2104 + UCC27511 idle supply, A (estimate)


def boost_sc95(vin, pout, vled, f=100e3, L=100e-6, sync=False):
    """Async: UCC27511 drives Q1, D1 rectifies. Sync: a second IR2104
    drives Q1 (LO) and Q6 (HO), D1 kept for the dead time."""
    iled = pout / vled
    vd = 0.42
    vout = vled + 0.1 * iled + (0.0 if sync else vd)
    d = 1 - vin / vout
    edge = IR_EDGE if sync else 20e-9
    eff = 0.95
    for _ in range(20):
        iin = pout / eff / vin
        di = vin * d / (f * L)
        irms_l = sqrt(iin**2 + di**2 / 12)
        irms_q = iin * sqrt(d)
        irms_sr = iin * sqrt(1 - d)
        loss = {
            "inductor DCR (40 mOhm)": irms_l**2 * 0.040,
            "inductor core": 0.06,
            "Q1 conduction (14 mOhm hot)": irms_q**2 * 0.014,
            f"Q1 switching (edges {edge*1e9:.0f} ns)": 0.5 * vout * iin * edge * f,
            "Q1 Coss (300 pF)": 0.5 * 300e-12 * vout**2 * f,
            "gate drive (25 nC at VDRV = battery)": 25e-9 * vin * f * (2 if sync else 1),
            "LED sense resistor (0.1 Ohm)": iled**2 * 0.100,
            "switch sense, fault only (33 mOhm)": irms_q**2 * 0.033,
            "LED disconnect FET (20 mOhm)": iled**2 * 0.020,
            "5 V rail: loads 7 mA + L78L05 4.5 mA": (I_5V_RAIL + I_78L05_Q) * vin,
            "gate drivers idle": I_DRV_Q * vin,
            "caps ESR + PCB copper": 0.035,
        }
        if sync:
            loss["Q6 conduction (14 mOhm hot)"] = irms_sr**2 * 0.014
            loss["D1 during 2 x 520 ns dead time"] = 2 * IR_DT * f * 0.45 * iin
        else:
            loss["Schottky diode D1"] = vd * iled
        ptot = sum(loss.values())
        eff = pout / (pout + ptot)
    return eff, loss, d, iin, di


def charger_sc95(pin, vin=18.0, vbat=13.6, f=100e3):
    """Sync buck driven by the IR2104: slow edges, 520 ns dead time, D2 conducts."""
    eff, loss, d, iout, di = buck_losses(vin, vbat, pin)
    loss = dict(loss)
    loss.pop("high-side FET switching (tr+tf=20 ns)")
    loss.pop("dead-time body diode (2x20 ns)")
    loss.pop("gate drive (2x30 nC, 10 V)")
    loss.pop("PIC + 5 V/10 V rails + gate driver")
    loss[f"Q3 switching (IR2104 edges {IR_EDGE*1e9:.0f} ns)"] = 0.5 * vin * iout * IR_EDGE * f
    loss["D2 during 2 x 520 ns dead time"] = 2 * IR_DT * f * 0.45 * iout
    loss["gate drive (2 x 30 nC at VDRV)"] = 2 * 30e-9 * vbat * f
    loss["5 V rail + L78L05 + drivers idle"] = (I_5V_RAIL + I_78L05_Q + I_DRV_Q) * vbat
    ptot = sum(loss.values())
    return (pin - ptot) / pin, loss


for sync in (False, True):
    name = "synchronous (Q6 + second IR2104)" if sync else "asynchronous (UCC27511 + D1)"
    print(f"\n  Boost, {name}")
    for vin in (BAT_V_MIN, BAT_V_NOM, BAT_V_MAX):
        e, loss, d, iin, di = boost_sc95(vin, P_LED, vled, sync=sync)
        print(f"    Vin {vin:4.1f} V  D={d:.3f}  Ipk={iin+di/2:.2f} A  dI={di:.2f} A  eff={e*100:.2f} %")
    for frac in (0.5, 0.3):
        e, *_ = boost_sc95(BAT_V_NOM, P_LED * frac, vled * 0.97, sync=sync)
        print(f"    {frac*100:3.0f} % brightness  eff={e*100:.2f} %")
e_async, loss_a, *_ = boost_sc95(BAT_V_NOM, P_LED, vled)
show("  Loss breakdown, async boost at 12.8 V, 20 W", loss_a, P_LED, e_async)
e_sync = boost_sc95(BAT_V_NOM, P_LED, vled, sync=True)[0]
print("  With IR2104 edges and dead time the synchronous boost is not better than D1,"
      " so keep the asynchronous boost.")

print("\n  Charger, IR2104 driving Q3/Q4 (sync buck, 100 kHz)")
for pin in (80, 40, 16):
    e, l = charger_sc95(pin)
    print(f"    {pin:3d} W from the panel: {e*100:.2f} %  (loss {sum(l.values()):.2f} W)")
eff_c2, loss_c2 = charger_sc95(80)
show("  Loss breakdown, charger at 80 W, 18 V -> 13.6 V", loss_c2, 80, eff_c2)
print("  Below about 0.2 A charge current, firmware stops switching with IR2104 SD"
      " (the IR2104 cannot hold Q4 off while Q3 switches).")

print("\n  Standby and energy budget, SC95F8523 version")
p_stby = (I_5V_RAIL + I_78L05_Q + I_DRV_Q) * BAT_V_NOM
print(f"    always-on draw: {p_stby*1e3:.0f} mW ({p_stby*24:.1f} Wh/day), "
      f"of which L78L05 quiescent {I_78L05_Q*BAT_V_NOM*1e3:.0f} mW ({I_78L05_Q*BAT_V_NOM*24:.1f} Wh/day)")
e_led = sum(h * fr * P_LED for h, fr in PROFILE)
e_drv = boost_sc95(BAT_V_NOM, P_LED * 0.6, vled)[0]   # includes rail power during the night
night = sum(h for h, _ in PROFILE)
e_bat = e_led / e_drv + p_stby * (24 - night)
print(f"    battery draw per 24 h: {e_bat:.0f} Wh -> autonomy "
      f"{BAT_V_NOM * BAT_AH * DOD / e_bat:.2f} nights")

print("\n  Duty resolution and dithering (32 MHz / 100 kHz = 320 counts)")
d = 1 - BAT_V_NOM / (vled + 0.48)
dvdd = BAT_V_NOM / (1 - d) ** 2          # dVout/dD
r_dyn = LED_N_SERIES * 0.5               # string dynamic resistance, ohm (estimate)
step_v = dvdd / 320
print(f"    one count: Vout step {step_v*1e3:.0f} mV -> LED current step "
      f"{step_v/r_dyn*1e3:.0f} mA without dithering")
for bits in (4, 6):
    print(f"    {bits}-bit sigma-delta dither: {step_v/r_dyn/2**bits*1e3:.1f} mA effective step")
cout = 4 * 4.7e-6
f0 = (1 - d) / (2 * 3.14159 * sqrt(100e-6 * cout))
print(f"    output LC double pole about {f0/1e3:.1f} kHz; firmware loop 10 kHz, crossover 100-200 Hz")
print(f"    dither in PWM interrupt at 100 kHz -> 4-bit pattern repeats at >= 6.25 kHz,"
      f" above the {f0/1e3:.1f} kHz LC pole, so the output filter smooths it")
dmax = 13.6 / 15.5                        # buck duty at a hot 36-cell panel (Vmp 15.5 V)
print(f"    charger: hot-panel duty {dmax:.3f} + IR2104 dead time {IR_DT*1e5:.3f}"
      f" = {dmax + IR_DT*1e5:.3f} of the period on the IN pin; Q4 stays on for "
      f"{((1 - dmax) * 10e-6 - 2 * IR_DT) * 1e9:.0f} ns per cycle (bootstrap refresh)")

print("\n  ADC (12-bit, 2.048 V internal reference)")
lsb = 2.048 / 4096
for name, v in (("Iled full (INA181A1 x20, 0.1 Ohm)", 0.565 * 0.1 * 20),
                ("Iled 30 %", 0.3 * 0.565 * 0.1 * 20),
                ("Ichg 5.8 A (INA181A3 x100, 2 mOhm, REF=GND)", 5.8 * 0.002 * 100),
                ("Ichg 0.2 A switching-stop threshold", 0.2 * 0.002 * 100)):
    print(f"    {name:<46s} {v:5.3f} V = {v/lsb:5.0f} counts")

print("\n  Fault thresholds from VREF25 (LM4040-2.5) instead of the L78L05 rail")
for nm, r1, r2, scale, unit in (("REF_A boost switch", 21.0, 1.0, 1 / 0.033, "A"),
                                ("REF_B LED OVP", 3.01, 10, 22.5, "V"),
                                ("REF_C charge OC", 8.06, 10, 1 / (0.002 * 100), "A"),
                                ("REF_D battery OV", 6.81, 10, 10.1, "V")):
    ref = 2.5 * r2 / (r1 + r2)
    lo, hi = ref * 0.98 * scale, ref * 1.02 * scale          # 0.5 % ref + 1 % resistors, rough
    print(f"    {nm:<20s} {ref:.4f} V -> {ref*scale:5.2f} {unit} "
          f"(about {lo:.2f}-{hi:.2f} {unit})")
print(f"    same battery OV divider fed from 5 V +/-5 %: "
      f"{1.484*0.95*10.1:.2f}-{1.484*1.05*10.1:.2f} V (low end is below the 14.4 V charge voltage)")

print("\n  Chain efficiency, SC95F8523 version")
for label, e in (("async boost", e_async), ("sync boost", e_sync)):
    print(f"    {label}: battery->LED {e*100:.1f} %, panel->LED incl. battery "
          f"{0.99*eff_c2*BAT_ROUNDTRIP*e*100:.1f} %")
