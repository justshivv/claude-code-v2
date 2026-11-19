# 12 V 20 W Solar Street Light, PIC-Controlled Power Design (efficiency > 91 %)

One PIC microcontroller runs both power stages: the MPPT solar charger
and the constant-current LED driver. There is no dedicated LED driver IC
or charger IC.

A version using the SinOne SC95F8523 instead of the PIC is in
`SC95F8523.md`.

All numbers come from `calc.py` in this folder (output in
`calc_output.txt`). Loss models are first-order estimates. Treat them as a
design target and confirm on the bench with the test procedure at the end.
PIC peripheral details (counts, ranges, register names) are from the
PIC16F1769 family as I know it; check them against the current datasheet
before committing a layout.

## 1. Specification

| Item | Value |
|---|---|
| System voltage | 12 V class, LiFePO4 4S (12.8 V nominal, 11.2–14.4 V) |
| LED power | 20 W at full brightness |
| LED driver efficiency (battery → LED) | > 91 % required, 95.8 % designed |
| Charger efficiency (panel → battery) | > 91 % required, 97–98 % designed |
| Controller | PIC16F1769 (8-bit, on-chip op-amps, comparators, slope compensation, complementary output generators) |
| Night | 12 h: 4 h at 100 %, 2 h at 50 %, 6 h at 30 % |
| Autonomy | 2.4 nights on the profile above |
| Light output | about 2800–3200 lm from the LEDs, depending on bin and optics |

The 91 % figure is met by each power stage on its own with 4–7 points to
spare. End to end (panel output to light, including the battery
charge/discharge cycle) the estimate is about 90 %; section 10 covers
that case.

## 2. Why the PIC16F1769

An 8-bit PIC cannot run a fast current loop in firmware at 200 kHz. The
PIC16F1769 does not need to: its analog peripherals close the fast loop
in hardware, and firmware only sets references and supervises.

| On-chip block | Used for |
|---|---|
| 2 op-amps | LED current sense amplifier, LED current error amplifier |
| High-speed comparators | Boost peak current trip, LED open-circuit OVP, charger over-current, battery over-voltage |
| Programmable ramp generator (PRG) | Slope compensation for the boost (duty above 50 %) |
| 2 complementary output generators (COG) | COG1: charger half-bridge with dead-band. COG2: boost switch. Both with hardware auto-shutdown |
| 16-bit / 10-bit PWM | Switching clocks: 100 kHz charger, 200 kHz boost |
| 10-bit DAC | LED current reference (sets brightness) |
| 10-bit ADC | Panel and battery voltage, charge current, LED current and voltage, NTCs |
| High-endurance flash | Calibration values and SOC record |

If you want everything in firmware (digital loops, finer PWM, more
headroom for features), a dsPIC33CK-series part is the step up. The power
stage below stays the same.

## 3. Architecture

```
 80 W PANEL         MPPT CHARGER (sync buck)          BATTERY            LED DRIVER (boost)            LED LOAD
 Vmp 18-20 V   ┌──────────────────────────────┐   LiFePO4 4S5P    ┌───────────────────────────┐
 ─────────────►│ TVS ─ ideal diode ─ Q3/Q4 ─ L2│──► 12.8 V 30 Ah ─►│ L1 ─ Q1 ─ D1 ─ COUT        │──► 12 x 3535 LED
               │ ─ 2 mΩ shunt (INA181)         │    + 4S BMS       │ Q1 source: 50 mΩ RSW       │    Q2 disconnect
               └──────▲──────────────▲─────────┘                   └──────▲──────────▲─────────┘    0.1 Ω RLED to GND
                      │ UCC27211     │ Ichg                               │ UCC27517 │ RSW, RLED, Vled
                      │ (HO/LO)      │                                    │ (gate)   │
               ┌──────┴──────────────┴────────────────────────────────────┴──────────┴──────────┐
               │ PIC16F1769                                                                       │
               │  Charger: PWM 100 kHz → COG1 (half-bridge, dead-band) ; firmware P&O MPPT, CC/CV │
               │  LED:     PWM 200 kHz → COG2 ; comparator + PRG = peak current mode ;            │
               │           OPA1 senses RLED (x20), OPA2 error amp vs DAC = LED current loop       │
               │  ADC: Vpanel, Vbat, Ichg, Iled, Vled, NTC bat, NTC LED   Supply: 5 V LDO          │
               └──────────────────────────────────────────────────────────────────────────────────┘
```

## 4. LED load

12 LEDs in series, one string (12S1P), 3535 ceramic high-power package
rated 1 A or more, run at 0.565 A.

| Parameter | Value |
|---|---|
| Vf per LED at 0.565 A, 25 °C | about 2.95 V (use the datasheet bin) |
| String voltage | 35.4 V nominal, roughly 33.5–37.5 V over bin and temperature |
| String current | 0.565 A → 20.0 W |
| Expected efficacy | about 150 lm/W at this current for a current 3535 part |
| Board | 1.5 mm aluminium MCPCB, thermal pad to housing |

Keep the LED case below 85 °C at 40 °C ambient. With roughly 13 W of
heat that needs about 400–450 cm² of finned housing area. Use a type II
street lens.

## 5. LED driver: PIC-controlled boost, peak current mode

### How the loop works

1. PWM (200 kHz) starts each cycle: COG2 turns Q1 on through the gate driver.
2. Inductor current ramps up and shows as a voltage on RSW (50 mΩ) in Q1's source.
3. The PRG subtracts a slope from the error-amplifier output. The comparator trips when the RSW voltage reaches that level, and COG2 turns Q1 off. This is cycle-by-cycle peak current control, done entirely in hardware.
4. OPA1 amplifies the LED current sense voltage (0.1 Ω in the string's low side) by 20.
5. OPA2 is the error amplifier. It compares OPA1's output with the DAC reference, and its output (with a type II RC network) sets the peak current level.
6. Firmware changes brightness by writing the DAC. It does not touch the fast loop.

### Operating points (20 W out)

| Vin | Duty | Iin | Ripple | Peak current | Efficiency |
|---|---|---|---|---|---|
| 11.2 V (LVD) | 0.688 | 1.87 A | 0.57 A | 2.15 A | 95.4 % |
| 12.8 V | 0.644 | 1.63 A | 0.61 A | 1.93 A | 95.8 % |
| 14.4 V | 0.599 | 1.45 A | 0.63 A | 1.76 A | 96.1 % |

At 50 % brightness (10 W) the estimate is 95.1 %, at 30 % (6 W) 93.6 %.

### Loop numbers

| Item | Value |
|---|---|
| Right-half-plane zero | 14.5 kHz at 11.2 V (worst case), 23.9 kHz at 14.4 V |
| Crossover | 1–2 kHz (below RHP zero / 5 = 2.9 kHz) |
| Inductor down-slope at RSW | 18.1 mV/µs worst case |
| Slope compensation (PRG) | about 14 mV/µs (at least 9.1 mV/µs, half the down-slope, to stop subharmonic oscillation above 50 % duty) |
| Peak RSW voltage | 108 mV at 2.15 A; set the trip ceiling (error amp clamp) to about 150 mV → 3 A limit |
| LED sense | 56.5 mV at 0.565 A → 1.13 V after OPA1 (gain 20) → DAC full-scale reference 1.13 V |

Tune the type II network on the bench by injecting into the loop or by
checking the LED current step response to a DAC step. Aim for 45° phase
margin or more across 11.2–14.4 V.

### Component values

| Ref | Part | Value / rating |
|---|---|---|
| L1 | Shielded power inductor | 68 µH, Isat ≥ 3.5 A, DCR ≤ 35 mΩ, low-loss ferrite |
| Q1 | N-MOSFET | 60 V, Rds(on) ≤ 10 mΩ at 10 V, Qg ≤ 25 nC |
| U2 | Low-side gate driver | UCC27517 (or Microchip MCP1416), 10 V supply, 5 V logic input from COG2 |
| D1 | Schottky | 60 V, 3–5 A, Vf ≈ 0.42 V at 0.6 A |
| RSW | Switch current sense | 50 mΩ, 1 %, 0.5 W, with 100 Ω / 470 pF RC filter to the comparator and leading-edge blanking from COG2 |
| RLED | LED current sense | 0.1 Ω, 1 %, 0.25 W, low side of the string |
| Q2 | LED disconnect | Logic-level N-MOSFET, 60 V, ≤ 20 mΩ at 4.5 V, driven from a PIC pin |
| COUT | Ceramic X7R | 4 × 4.7 µF 100 V |
| CIN | Ceramic + polymer | 2 × 10 µF 25 V + 100 µF 25 V |
| OVP divider | 330 kΩ / 39 kΩ | 42.5 V → 4.48 V into a comparator, COG2 auto-shutdown |
| Vled divider | 330 kΩ / 39 kΩ (shared) | Also read by ADC for LED fault diagnosis |

### Loss budget at 12.8 V in, 20 W out

| Loss | mW |
|---|---|
| Schottky diode | 237 |
| Q1 switching | 117 |
| Inductor copper | 94 |
| Switch sense resistor (50 mΩ) | 86 |
| Inductor core | 80 |
| PIC + 5 V LDO | 64 |
| Gate drive (10 V) | 50 |
| Q1 Coss | 39 |
| PCB copper and capacitor ESR | 35 |
| LED sense resistor (0.1 Ω) | 32 |
| Q1 conduction | 24 |
| Gate driver quiescent | 10 |
| Disconnect FET | 6 |
| **Total** | **874 → 95.8 %** |

Compared with a dedicated LED controller, the PIC version moves the LED
sense resistor to the low side (lower loss, since the op-amp provides the
gain) but needs a larger switch sense resistor so the comparator sees a
clean signal. The net result is within half a point.

## 6. MPPT charger: PIC-controlled synchronous buck

A battery is a stiff load, so in a buck the duty cycle sets the panel
voltage directly (Vpanel ≈ Vbat / D). No fast loop is needed. Firmware
writes the duty cycle; hardware only handles fast faults.

### Control

| Function | How |
|---|---|
| Switching | 10-bit PWM at 100 kHz → COG1 in half-bridge mode with dead-band (about 50 ns rising and falling) → UCC27211 high/low side driver |
| PWM resolution | 32 MHz / 100 kHz = 320 steps (0.31 % per step), about 60–90 mV of panel voltage per step |
| MPPT | Perturb and observe on battery-side power (Vbat × Ichg), every 100 ms, one PWM step per move. Full duty sweep every 10 minutes for partial shading |
| CC/CV | If Ichg > 5.8 A or Vbat > 14.4 V, firmware lowers duty and this overrides MPPT |
| Fast over-current | INA181 output into a comparator; trip goes to COG1 auto-shutdown (both FETs off within one cycle) |
| Battery over-voltage | Vbat divider into a comparator, also to COG1 auto-shutdown (catches a BMS open-circuit) |
| Low-current mode | Below 0.3 A charge current, disable the low-side FET output in COG1 (asynchronous operation through Q4's body diode or a parallel Schottky). This stops the synchronous buck from pulling current back out of the battery at dawn, dusk and under heavy cloud |

### Component values

| Ref | Part | Value / rating |
|---|---|---|
| Panel | 80 W mono | Vmp 18–20 V (36–40 cells), Voc ≤ 23 V at 25 °C |
| TVS | SMBJ28A | Panel input surge |
| U3 | Ideal diode controller | LM74700-Q1 + one 60 V, ≤ 4 mΩ N-MOSFET: reverse polarity and night back-feed blocking |
| U4 | Half-bridge driver | UCC27211, 10 V supply, bootstrap 0.22 µF |
| Q3, Q4 | N-MOSFETs | 60 V, Rds(on) ≤ 5 mΩ, Qg ≤ 30 nC |
| L2 | Power inductor | 22 µH, Isat ≥ 9 A, DCR ≤ 12 mΩ |
| D2 | Schottky across Q4 (optional) | 60 V 5 A, for low-current mode |
| RSH | Charge current shunt | 2 mΩ, 1 %, 1 W |
| U5 | Current sense amplifier | INA181 (gain 50 → 0.58 V at 5.8 A), REF pin biased about 0.3 V so small reverse current is readable |
| CIN | Ceramic | 4 × 10 µF 50 V |
| COUT | Ceramic + polymer | 2 × 22 µF 25 V + 220 µF 25 V |

Estimated efficiency: 98.4 % at 80 W, 97.6 % at 16 W. Expect about 97 %
measured. Limit max duty to 0.95 so the bootstrap capacitor refreshes. At
65 °C cell temperature a 36-cell panel's Vmp falls to about 15.5 V, still
above the 14.4 V end-of-charge voltage.

## 7. Battery and BMS

| Item | Value |
|---|---|
| Chemistry | LiFePO4, 4S5P of 6 Ah 32700 cells = 12.8 V 30 Ah (384 Wh) |
| Usable | 346 Wh at 90 % depth of discharge |
| Night draw | 146 Wh (136 Wh LED energy + driver loss + standby) |
| Autonomy | 2.4 nights |
| Charge | CC 5.8 A max (0.19 C) to 14.4 V, CV until current < 1.5 A, then stop; optional float 13.6 V |
| Temperature | No charging below 0 °C or above 45 °C (NTC on the pack, read by the PIC ADC) |
| BMS | 4S, ≥ 10 A continuous, cell balancing, OV/UV/OC/short protection |
| Firmware LVD | 12.0 V: force 30 %. 11.2 V: LED off. Reconnect at 12.6 V |

Panel sizing at 4 peak sun hours (worst month, adjust for your site) and
0.8 derating: the minimum is 49 W. An 80 W panel refills two empty nights
in about 3 days; a 60 W panel takes about 9 days.

## 8. Power supplies for the control side

| Rail | From | Load |
|---|---|---|
| 10 V | Battery, low-Iq LDO | UCC27211, UCC27517 |
| 5 V | Battery, low-Iq LDO | PIC16F1769, INA181, dividers |

Run the PIC at 5 V. The op-amps, comparators and DAC get more headroom
and the 1.13 V LED reference sits well inside the DAC range.

## 9. Firmware

Main loop on a 1 ms timer tick. All fast protection is in hardware
(comparator → COG auto-shutdown), so a firmware hang cannot leave a FET
stuck on. The watchdog and brown-out reset are enabled.

| Task | Rate | What it does |
|---|---|---|
| ADC scan | 1 ms | Vpanel, Vbat, Ichg, Iled, Vled, NTCs; 16-sample average |
| Day/night state | 1 s | Dusk: Vpanel < 5 V for 5 min. Dawn: Vpanel > 8 V for 5 min |
| MPPT + CC/CV | 100 ms | Day only. P&O step, then apply current and voltage limits |
| LED schedule | 1 s | Night only. Writes the DAC: 100 % / 50 % / 30 % by hours since dusk; 2 s soft ramp between levels |
| SOC | 1 s | Coulomb count from Ichg and Iled × Vled / Vbat; reset to 100 % at end of charge |
| Adaptive dimming | at dusk | If SOC < 50 %, scale the whole night profile down so the lamp lasts until dawn |
| Fault handler | 10 ms | Reads COG shutdown flags, logs the fault, retries after 1 s, gives up after 5 tries until the next night/day |
| Calibration | at production | Store LED sense offset (DAC trim with LED off) and Vbat gain in high-endurance flash |

Start-up order at dusk: charger already off, enable 10 V rail, turn Q2
on, ramp the DAC from 0 over 2 s, check that Vled settles in the expected
33–38 V range. Vled at the OVP level means an open string; Vled near Vbat
with high input current means a short.

The op-amp offset matters at a 56.5 mV sense level (a few mV of offset is
a few % of current error). The production calibration step trims it out.

## 10. Efficiency summary

| Path | Estimate | Requirement |
|---|---|---|
| Battery → LED (PIC boost driver) | 95.8 % (95.4–96.1 % over battery range) | > 91 % |
| Panel → battery (MPPT 99 % × buck 98.4 %) | 97.5 % | > 91 % |
| Panel → LED, including battery cycle (96 %) | 89.7 % | see below |

If the 91 % has to hold end to end, make the boost synchronous: replace
D1 with a FET and drive it from the second COG2 output with dead-band
(the same way COG1 drives the charger). That removes most of the 237 mW
diode loss and lifts the driver to about 97 %, giving about 91 % end to
end. The battery cycle loss cannot be designed out, because the lamp runs
when the panel produces nothing.

## 11. Protection

| Fault | Handling |
|---|---|
| Panel reverse polarity | Ideal-diode FET stays off |
| Night back-feed into panel | Ideal-diode FET blocks; COG1 shut down at night |
| Reverse charger current at low light | Low-current mode turns off Q4 below 0.3 A |
| Surge on panel cable | SMBJ28A TVS; all FETs and caps on that node rated 60 V |
| Open LED string | OVP comparator → COG2 shutdown at 42.5 V |
| Shorted LED string | Firmware opens Q2; 5 A fuse on the driver input as backup (a boost has a DC path from input to output) |
| Boost over-current | Comparator peak limit about 3 A, every cycle |
| Battery reverse | Fuse plus reverse-polarity FET in the battery line, or a keyed connector |
| Over-temperature | LED board NTC; firmware lowers the DAC above 85 °C board temperature |
| Firmware hang | Watchdog reset; COG outputs default to off |

## 12. Layout and thermal notes

- Boost hot loop Q1 → D1 → COUT → ground return to Q1 source: keep it under 2 cm² on the top layer over a solid ground plane.
- Buck hot loop CIN → Q3 → Q4 → CIN: same rule.
- Kelvin-route RSW, RLED and RSH. Put the RSW RC filter right at the PIC comparator pin.
- Keep the PIC's analog ground (op-amp, comparator, DAC returns) as one star point at RLED's ground end, away from the switch-node return currents.
- 2 oz copper for power paths. Thermal vias under Q1, D1, Q3, Q4.
- Seal the board to IP66 or better and fit a pressure-equalising vent.

## 13. Efficiency test procedure

1. Power the LED driver from a bench supply through 4-wire leads. Measure input voltage at the board terminals and input current with a calibrated shunt or power analyzer (0.1 % class or better).
2. Measure LED string voltage across the string and LED current through a separate 4-wire shunt.
3. Run at 20 W until the heatsink is stable (about 30 minutes at 25 °C ambient).
4. Record efficiency = (Vled × Iled) / (Vin × Iin) at 11.2, 12.8 and 14.4 V, and at 100 %, 50 % and 30 % brightness. Include the PIC and LDO supply current in Iin.
5. Pass: every point ≥ 91 %. Design target: ≥ 95 % at 100 %.
6. Repeat for the charger with a solar array simulator or a current-limited supply set to the panel's Vmp/Imp, measuring panel-side and battery-side power. Also check MPPT tracking by comparing harvested power with the simulator's maximum power point.

## 14. Key parts summary

| Function | Part / spec |
|---|---|
| Controller | PIC16F1769 (or dsPIC33CK for full digital control) |
| LED | 12 × 3535 ceramic high-power LED, ≥ 1 A rated, 5000–5700 K, CRI ≥ 70 |
| Boost FET Q1 | 60 V, ≤ 10 mΩ, Qg ≤ 25 nC |
| Boost diode D1 | 60 V 3–5 A Schottky, low Vf |
| Boost inductor L1 | 68 µH, Isat ≥ 3.5 A, DCR ≤ 35 mΩ |
| Boost gate driver | UCC27517 or MCP1416 |
| LED disconnect Q2 | Logic-level 60 V, ≤ 20 mΩ |
| Charger FETs Q3, Q4 | 60 V, ≤ 5 mΩ, Qg ≤ 30 nC |
| Charger inductor L2 | 22 µH, Isat ≥ 9 A, DCR ≤ 12 mΩ |
| Half-bridge driver | UCC27211 |
| Ideal diode | LM74700-Q1 + 60 V ≤ 4 mΩ FET |
| Current sense amp | INA181 |
| Regulators | 10 V and 5 V low-Iq LDOs |
| Battery | LiFePO4 4S5P 32700, 30 Ah, 4S BMS with balancing |
| Panel | 80 W mono, Vmp 18–20 V |
