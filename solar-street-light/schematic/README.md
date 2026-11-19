# Schematic renders

PNG renders of the four KiCad sheets, and `schematic.pdf` (all five pages,
root included). The source is the KiCad project in `../kicad/`; these files
are exported from it:

```
kicad-cli sch export pdf -o schematic.pdf ../kicad/solar_light.kicad_sch
pdftoppm -r 150 -png -f 2 -l 2 -singlefile schematic.pdf sheet1_charger   # pages 3-5 likewise
```

| File | Sheet |
|---|---|
| `sheet1_charger.png` | MPPT charger power stage |
| `sheet2_led_driver.png` | Boost LED driver |
| `sheet3_controller.png` | SC95F8523, gate-drive and 5 V supplies, connectors |
| `sheet4_drivers.png` | IR2104 and UCC27511 drivers, current sense, fault comparators |
