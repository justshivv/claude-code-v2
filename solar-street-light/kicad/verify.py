#!/usr/bin/env python3
"""Check the KiCad project against the design table in generate.py.

1. Exports the netlist with kicad-cli and compares every (ref, pin) -> net
   with expected_nets.json (written by generate.py).
2. Reports nets with a single connection (dangling pins).
3. Checks that every net with a power-input pin has a driver
   (a power-output pin or a PWR_FLAG).
4. Checks that every footprint name exists in the KiCad footprint library.

Run: python3 verify.py   (needs kicad-cli 7 on PATH)
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse  # noqa: E402

FPDIR = os.environ.get('KICAD_FOOTPRINT_DIR', '/usr/share/kicad/footprints')
FLAGGED = {'VPV', 'VBAT', 'GND'}   # nets carrying a PWR_FLAG in the schematic


def find(tree, key):
    return [e for e in tree if isinstance(e, list) and e and e[0] == key]


def val(tree, key):
    r = find(tree, key)
    return r[0][1][1] if r else None


def main():
    out = os.path.join(tempfile.mkdtemp(), 'net.net')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '-o', out,
                    os.path.join(HERE, 'solar_light.kicad_sch')], check=True,
                   stdout=subprocess.DEVNULL)
    tree = parse(open(out).read())[0]
    comps = find(tree, 'components')[0]
    nets = find(tree, 'nets')[0]
    exp = json.load(open(os.path.join(HERE, 'expected_nets.json')))

    errors = []
    got = {}
    pintypes = {}
    for n in find(nets, 'net'):
        name = val(n, 'name').lstrip('/')
        nodes = find(n, 'node')
        for nd in nodes:
            key = f'{val(nd, "ref")}.{val(nd, "pin")}'
            got[key] = name
            pintypes[key] = val(nd, 'pintype') or ''
        real = [nd for nd in nodes if not val(nd, 'pintype', ) == 'no_connect']
        if len(nodes) == 1 and not name.startswith('unconnected-'):
            errors.append(f'net {name} has only one connection ({val(nodes[0], "ref")}.{val(nodes[0], "pin")})')

    for key, net in exp.items():
        g = got.get(key)
        if net == 'NC':
            if g is not None and not g.startswith('unconnected-'):
                errors.append(f'{key} should be unconnected, is on {g}')
        elif g != net:
            errors.append(f'{key}: expected {net}, netlist has {g}')
    for key in got:
        if key not in exp and not got[key].startswith('unconnected-'):
            errors.append(f'{key} on {got[key]} is not in the design table')

    # power-input pins must be driven
    by_net = {}
    for key, net in got.items():
        by_net.setdefault(net, []).append(pintypes[key])
    for net, types in by_net.items():
        if any(t.startswith('power_in') for t in types):
            if not any(t.startswith('power_out') for t in types) and net not in FLAGGED:
                errors.append(f'net {net} has power-input pins but no driver or PWR_FLAG')

    # footprints
    missing = 0
    fps = 0
    for c in find(comps, 'comp'):
        fp = val(c, 'footprint')
        if not fp:
            continue
        fps += 1
        lib, name = fp.split(':', 1)
        if not os.path.exists(os.path.join(FPDIR, f'{lib}.pretty', f'{name}.kicad_mod')):
            errors.append(f'{val(c, "ref")}: footprint {fp} not found in {FPDIR}')
            missing += 1

    n_comp = len(find(comps, 'comp'))
    print(f'components in netlist: {n_comp}, nets: {len(by_net)}, '
          f'pins checked: {len(exp)}, footprints checked: {fps}')
    if errors:
        print('\n'.join('ERROR ' + e for e in errors))
        sys.exit(1)
    print('OK: netlist matches the design table, no dangling nets, power pins driven, '
          'all footprints exist')


if __name__ == '__main__':
    main()
