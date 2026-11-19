# KiCad project: SC95F8523 solar street light

KiCad 7 schematic for the SC95F8523 version of the design (`../SC95F8523.md`).
Open `solar_light.kicad_pro` in KiCad 7 or later. `solar_light_schematic.pdf` is a
PDF export of all five pages.

| Sheet | File | Contents |
|---|---|---|
| Root | `solar_light.kicad_sch` | Sheet index |
| 1 | `charger.kicad_sch` | MPPT charger power stage (sync buck, ideal diode, shunt, battery) |
| 2 | `led_driver.kicad_sch` | Boost LED driver, LED disconnect, LED string |
| 3 | `controller.kicad_sch` | SC95F8523, gate-drive supply (VDRV), L78L05 5 V rail, crystal, NTCs, connectors |
| 4 | `drivers.kicad_sch` | IR2104, UCC27511, INA181 x2, LM4040 reference, LM2901 fault comparators |

## How it is built

`generate.py` writes every file from one table of parts, positions and pin-to-net
assignments. Pins connect through a short wire to a global label or a power symbol,
so the netlist is exactly that table. `verify.py` exports the netlist with
`kicad-cli` and checks:

- every pin is on the net the table says,
- no net has only one connection,
- every net with a power-input pin has a driver or a PWR_FLAG,
- every footprint name exists in the KiCad footprint library.

```
python3 generate.py && python3 verify.py
```

If you edit the schematic in KiCad by hand, stop using `generate.py`, or your
changes will be overwritten the next time it runs.

## Symbols

Library symbols (with their pin numbers) come from the KiCad 7 symbol library:
IR2104, UCC27511ADBV, INA181, LM2901, LM74700, L78L05, LM4040-2.5, and the
passive parts. Two symbols are custom, in `solar_light.kicad_sym` (registered
in `sym-lib-table`):

- **SC95F8523**: pins from the SinOne datasheet V0.3, 28-pin package.
- **BMS_4S**: placeholder for the off-board battery management board.

## Before layout

- **No footprint yet**: Q1, Q3, Q4, Q5 (power MOSFETs), L1, L2 (inductors) and
  F1, F2 (fuses). Pick the exact parts, then assign footprints. The KiCad MOSFET
  symbol is G-D-S = 1-2-3; check that against the footprint's pad numbers.
- **Q2** has a SOT-23 footprint, which assumes the part's pinout is G-S-D = 1-2-3.
  Check it against the part you choose.
- **SC95F8523 footprint** is SOIC-28W (7.5 mm body). Confirm the SOP28 body width
  from SinOne's package drawing.
- **Off-board parts** (panel PV1, battery BT1, BMS1, LEDs D4–D15, NTCs TH1/TH2) are
  marked "exclude from board" and "exclude from BOM". They connect through J1, J2,
  J6, J7, J8.
- **No ERC run**: KiCad 7's command line has no ERC, so run Inspect → Electrical
  Rules Checker in the KiCad GUI once. `verify.py` covers connectivity and power
  drivers but not every ERC rule.
