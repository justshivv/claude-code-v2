# 12 V 20 W Solar Street Light, Power Design (efficiency > 91 %)

All numbers below come from `calc.py` in this folder (output saved in
`calc_output.txt`). Loss models are first-order estimates. Treat them as a
design target and confirm on the bench with the test procedure at the end.

## 1. Specification

| Item | Value |
|---|---|
| System voltage | 12 V class, LiFePO4 4S (12.8 V nominal, 11.2–14.4 V) |
| LED power | 20 W at full brightness |
| LED driver efficiency (battery → LED) | > 91 % required, 96 % designed |
| Charger efficiency (panel → battery) | > 91 % required, 97–98 % designed |
| Night | 12 h: 4 h at 100 %, 2 h at 50 %, 6 h at 30 % |
| Autonomy | 2.4 nights on the profile above |
| Light output | about 2800–3200 lm from the LEDs, depending on bin and optics |

The 91 % figure is met by each power stage on its own with 4–7 points to
spare. If the requirement is end to end (sunlight on the panel's output to
light, including the battery charge/discharge cycle), the estimate is
about 90 %, because LiFePO4 round trip is about 96 %. Section 9 shows how
to get that above 91 %.

## 2. Architecture

```
 80 W PANEL            MPPT CHARGER                  BATTERY            LED DRIVER                LED LOAD
 Vmp 18-20 V   ┌──────────────────────────┐      LiFePO4 4S5P     ┌──────────────────────┐
 ──────┬──────►│ TVS ─ ideal diode ─ sync  │────► 12.8 V 30 Ah ───►│ async boost, 200 kHz │───► 12 x 3535 LED
       │       │ buck 100 kHz ─ shunt      │      + 4S BMS         │ 0.565 A constant I   │     in series
       │       └────────────▲─────────────┘           │           └──────────▲───────────┘     35.4 V
       │                    │ PWM                     │                      │ EN / CTRL (dim)
       │              ┌─────┴─────────────────────────┴──────────────────────┴───┐
       └─ Vpanel ────►│ MCU: MPPT (P&O), charge profile, dusk/dawn, dimming,     │◄── NTC (battery)
          (dusk/dawn) │ low-voltage disconnect, coulomb counting                │◄── PIR (optional)
                      └─────────────────────────────────────────────────────────┘
```

A boost LED driver is the usual choice for a 12 V system. A single string
at about 35 V needs no current balancing, keeps the LED current low (so
sense and diode losses stay small), and keeps working as the battery falls
to 11.2 V. A buck to a short string would need 2 A or more through every
part and stops regulating once the battery sags.

## 3. LED load

12 LEDs in series, one string (12S1P), 3535 ceramic high-power package
rated 1 A or more, run at 0.565 A.

| Parameter | Value |
|---|---|
| Vf per LED at 0.565 A, 25 °C | about 2.95 V (use the datasheet bin) |
| String voltage | 35.4 V nominal, roughly 33.5–37.5 V over bin and temperature |
| String current | 0.565 A → 20.0 W |
| Expected efficacy | about 150 lm/W at this current for a current 3535 part |
| Board | 1.5 mm aluminium MCPCB, thermal pad to housing |

Running a 1 A part at 0.565 A buys efficacy and lifetime. Keep the LED
case below 85 °C at 40 °C ambient. With roughly 13 W of heat that takes
about 400–450 cm² of finned housing area.

Use a type II street lens (asymmetric) for a single-lane road.

## 4. LED driver: asynchronous boost, constant current

Controller: Analog Devices LT3756 (6–100 V in, boost LED controller with
high-side LED current sense and a PWM disconnect FET driver). Any boost LED
controller with a sense threshold of 100 mV or less and an output
disconnect FET will hit the same numbers. Check every threshold below
against the datasheet of the part you buy.

### Operating points (20 W out)

| Vin | Duty | Iin | Inductor ripple | Peak current | Efficiency |
|---|---|---|---|---|---|
| 11.2 V (LVD) | 0.688 | 1.86 A | 0.57 A | 2.15 A | 95.8 % |
| 12.8 V | 0.644 | 1.63 A | 0.61 A | 1.93 A | 96.1 % |
| 14.4 V | 0.599 | 1.44 A | 0.63 A | 1.76 A | 96.3 % |

At 50 % brightness (10 W) the estimate is 95.5 %, at 30 % (6 W) 94.3 %.

### Component values

| Ref | Part | Value / rating | Reason |
|---|---|---|---|
| Fsw | RT resistor | 200 kHz | Low switching loss, inductor still a sensible size |
| L1 | Shielded power inductor | 68 µH, Isat ≥ 3.5 A, DCR ≤ 35 mΩ, low-loss ferrite | Ripple about 35 % of Iin |
| Q1 | N-MOSFET | 60 V, Rds(on) ≤ 10 mΩ at 25 °C, Qg ≤ 20 nC | Small conduction loss, fast edges |
| D1 | Schottky | 60 V, 3–5 A, Vf ≈ 0.42 V at 0.6 A | Largest single loss (0.24 W) |
| RLED | LED sense | 0.18 Ω ∥ 10 Ω = 0.177 Ω, 1 %, 0.5 W | ILED = 100 mV / 0.177 Ω = 0.565 A |
| RSW | Switch sense | 33 mΩ, 1 %, 0.5 W | Cycle-by-cycle limit near 3 A (≈100 mV threshold) |
| Q2 | LED disconnect P/N-FET (per controller) | 60 V, ≤ 20 mΩ | PWM dimming, open/short isolation |
| COUT | Ceramic X7R | 4 × 4.7 µF 100 V | Output ripple current 0.76 A rms |
| CIN | Ceramic X7R + polymer | 2 × 10 µF 25 V + 100 µF 25 V | Input ripple and cable inductance |
| R1/R2 | OVP divider | 330 kΩ / 10 kΩ | 1.25 V × 34 = 42.5 V open-LED clamp (check FB reference) |
| EN/UVLO | Divider | Off at 10.8 V | Hardware backup to the firmware LVD |

### Loss budget at 12.8 V in, 20 W out

| Loss | mW |
|---|---|
| Schottky diode (0.42 V × 0.565 A) | 237 |
| MOSFET switching (20 ns total edges) | 117 |
| Inductor copper (35 mΩ) | 94 |
| Inductor core | 80 |
| LED sense resistor | 57 |
| Switch sense resistor | 56 |
| MOSFET Coss | 39 |
| Controller quiescent | 38 |
| PCB copper and capacitor ESR | 35 |
| Gate drive | 28 |
| MOSFET conduction | 24 |
| Disconnect FET | 6 |
| **Total** | **811 → 96.1 %** |

Dimming: use analog dimming on the CTRL pin (MCU PWM through an RC
filter) for the 50 % and 30 % steps. The converter loses about 2 points
at 30 %, but the LEDs gain more than that in lm/W at lower current, so
light per battery watt-hour goes up. Keep PWM dimming for fades and
motion-sensor steps if wanted.

## 5. MPPT charger: synchronous buck

| Item | Choice |
|---|---|
| Panel | 80 W mono, Vmp 18–20 V (36–40 cells), Voc ≤ 23 V at 25 °C |
| Topology | Synchronous buck, 100 kHz, MCU controlled |
| Gate driver | TI UCC27211 half-bridge driver (or similar 100 V bootstrap driver), 10 V rail from an LDO |
| Q3, Q4 | N-MOSFETs, 60 V, Rds(on) ≤ 5 mΩ at 25 °C, Qg ≤ 30 nC |
| L2 | 22 µH, Isat ≥ 9 A, DCR ≤ 12 mΩ |
| Input | SMBJ28A TVS, then ideal-diode controller (TI LM74700-Q1) with one 60 V, ≤ 4 mΩ FET to block reverse polarity and night-time back-feed through Q3's body diode |
| Current sense | 2 mΩ shunt + INA181 amplifier to the MCU ADC |
| MCU | Small Cortex-M0+ (for example STM32G031) with a 64 MHz timer for 640-step PWM at 100 kHz |

Estimated efficiency: 98.4 % at 80 W, 97.6 % at 16 W. Expect about
97 % measured once real inductor core loss and layout are included. The
largest losses are inductor copper (0.40 W) and high-side FET conduction
(0.18 W).

At 65 °C cell temperature a 36-cell panel's Vmp falls to about 15.5 V.
That still leaves headroom above the 14.4 V end-of-charge voltage at a
duty cycle below 0.95. Keep max duty at 0.95 so the bootstrap capacitor
refreshes.

MPPT algorithm: perturb and observe on battery-side power (charge current
times battery voltage), 2 Hz update, 0.5 % duty step, plus a full sweep
every 10 minutes to escape local peaks from partial shading.

## 6. Battery and BMS

| Item | Value |
|---|---|
| Chemistry | LiFePO4, 4S5P of 6 Ah 32700 cells = 12.8 V 30 Ah (384 Wh) |
| Usable | 346 Wh at 90 % depth of discharge |
| Night draw | 145 Wh (136 Wh LED energy + driver loss + 0.13 W standby × 24 h) |
| Autonomy | 2.4 nights |
| Charge | CC 5.8 A max (0.19 C) to 14.4 V, CV until current < 1.5 A, then rest; float 13.6 V optional |
| Temperature | No charging below 0 °C or above 45 °C (NTC on the pack to the MCU) |
| BMS | 4S, ≥ 10 A continuous, cell balancing, OV/UV/OC/short protection |
| Firmware LVD | 12.0 V: force 30 % brightness. 11.2 V: LED off. Reconnect at 12.6 V |

Panel sizing at 4 peak sun hours (worst month, adjust for your site) and
0.8 derating: the minimum is 49 W. An 80 W panel stores about 238 Wh a
day, which refills two empty nights in about 3 days. A 60 W panel works
but takes about 9 days to recover.

## 7. Control firmware

1. Dusk: panel voltage below 5 V for 5 minutes. Dawn: above 8 V for 5 minutes. Hysteresis and time filter stop headlights or lightning from toggling the lamp.
2. Night schedule from dusk: 4 h at 100 %, 2 h at 50 %, rest at 30 %. Optional PIR or microwave sensor lifts 30 % to 100 % for 30 s.
3. Day: MPPT charging with the CC/CV profile and temperature limits above.
4. State of charge by coulomb counting through the shunt, re-zeroed at full charge. LiFePO4 voltage is too flat to read SOC from voltage alone.
5. Adaptive dimming: if SOC at dusk is below 50 %, scale the whole night profile down so the lamp lasts until dawn.
6. Standby target ≤ 10 mA at 12.8 V (MCU in stop mode between tasks, LED driver disabled during the day, charger gate driver disabled at night).

## 8. Protection

| Fault | Handling |
|---|---|
| Panel reverse polarity | Ideal-diode FET stays off |
| Night back-feed into panel | Ideal-diode FET blocks; buck disabled |
| Surge on panel cable | SMBJ28A TVS; all FETs and caps on that node rated 60 V |
| Open LED string | OVP divider clamps boost at about 42.5 V; MCU logs fault |
| Shorted LED string | Disconnect FET opens; 5 A fuse on driver input as backup (a boost has a DC path from input to output) |
| Battery reverse | Fuse plus reverse-polarity FET in battery line, or a keyed connector |
| Over-temperature | NTC near the LEDs; derate current above 85 °C board temperature |

## 9. Efficiency summary

| Path | Estimate | Requirement |
|---|---|---|
| Battery → LED (boost driver) | 96.1 % (95.8–96.3 % over battery range) | > 91 % |
| Panel → battery (MPPT 99 % × buck 98.4 %) | 97.5 % | > 91 % |
| Panel → LED, including battery cycle (96 %) | 90.0 % | see below |

If the 91 % has to hold end to end:

- Replace D1 with a synchronous rectifier FET (use a synchronous boost LED controller). That removes most of the 237 mW diode loss and lifts the driver to about 97.3 %, giving about 91 % end to end.
- Use a lower-DCR inductor for L2 (6 mΩ instead of 12 mΩ saves about 0.2 W at 80 W).
- The battery cycle loss cannot be designed out, because the lamp runs at night when the panel produces nothing. Charging at a low C-rate, as here, keeps it near 4 %.

## 10. Layout and thermal notes

- Boost hot loop is Q1 → D1 → COUT → ground return to Q1 source. Keep it under 2 cm² on the top layer with a solid ground plane under it.
- Buck hot loop is CIN → Q3 → Q4 → CIN. Same rule.
- Route both sense resistors with Kelvin connections straight to the controller pins.
- Use 2 oz copper for the power paths. Put thermal vias under Q1, D1, Q3, Q4.
- Keep the MCU ADC lines and the CTRL filter away from the switch nodes.
- Seal the driver board to IP66 or better and add a pressure-equalising vent to the housing.

## 11. Efficiency test procedure

1. Power the LED driver from a bench supply through 4-wire leads. Measure input voltage at the board terminals and input current with a calibrated shunt or power analyzer (0.1 % class or better).
2. Measure LED string voltage across the string and LED current through a separate 4-wire shunt.
3. Run at 20 W until the heatsink is stable (about 30 minutes at 25 °C ambient).
4. Record efficiency = (Vled × Iled) / (Vin × Iin) at 11.2, 12.8 and 14.4 V input, and at 100 %, 50 % and 30 % brightness.
5. Pass: every point ≥ 91 %. Design target: ≥ 95 % at 100 %.
6. Repeat for the charger with a solar array simulator or a current-limited supply set to the panel's Vmp/Imp, measuring panel-side and battery-side power.

## 12. Key parts summary

| Function | Part / spec |
|---|---|
| LED | 12 × 3535 ceramic high-power LED, ≥ 1 A rated, 5000–5700 K, CRI ≥ 70 |
| LED controller | LT3756 or equivalent boost LED controller (≤ 100 mV sense, disconnect FET drive) |
| Boost FET Q1 | 60 V, ≤ 10 mΩ, Qg ≤ 20 nC |
| Boost diode D1 | 60 V 3–5 A Schottky, low Vf |
| Boost inductor L1 | 68 µH, Isat ≥ 3.5 A, DCR ≤ 35 mΩ |
| Charger FETs Q3, Q4 | 60 V, ≤ 5 mΩ, Qg ≤ 30 nC |
| Charger inductor L2 | 22 µH, Isat ≥ 9 A, DCR ≤ 12 mΩ |
| Gate driver | UCC27211 or similar |
| Ideal diode | LM74700-Q1 + 60 V ≤ 4 mΩ FET |
| Current sense amp | INA181 |
| MCU | STM32G031 or similar |
| Battery | LiFePO4 4S5P 32700, 30 Ah, 4S BMS with balancing |
| Panel | 80 W mono, Vmp 18–20 V |
