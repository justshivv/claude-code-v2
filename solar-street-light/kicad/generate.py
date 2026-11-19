#!/usr/bin/env python3
"""Generate the KiCad 7 project for the SC95F8523 solar street light.

Every component, its position and the net on each pin are listed below as
data. The script writes:

  solar_light.kicad_pro / .kicad_sch (root)   project and root sheet
  charger.kicad_sch, led_driver.kicad_sch,     the four sub-sheets
  controller.kicad_sch, drivers.kicad_sch
  solar_light.kicad_sym + sym-lib-table        custom symbols (SC95F8523, BMS)

Connections are made with a short wire from each pin to a global label or
a power symbol, so the netlist is exactly the PIN->NET table below.
`verify.py` exports the netlist with kicad-cli and checks it against this
table.

Library symbols are copied from the KiCad 7 symbol library installed at
/usr/share/kicad/symbols (set KICAD_SYMBOL_DIR to override).
"""
import json
import math
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse, dump  # noqa: E402

SYMDIR = os.environ.get('KICAD_SYMBOL_DIR', '/usr/share/kicad/symbols')
PROJECT = 'solar_light'
ROOT_UUID = '4d1f6c3e-0b55-4c8e-9a51-5f2a1d3c0001'
NS = uuid.UUID('6f1a8f8e-2c4b-4a3e-9b0e-111111111111')
_counter = [0]


def uid(tag=None):
    """Deterministic UUIDs so regenerating gives a stable diff."""
    _counter[0] += 1
    return str(uuid.uuid5(NS, f'{tag}-{_counter[0]}'))


def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def f(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.') if isinstance(v, float) else str(v)


POWER_NETS = {'GND': ('power:GND', 270), '+5V': ('power:+5V', 90),
              '+10V': ('power:+10V', 90)}
NC = 'NC'

# ---------------------------------------------------------------------------
# Footprints (checked against the KiCad 7 footprint library by verify.py)
# ---------------------------------------------------------------------------
R0603 = 'Resistor_SMD:R_0603_1608Metric'
R1206 = 'Resistor_SMD:R_1206_3216Metric'
R2512 = 'Resistor_SMD:R_2512_6332Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
C1210 = 'Capacitor_SMD:C_1210_3225Metric'
CP63 = 'Capacitor_SMD:CP_Elec_6.3x7.7'
CP8 = 'Capacitor_SMD:CP_Elec_8x10'
TANT_A = 'Capacitor_Tantalum_SMD:CP_EIA-3216-18_Kemet-A'
D_SMB = 'Diode_SMD:D_SMB'
D_SMC = 'Diode_SMD:D_SMC'
TB2 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'
PH2 = 'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical'
HDR3 = 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical'
HDR4 = 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical'
SOIC8 = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
SOIC14 = 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'
SOIC28W = 'Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm'
SOT223 = 'Package_TO_SOT_SMD:SOT-223-3_TabPin2'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
XTAL = 'Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm'


class Comp:
    def __init__(self, ref, lib, value, x, y, rot=0, pins=None, fp='', unit=1,
                 board=True, desc=None, refpos=None):
        self.ref, self.lib, self.value = ref, lib, value
        self.x, self.y, self.rot = x, y, rot
        self.pins = pins or {}
        self.fp, self.unit, self.board = fp, unit, board
        self.desc = desc
        self.refpos = refpos


def R(ref, val, x, y, n1, n2, rot=0, fp=R0603, **kw):
    return Comp(ref, 'Device:R', val, x, y, rot, {'1': n1, '2': n2}, fp, **kw)


def C(ref, val, x, y, n1, n2, rot=0, fp=C0603, **kw):
    return Comp(ref, 'Device:C', val, x, y, rot, {'1': n1, '2': n2}, fp, **kw)


def CP(ref, val, x, y, n1, n2, rot=0, fp=CP63, **kw):
    return Comp(ref, 'Device:C_Polarized', val, x, y, rot, {'1': n1, '2': n2}, fp, **kw)


def NMOS(ref, val, x, y, g, d, s, rot=0, fp='', **kw):
    return Comp(ref, 'Device:Q_NMOS_GDS', val, x, y, rot, {'1': g, '2': d, '3': s}, fp, **kw)


def FLAG(ref, x, y, net, rot=0):
    return Comp(ref, 'power:PWR_FLAG', 'PWR_FLAG', x, y, rot, {'1': net}, unit=1)


# ---------------------------------------------------------------------------
# Sheet 1: MPPT charger power stage
# ---------------------------------------------------------------------------
def divider(rt, rb, cc, vt, vb, x, y, top, mid, cval='100n'):
    """Top resistor, bottom resistor and filter cap on the mid node."""
    return [R(rt, vt, x, y, top, mid), R(rb, vb, x, y + 35.56, mid, 'GND'),
            C(cc, cval, x + 12.7, y + 35.56, mid, 'GND')]


S1 = [
    Comp('PV1', 'Device:Solar_Cells', '80 W panel', 25.4, 90.17, 0,
         {'1': 'VPV', '2': 'GND'}, board=False),
    Comp('J1', 'Connector_Generic:Conn_01x02', 'PANEL', 50.8, 90.17, 180,
         {'1': 'VPV', '2': 'GND'}, TB2, refpos=((48.26, 81.28), (48.26, 97.79))),
    FLAG('#FLG01', 40.64, 63.5, 'VPV'),
    Comp('D3', 'Device:D_TVS', 'SMBJ28CA', 86.36, 90.17, 90, {'1': 'GND', '2': 'VPV'}, D_SMB,
         refpos=((88.9, 88.9), (88.9, 91.44))),
    *divider('R1', 'R2', 'C20', '200k', '10k', 111.76, 76.2, 'VPV', 'VPV_SNS'),
    NMOS('Q5', '60V 4mOhm', 160.02, 63.5, 'Q5_G', 'VIN_BUCK', 'VPV', rot=270,
         refpos=((166.37, 69.85), (166.37, 72.39))),
    Comp('U3', 'Power_Management:LM74700', 'LM74700-Q1', 162.56, 104.14, 0,
         {'1': 'U3_VCAP', '2': 'GND', '3': 'VPV', '4': 'VIN_BUCK', '5': 'Q5_G', '6': 'VPV'},
         'Package_TO_SOT_SMD:SOT-23-6', refpos=((172.72, 102.87), (172.72, 105.41))),
    C('C2', '100n', 139.7, 134.62, 'U3_VCAP', 'VPV', rot=90),
    C('C3', '10u 50V', 195.58, 96.52, 'VIN_BUCK', 'GND', fp=C1210),
    C('C7', '10u 50V', 210.82, 96.52, 'VIN_BUCK', 'GND', fp=C1210),
    C('C8', '10u 50V', 226.06, 96.52, 'VIN_BUCK', 'GND', fp=C1210),
    C('C9', '10u 50V', 241.3, 96.52, 'VIN_BUCK', 'GND', fp=C1210),
    NMOS('Q3', '60V 5mOhm', 271.78, 76.2, 'HO', 'VIN_BUCK', 'SW_C'),
    NMOS('Q4', '60V 5mOhm', 271.78, 124.46, 'LO', 'SW_C', 'GND'),
    Comp('D2', 'Device:D_Schottky', '60V 5A', 304.8, 124.46, 270,
         {'1': 'SW_C', '2': 'GND'}, D_SMC, refpos=((307.34, 123.19), (307.34, 125.73))),
    Comp('L2', 'Device:L', '22uH 9A', 337.82, 96.52, 90, {'1': 'SW_C', '2': 'VCHG'}),
    C('C12', '22u 25V', 35.56, 175.26, 'VCHG', 'GND', fp=C1210),
    C('C13', '22u 25V', 50.8, 175.26, 'VCHG', 'GND', fp=C1210),
    CP('C14', '220u 25V', 66.04, 175.26, 'VCHG', 'GND', fp=CP8),
    R('R12', '2m 1W', 99.06, 170.18, 'VCHG', 'VCHG_SH', rot=90, fp=R2512),
    Comp('F1', 'Device:Fuse', '10A', 134.62, 170.18, 90, {'1': 'VCHG_SH', '2': 'VBAT'}),
    *divider('R3', 'R4', 'C21', '91k', '10k', 165.1, 157.48, 'VBAT', 'VBAT_SNS'),
    Comp('J2', 'Connector_Generic:Conn_01x02', 'BATTERY', 220.98, 175.26, 0,
         {'1': 'VBAT', '2': 'GND'}, TB2, refpos=((218.44, 168.91), (218.44, 182.88))),
    FLAG('#FLG02', 236.22, 152.4, 'VBAT'),
    FLAG('#FLG03', 251.46, 152.4, 'GND'),
    Comp('BT1', 'Device:Battery', 'LiFePO4 4S5P 12.8V 30Ah', 279.4, 165.1, 0,
         {'1': 'VBAT', '2': '~'}, board=False),
    Comp('BMS1', 'solar_light:BMS_4S', 'BMS 4S >=10A', 279.4, 176.53, 0,
         {'1': '~', '2': 'GND'}, board=False, refpos=((285.75, 175.26), (285.75, 177.8))),
]
S1_NOTES = [
    (25.4, 30.48, 'Sheet 1: MPPT charger power stage. Synchronous buck, 100 kHz, '
     'driven by U4 (sheet 4) from PWM0/PWM1.', 2.0),
    (25.4, 210.82,
     'Notes\n'
     '- PV1: 80 W mono panel, Vmp 18-20 V, Voc <= 23 V. Off-board, connects through J1.\n'
     '- Q3, Q4, Q5: 60 V N-MOSFET, Rds(on) <= 5 mOhm (Q5 <= 4 mOhm), Qg <= 30 nC. '
     'L2: 22 uH, Isat >= 9 A, DCR <= 12 mOhm. F1: 10 A.\n'
     '   These five have no footprint yet: choose the exact part and assign it.\n'
     '- Everything on VPV / VIN_BUCK / SW_C is rated 60 V or more. C3, C7-C9 are X7R.\n'
     '- Q5 + U3 block reverse polarity and night-time back-feed through Q3\'s body diode.\n'
     '- D2 carries the inductor current during the 125 ns dead time.\n'
     '- R12 is a Kelvin shunt: route VCHG and VCHG_SH to U5 as a tight pair from the pads.\n'
     '- Hot loop C3/C7-C9 -> Q3 -> Q4 must be as small as possible.\n'
     '- BT1 (LiFePO4 4S5P, 12.8 V 30 Ah) and BMS1 are off-board; they connect through J2.', 1.5),
]

# ---------------------------------------------------------------------------
# Sheet 2: LED boost power stage
# ---------------------------------------------------------------------------
S2 = [
    Comp('F2', 'Device:Fuse', '5A', 30.48, 76.2, 90, {'1': 'VBAT', '2': 'VBAT_F2'}),
    C('C15', '10u 25V', 55.88, 96.52, 'VBAT_F2', 'GND', fp=C1210),
    C('C16', '10u 25V', 71.12, 96.52, 'VBAT_F2', 'GND', fp=C1210),
    CP('C17', '100u 25V', 86.36, 96.52, 'VBAT_F2', 'GND', fp=CP63),
    Comp('L1', 'Device:L', '100uH 3.5A', 114.3, 76.2, 90, {'1': 'VBAT_F2', '2': 'SW_B'}),
    NMOS('Q1', '60V 10mOhm', 142.24, 99.06, 'GATE_B', 'SW_B', 'ISW'),
    R('R13', '33m 1%', 144.78, 134.62, 'ISW', 'GND', fp=R1206),
    Comp('D1', 'Device:D_Schottky', '60V 3-5A', 172.72, 76.2, 180,
         {'1': 'VLED', '2': 'SW_B'}, D_SMC, refpos=((167.64, 71.12), (167.64, 81.28))),
    C('C18', '4.7u 100V', 200.66, 96.52, 'VLED', 'GND', fp=C1210),
    C('C19', '4.7u 100V', 215.9, 96.52, 'VLED', 'GND', fp=C1210),
    C('C22', '4.7u 100V', 231.14, 96.52, 'VLED', 'GND', fp=C1210),
    C('C23', '4.7u 100V', 246.38, 96.52, 'VLED', 'GND', fp=C1210),
    *divider('R5', 'R6', 'C24', '430k', '20k', 271.78, 76.2, 'VLED', 'VLED_SNS'),
    Comp('J6', 'Connector_Generic:Conn_01x02', 'LED STRING', 317.5, 96.52, 0,
         {'1': 'VLED', '2': 'LED_K'}, TB2, refpos=((314.96, 90.17), (314.96, 104.14))),
    R('R21', '100', 337.82, 99.06, 'LED_EN', 'Q2_G', rot=90),
    R('R22', '100k', 350.52, 119.38, 'Q2_G', 'GND'),
    NMOS('Q2', '60V 20mOhm LL', 373.38, 99.06, 'Q2_G', 'LED_K', 'ILED_P', fp=SOT23),
    R('R14', '0.1 1%', 375.92, 134.62, 'ILED_P', 'GND', fp=R1206),
]
# 12 LEDs in series on the LED board (off-board), pins touching end to end
for i in range(12):
    x = 63.5 + i * 7.62
    S2.append(Comp(f'D{4 + i}', 'Device:LED', '12x 3535 LED, 0.565 A' if i == 0 else '3535',
                   x, 172.72, 180,
                   {'2': 'VLED' if i == 0 else '~', '1': 'LED_K' if i == 11 else '~'},
                   board=False, refpos=((x - 1.905, 167.64), (63.5 - 3.81, 179.07)),
                   desc='hideval' if i else None))
S2_NOTES = [
    (25.4, 30.48, 'Sheet 2: LED driver power stage. Boost, 100 kHz, gate from U7 '
     '(sheet 4) on PWM2. 12 LEDs in series, 35.4 V at 0.565 A = 20 W.', 2.0),
    (25.4, 154.94, 'LED board (off-board, excluded from PCB): D4-D15 in series '
     'between J6 pin 1 (VLED) and J6 pin 2 (LED_K). NTC2 for the LED board is on sheet 3.', 1.5),
    (25.4, 200.66,
     'Notes\n'
     '- Q1: 60 V N-MOSFET, Rds(on) <= 10 mOhm, Qg <= 25 nC. L1: 100 uH, Isat >= 3.5 A, DCR <= 40 mOhm. '
     'F2: 5 A. These three have no footprint yet.\n'
     '- Q2: logic-level 60 V N-MOSFET, Rds(on) <= 20 mOhm at 4.5 V (SOT-23 footprint assumes G-S-D = 1-2-3; check the part).\n'
     '- F2 protects against a shorted LED string: a boost has a DC path from input to output.\n'
     '- Hot loop Q1 -> D1 -> C18/C19/C22/C23 -> R13 must be as small as possible.\n'
     '- R13 feeds only the over-current comparator (sheet 4). LED current is regulated in firmware '
     'from R14 through U6.\n'
     '- R14: Kelvin connect ILED_P and the R14 ground pad to U6 IN+ / IN-.\n'
     '- R5/R6: ADC reading of the LED voltage and the 43.3 V over-voltage trip.\n'
     '- Optional synchronous boost: Q6 (60 V, <=14 mOhm) across D1, gate from PWM3 through a '
     'second IR2104 (its LO/HO pair gives the dead time); keep D1 across Q6.', 1.5),
]

# ---------------------------------------------------------------------------
# Sheet 3: SC95F8523, supplies, connectors
# ---------------------------------------------------------------------------
U1_PINS = {'1': '+5V', '2': NC, '3': 'GND', '4': 'XIN', '5': 'XOUT', '6': 'RST',
           '7': 'TCK', '8': 'TDIO', '9': 'PIR_IN', '10': 'LED_EN', '11': NC,
           '12': 'NTC_LED', '13': 'NTC_BAT', '14': 'VLED_SNS', '15': 'ILED',
           '16': 'ICHG', '17': 'VBAT_SNS', '18': 'VPV_SNS', '19': 'RXD', '20': 'TXD',
           '21': NC, '22': NC, '23': NC, '24': 'FLT', '25': NC, '26': 'IN_B',
           '27': 'BUCK_SD', '28': 'BUCK_IN'}
S3 = [
    Comp('U1', 'solar_light:SC95F8523', 'SC95F8523 (SOP28)', 101.6, 104.14, 0, U1_PINS, SOIC28W,
         refpos=((76.2, 82.55), (76.2, 125.73))),
    C('C10', '100n', 33.02, 175.26, '+5V', 'GND'),
    C('C11', '10u', 48.26, 175.26, '+5V', 'GND', fp=C1206),
    R('R9', '10k', 63.5, 175.26, '+5V', 'RST'),
    Comp('Y1', 'Device:Crystal', '32.768kHz', 101.6, 172.72, 0, {'1': 'XIN', '2': 'XOUT'}, XTAL,
         refpos=((99.06, 166.37), (96.52, 177.8))),
    C('C25', '12p', 86.36, 200.66, 'XIN', 'GND'),
    C('C26', '12p', 116.84, 200.66, 'XOUT', 'GND'),
    # gate-drive supply: battery through an RC filter (IR2104 needs 10-20 V)
    R('R47', '10', 205.74, 66.04, 'VBAT', 'VDRV', rot=90, fp=R0603),
    C('C49', '10u 25V', 223.52, 78.74, 'VDRV', 'GND', fp=C1206),
    C('C50', '100n', 238.76, 78.74, 'VDRV', 'GND'),
    FLAG('#FLG04', 254.0, 60.96, 'VDRV'),
    # 5 V logic rail
    Comp('U9', 'Regulator_Linear:L78L05_SOT89', 'L78L05 (LM78L05)', 213.36, 134.62, 0,
         {'1': '+5V', '2': 'GND', '3': 'VBAT'}, 'Package_TO_SOT_SMD:SOT-89-3',
         refpos=((199.39, 127.0), (208.28, 127.0))),
    C('C30', '1u 50V', 187.96, 144.78, 'VBAT', 'GND', fp=C1206),
    C('C31', '10u 16V', 238.76, 144.78, '+5V', 'GND', fp=C1206),
    # NTCs
    R('R10', '100k 1%', 330.2, 152.4, '+5V', 'NTC_BAT'),
    C('C32', '100n', 342.9, 175.26, 'NTC_BAT', 'GND'),
    Comp('J7', 'Connector_Generic:Conn_01x02', 'NTC BAT', 368.3, 175.26, 0,
         {'1': 'NTC_BAT', '2': 'GND'}, PH2, refpos=((365.76, 168.91), (365.76, 182.88))),
    Comp('TH1', 'Device:Thermistor_NTC', '10k B3950', 391.16, 175.26, 0,
         {'1': 'NTC_BAT', '2': 'GND'}, board=False),
    R('R11', '100k 1%', 330.2, 195.58, '+5V', 'NTC_LED'),
    C('C33', '100n', 342.9, 218.44, 'NTC_LED', 'GND'),
    Comp('J8', 'Connector_Generic:Conn_01x02', 'NTC LED', 368.3, 218.44, 0,
         {'1': 'NTC_LED', '2': 'GND'}, PH2, refpos=((365.76, 212.09), (365.76, 226.06))),
    Comp('TH2', 'Device:Thermistor_NTC', '10k B3950', 391.16, 218.44, 0,
         {'1': 'NTC_LED', '2': 'GND'}, board=False),
    # Connectors
    Comp('J3', 'Connector_Generic:Conn_01x04', 'PROG', 175.26, 180.34, 0,
         {'1': '+5V', '2': 'TCK', '3': 'TDIO', '4': 'GND'}, HDR4,
         refpos=((172.72, 173.99), (172.72, 189.23))),
    Comp('J4', 'Connector_Generic:Conn_01x03', 'PIR', 175.26, 203.2, 0,
         {'1': '+5V', '2': 'PIR_IN', '3': 'GND'}, HDR3,
         refpos=((172.72, 196.85), (172.72, 209.55))),
    R('R28', '100k', 143.51, 215.9, 'PIR_IN', 'GND'),
    Comp('J5', 'Connector_Generic:Conn_01x03', 'UART', 175.26, 226.06, 0,
         {'1': 'TXD', '2': 'RXD', '3': 'GND'}, HDR3,
         refpos=((172.72, 219.71), (172.72, 232.41))),
]
S3_NOTES = [
    (25.4, 30.48, 'Sheet 3: SC95F8523 controller, supplies and connectors. '
     'Pin numbers: SOP28/TSSOP28 (SinOne datasheet V0.3).', 2.0),
    (172.72, 40.64, 'Gate-drive supply VDRV = battery (11.2-14.6 V) through R47/C49.\n'
     'IR2104 needs 10-20 V on VCC (UVLO about 8-9.8 V), so no regulator.', 1.5),
    (172.72, 116.84, '5 V logic rail, always on. L78L05: about 3-6 mA quiescent, +/-5 %.\n'
     'ADC uses the internal 2.048 V reference; fault thresholds use U10 (sheet 4).', 1.5),
    (320.04, 137.16, 'NTC inputs: 100k pull-up, 10k B3950 NTC (off-board),\n'
     '12-bit ADC with 2.048 V reference.', 1.5),
    (25.4, 238.76,
     'Notes\n'
     '- Unused pins P1.0, P1.6, P0.5, P0.6, P0.7 and PWM3: set as outputs driven low in firmware.\n'
     '- NTC readings scale with the 5 V rail: correct them with the internal 1/4 VDD ADC channel.\n'
     '- C25/C26: use the load capacitance from the crystal datasheet (typ. 10-15 pF).\n'
     '- Every ADC divider has 100 nF at the divider. Analog ground (dividers, NTCs, U5/U6) joins '
     'power ground at one point near R14.\n'
     '- J3: SinOne 2-wire programming (tCK/tDIO). J4: PIR / motion sensor. J5: service UART.', 1.5),
]

# ---------------------------------------------------------------------------
# Sheet 4: gate drivers, current sense, fault comparators
# ---------------------------------------------------------------------------
S4 = [
    Comp('U4', 'Driver_FET:IR2104', 'IR2104S', 76.2, 76.2, 0,
         {'1': 'VDRV', '2': 'BUCK_IN', '3': 'BUCK_SD', '4': 'GND', '5': 'LO_DRV', '6': 'SW_C',
          '7': 'HO_DRV', '8': 'HB'}, SOIC8),
    R('R29', '10k', 35.56, 106.68, 'BUCK_IN', 'GND'),
    R('R30', '10k', 48.26, 106.68, 'BUCK_SD', 'GND'),
    C('C34', '1u 25V', 30.48, 50.8, 'VDRV', 'GND', fp=C1206),
    C('C35', '100n', 45.72, 50.8, 'VDRV', 'GND'),
    Comp('D16', 'Device:D', 'ES1D (bootstrap)', 132.08, 50.8, 0, {'1': 'HB', '2': 'VDRV'},
         'Diode_SMD:D_SMA'),
    R('R31', '2.2', 127.0, 71.12, 'HO_DRV', 'HO', rot=90),
    R('R32', '2.2', 127.0, 96.52, 'LO_DRV', 'LO', rot=90),
    C('C36', '100n 25V', 152.4, 81.28, 'HB', 'SW_C'),
    Comp('U7', 'Driver_FET:UCC27511ADBV', 'UCC27511ADBV', 76.2, 152.4, 0,
         {'1': 'VDRV', '2': 'OUTH_B', '3': 'OUTL_B', '4': 'GND', '5': 'GND', '6': 'IN_B'},
         'Package_TO_SOT_SMD:SOT-23-6', refpos=((88.9, 140.97), (88.9, 165.1))),
    R('R33', '10k', 45.72, 172.72, 'IN_B', 'GND'),
    C('C37', '1u 25V', 30.48, 139.7, 'VDRV', 'GND', fp=C1206),
    C('C38', '100n', 45.72, 139.7, 'VDRV', 'GND'),
    R('R34', '4.7', 127.0, 142.24, 'OUTH_B', 'GATE_B', rot=90),
    R('R35', '2.2', 127.0, 165.1, 'OUTL_B', 'GATE_B', rot=90),
    # current sense
    Comp('U5', 'Amplifier_Current:INA181', 'INA181A3', 205.74, 71.12, 0,
         {'1': 'U5_OUT', '2': 'GND', '3': 'VCHG', '4': 'VCHG_SH', '5': 'GND', '6': '+5V'},
         'Package_TO_SOT_SMD:SOT-23-6', refpos=((210.82, 62.23), (210.82, 80.01))),
    R('R36', '1k', 246.38, 71.12, 'U5_OUT', 'ICHG', rot=90),
    C('C39', '10n', 264.16, 83.82, 'ICHG', 'GND'),
    C('C40', '100n', 180.34, 50.8, '+5V', 'GND'),
    Comp('U6', 'Amplifier_Current:INA181', 'INA181A1', 205.74, 134.62, 0,
         {'1': 'U6_OUT', '2': 'GND', '3': 'ILED_P', '4': 'GND', '5': 'GND', '6': '+5V'},
         'Package_TO_SOT_SMD:SOT-23-6', refpos=((210.82, 125.73), (210.82, 143.51))),
    R('R37', '1k', 246.38, 134.62, 'U6_OUT', 'ILED', rot=90),
    C('C41', '10n', 264.16, 147.32, 'ILED', 'GND'),
    C('C42', '100n', 180.34, 114.3, '+5V', 'GND'),
    # comparators: signal on -, threshold on +, open-collector outputs to FLT
    Comp('U2', 'Comparator:LM2901', 'LM2901', 50.8, 205.74, 0,
         {'4': 'ISW_F', '5': 'REF_A', '2': 'FLT'}, SOIC14, unit=1),
    Comp('U2', 'Comparator:LM2901', 'LM2901', 116.84, 205.74, 0,
         {'6': 'VLED_SNS', '7': 'REF_B', '1': 'FLT'}, SOIC14, unit=2),
    Comp('U2', 'Comparator:LM2901', 'LM2901', 182.88, 205.74, 0,
         {'10': 'ICHG', '11': 'REF_C', '13': 'FLT'}, SOIC14, unit=3),
    Comp('U2', 'Comparator:LM2901', 'LM2901', 248.92, 205.74, 0,
         {'8': 'VBAT_SNS', '9': 'REF_D', '14': 'FLT'}, SOIC14, unit=4),
    Comp('U2', 'Comparator:LM2901', 'LM2901', 294.64, 205.74, 0,
         {'3': '+5V', '12': 'GND'}, SOIC14, unit=5, refpos=((299.72, 203.2), (299.72, 208.28))),
    C('C43', '100n', 314.96, 205.74, '+5V', 'GND'),
    R('R20', '4.7k', 330.2, 205.74, '+5V', 'FLT'),
    # ISW filter
    R('R38', '100', 299.72, 55.88, 'ISW', 'ISW_F', rot=90),
    C('C44', '1n', 317.5, 68.58, 'ISW_F', 'GND'),
    # 2.5 V reference for the fault thresholds
    R('R48', '3.0k', 391.16, 60.96, '+5V', 'VREF25'),
    Comp('U10', 'Reference_Voltage:LM4040DBZ-2.5', 'LM4040-2.5', 391.16, 93.98, 90,
         {'1': 'VREF25', '2': 'GND'}, SOT23, refpos=((394.97, 92.71), (394.97, 95.25))),
    C('C51', '100n', 378.46, 93.98, 'VREF25', 'GND'),
    # threshold dividers (from VREF25)
    *divider('R39', 'R40', 'C45', '21.0k 1%', '1.0k 1%', 289.56, 101.6, 'VREF25', 'REF_A'),
    *divider('R41', 'R42', 'C46', '3.01k 1%', '10k 1%', 314.96, 101.6, 'VREF25', 'REF_B'),
    *divider('R43', 'R44', 'C47', '8.06k 1%', '10k 1%', 340.36, 101.6, 'VREF25', 'REF_C'),
    *divider('R45', 'R46', 'C48', '6.81k 1%', '10k 1%', 365.76, 101.6, 'VREF25', 'REF_D'),
]
S4_NOTES = [
    (25.4, 30.48, 'Sheet 4: gate drivers, current sense and fault comparators', 2.0),
    (284.48, 160.02, 'Fault thresholds (dividers from VREF25 = 2.500 V, U10):\n'
     'REF_A 0.114 V = 3.4 A in R13 (boost switch)\n'
     'REF_B 1.92 V = 43.2 V on VLED\n'
     'REF_C 1.38 V = 6.9 A charge current\n'
     'REF_D 1.49 V = 15.0 V battery\n'
     'U10 current: about 0.24 mA (R48 0.83 mA minus 0.59 mA in the dividers)', 1.5),
    (25.4, 185.42, 'U2 LM2901: open-collector outputs wired together on FLT (U1 pin 24, active low, '
     'latched, 1 us filter). Signal on -, threshold on +, so a fault pulls FLT low.', 1.5),
    (25.4, 233.68,
     'Notes\n'
     '- R29, R30, R33: PWM pins go high-impedance on a FLT fault; these keep the drivers off (SD low = both FETs off).\n'
     '- U4 IR2104: IN = PWM0 (high = Q3 on, low = Q4 on), SD = P0.1 as GPIO. Dead time (about 520 ns) is set inside U4.\n'
     '   It cannot hold Q4 off while Q3 switches: below about 0.2 A charge current, firmware stops switching with SD.\n'
     '- U4 VS pin is SW_C (sheet 1). D16 (ultrafast, >=100 V) and C36 (100 nF) form the bootstrap supply.\n'
     '- U7 split outputs: R34 sets turn-on speed, R35 turn-off.\n'
     '- U5: charge current 5.8 A -> 1.16 V, 7 A -> 1.40 V.  U6: LED current 0.565 A -> 1.13 V.\n'
     '- U6 IN- (pin 4) must be Kelvin-routed to the ground pad of R14, not to the nearest ground.', 1.5),
]

SHEETS = [
    ('charger', 'MPPT charger', S1, S1_NOTES),
    ('led_driver', 'LED driver', S2, S2_NOTES),
    ('controller', 'Controller and supplies', S3, S3_NOTES),
    ('drivers', 'Drivers, sense, protection', S4, S4_NOTES),
]


# ---------------------------------------------------------------------------
# Custom symbols
# ---------------------------------------------------------------------------
def pin(kind, x, y, ang, name, num, length=5.08, hide=False):
    return (f'(pin {kind} line (at {f(x)} {f(y)} {ang}) (length {f(length)}){" hide" if hide else ""} '
            f'(name {q(name)} (effects (font (size 1.27 1.27)))) '
            f'(number {q(num)} (effects (font (size 1.27 1.27)))))')


def prop(name, val, x, y, hide=False, justify=None):
    j = f' (justify {justify})' if justify else ''
    return (f'(property {q(name)} {q(val)} (at {f(x)} {f(y)} 0) '
            f'(effects (font (size 1.27 1.27)){j}{" hide" if hide else ""}))')


def custom_symbols():
    out = {}
    # SC95F8523, 28 pins
    left = [('1', 'VDD', 'power_in'), ('2', 'P1.0/CMOD', 'bidirectional'), ('3', 'VSS', 'power_in'),
            ('4', 'P5.1/OSCI', 'bidirectional'), ('5', 'P5.0/OSCO', 'bidirectional'),
            ('6', 'P1.1/RST', 'bidirectional'), ('7', 'P1.2/tCK', 'bidirectional'),
            ('8', 'P1.3/tDIO', 'bidirectional'), ('9', 'P1.4/AIN9', 'bidirectional'),
            ('10', 'P1.5/AIN8', 'bidirectional'), ('11', 'P1.6/AIN7', 'bidirectional'),
            ('12', 'P1.7/AIN6', 'bidirectional'), ('13', 'P2.7/AIN5/PWM7', 'bidirectional'),
            ('14', 'P2.6/AIN4/PWM6', 'bidirectional')]
    right = [('28', 'P0.0/PWM0', 'bidirectional'), ('27', 'P0.1/PWM1', 'bidirectional'),
             ('26', 'P0.2/PWM2', 'bidirectional'), ('25', 'P0.3/PWM3', 'bidirectional'),
             ('24', 'P0.4/FLT', 'bidirectional'), ('23', 'P0.5', 'bidirectional'),
             ('22', 'P0.6', 'bidirectional'), ('21', 'P0.7', 'bidirectional'),
             ('20', 'P2.0/USTX0', 'bidirectional'), ('19', 'P2.1/USRX0', 'bidirectional'),
             ('18', 'P2.2/AIN0', 'bidirectional'), ('17', 'P2.3/AIN1', 'bidirectional'),
             ('16', 'P2.4/AIN2/PWM4', 'bidirectional'), ('15', 'P2.5/AIN3/PWM5', 'bidirectional')]
    pins = []
    for i, (num, name, kind) in enumerate(left):
        pins.append(pin(kind, -25.4, 16.51 - i * 2.54, 0, name, num))
    for i, (num, name, kind) in enumerate(right):
        pins.append(pin(kind, 25.4, 16.51 - i * 2.54, 180, name, num))
    out['SC95F8523'] = (
        '(symbol "SC95F8523" (pin_names (offset 1.016)) (in_bom yes) (on_board yes) '
        + prop('Reference', 'U', -20.32, 20.32, justify='left')
        + prop('Value', 'SC95F8523', -20.32, -20.32, justify='left')
        + prop('Footprint', SOIC28W, 0, -22.86, hide=True)
        + prop('Datasheet', 'http://www.socmcu.com', 0, -25.4, hide=True)
        + prop('ki_description', 'SinOne 1T 8051 MCU, 32 KB flash, 12-bit ADC, 8x16-bit PWM, 28-pin', 0, 0, hide=True)
        + '(symbol "SC95F8523_0_1" (rectangle (start -20.32 19.05) (end 20.32 -19.05) '
          '(stroke (width 0.254) (type default)) (fill (type background))))'
        + '(symbol "SC95F8523_1_1" ' + ' '.join(pins) + '))')
    # BMS (off-board)
    out['BMS_4S'] = (
        '(symbol "BMS_4S" (pin_names (offset 1.016) hide) (in_bom no) (on_board no) '
        + prop('Reference', 'BMS', 6.35, 1.27, justify='left')
        + prop('Value', 'BMS_4S', 6.35, -1.27, justify='left')
        + prop('Footprint', '', 0, 0, hide=True) + prop('Datasheet', '~', 0, 0, hide=True)
        + '(symbol "BMS_4S_0_1" (rectangle (start -5.08 3.81) (end 5.08 -3.81) '
          '(stroke (width 0.254) (type default)) (fill (type background))) '
          '(text "4S BMS" (at 0 0 0) (effects (font (size 1.27 1.27)))))'
        + '(symbol "BMS_4S_1_1" ' + pin('passive', 0, 6.35, 270, 'B-', '1', 2.54)
        + ' ' + pin('passive', 0, -6.35, 90, 'P-', '2', 2.54) + '))')
    return out


# ---------------------------------------------------------------------------
# Library symbol loading
# ---------------------------------------------------------------------------
_libcache = {}


def load_lib(lib):
    if lib not in _libcache:
        tree = parse(open(os.path.join(SYMDIR, f'{lib}.kicad_sym')).read())[0]
        _libcache[lib] = {s[1][1]: s for s in tree if isinstance(s, list) and s and s[0] == 'symbol'}
    return _libcache[lib]


def flatten(lib, name):
    syms = load_lib(lib)
    s = syms[name]
    ext = [e for e in s if isinstance(e, list) and e[0] == 'extends']
    if not ext:
        return s
    parent = flatten(lib, ext[0][1][1])
    pname = parent[1][1]
    child_props = [e for e in s if isinstance(e, list) and e[0] == 'property']
    out = ['symbol', ('S', name)]
    for e in parent[2:]:
        if isinstance(e, list) and e[0] == 'property':
            continue
        if isinstance(e, list) and e[0] == 'symbol':
            e = ['symbol', ('S', e[1][1].replace(pname, name, 1))] + e[2:]
        out.append(e)
    # put properties right after the header attributes
    head = [e for e in out[2:] if not (isinstance(e, list) and e[0] == 'symbol')]
    subs = [e for e in out[2:] if isinstance(e, list) and e[0] == 'symbol']
    return ['symbol', ('S', name)] + head + child_props + subs


CUSTOM = custom_symbols()


def symbol_def(lib_id):
    lib, name = lib_id.split(':')
    if lib == 'solar_light':
        txt = CUSTOM[name]
        tree = parse(txt)[0]
    else:
        tree = flatten(lib, name)
    return tree


def lib_symbol_text(lib_id):
    tree = symbol_def(lib_id)
    tree = ['symbol', ('S', lib_id)] + tree[2:]
    return dump(tree)


def symbol_pins(lib_id, unit):
    """[(number, name, type, x, y, angle)] for the unit (plus common unit 0)."""
    tree = symbol_def(lib_id)
    res = []
    for sub in tree:
        if not (isinstance(sub, list) and sub and sub[0] == 'symbol'):
            continue
        m = re.match(r'.*_(\d+)_(\d+)$', sub[1][1])
        u = int(m.group(1))
        if u not in (0, unit):
            continue
        for e in sub:
            if isinstance(e, list) and e and e[0] == 'pin':
                at = [a for a in e if isinstance(a, list) and a[0] == 'at'][0]
                nm = [a for a in e if isinstance(a, list) and a[0] == 'name'][0][1][1]
                num = [a for a in e if isinstance(a, list) and a[0] == 'number'][0][1][1]
                res.append((num, nm, e[1], float(at[1]), float(at[2]), int(float(at[3]))))
    return res


def xform(c, px, py):
    a = math.radians(c.rot)
    x = px * math.cos(a) - py * math.sin(a)
    y = px * math.sin(a) + py * math.cos(a)
    return round(c.x + x, 4), round(c.y - y, 4)


def snap(v):
    return round(round(v / 1.27) * 1.27, 4)


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
def sym_instance(c, sheet_path, ref=None, value=None, hide_ref=False, hide_val=False):
    pins = symbol_pins(c.lib, c.unit)
    ref = ref or c.ref
    value = value if value is not None else c.value
    # field positions: right of the part for vertical two-pin parts, above otherwise
    two_pin = len(pins) == 2 and c.lib.startswith('Device:')
    vertical = two_pin and c.rot in (0, 180)
    if c.refpos:
        (rx, ry), (vx, vy) = c.refpos
    elif c.lib == 'Device:Q_NMOS_GDS' and c.rot == 0:
        rx, ry, vx, vy = c.x + 5.08, c.y - 1.27, c.x + 5.08, c.y + 1.27
    elif vertical:
        rx, ry, vx, vy = c.x + 2.54, c.y - 1.27, c.x + 2.54, c.y + 1.27
    elif two_pin:
        rx, ry, vx, vy = c.x - 2.54, c.y - 3.81, c.x - 2.54, c.y + 4.445
    else:
        ys = [xform(c, p[3], p[4])[1] for p in pins]
        top = min(ys + [c.y - 5.08]) - 2.54
        bot = max(ys + [c.y + 5.08]) + 2.54
        rx, ry, vx, vy = c.x - 5.08, top, c.x - 5.08, bot
    fp = c.fp
    fa = 90 if c.rot in (90, 270) else 0
    jf = 'right' if c.rot in (90, 180) else 'left'   # KiCad mirrors justification at 90/180
    hide_val = hide_val or c.desc == 'hideval' or c.lib == 'power:PWR_FLAG'
    lines = [f'(symbol (lib_id {q(c.lib)}) (at {f(c.x)} {f(c.y)} {c.rot}) (unit {c.unit})',
             f'  (in_bom {"yes" if c.board else "no"}) (on_board {"yes" if c.board else "no"}) (dnp no)',
             f'  (uuid {uid("sym")})',
             f'  (property "Reference" {q(ref)} (at {f(rx)} {f(ry)} {fa}) (effects (font (size 1.27 1.27)) (justify {jf}){" hide" if hide_ref else ""}))',
             f'  (property "Value" {q(value)} (at {f(vx)} {f(vy)} {fa}) (effects (font (size 1.27 1.27)) (justify {jf}){" hide" if hide_val else ""}))',
             f'  (property "Footprint" {q(fp)} (at {f(c.x)} {f(c.y)} {fa}) (effects (font (size 1.27 1.27)) hide))',
             f'  (property "Datasheet" "~" (at {f(c.x)} {f(c.y)} {fa}) (effects (font (size 1.27 1.27)) hide))']
    for p in pins:
        lines.append(f'  (pin {q(p[0])} (uuid {uid("pin")}))')
    lines.append(f'  (instances (project {q(PROJECT)} (path {q(sheet_path)} (reference {q(ref)}) (unit {c.unit}))))')
    lines.append(')')
    return '\n'.join(lines)


class SheetWriter:
    def __init__(self, path):
        self.items = []
        self.libs = set()
        self.path = path
        self.pwr_n = 0

    def add_power(self, net, x, y, a):
        lib, body = POWER_NETS[net]
        self.libs.add(lib)
        rot = (a - body) % 360
        PWR_COUNTER[0] += 1
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        vpos = (x + 4.6 * ca - 1.6, y - 4.6 * sa + (1.0 if sa < -0.5 else 0.0))
        c = Comp('#PWR', lib, net, x, y, rot, {'1': net}, refpos=((x, y), vpos))
        self.items.append(sym_instance(c, self.path, ref=f'#PWR{PWR_COUNTER[0]:03d}', hide_ref=True))

    def wire(self, x1, y1, x2, y2):
        self.items.append(f'(wire (pts (xy {f(x1)} {f(y1)}) (xy {f(x2)} {f(y2)})) '
                          f'(stroke (width 0) (type default)) (uuid {uid("w")}))')

    def label(self, net, x, y, a):
        just = 'left' if a in (0, 90) else 'right'
        self.items.append(
            f'(global_label {q(net)} (shape passive) (at {f(x)} {f(y)} {a}) (fields_autoplaced) '
            f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {uid("gl")}) '
            f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {f(x)} {f(y)} 0) '
            f'(effects (font (size 1.27 1.27)) hide)))')

    def noconnect(self, x, y):
        self.items.append(f'(no_connect (at {f(x)} {f(y)}) (uuid {uid("nc")}))')

    def text(self, x, y, s, size=1.27):
        self.items.append(f'(text {q(s)} (at {f(x)} {f(y)} 0) '
                          f'(effects (font (size {size} {size})) (justify left top)) (uuid {uid("t")}))')

    def component(self, c):
        self.libs.add(c.lib)
        if c.lib == 'power:PWR_FLAG':
            PWR_COUNTER[0] += 1
            self.items.append(sym_instance(c, self.path, ref=f'#FLG{PWR_COUNTER[0]:03d}', hide_ref=True,
                                           hide_val=False))
        else:
            self.items.append(sym_instance(c, self.path))
        done = set()
        for (num, name, kind, px, py, ang) in symbol_pins(c.lib, c.unit):
            net = c.pins.get(num)
            if net is None:
                raise SystemExit(f'{c.ref}: pin {num} ({name}) has no net')
            x, y = xform(c, px, py)
            if (x, y) in done:          # stacked pins (e.g. LT3010 GND + EP)
                continue
            done.add((x, y))
            if net == NC:
                self.noconnect(x, y)
                continue
            if net == '~':          # joined by touching another pin
                continue
            a = (ang + 180 + c.rot) % 360
            L = 5.08 if (net in POWER_NETS and a in (0, 180)) else 2.54
            x2 = round(x + L * math.cos(math.radians(a)), 4)
            y2 = round(y - L * math.sin(math.radians(a)), 4)
            self.wire(x, y, x2, y2)
            if net in POWER_NETS:
                self.add_power(net, x2, y2, a)
            else:
                self.label(net, x2, y2, a)

    def write(self, fn, title, page, paper='A3'):
        libs = ''.join(lib_symbol_text(l) + '\n' for l in sorted(self.libs))
        body = '\n'.join(self.items)
        txt = (f'(kicad_sch (version 20230121) (generator eeschema)\n'
               f'(uuid {uid("sheet")})\n(paper {q(paper)})\n'
               f'(title_block (title {q(title)}) (date "2026-11-19") (rev "A") '
               f'(comment 1 "12 V 20 W solar street light, SC95F8523 control"))\n'
               f'(lib_symbols\n{libs})\n{body}\n)\n')
        open(fn, 'w').write(txt)


PWR_COUNTER = [0]


def expected_netlist():
    """{(ref, pin): net} for all on-sheet parts, used by verify.py."""
    exp = {}
    for _, _, comps, _ in SHEETS:
        for c in comps:
            if c.lib.startswith('power:') or not c.board:
                continue   # off-board parts are excluded from the netlist by KiCad
            for num, net in c.pins.items():
                if net != '~':
                    exp[(c.ref, num)] = net
    return exp


def main():
    sheet_uuids = [uid('sheetref') for _ in SHEETS]
    root_items = []
    for i, (fn, name, comps, notes) in enumerate(SHEETS):
        sw = SheetWriter(f'/{ROOT_UUID}/{sheet_uuids[i]}')
        for c in comps:
            c.x, c.y = snap(c.x), snap(c.y)
            sw.component(c)
        for (x, y, s, size) in notes:
            sw.text(x, y, s, size)
        sw.write(os.path.join(HERE, f'{fn}.kicad_sch'), name, str(i + 2))
        x = 30.48 + i * 60.96
        root_items.append(
            f'(sheet (at {f(x)} 60.96) (size 45.72 25.4) (fields_autoplaced)\n'
            f'  (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000))\n'
            f'  (uuid {sheet_uuids[i]})\n'
            f'  (property "Sheetname" {q(f"{i + 1} {name}")} (at {f(x)} 60.2484 0) '
            f'(effects (font (size 1.27 1.27)) (justify left bottom)))\n'
            f'  (property "Sheetfile" {q(fn + ".kicad_sch")} (at {f(x)} 86.9446 0) '
            f'(effects (font (size 1.27 1.27)) (justify left top)))\n'
            f'  (instances (project {q(PROJECT)} (path {q("/" + ROOT_UUID)} (page {q(str(i + 2))}))))\n)')
    notes = (
        '12 V 20 W solar street light, SC95F8523 version\n\n'
        'Sheet 1: MPPT charger (sync buck, 100 kHz)\n'
        'Sheet 2: LED driver (boost, 100 kHz, 12 LEDs at 0.565 A)\n'
        'Sheet 3: SC95F8523, 10 V and 5 V rails, connectors, NTCs\n'
        'Sheet 4: gate drivers, current sense, fault comparators\n\n'
        'Nets connect by global label and power symbol. Generated by generate.py;\n'
        'verify.py checks the exported netlist against the design table.\n'
        'Design notes: ../DESIGN.md and ../SC95F8523.md')
    root = (f'(kicad_sch (version 20230121) (generator eeschema)\n'
            f'(uuid {ROOT_UUID})\n(paper "A4")\n'
            f'(title_block (title "12 V 20 W solar street light") (date "2026-11-19") (rev "A") '
            f'(comment 1 "SC95F8523 control, MPPT charger + boost LED driver"))\n'
            f'(lib_symbols)\n'
            f'(text {q(notes)} (at 30.48 101.6 0) (effects (font (size 1.524 1.524)) (justify left top)) '
            f'(uuid {uid("t")}))\n'
            + '\n'.join(root_items) +
            '\n(sheet_instances (path "/" (page "1")))\n)\n')
    open(os.path.join(HERE, f'{PROJECT}.kicad_sch'), 'w').write(root)

    # custom symbol library + table
    lib = '(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n'
    lib += '\n'.join(CUSTOM.values()) + '\n)\n'
    open(os.path.join(HERE, 'solar_light.kicad_sym'), 'w').write(lib)
    open(os.path.join(HERE, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n  (lib (name "solar_light")(type "KiCad")(uri "${KIPRJMOD}/solar_light.kicad_sym")'
        '(options "")(descr "Custom symbols for the solar street light"))\n)\n')
    # project file from KiCad's default template
    tpl = '/usr/share/kicad/template/kicad.kicad_pro'
    pro = json.load(open(tpl)) if os.path.exists(tpl) else {}
    pro.setdefault('meta', {})['filename'] = f'{PROJECT}.kicad_pro'
    pro['sheets'] = [[ROOT_UUID, '']] + [[u, f'{i + 1} {SHEETS[i][1]}'] for i, u in enumerate(sheet_uuids)]
    json.dump(pro, open(os.path.join(HERE, f'{PROJECT}.kicad_pro'), 'w'), indent=2)
    json.dump({f'{k[0]}.{k[1]}': v for k, v in expected_netlist().items()},
              open(os.path.join(HERE, 'expected_nets.json'), 'w'), indent=1, sort_keys=True)
    print('wrote', len(SHEETS), 'sheets,', sum(len(s[2]) for s in SHEETS), 'symbol units')


if __name__ == '__main__':
    main()
