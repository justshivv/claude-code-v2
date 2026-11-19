#!/usr/bin/env python3
"""Schematic for the SC95F8523 version of the 12 V 20 W solar street light.

Draws four sheets with schemdraw and writes PNG + SVG per sheet and one
multi-page PDF. Sheets connect through net names (open circles).

    pip install schemdraw matplotlib pypdf
    python3 schematic.py
"""
import os
import schemdraw
import schemdraw.elements as elm

schemdraw.use('matplotlib')
OUT = os.path.dirname(os.path.abspath(__file__))
FS = 10        # component label font size
NFS = 9        # net label font size
NETC = '#1f5fa8'


def P(**kw):
    """IC pin with a smaller pin-name font."""
    kw.setdefault('lblsize', 8.5)
    return elm.IcPin(**kw)


class Sheet:
    def __init__(self):
        self.d = schemdraw.Drawing(show=False)
        self.d.config(unit=2.5, fontsize=FS, lw=1.3)

    def add(self, e):
        if isinstance(e, (elm.Ic, elm.Opamp)):
            e.theta(0)
        return self.d.add(e)

    # --- helpers -------------------------------------------------------
    def wire(self, a, b, shape='-'):
        return self.add(elm.Wire(shape).at(a).to(b))

    def dot(self, p):
        return self.add(elm.Dot().at(p))

    def gnd(self, p):
        return self.add(elm.Ground().at(p))

    def net(self, p, name, side='right', length=0.7):
        ln = elm.Line().at(p)
        getattr(ln, side)()
        ln = self.add(ln.length(length))
        self.add(elm.Dot(open=True).at(ln.end).color(NETC)
                 .label(name, loc={'up': 'top', 'down': 'bottom'}.get(side, side),
                        fontsize=NFS, color=NETC))
        return ln.end

    def text(self, p, s, size=FS, halign='left', valign='top', color='black'):
        self.add(elm.Label().at(p).label(s, fontsize=size, halign=halign,
                                         valign=valign, color=color))

    def title(self, p, s, sub=None):
        self.text(p, s, size=14)
        if sub:
            self.text((p[0], p[1] - 0.9), sub, size=10, color='#444')

    def vert(self, x, ytop, ybot, e, label=None, loc='bottom'):
        """Two-terminal part from (x,ytop) down to (x,ybot) and ground."""
        e = e.at((x, ytop)).down()
        if label:
            e = e.label(label, loc=loc, fontsize=FS)
        e = self.add(e)
        if abs(e.end[1] - ybot) > 1e-6:
            self.wire(e.end, (x, ybot))
        self.gnd((x, ybot))
        return e

    def divider(self, x, ytop, ybot, r1, r2, netname, side='right'):
        mid = ytop - (ytop - ybot) / 2
        self.add(elm.Resistor().at((x, ytop)).to((x, mid + 0.25))
                 .label(r1, loc='bottom', fontsize=FS))
        self.wire((x, mid + 0.25), (x, mid - 0.25))
        self.dot((x, mid))
        r = self.add(elm.Resistor().at((x, mid - 0.25)).to((x, ybot + 0.6))
                     .label(r2, loc='bottom', fontsize=FS))
        self.wire(r.end, (x, ybot))
        self.gnd((x, ybot))
        self.net((x, mid), netname, side=side)

    def save(self, name):
        for ext in ('png', 'svg', 'pdf'):
            kw = {'dpi': 160} if ext == 'png' else {}
            self.d.save(os.path.join(OUT, f'{name}.{ext}'), **kw)


# ======================================================================
# Sheet 1: MPPT charger power stage
# ======================================================================
def sheet1():
    s = Sheet()
    T, G = 6.0, 0.0
    s.title((0, 10.2), 'Sheet 1 of 4: MPPT charger power stage',
            'Synchronous buck, 100 kHz, PWM0/PWM1 via UCC27211 (sheet 4)')

    # PV panel
    s.wire((0, G), (0, 1.5))
    s.gnd((0, G))
    s.add(elm.Solar().at((0, 1.5)).up().length(3)
          .label('PV1\n80 W mono\nVmp 18–20 V\nVoc ≤ 23 V', loc='top', fontsize=FS))
    s.wire((0, 4.5), (0, T))
    s.text((0.25, 4.9), '+', size=11)
    s.add(elm.Line().at((0, T)).right().length(2))
    s.text((0.3, T + 0.55), 'J1 panel input', size=9, color='#444')

    # TVS
    s.dot((2, T))
    s.vert(2, T, G, elm.Zener().reverse().length(3), 'D3\nSMBJ28A\nTVS')

    # Panel voltage divider (panel side, for dusk/dawn)
    s.wire((2, T), (3.6, T))
    s.dot((3.6, T))
    s.divider(3.6, T, G, 'R1\n200k', 'R2\n10k', 'VPV_SNS')
    s.text((3.2, T + 0.55), 'VPV', size=NFS, color=NETC)

    # Ideal diode Q5 + U3
    s.wire((3.6, T), (6.4, T))
    q5 = s.add(elm.NFet().down().anchor('source').at((6.4, T)))
    s.text((5.6, T + 1.0), 'Q5  60 V ≤ 4 mΩ', size=FS)
    u3 = s.add(elm.Ic(pins=[P(name='A', side='top'),
                            P(name='GATE', side='top'),
                            P(name='C', side='top'),
                            P(name='GND', side='bottom')],
                       size=(3.0, 1.2), pinspacing=0.9, leadlen=0.4)
               .anchor('GATE').at((q5.gate[0], 3.7)))
    s.text((u3.GND[0] + 0.45, u3.GND[1] - 0.2),
           'U3 LM74700-Q1 ideal diode\nEN → A, VCAP: 0.1 µF to A', size=8)
    s.wire(q5.gate, u3.GATE)
    s.wire((5.6, T), (5.6, 4.6))
    s.dot((5.6, T))
    s.wire((5.6, 4.6), u3.A, '-|')
    s.wire((8.6, T), (8.6, 4.6))
    s.dot((8.6, T))
    s.wire((8.6, 4.6), u3.C, '-|')
    s.wire(u3.GND, (u3.GND[0], G))
    s.gnd((u3.GND[0], G))

    # VIN rail and input caps
    s.wire(q5.drain, (9.2, T))
    s.text((7.6, T + 0.55), 'VIN_BUCK', size=NFS, color=NETC)
    s.dot((9.2, T))
    s.vert(9.2, T, G, elm.Capacitor().length(3), 'C3\n4 × 10 µF\n50 V X7R')

    # Half-bridge Q3 / Q4
    X = 12.2
    s.wire((9.2, T), (X, T))
    q3 = s.add(elm.NFet().right().reverse().anchor('drain').at((X, T)))
    s.text((q3.drain[0] + 0.45, q3.drain[1] - 0.05), 'Q3\n60 V\n≤ 5 mΩ')
    sw = (X, 3.6)
    s.wire(q3.source, sw)
    s.dot(sw)
    q4 = s.add(elm.NFet().right().reverse().anchor('drain').at((X, 3.0)))
    s.text((q4.drain[0] + 0.45, q4.drain[1] - 0.05), 'Q4\n60 V\n≤ 5 mΩ')
    s.wire(sw, q4.drain)
    s.wire(q4.source, (X, G))
    s.gnd((X, G))
    s.net(q3.gate, 'HO', side='left', length=0.5)
    s.net(q4.gate, 'LO', side='left', length=0.5)
    s.net(sw, 'HS', side='left', length=0.5) if False else None
    s.text((X - 2.2, sw[1] + 0.45), 'HS (to U4)', size=NFS, color=NETC)
    s.wire(sw, (X - 0.9, sw[1]))
    s.add(elm.Dot(open=True).at((X - 0.9, sw[1])).color(NETC))

    # D2 Schottky across Q4
    s.wire(sw, (14.2, sw[1]))
    s.dot((14.2, sw[1]))
    s.vert(14.2, sw[1], G, elm.Schottky().reverse().length(2.4),
           'D2\n60 V 5 A\nSchottky')

    # L2
    l2 = s.add(elm.Inductor2(loops=3).at((14.2, sw[1])).right().length(3)
               .label('L2  22 µH\nIsat ≥ 9 A, DCR ≤ 12 mΩ', loc='top', fontsize=FS))
    s.wire(l2.end, (17.2, T))  # up to output rail via corner
    s.wire((17.2, T), (18.2, T))
    s.text((17.4, T + 0.55), 'VCHG', size=NFS, color=NETC)
    s.dot((18.2, T))
    s.vert(18.2, T, G, elm.Capacitor().length(3), 'C4\n2 × 22 µF 25 V\n+ 220 µF polymer')

    # Shunt with Kelvin taps
    s.wire((18.2, T), (19.4, T))
    s.dot((19.4, T))
    rsh = s.add(elm.Resistor().at((19.4, T)).right().length(2.4)
                .label('RSH 2 mΩ 1 W', loc='bottom', fontsize=FS))
    s.dot(rsh.end)
    s.net((19.4, T), 'ICHG+', side='up', length=0.9)
    s.net(rsh.end, 'ICHG−', side='up', length=0.9)

    # Fuse
    f1 = s.add(elm.Fuse().at(rsh.end).right().length(2.4)
               .label('F1 10 A', loc='bottom', fontsize=FS))
    xb = f1.end[0] + 1.2
    s.wire(f1.end, (xb, T))
    s.dot((xb, T))
    s.text((xb - 0.5, T + 0.55), 'VBAT', size=NFS, color=NETC)
    s.divider(xb, T, G, 'R3\n91k', 'R4\n10k', 'VBAT_SNS')

    # Battery + BMS
    xbat = xb + 5.0
    s.wire((xb, T), (xbat, T))
    s.dot((xbat, T))
    s.add(elm.Battery().at((xbat, T)).down().length(2.6)
          .label('BT1 LiFePO4 4S5P\n12.8 V 30 Ah', loc='bottom', fontsize=FS))
    bms = s.add(elm.Ic(pins=[P(anchorname='BN', side='top'),
                             P(anchorname='PN', side='bottom')],
                       size=(2.8, 1.6), leadlen=0.35)
                .anchor('BN').at((xbat, T - 2.6))
                .label('BMS 4S\nbalancing\nOV/UV/OC/SC\n(B− top, P− bottom)', loc='center', fontsize=8))
    s.wire(bms.PN, (xbat, G))
    s.gnd((xbat, G))
    s.net((xbat, T), 'VBAT (sheet 2, 3)', side='right', length=1.0)

    s.text((0, -1.6),
           'Notes: all parts on VPV / VIN_BUCK rated 60 V. Q5 blocks reverse polarity and night back-feed '
           'through Q3. D2 carries current during the 125 ns dead time.\n'
           'System ground = BMS P−. Kelvin-route ICHG+/ICHG− to U5 (sheet 4). '
           'Hot loop C3 → Q3 → Q4 → C3 as small as possible.', size=9, color='#444')
    s.save('sheet1_charger')


# ======================================================================
# Sheet 2: LED boost power stage
# ======================================================================
def sheet2():
    s = Sheet()
    T, G = 6.0, 0.0
    s.title((0, 11.6), 'Sheet 2 of 4: LED driver power stage',
            'Boost, 100 kHz, PWM2 via UCC27517 (sheet 4), 12 LEDs at 0.565 A')

    s.add(elm.Dot(open=True).at((0, T)).color(NETC)
          .label('VBAT', loc='left', fontsize=NFS, color=NETC))
    f2 = s.add(elm.Fuse().at((0, T)).right().length(2.4)
               .label('F2 5 A', loc='top', fontsize=FS))
    s.wire(f2.end, (3.2, T))
    s.dot((3.2, T))
    s.vert(3.2, T, G, elm.Capacitor().length(3), 'C5\n2 × 10 µF 25 V\n+ 100 µF polymer')

    l1 = s.add(elm.Inductor2(loops=4).at((3.2, T)).right().length(3.6)
               .label('L1  100 µH\nIsat ≥ 3.5 A, DCR ≤ 40 mΩ', loc='top', fontsize=FS))
    swb = l1.end
    s.dot(swb)
    s.text((swb[0] - 1.15, T - 0.15), 'SW_B', size=NFS, color=NETC)
    q1 = s.add(elm.NFet().right().reverse().anchor('drain').at(swb))
    s.text((q1.drain[0] + 0.45, q1.drain[1] - 0.05), 'Q1\n60 V\n≤ 10 mΩ')
    s.net(q1.gate, 'GATE_B', side='left', length=0.6)
    s.dot(q1.source)
    s.vert(q1.source[0], q1.source[1], G, elm.Resistor().length(2.6), 'RSW\n33 mΩ\n1 %')
    s.net(q1.source, 'ISW', side='left', length=0.9) if False else None
    s.wire(q1.source, (q1.source[0] + 1.3, q1.source[1]))
    s.add(elm.Dot(open=True).at((q1.source[0] + 1.3, q1.source[1])).color(NETC)
          .label('ISW', loc='right', fontsize=NFS, color=NETC))

    d1 = s.add(elm.Schottky().at(swb).right().length(4.4)
               .label('D1  60 V 3–5 A\nSchottky', loc='top', fontsize=FS))
    vo = d1.end
    s.dot(vo)
    s.text((vo[0] + 0.15, T + 0.55), 'VLED', size=NFS, color=NETC)
    s.vert(vo[0], T, G, elm.Capacitor().length(3), 'C6\n4 × 4.7 µF\n100 V X7R')

    s.wire(vo, (vo[0] + 2.4, T))
    xd = vo[0] + 2.4
    s.dot((xd, T))
    s.divider(xd, T, G, 'R5\n430k', 'R6\n20k', 'VLED_SNS')

    # LED string, horizontal on top
    xs = xd + 2.6
    Y = 9.0
    s.wire((xd, T), (xs, T))
    s.wire((xs, T), (xs, Y))
    x = xs
    for i in range(3):
        e = s.add(elm.LED().at((x, Y)).right().length(1.8))
        x = e.end[0]
    s.add(elm.Line().at((x, Y)).right().length(1.6).linestyle(':'))
    x += 1.6
    for i in range(2):
        e = s.add(elm.LED().at((x, Y)).right().length(1.8))
        x = e.end[0]
    s.text((xs + 0.4, Y + 1.5),
           'D4–D15: 12 × 3535 LED in series, about 35.4 V at 0.565 A (20 W)  ·  on LED MCPCB with NTC2',
           size=9)
    xk = x + 0.6
    s.wire((x, Y), (xk, Y))
    s.wire((xk, Y), (xk, 5.2))
    s.dot((xk, 5.2))
    s.text((xk + 0.2, 5.75), 'LED_K', size=NFS, color=NETC)
    q2 = s.add(elm.NFet().right().reverse().anchor('drain').at((xk, 4.6)))
    s.text((q2.drain[0] + 0.45, q2.drain[1] - 0.05), 'Q2\nlogic-level\n60 V ≤ 20 mΩ')
    s.wire((xk, 5.2), q2.drain)
    s.net(q2.gate, 'LED_EN', side='left', length=0.6)
    s.dot(q2.source)
    s.vert(xk, q2.source[1], G, elm.Resistor().length(2.4), 'RLED\n0.1 Ω 1 %')
    s.wire(q2.source, (xk + 1.4, q2.source[1]))
    s.add(elm.Dot(open=True).at((xk + 1.4, q2.source[1])).color(NETC)
          .label('ILED+', loc='right', fontsize=NFS, color=NETC))
    s.text((xk + 0.4, 0.9), 'Kelvin GND tap\n→ ILED− (U6)', size=8, color=NETC)

    s.text((0, -1.6),
           'Notes: F2 protects against an LED string short (a boost has a DC path from input to output). '
           'Hot loop Q1 → D1 → C6 → RSW as small as possible.\n'
           'RSW feeds only the over-current comparator (sheet 4); LED current is regulated in firmware from RLED via U6. '
           'R5/R6: 43.3 V OVP trip and ADC reading.\n'
           'Optional synchronous boost: Q6 (60 V ≤ 14 mΩ) across D1, gate from PWM3 through a second UCC27211; keep D1 for the 125 ns dead time.', size=9, color='#444')
    s.save('sheet2_led_driver')


# ======================================================================
# Sheet 3: SC95F8523, supplies, connectors
# ======================================================================
def sheet3():
    s = Sheet()
    s.title((-9, 9.6), 'Sheet 3 of 4: SC95F8523 controller, supplies, connectors',
            'Pin numbers are for the 28-pin SOP/TSSOP package (datasheet V0.3)')

    left = [('1', 'VDD'), ('2', 'P1.0/CMOD'), ('3', 'VSS'), ('4', 'P5.1/OSCI'),
            ('5', 'P5.0/OSCO'), ('6', 'P1.1/RST'), ('7', 'P1.2/tCK'),
            ('8', 'P1.3/tDIO'), ('9', 'P1.4'), ('10', 'P1.5'), ('11', 'P1.6/AIN7'),
            ('12', 'P1.7/AIN6'), ('13', 'P2.7/AIN5'), ('14', 'P2.6/AIN4')]
    right = [('28', 'P0.0/PWM0'), ('27', 'P0.1/PWM1'), ('26', 'P0.2/PWM2'),
             ('25', 'P0.3/PWM3'), ('24', 'P0.4/FLT'), ('23', 'P0.5'),
             ('22', 'P0.6'), ('21', 'P0.7'), ('20', 'P2.0/USTX0'),
             ('19', 'P2.1/USRX0'), ('18', 'P2.2/AIN0'), ('17', 'P2.3/AIN1'),
             ('16', 'P2.4/AIN2'), ('15', 'P2.5/AIN3')]
    pins = [P(name=n, pin=p, side='left', slot=f'{14 - i}/14')
            for i, (p, n) in enumerate(left)]
    pins += [P(name=n, pin=p, side='right', slot=f'{14 - i}/14')
             for i, (p, n) in enumerate(right)]
    u1 = s.add(elm.Ic(pins=pins, size=(5.4, 11.2), pinspacing=0.8, leadlen=0.8,
                      fontsize=9)
               .at((0, -3)).label('U1\nSC95F8523\n(28-pin)', loc='center', fontsize=12))

    lnets = {'VDD': '+5V', 'P1.0/CMOD': 'NC', 'VSS': 'GND',
             'P5.1/OSCI': 'XIN', 'P5.0/OSCO': 'XOUT', 'P1.1/RST': 'RST',
             'P1.2/tCK': 'tCK', 'P1.3/tDIO': 'tDIO', 'P1.4': 'PIR_IN',
             'P1.5': 'LED_EN', 'P1.6/AIN7': 'V10_SNS', 'P1.7/AIN6': 'NTC_LED',
             'P2.7/AIN5': 'NTC_BAT', 'P2.6/AIN4': 'VLED_SNS'}
    rnets = {'P0.0/PWM0': 'HI', 'P0.1/PWM1': 'LI', 'P0.2/PWM2': 'IN_B',
             'P0.3/PWM3': 'PWM3 (opt. sync)', 'P0.4/FLT': 'FLT',
             'P0.5': 'EN_10V', 'P0.6': 'NC', 'P0.7': 'NC',
             'P2.0/USTX0': 'TXD', 'P2.1/USRX0': 'RXD', 'P2.2/AIN0': 'VPV_SNS',
             'P2.3/AIN1': 'VBAT_SNS', 'P2.4/AIN2': 'ICHG', 'P2.5/AIN3': 'ILED'}
    for n, net in lnets.items():
        s.net(u1.absanchors[n], net, side='left', length=0.9)
    for n, net in rnets.items():
        s.net(u1.absanchors[n], net, side='right', length=0.9)

    # ---- right column: supplies ----
    X0 = 12.5
    s.text((X0, 9.0), 'Supplies', size=11)
    def ldo(y, name, part, out, en=None):
        pins = [P(name='IN', side='left'), P(name='OUT', side='right'),
                P(name='GND', side='bottom', slot='2/2' if en else '1/1')]
        if en:
            pins.append(P(name='EN', side='bottom', slot='1/2'))
        u = s.add(elm.Ic(pins=pins, size=(2.8, 1.6), leadlen=0.5)
                  .at((X0 + 2.5, y)).label(name, loc='center', fontsize=8))
        s.text((u.IN[0] + 0.5, u.OUT[1] + 1.35), part, size=7, color='#444')
        s.net(u.IN, 'VBAT', side='left', length=1.6)
        s.dot((u.IN[0] - 0.8, u.IN[1]))
        s.vert(u.IN[0] - 0.8, u.IN[1], u.IN[1] - 2.4, elm.Capacitor().length(1.6),
               '1 µF\n50 V', loc='top')
        s.gnd(u.GND)
        s.dot((u.OUT[0] + 0.8, u.OUT[1]))
        s.wire(u.OUT, (u.OUT[0] + 0.8, u.OUT[1]))
        s.vert(u.OUT[0] + 0.8, u.OUT[1], u.OUT[1] - 2.4, elm.Capacitor().length(1.6),
               '2.2 µF', loc='bottom')
        s.net((u.OUT[0] + 0.8, u.OUT[1]), out, side='right', length=0.8)
        if en:
            s.net(u.EN, en, side='down', length=0.6)
        return u
    ldo(6.3, 'U8\n10 V LDO', 'Vin ≥ 30 V, Iq < 50 µA', '+10V', en='EN_10V')
    ldo(1.8, 'U9\n5 V LDO', 'Vin ≥ 30 V, Iq < 50 µA', '+5V')
    s.divider(X0 + 10.0, 6.8, 2.6, 'R7 47k', 'R8 10k', 'V10_SNS')
    s.net((X0 + 10.0, 6.8), '+10V', side='up', length=0.6)

    # ---- U1 decoupling ----
    yb = -3.0
    s.text((X0, yb + 1.3), 'U1 decoupling, reset, crystal', size=11)
    s.net((X0 + 0.6, yb), '+5V', side='up', length=0.5)
    s.dot((X0 + 0.6, yb))
    s.wire((X0 + 0.6, yb), (X0 + 2.2, yb))
    s.vert(X0 + 0.6, yb, yb - 2.6, elm.Capacitor().length(1.8), 'C10\n100 nF', loc='bottom')
    s.vert(X0 + 2.2, yb, yb - 2.6, elm.Capacitor().length(1.8), 'C11\n10 µF', loc='bottom')
    # reset pull-up
    s.net((X0 + 4.2, yb), '+5V', side='up', length=0.5)
    s.add(elm.Resistor().at((X0 + 4.2, yb)).down().length(1.8)
          .label('R9\n10k', loc='bottom', fontsize=FS))
    s.net((X0 + 4.2, yb - 1.8), 'RST', side='down', length=0.5)
    # crystal
    xc = X0 + 6.2
    s.net((xc, yb), 'XIN', side='up', length=0.5)
    y1 = s.add(elm.Crystal().at((xc, yb)).right().length(2.4)
               .label('Y1 32.768 kHz', loc='top', fontsize=9))
    s.net(y1.end, 'XOUT', side='up', length=0.5)
    s.dot((xc, yb))
    s.dot(y1.end)
    s.vert(xc, yb, yb - 2.6, elm.Capacitor().length(1.8), 'CL', loc='top')
    s.vert(y1.end[0], yb, yb - 2.6, elm.Capacitor().length(1.8), 'CL', loc='bottom')
    s.text((xc - 0.2, yb - 3.3), 'CL per crystal datasheet (typ. 10–15 pF)', size=8, color='#444')

    # ---- NTCs ----
    yn = -8.0
    s.text((X0, yn + 1.3), 'Temperature sensing (12-bit ADC, 2.048 V ref)', size=11)
    for i, (xn, net, nm, where) in enumerate([(X0 + 0.8, 'NTC_BAT', 'NTC1', 'on battery pack'),
                                              (X0 + 6.0, 'NTC_LED', 'NTC2', 'on LED board')]):
        s.net((xn, yn), '+5V', side='up', length=0.5)
        r = s.add(elm.Resistor().at((xn, yn)).down().length(1.8)
                  .label(f'R{10 + i}\n100k 1 %', loc='bottom', fontsize=FS))
        s.dot(r.end)
        s.add(elm.Thermistor().at(r.end).down().length(1.8)
              .label(f'{nm}\n10k B3950\n{where}', loc='bottom', fontsize=FS))
        s.gnd((xn, r.end[1] - 1.8))
        s.wire(r.end, (xn - 1.3, r.end[1]))
        s.dot((xn - 1.3, r.end[1]))
        s.add(elm.Capacitor().at((xn - 1.3, r.end[1])).down().length(1.8)
              .label('100 nF', loc='top', fontsize=FS))
        s.gnd((xn - 1.3, r.end[1] - 1.8))
        s.net(r.end, net, side='right', length=0.8) if False else None
        s.wire(r.end, (xn + 1.0, r.end[1]))
        s.add(elm.Dot(open=True).at((xn + 1.0, r.end[1])).color(NETC)
              .label(net, loc='right', fontsize=NFS, color=NETC))

    # ---- Connectors ----
    yc = -14.5
    s.text((-9, yc + 2.6), 'Connectors', size=11)
    def header(x, name, pins_):
        n = len(pins_)
        ps = [P(name=p, pin=str(i + 1), side='right', slot=f'{n - i}/{n}') for i, p in enumerate(pins_)]
        h = s.add(elm.Ic(pins=ps, size=(1.6, 0.8 * len(pins_) + 0.4), pinspacing=0.8, leadlen=0.4)
                  .at((x, yc - 0.8 * len(pins_))).label(name, loc='top', fontsize=9))
        for p in pins_:
            s.net(h.absanchors[p], p if p not in ('5V',) else '+5V', side='right', length=0.6)
    header(-9, 'J3 program\n(tCK/tDIO)', ['+5V', 'tCK', 'tDIO', 'GND'])
    header(-3, 'J4 PIR / motion\nsensor (optional)', ['+5V', 'PIR_IN', 'GND'])
    header(3, 'J5 service UART', ['TXD', 'RXD', 'GND'])
    s.text((-9, yc - 4.8),
           'PIR_IN: 100k pull-down. LED_EN: 100 Ω series + 100k pull-down at Q2 gate. '
           'Unused pins (P1.0, P0.6, P0.7): output low.\n'
           'ADC divider nodes get 100 nF to GND at the U1 pin. '
           'Analog ground (dividers, NTCs, U5/U6 GND) joins power ground at one point near RLED.',
           size=9, color='#444')
    s.save('sheet3_controller')


# ======================================================================
# Sheet 4: gate drivers, current sense, fault comparators
# ======================================================================
def sheet4():
    s = Sheet()
    s.title((0, 10.6), 'Sheet 4 of 4: gate drivers, current sense, fault comparators',
            'Pin numbers omitted for U4–U7: take them from each part\'s datasheet')

    # ---- U4 UCC27211 ----
    u4 = s.add(elm.Ic(pins=[P(name='HI', side='left', slot='4/4'),
                            P(name='LI', side='left', slot='3/4'),
                            P(name='VDD', side='left', slot='2/4'),
                            P(name='VSS', side='left', slot='1/4'),
                            P(name='HO', side='right', slot='4/4'),
                            P(name='HB', side='right', slot='3/4'),
                            P(name='HS', side='right', slot='2/4'),
                            P(name='LO', side='right', slot='1/4')],
                      size=(3.0, 3.6), pinspacing=0.8, leadlen=0.6)
               .at((3.5, 4.2)).label('U4\nUCC27211\nhalf-bridge\ndriver', loc='center', fontsize=9))
    s.net(u4.HI, 'HI', side='left', length=2.6)
    s.net(u4.LI, 'LI', side='left', length=2.6)
    s.text((u4.HI[0] - 4.0, u4.HI[1] + 1.2),
           '10k pull-down to GND on HI and on LI\n(PWM pins go high-Z on a FLT fault)',
           size=8, color='#444')
    s.net(u4.VDD, '+10V', side='left', length=2.6)
    s.wire(u4.VSS, (u4.VSS[0] - 0.6, u4.VSS[1]))
    s.gnd((u4.VSS[0] - 0.6, u4.VSS[1]))
    for pin, net in (('HO', 'HO'), ('LO', 'LO')):
        r = s.add(elm.Resistor().at(u4.absanchors[pin]).right().length(2.2)
                  .label('2.2 Ω', loc='top', fontsize=8))
        s.net(r.end, net, side='right', length=0.6)
    xb = u4.HB[0] + 0.6
    s.wire(u4.HB, (xb, u4.HB[1]))
    s.add(elm.Capacitor().at((xb, u4.HB[1])).to((xb, u4.HS[1])))
    s.text((xb + 0.35, u4.HB[1] - 0.05), 'CBOOT 0.22 µF', size=8)
    s.dot((xb, u4.HS[1]))
    s.net(u4.HS, 'HS', side='right', length=2.8)

    # ---- U7 UCC27517 ----
    u7 = s.add(elm.Ic(pins=[P(name='IN+', side='left', slot='3/3'),
                            P(name='IN−', side='left', slot='2/3'),
                            P(name='VDD', side='left', slot='1/3'),
                            P(name='OUT', side='right', slot='2/2'),
                            P(name='GND', side='bottom')],
                      size=(3.0, 2.6), pinspacing=0.8, leadlen=0.6)
               .at((3.5, -2.2)).label('U7\nUCC27517\nlow-side\ndriver', loc='center', fontsize=9))
    s.net(u7['IN+'], 'IN_B', side='left', length=2.6)
    s.wire(u7['IN−'], (u7['IN−'][0] - 0.8, u7['IN−'][1]))
    s.gnd((u7['IN−'][0] - 0.8, u7['IN−'][1]))
    s.net(u7.VDD, '+10V', side='left', length=2.6)
    s.gnd(u7.GND)
    s.add(elm.Resistor().at(u7.OUT).right().length(2.0)
          .label('4.7 Ω', loc='top', fontsize=9))
    s.net((u7.OUT[0] + 2.0, u7.OUT[1]), 'GATE_B', side='right', length=0.5)
    s.text((u7['IN+'][0] - 4.0, u7['IN+'][1] + 0.9), '10k pull-down to GND on IN_B', size=8, color='#444')
    s.text((-0.5, -5.6), 'Decouple U4 and U7 VDD with 1 µF + 100 nF each, at the pins.',
           size=8, color='#444')

    # ---- INA181 current-sense amplifiers ----
    def ina(x, y, name, gain, inp, inn, out, note):
        u = s.add(elm.Ic(pins=[P(name='IN+', side='left', slot='2/2'),
                               P(name='IN−', side='left', slot='1/2'),
                               P(name='OUT', side='right', slot='2/2'),
                               P(name='REF', side='right', slot='1/2'),
                               P(name='VS', side='top'),
                               P(name='GND', side='bottom')],
                         size=(4.6, 2.2), pinspacing=0.8, leadlen=0.5)
                  .at((x, y)).label(f'{name}\nINA181{gain}', loc='center', fontsize=8))
        s.net(u['IN+'], inp, side='left', length=1.0)
        s.net(u['IN−'], inn, side='left', length=1.0)
        s.net(u.VS, '+5V', side='up', length=0.4)
        s.gnd(u.GND)
        s.wire(u.REF, (u.REF[0] + 0.6, u.REF[1]))
        s.gnd((u.REF[0] + 0.6, u.REF[1]))
        s.add(elm.Resistor().at(u.OUT).right().length(1.8).label('1k', loc='top', fontsize=8))
        po = (u.OUT[0] + 1.8, u.OUT[1])
        s.dot(po)
        s.add(elm.Capacitor().at(po).down().length(1.2).label('10 nF', loc='bottom', fontsize=8))
        s.gnd((po[0], po[1] - 1.2))
        s.net(po, out, side='right', length=0.6)
        s.text((u.GND[0] + 0.35, u.GND[1] - 0.1), note, size=8, color='#444')
        return u
    ina(14.5, 5.0, 'U5 charge current', 'A3 (×100)', 'ICHG+', 'ICHG−', 'ICHG',
        'out: 5.8 A → 1.16 V, 7 A → 1.40 V')
    ina(14.5, 0.0, 'U6 LED current', 'A1 (×20)', 'ILED+', 'ILED− (GND Kelvin)', 'ILED',
        'out: 0.565 A → 1.13 V')

    # ---- LM2901 fault comparators ----
    yc0 = -8.0
    s.text((0, yc0 + 1.6), 'Fault comparators U2 LM2901 (quad, open collector): '
           'signal on −, threshold on +, so a fault pulls FLT low', size=11)
    comps = [('U2A boost over-current', 'ISW_F', 'REF_A'),
             ('U2B LED over-voltage', 'VLED_SNS', 'REF_B'),
             ('U2C charger over-current', 'ICHG', 'REF_C'),
             ('U2D battery over-voltage', 'VBAT_SNS', 'REF_D')]
    xbus = 0
    outs = []
    for i, (nm, sig, ref) in enumerate(comps):
        x = 3.5 + i * 6.2
        op = s.add(elm.Opamp(leads=True).at((x, yc0 - 2.0)).anchor('in1')
                   .label(nm, loc='top', ofst=(0, 0.6), fontsize=9))
        s.net(op.in1, sig, side='left', length=0.5)
        s.net(op.in2, ref, side='left', length=0.5)
        outs.append(op.out)
    ybus = yc0 - 4.6
    for o in outs:
        s.dot(o)
        s.wire(o, (o[0], ybus))
        s.dot((o[0], ybus))
    s.wire((outs[0][0], ybus), (outs[-1][0] + 1.5, ybus))
    xf = outs[-1][0] + 1.5
    s.net((xf, ybus), 'FLT', side='right', length=0.8)
    s.add(elm.Resistor().at((xf, ybus)).up().length(2.0)
          .label('R20\n4.7k', loc='bottom', fontsize=9))
    s.net((xf, ybus + 2.0), '+5V', side='up', length=0.4)
    s.dot((xf, ybus))

    # ISW RC filter
    yr = ybus - 2.2
    s.text((0, yr + 0.6), 'ISW filter', size=10)
    s.add(elm.Dot(open=True).at((0.4, yr - 0.6)).color(NETC)
          .label('ISW', loc='left', fontsize=NFS, color=NETC))
    r = s.add(elm.Resistor().at((0.4, yr - 0.6)).right().length(2.0)
              .label('100 Ω', loc='top', fontsize=9))
    s.dot(r.end)
    s.add(elm.Capacitor().at(r.end).down().length(1.4).label('1 nF', loc='bottom', fontsize=9))
    s.gnd((r.end[0], r.end[1] - 1.4))
    s.net(r.end, 'ISW_F', side='right', length=0.8)

    s.text((7.5, yr + 0.6),
           'Threshold dividers from +5V (1 %), 100 nF on each REF node:\n'
           'REF_A  43k / 1.0k   → 0.114 V  = 3.4 A in RSW (33 mΩ)\n'
           'REF_B  16k / 10k    → 1.92 V   = 43.3 V on VLED (R5/R6 430k/20k)\n'
           'REF_C  26k / 10k    → 1.39 V   = 6.9 A charge current (U5 ×100, 2 mΩ)\n'
           'REF_D  23.7k / 10k  → 1.48 V   = 15.0 V battery (R3/R4 91k/10k)\n'
           'U1 FLT: active low, latched mode, 1 µs filter. U2 VCC = +5V, 100 nF.',
           size=9)
    s.save('sheet4_drivers_protection')


if __name__ == '__main__':
    sheet1()
    sheet2()
    sheet3()
    sheet4()
    try:
        from pypdf import PdfWriter
        w = PdfWriter()
        for n in ('sheet1_charger', 'sheet2_led_driver', 'sheet3_controller',
                  'sheet4_drivers_protection'):
            w.append(os.path.join(OUT, f'{n}.pdf'))
        w.write(os.path.join(OUT, 'schematic.pdf'))
    except ImportError:
        print('pypdf not installed: skipped combined PDF')
    print('done')
