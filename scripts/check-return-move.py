#!/usr/bin/python
"""Regression: active moves/reopenings; --occupied also checks workspace swaps."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omaspace.core import Hypr, lua, run
h = Hypr()
original = h.query('monitors')
focused = h.query('activewindow').get('address')
original_clients = {c['address']: c['workspace']['id'] for c in h.query('clients')}
assert not any(w['id'] in (94, 95) for w in h.query('workspaces')), 'Test workspaces already in use'
fixture_class = 'org.omaspace.return-test.' + str(time.time_ns())
monitor = next(m['name'] for m in original if m['focused'])
was_running = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'omaspace-session.service']).returncode == 0

def wait(fn, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = fn()
        if result: return result
        time.sleep(.05)
    raise AssertionError('Timed out')

def fixtures():
    return [c for c in h.query('clients') if c['class'] == fixture_class]

subprocess.run(['systemctl', '--user', 'stop', 'omaspace-session.service'], check=True)
subprocess.run([str(ROOT / 'bin-omaspace'), 'close'], check=True)
try:
    # Nonpersistent rules expose empty destinations in the UI without touching files.
    h.evaluate('_omaspaceReturnRules={hl.workspace_rule({workspace="94",monitor=' + lua(monitor) + '}),hl.workspace_rule({workspace="95",monitor=' + lua(monitor) + '})}; return "OMASPACE_OK"')
    h.evaluate('hl.exec_cmd(' + lua('foot --app-id=' + fixture_class + ' --title=OmaSpace-return-test sleep 120') + ', {workspace="95 silent"}); return "OMASPACE_OK"')
    client = wait(lambda: next(iter(fixtures()), None))
    if '--occupied' in sys.argv:
        h.evaluate('hl.exec_cmd(' + lua('foot --app-id=' + fixture_class + ' --title=OmaSpace-swap-test sleep 120') + ', {workspace="94 silent"}); return "OMASPACE_OK"')
        wait(lambda: len(fixtures()) == 2)
    h.dispatch('focus', {'workspace': '95'})
    with tempfile.TemporaryDirectory(prefix='omaspace-return-') as directory:
        tmp = Path(directory)
        ui = tmp / 'ui'
        shutil.copytree(ROOT / 'ui', ui)
        (tmp / 'bin-omaspace').symlink_to(ROOT / 'bin-omaspace')
        env = dict(os.environ, XDG_STATE_HOME=str(tmp / 'state'))
        subprocess.run(['qs', '-p', str(ui), '-d', '-n'], env=env, check=True, capture_output=True)
        def ipc(method, target='omaspace'): return run(['qs', 'ipc', '-p', str(ui), 'call', target, method])
        def inspect(): return json.loads(ipc('inspect'))
        def caches_match():
            native = {m['name']: m['activeWorkspace']['id'] for m in h.query('monitors')}
            focused_id = h.query('activeworkspace')['id']
            for state in [json.loads(ipc('inspect', 'omaspace-sync')),
                          json.loads(run(['omarchy-shell', 'omaspace-sync', 'inspect']))]:
                if state['focused'] != focused_id: return False
                if {m['name']: m['workspace'] for m in state['monitors']} != native: return False
                counts = {w['id']: w.get('windows') for w in state['workspaces']}
                for w in h.query('workspaces'):
                    if counts.get(w['id']) != w['windows']: return False
            return True
        try:
            for source, destination, arrow in [(95,94,'Left'), (94,95,'Right')] * 3:
                ipc('open')
                wait(lambda: inspect()['workspaces'] and not inspect()['busy'])
                actual = inspect()
                assert actual['selected'] == source, f"Reopen selected stale workspace: {actual}, expected {source}"
                subprocess.run(['wtype', '-k', 'm', '-k', arrow], check=True)
                chosen = inspect()
                assert (chosen['carrying'], chosen['selected']) == (source, destination), chosen
                subprocess.run(['wtype', '-k', 'Return'], check=True)
                wait(lambda: next(c for c in fixtures() if c['address'] == client['address'])['workspace']['id'] == destination)
                wait(lambda: not inspect()['busy'])
                try:
                    wait(caches_match)
                except AssertionError:
                    print('Native:', json.dumps({'monitors': {m['name']: m['activeWorkspace']['id'] for m in h.query('monitors')}, 'workspaces': {w['id']: w['windows'] for w in h.query('workspaces')}}))
                    print('Popup cache:', ipc('inspect', 'omaspace-sync'))
                    print('Bar cache:', run(['omarchy-shell', 'omaspace-sync', 'inspect']))
                    raise
                assert inspect()['selected'] == destination, inspect()
                ipc('close')
                print(f'PASS: reopen → move {source} to {destination}; popup and Omarchy bar match native workspace state', flush=True)
            logs = run(['qs', 'log', '-p', str(ui), '-t', '30', '--no-color'])
            assert not any(e in logs for e in ['ERROR', 'TypeError', 'ReferenceError']), logs
        finally:
            subprocess.run(['qs', 'kill', '-p', str(ui)], capture_output=True)
finally:
    for c in fixtures(): h.dispatch('window.close', {'window': 'address:' + c['address']})
    h.evaluate('if _omaspaceReturnRules then for _,r in ipairs(_omaspaceReturnRules) do r:set_enabled(false) end; _omaspaceReturnRules=nil end; return "OMASPACE_OK"')
    for m in original: h.dispatch('focus', {'workspace': str(m['activeWorkspace']['id'])})
    if focused: h.dispatch('focus', {'window': 'address:' + focused})
    if was_running: subprocess.run(['systemctl', '--user', 'start', 'omaspace-session.service'], check=True)
    now = {c['address']: c['workspace']['id'] for c in h.query('clients')}
    assert all(now.get(addr) == ws for addr, ws in original_clients.items()), 'A work window changed workspace'
    print('PASS: work windows stayed on their original workspaces; temporary fixture removed.', flush=True)
