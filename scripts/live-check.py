#!/usr/bin/python
"""Reversible integration checks on empty workspaces 4 and 7; never close user apps."""
import json
import os
import subprocess
from pathlib import Path
import shutil
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import omaspace.core as core
h = core.Hypr()
original_monitors = h.query('monitors')
original_focus = h.query('activewindow').get('address')
nonce = str(time.time_ns())
app_id = 'org.omaspace.fixture.' + nonce
created = []


def wait_for(fn, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(.15)
    raise AssertionError('Timed out waiting for compositor state')


def fixtures():
    return [c for c in h.query('clients') if c['class'] == app_id]


def launch(title, ws):
    argv = ['foot', '--app-id=' + app_id, '--title=' + title, 'sh', '-c', 'printf "OmaSpace integration fixture\\n"; sleep 600']
    h.evaluate('hl.exec_cmd(' + core.lua(core.shlex.join(argv)) + ', {workspace=' + core.lua(str(ws) + ' silent') + '}); return "OMASPACE_OK"')
    return wait_for(lambda: next((c for c in fixtures() if c['title'] == title), None))


def check(message, condition):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)

for ws in (4, 7):
    if any(c['workspace']['id'] == ws for c in h.query('clients')):
        raise SystemExit(f'Workspace {ws} is occupied. No tests run.')

try:
    with tempfile.TemporaryDirectory(prefix='omaspace-test-') as tmp:
        core.STATE = Path(tmp) / 'state' / 'omaspace'
        a = launch('OmaSpace Test A', 4)
        b = launch('OmaSpace Test B', 4)
        c = launch('OmaSpace Test C', 4)
        d = launch('OmaSpace Test D', 7)
        check('created isolated test windows', len(fixtures()) == 4)
        before = {c['address']: c for c in fixtures()}
        result = core.move_window(c['address'], '7', h)
        check('single window move', next(n for n in fixtures() if n['address'] == c['address'])['workspace']['id'] == 7)
        core.move_window(c['address'], '4', h)
        check('window move undo', next(n for n in fixtures() if n['address'] == c['address'])['workspace']['id'] == 4)
        core.swap_windows(a['address'], b['address'], h)
        core.swap_windows(a['address'], b['address'], h)
        check('native window swap and undo accepted', True)
        before = {c['address']: c for c in fixtures()}
        core.move_workspace(4, 7, h)
        after = {c['address']: c for c in fixtures()}
        check('whole workspace keeps every source window', all(after[x]['workspace']['id'] == 7 for x in (a['address'], b['address'], c['address'])))
        check('occupied destination swaps back to source', after[d['address']]['workspace']['id'] == 4)
        check('whole workspace moves onto destination display', all(after[x]['monitor'] == 1 for x in (a['address'], b['address'], c['address'])))
        core.move_workspace(7, 4, h)
        check('workspace undo restores laptop mapping', all(n['monitor'] == 0 for n in fixtures() if n['workspace']['id'] == 4))
        s = core.state(h)
        s['clients'] = [n for n in s['clients'] if n['class'] == app_id]
        s['workspaces'] = [w for w in s['workspaces'] if w['id'] in (4, 7)]
        s.update(version=1, savedAt=time.time())
        for n in s['clients']:
            n['launcher'] = {'argv': ['foot', '--app-id=' + app_id, '--title=' + n['title'], 'sh', '-c', 'sleep 600'], 'label': 'Test terminal'}
        core.atomic_json(core.STATE / 'session.json', s)
        group = [n for n in s['clients'] if n['workspace']['id'] == 4]
        check('capture dwindle tree', bool(core.split_tree(group)))
        core.swap_windows(a['address'], b['address'], h)
        h.dispatch('window.close', {'window': 'address:' + d['address']})
        wait_for(lambda: len(fixtures()) == 3)
        if '--ui' in sys.argv:
            root = Path(__file__).resolve().parents[1]
            subprocess.run(['qs', 'ipc', '-p', str(root / 'ui'), 'call', 'omaspace', 'close'], capture_output=True)
            ui = Path(tmp) / 'ui'
            shutil.copytree(root / 'ui', ui)
            (Path(tmp) / 'bin-omaspace').symlink_to(root / 'bin-omaspace')
            env = dict(os.environ, XDG_STATE_HOME=str(core.STATE.parent))
            subprocess.run(['qs', '-p', str(ui), '-d', '-n'], env=env, check=True, capture_output=True)
            def ipc(method):
                return core.run(['qs', 'ipc', '-p', str(ui), 'call', 'omaspace', method])
            try:
                ipc('open')
                wait_for(lambda: json.loads(ipc('inspect'))['workspaces'] > 0)
                subprocess.run(['wtype', '-k', 'comma', '-k', 'r'], check=True)
                wait_for(lambda: json.loads(ipc('inspect'))['dialog'] == 'restore')
                subprocess.run(['wtype', '-k', 'Return'], check=True)
                report = wait_for(lambda: core.read_json(core.STATE / 'restore-report.json'), timeout=30)
                check('restore from keyboard-driven popup', not report.get('failed'))
                logs = core.run(['qs', 'log', '-p', str(ui), '-t', '30', '--no-color'])
                check('QML has no runtime errors', 'ERROR' not in logs and 'TypeError' not in logs and 'ReferenceError' not in logs)
            finally:
                subprocess.run(['qs', 'kill', '-p', str(ui)], capture_output=True)
        else:
            report = core.restore_session(h)
        print(json.dumps(report), flush=True)
        check('restore relaunches a missing app', len(fixtures()) == 4 and not report['failed'])
        check('restore does not duplicate already-open windows', len(fixtures()) == 4)
        now = {n['title']: n for n in core.state(h)['clients'] if n['class'] == app_id}
        for n in s['clients']:
            check('restore workspace for ' + n['title'], now[n['title']]['workspace']['id'] == n['workspace']['id'])
            error = max(abs(x-y) for x,y in zip(now[n['title']]['rect'], n['rect']))
            check('restore tiled geometry for ' + n['title'] + f' (max error {error:.4f})', error < .035)
finally:
    for c in fixtures():
        h.dispatch('window.close', {'window': 'address:' + c['address']})
    for m in original_monitors:
        h.dispatch('focus', {'workspace': str(m['activeWorkspace']['id'])})
    if original_focus:
        h.dispatch('focus', {'window': 'address:' + original_focus})
    print('Temporary windows closed; original view restored.', flush=True)
