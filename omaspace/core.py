from __future__ import annotations

import configparser
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'omaspace'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'omaspace'


def run(argv, timeout=8):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f'{argv[0]} failed')
    return p.stdout.strip()


def lua(value):
    """Encode data, never interpolate application titles as Lua code."""
    if value is None:
        return 'nil'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('Non-finite number')
        return str(value)
    if isinstance(value, str):
        return '"' + ''.join('\\%03d' % b if b < 32 or b in (34, 92) else chr(b)
                             for b in value.encode('utf-8')) + '"' if value.isascii() else lua_utf8(value)
    if isinstance(value, list):
        return '{' + ','.join(map(lua, value)) + '}'
    if isinstance(value, dict):
        return '{' + ','.join('[' + lua(k) + ']=' + lua(v) for k, v in value.items()) + '}'
    raise TypeError(type(value))


def lua_utf8(value):
    return '"' + ''.join('\\%03d' % b for b in value.encode('utf-8')) + '"'


class Hypr:
    def query(self, name):
        return json.loads(run(['hyprctl', '-j', name]))

    def evaluate(self, code):
        result = run(['hyprctl', 'repl', code])
        if result != 'OMASPACE_OK':
            raise RuntimeError(result or 'Hyprland did not acknowledge the action')

    def dispatch(self, method, args):
        self.evaluate('local r=hl.dispatch(hl.dsp.' + method + '(' + lua(args) + ')); '
                      'if r and r.error then error(tostring(r.error)) end; return "OMASPACE_OK"')


def selector(ws):
    name = ws['name']
    return name if name.startswith('special:') else str(ws['id']) if ws['id'] > 0 else 'name:' + name


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


@contextlib.contextmanager
def lock(name='operation'):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / (name + '.lock')).open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another OmaSpace operation is running. Try again in a moment.')
        yield


class DesktopRegistry:
    def __init__(self):
        self.entries = []
        dirs = [Path.home() / '.local/share/applications']
        dirs += [Path(p) / 'applications' for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')]
        dirs += [Path.home() / '.local/share/flatpak/exports/share/applications', Path('/var/lib/flatpak/exports/share/applications')]
        seen = set()
        for directory in dirs:
            for path in directory.glob('**/*.desktop'):
                ident = str(path.relative_to(directory)).replace('/', '-')
                if ident in seen:
                    continue
                seen.add(ident)
                p = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    p.read(path)
                    d = dict(p['Desktop Entry'])
                    if d.get('hidden') == 'true' or d.get('type') != 'Application' or not d.get('exec'):
                        continue
                    tokens = shlex.split(d['exec'])
                    d.update(id=ident, path=str(path), binary=Path(tokens[0]).name if tokens else '')
                    self.entries.append(d)
                except (configparser.Error, ValueError, KeyError, OSError):
                    continue
        self.overrides = read_json(CONFIG / 'launchers.json', {})

    def resolve(self, client):
        cls = client.get('initialClass') or client['class']
        override = self.overrides.get(cls)
        if override:
            if isinstance(override, list) and override and all(isinstance(v, str) for v in override):
                return {'argv': override, 'label': cls}
            return None
        names = {cls.lower(), client['class'].lower()}
        matches = []
        for d in self.entries:
            score = 0
            if d.get('startupwmclass', '').lower() in names:
                score = 100
            if d['id'][:-8].lower() in names:
                score = max(score, 95)
            if d['binary'].lower() in names:
                score = max(score, 80)
            if d.get('name', '').lower() in names:
                score = max(score, 70)
            # Chromium app windows have dedicated desktop launchers.
            if any(('--class=' + n) in d['exec'].lower() for n in names if n):
                score = max(score, 100)
            if score:
                matches.append((score, d))
        if matches:
            d = sorted(matches, key=lambda x: (-x[0], len(x[1]['id'])))[0][1]
            return {'desktop': d['path'], 'label': d.get('name', cls), 'icon': d.get('icon', '')}
        return None


def theme():
    paths = [Path.home() / '.local/state/omarchy/current/theme/colors.toml',
             Path.home() / '.config/omarchy/current/theme/colors.toml']
    colors = {}
    for path in paths:
        try:
            colors = tomllib.loads(path.read_text())
            break
        except (OSError, ValueError):
            pass
    try:
        font = run(['fc-match', 'monospace', '-f', '%{family}']).split(',')[0]
    except (OSError, RuntimeError):
        font = 'monospace'
    return {'background': colors.get('background', '#101315'),
            'foreground': colors.get('foreground', '#cacccc'),
            'accent': colors.get('accent', colors.get('color4', '#7cb8a0')),
            'surface': colors.get('lighter_background', colors.get('background', '#101315')),
            'font': font}


def sunshine_connected():
    """Read connection events from the running service, never old boot logs."""
    for unit in ('app-dev.lizardbyte.app.Sunshine.service', 'sunshine.service'):
        try:
            properties = dict(line.split('=', 1) for line in run(
                ['systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'InvocationID'], timeout=2).splitlines())
            invocation = properties.get('InvocationID')
            if properties.get('ActiveState') != 'active' or not invocation:
                continue
            events = run(['journalctl', '--user', '_SYSTEMD_INVOCATION_ID=' + invocation,
                          '--no-pager', '-o', 'cat', '-g', 'CLIENT (DIS)?CONNECTED', '-n', '1'], timeout=2)
            return 'CLIENT CONNECTED' in events
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            continue
    return False


def connected_monitors(monitors):
    # Sunshine keeps its headless output even when Moonlight is disconnected.
    modes = read_json(CONFIG / 'displays.json', {}).get('virtual', {'iPad': 'sunshine'})
    streaming = sunshine_connected() if any(modes.get(m['name']) == 'sunshine' for m in monitors) else False
    return [m for m in monitors if not m.get('disabled') and m.get('mirrorOf', 'none') in ('none', '', None)
            and modes.get(m['name']) != 'off'
            and (modes.get(m['name']) != 'sunshine' or streaming)]


def display_profile(monitors):
    names = sorted(m['name'] for m in monitors)
    key = hashlib.sha256(json.dumps(names).encode()).hexdigest()[:16]
    labels = ['Laptop' if n.startswith(('eDP', 'LVDS')) else n for n in names]
    labels.sort(key=lambda n: (n != 'Laptop', n))
    return {'id': key, 'name': ' + '.join(labels) or 'No displays', 'outputs': names}


def profile_directory(monitors):
    return STATE / 'profiles' / display_profile(monitors)['id']


def migrate_profiles():
    """Copy legacy saves by their recorded displays; keep the originals intact."""
    marker = STATE / 'profiles-migrated.json'
    if marker.exists():
        return
    for filename in ('session.json', 'pinned-session.json'):
        saved = read_json(STATE / filename)
        if not saved or not saved.get('monitors'):
            continue
        profile = display_profile(saved['monitors'])
        directory = profile_directory(saved['monitors'])
        if not (directory / filename).exists():
            atomic_json(directory / filename, dict(saved, profile=profile))
        if filename == 'pinned-session.json' and not (directory / 'session.json').exists():
            atomic_json(directory / 'session.json', dict(saved, profile=profile))
        atomic_json(directory / 'profile.json', profile)
        if filename == 'session.json':
            for name in ('restore-incomplete.json', 'restore-report.json'):
                value = read_json(STATE / name)
                if value is not None and not (directory / name).exists():
                    atomic_json(directory / name, value)
    atomic_json(marker, {'at': time.time()})


def state(h=None, launchers=True):
    h = h or Hypr()
    all_monitors = h.query('monitors')
    monitors = connected_monitors(all_monitors)
    workspaces = h.query('workspaces')
    clients = [c for c in h.query('clients') if c.get('mapped') and c['class'] != 'org.omaspace.test']
    rules = h.query('workspacerules')
    present = {w['id'] for w in workspaces}
    names = {m['name'] for m in monitors}
    configured = {}
    # Monitor rules are authoritative even when Hyprland has moved an empty
    # persistent workspace onto a fallback display.
    for rule in rules:
        s = rule.get('workspaceString', '')
        if s.isdigit() and rule.get('enabled', True):
            target = rule.get('monitor', '')
            if target.startswith('desc:'):
                target = next((m['name'] for m in monitors if m.get('description', '').startswith(target[5:])), target)
            configured[int(s)] = target
            if int(s) not in present and (not target or target in names):
                workspaces.append({'id': int(s), 'name': s, 'monitor': target or (monitors[0]['name'] if monitors else ''), 'windows': 0})
                present.add(int(s))
    by_id = {m['id']: m for m in all_monitors}
    registry = DesktopRegistry() if launchers else None
    clients.sort(key=lambda c: (c['workspace']['id'], c['at'][0], c['at'][1], c['address']))
    for c in clients:
        if registry:
            c['launcher'] = registry.resolve(c)
        m = by_id.get(c['monitor'], monitors[0] if monitors else {})
        mw, mh = m.get('width', 1920) / m.get('scale', 1), m.get('height', 1080) / m.get('scale', 1)
        if m.get('transform', 0) % 2:
            mw, mh = mh, mw
        c['rect'] = [(c['at'][0] - m.get('x', 0)) / mw, (c['at'][1] - m.get('y', 0)) / mh,
                     c['size'][0] / mw, c['size'][1] / mh]
    for w in workspaces:
        w['selector'] = selector(w)
        w['label'] = '0' if w['id'] == 10 else str(w['id']) if w['id'] > 0 else w['name'].removeprefix('special:')
        w['clients'] = [c for c in clients if c['workspace']['id'] == w['id']]
        w['connected'] = w.get('monitor') in {m['name'] for m in monitors}
        w['active'] = any(m['activeWorkspace']['id'] == w['id'] for m in monitors)
    workspaces.sort(key=lambda w: (w['id'] <= 0, w['id']))
    primary, auxiliary = [], []
    for w in workspaces:
        target = configured.get(w['id'], w.get('monitor', ''))
        if w['id'] > 0 and (w['id'] in configured and (not target or target in names)):
            primary.append(w)
        elif (w['id'] > 0 and w['id'] not in configured and w['connected'] and w['active']
              and not any(not target or target == w.get('monitor') for target in configured.values())):
            primary.append(w)
        elif w['id'] > 0 and not configured and w['connected']:
            primary.append(w)
        elif w['clients']:
            auxiliary.append(w)
    profile = display_profile(monitors)
    directory = profile_directory(monitors)
    saved = read_json(directory / 'session.json', {})
    pinned = read_json(directory / 'pinned-session.json', {})
    profiles = [read_json(p) for p in sorted((STATE / 'profiles').glob('*/profile.json'))]
    return {'monitors': monitors, 'workspaces': primary, 'auxiliaryWorkspaces': auxiliary, 'clients': clients,
            'profile': profile, 'profiles': profiles, 'savePaused': (directory / 'restore-incomplete.json').exists(),
            'theme': theme(), 'savedAt': saved.get('savedAt'), 'savedCount': len(saved.get('clients', [])),
            'pinnedAt': pinned.get('savedAt'),
            'autoRestore': settings().get('autoRestore', True),
            'autoProfileRestore': settings().get('autoProfileRestore', True),
            'lastRestore': read_json(directory / 'restore-report.json', {})}


def settings():
    return read_json(CONFIG / 'settings.json', {'autoRestore': True, 'autosave': True})


def save_session(h=None, automatic=False, expected_profile=None):
    h = h or Hypr()
    migrate_profiles()
    s = state(h)
    if not s['monitors']:
        raise RuntimeError('No connected displays; keeping saved profiles.')
    if expected_profile and s['profile']['id'] != expected_profile:
        raise RuntimeError('Displays changed during save; keeping the previous profile.')
    directory = profile_directory(s['monitors'])
    if automatic and (directory / 'restore-incomplete.json').exists():
        return {'message': 'Automatic saving paused for this display profile.'}
    # Scratchpads are owned by Omarchy's own preloader and excluded from reboot launch.
    s['clients'] = [c for c in s['clients'] if c['workspace']['id'] > 0
                    and c['monitor'] in {m['id'] for m in s['monitors']}]
    s['workspaces'] += [w for w in s.pop('auxiliaryWorkspaces') if w['id'] > 0 and w['connected']]
    s.update(version=1, savedAt=time.time(), automatic=automatic)
    if display_profile(connected_monitors(h.query('monitors')))['id'] != s['profile']['id']:
        raise RuntimeError('Displays changed during save; keeping the previous profile.')
    old = read_json(directory / 'session.json')
    if automatic and not s['clients']:
        return {'message': 'Empty desktop: keeping the previous session.'}
    if old:
        history = directory / 'history'
        atomic_json(history / (str(time.time_ns()) + '.json'), old)
        for p in sorted(history.glob('*.json'))[:-20]:
            p.unlink()
    atomic_json(directory / 'profile.json', s['profile'])
    atomic_json(directory / 'session.json', s)
    if not automatic:
        atomic_json(directory / 'pinned-session.json', s)
        (directory / 'restore-incomplete.json').unlink(missing_ok=True)
    count = sum(bool(c.get('launcher')) for c in s['clients'])
    return {'message': f'Saved {s["profile"]["name"]}: {len(s["clients"])} windows · {count} can reopen automatically.'}


def move_window(address, target, h=None):
    h = h or Hypr()
    live = h.query('clients')
    c = next((c for c in live if c['address'] == address), None)
    if not c:
        raise RuntimeError('That window has closed.')
    if c.get('pinned'):
        raise RuntimeError('Unpin this window before moving it.')
    if not re.fullmatch(r'[1-9][0-9]*|special:[\w-]+|name:[^\n\r]+', str(target)):
        raise ValueError('Invalid destination')
    h.dispatch('window.move', {'window': 'address:' + address, 'workspace': str(target), 'follow': False})
    return {'message': 'Window moved.', 'undo': ['move-window', address, selector(c['workspace'])]}


def swap_windows(a, b, h=None):
    h = h or Hypr()
    live = {c['address']: c for c in h.query('clients')}
    if a not in live or b not in live:
        raise RuntimeError('A selected window has closed.')
    if a == b:
        return {'message': 'Choose a different window.'}
    if live[a].get('floating') or live[b].get('floating'):
        raise RuntimeError('Position swaps currently require two tiled windows.')
    h.dispatch('window.swap', {'window': 'address:' + a, 'target': 'address:' + b})
    return {'message': 'Window positions swapped.', 'undo': ['swap-windows', a, b]}


def move_workspace(source, destination, h=None):
    h = h or Hypr()
    source, destination = int(source), int(destination)
    if min(source, destination) <= 0 or max(source, destination) > 2147483647:
        raise ValueError('Whole-workspace moves require numbered workspaces.')
    if source == destination:
        return {'message': 'Choose a different workspace.'}
    current = {w['id']: w for w in h.query('workspaces')}
    if source not in current:
        raise RuntimeError('The source workspace no longer exists.')
    temp = next(n for n in range(2000000000, 2000001000) if n not in current)
    src = current[source]
    dst = current.get(destination)
    monitors = {m['name'] for m in h.query('monitors')}
    target_monitor = dst.get('monitor') if dst else src.get('monitor')
    if not dst:
        for rule in h.query('workspacerules'):
            if rule.get('workspaceString') == str(destination):
                target_monitor = rule.get('monitor', target_monitor)
    # One compositor-side operation retains the actual layout trees. Lua dispatch
    # errors are checked at each step, with ID rollback if an intermediate step fails.
    ops, inverse = [], []
    if dst:
        ops.append(('workspace.change_id', {'workspace': str(destination), 'id': temp}))
        inverse.append(('workspace.change_id', {'workspace': str(temp), 'id': destination}))
    ops.append(('workspace.change_id', {'workspace': str(source), 'id': destination}))
    inverse.append(('workspace.change_id', {'workspace': str(destination), 'id': source}))
    if dst:
        ops.append(('workspace.change_id', {'workspace': str(temp), 'id': source}))
        inverse.append(('workspace.change_id', {'workspace': str(source), 'id': temp}))
    if target_monitor in monitors:
        ops.append(('workspace.move', {'workspace': str(destination), 'monitor': target_monitor}))
        inverse.append(('workspace.move', {'workspace': str(destination), 'monitor': src['monitor']}))
    if dst and src['monitor'] in monitors:
        ops.append(('workspace.move', {'workspace': str(source), 'monitor': src['monitor']}))
        inverse.append(('workspace.move', {'workspace': str(source), 'monitor': dst['monitor']}))
    # Store recovery info before the operation; no windows are closed or recreated.
    atomic_json(STATE / 'workspace-recovery.json', {'source': source, 'destination': destination, 'temporary': temp, 'before': list(current.values())})
    code = 'local function d(f) local r=hl.dispatch(f); if r and r.error then error(tostring(r.error)) end end; local undo={}; '
    code += 'local ok,err=pcall(function() '
    for (method, args), (back_method, back_args) in zip(ops, inverse):
        code += 'd(hl.dsp.' + method + '(' + lua(args) + ')); '
        code += 'table.insert(undo,function() d(hl.dsp.' + back_method + '(' + lua(back_args) + ')) end); '
    code += 'end); if not ok then local rollback=true; for i=#undo,1,-1 do local success=pcall(undo[i]); rollback=rollback and success end; error(tostring(err)..(rollback and " (rolled back)" or " (rollback incomplete; see workspace-recovery.json)")) end; return "OMASPACE_OK"'
    h.evaluate(code)
    after = {w['id']: w for w in h.query('workspaces')}
    if temp in after:
        raise RuntimeError('Workspace move incomplete; recovery details saved in workspace-recovery.json.')
    return {'message': f'Workspaces {source} and {destination} swapped.' if dst and dst.get('windows') else f'Workspace {source} moved to {destination}.',
            'selectedWorkspace': destination,
            'undo': ['move-workspace', str(destination), str(source)]}


def split_tree(clients):
    """Recover a guillotine tiling tree from normalized window rectangles."""
    if not clients:
        return None
    if len(clients) == 1:
        return {'leaf': clients[0]['address']}
    for axis in (0, 1):
        ordered = sorted(clients, key=lambda c: c['rect'][axis])
        for i in range(1, len(ordered)):
            left, right = ordered[:i], ordered[i:]
            edge = max(c['rect'][axis] + c['rect'][axis + 2] for c in left)
            start = min(c['rect'][axis] for c in right)
            if edge <= start + 0.002:
                lo = min(c['rect'][axis] for c in clients)
                hi = max(c['rect'][axis] + c['rect'][axis + 2] for c in clients)
                a, b = split_tree(left), split_tree(right)
                if a is not None and b is not None:
                    return {'axis': axis, 'ratio': ((edge + start) / 2 - lo) / max(hi - lo, 0.001),
                            'a': a, 'b': b}
    return None


def restore_layout(saved, matched, h):
    tiled = [c for c in saved if not c.get('floating') and c['address'] in matched]
    tree = split_tree(tiled)
    ops = []
    def add(method, args):
        ops.append('d(hl.dsp.' + method + '(' + lua(args) + '));')
    def focus(addr):
        add('focus', {'window': 'address:' + matched[addr]})
        # Never send layout messages to an unrelated window if focus was denied.
        ops.append('assert(hl.get_active_window() and hl.get_active_window().address == ' + lua(matched[addr]) + ', "Window focus was blocked; close other overlays before restoring");')
    def leaf(node):
        return node['leaf'] if 'leaf' in node else leaf(node['a'])
    def build(node):
        if 'leaf' in node:
            return
        a, b = leaf(node['a']), leaf(node['b'])
        focus(a)
        add('layout', 'preselect ' + ('r' if node['axis'] == 0 else 'd'))
        add('window.float', {'window': 'address:' + matched[b], 'action': 'off'})
        focus(b)
        add('layout', f'splitratio {max(.1, min(1.9, node["ratio"] * 2)):.6f} exact')
        build(node['a'])
        build(node['b'])
    if tree and tiled:
        # Check focus before changing any floating state.
        focus(leaf(tree))
        for c in tiled:
            add('window.float', {'window': 'address:' + matched[c['address']], 'action': 'on'})
        add('window.float', {'window': 'address:' + matched[leaf(tree)], 'action': 'off'})
        build(tree)
        add('layout', 'preselect none')
        # One IPC request: user input cannot interleave the focus-dependent steps.
        code = 'local function d(f) local r=hl.dispatch(f); if r and r.error then error(tostring(r.error)) end end; '
        h.evaluate(code + ' '.join(ops) + ' return "OMASPACE_OK"')
    return bool(tree) or not tiled


def restore_session(h=None, pinned=False, expected_profile=None):
    h = h or Hypr()
    migrate_profiles()
    detected = connected_monitors(h.query('monitors'))
    profile = display_profile(detected)
    if not detected:
        raise RuntimeError('No connected displays; keeping saved profiles.')
    if expected_profile and profile['id'] != expected_profile:
        raise RuntimeError('Displays changed before restore; try again after they settle.')
    directory = profile_directory(detected)
    def check_displays():
        if display_profile(connected_monitors(h.query('monitors')))['id'] != profile['id']:
            raise RuntimeError('Displays changed during restore; saved profile protected. Retry when connected.')
    s = read_json(directory / ('pinned-session.json' if pinned else 'session.json'))
    if not s or s.get('version') != 1:
        raise RuntimeError('No saved layout for these displays yet. Press S to save this profile.')
    atomic_json(directory / 'before-restore.json', state(h))
    atomic_json(directory / 'restore-incomplete.json', {'savedAt': s['savedAt']})
    saved = s['clients']
    check_displays()
    matched, used, failed, skipped = {}, set(), [], []
    initial = h.query('clients')
    original_monitors = detected
    active = next((c['address'] for c in initial if c.get('focusHistoryID') == 0), None)
    def identity(c):
        return c.get('initialClass') or c['class']
    def match_existing(clients):
        # Reserve every exact title before a fallback can steal another window's
        # match (common with several terminals or browser windows).
        for exact in (True, False):
            for c in saved:
                if c['address'] in matched:
                    continue
                available = [n for n in clients if identity(n) == identity(c)
                             and n['address'] not in used
                             and (not exact or n['title'] == c['title'])]
                if available:
                    n = available[0]
                    matched[c['address']] = n['address']
                    used.add(n['address'])
    match_existing(initial)
    for c in saved:
        check_displays()
        if c['address'] in matched:
            continue
        # A previous launch may have restored several windows (for example Chrome).
        match_existing(h.query('clients'))
        if c['address'] in matched:
            continue
        launch = c.get('launcher')
        if not launch:
            skipped.append(c['class'])
            continue
        if launch.get('desktop'):
            if not Path(launch['desktop']).is_file():
                failed.append(c['class'] + ': launcher is missing')
                continue
            argv = ['gio', 'launch', launch['desktop']]
        else:
            argv = launch.get('argv', [])
        if not argv:
            skipped.append(c['class'])
            continue
        # Exec rules assist ordinary apps; post-launch matching also handles apps
        # that delegate window creation to an already-running process.
        h.evaluate('hl.exec_cmd(' + lua(shlex.join(argv)) + ', {workspace=' + lua(str(c['workspace']['id']) + ' silent') + '}); return "OMASPACE_OK"')
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            check_displays()
            candidates = [n for n in h.query('clients') if identity(n) == identity(c) and n['address'] not in used]
            if candidates:
                n = next((n for n in candidates if n['title'] == c['title']), candidates[0])
                matched[c['address']] = n['address']
                used.add(n['address'])
                break
            time.sleep(.3)
        else:
            failed.append(c['class'] + ': no new window appeared')
    check_displays()
    monitors = connected_monitors(h.query('monitors'))
    by_name = {m['name']: m for m in monitors}
    for ws in s['workspaces']:
        check_displays()
        if ws['id'] > 0 and ws.get('monitor') in by_name and any(w['id'] == ws['id'] for w in h.query('workspaces')):
            h.dispatch('workspace.move', {'workspace': str(ws['id']), 'monitor': ws['monitor']})
    for c in saved:
        check_displays()
        address = matched.get(c['address'])
        if not address:
            continue
        h.dispatch('window.fullscreen_state', {'window': 'address:' + address, 'internal': 0, 'client': 0})
        h.dispatch('window.move', {'window': 'address:' + address, 'workspace': str(c['workspace']['id']), 'follow': False})
        if not c.get('floating'):
            h.dispatch('window.float', {'window': 'address:' + address, 'action': 'off'})
        if c.get('floating'):
            h.dispatch('window.float', {'window': 'address:' + address, 'action': 'on'})
            ws = next((w for w in s['workspaces'] if w['id'] == c['workspace']['id']), {})
            m = by_name.get(ws.get('monitor'), monitors[0])
            mw, mh = m['width'] / m['scale'], m['height'] / m['scale']
            x, y, w, height = c['rect']
            h.dispatch('window.resize', {'window': 'address:' + address, 'x': max(80, round(w * mw)), 'y': max(60, round(height * mh)), 'relative': False})
            h.dispatch('window.move', {'window': 'address:' + address, 'x': m['x'] + max(0, round(x * mw)), 'y': m['y'] + max(0, round(y * mh)), 'relative': False})
    layout_warnings, relocated = [], []
    occupied_ids = {w['id'] for w in s['workspaces']} | {w['id'] for w in h.query('workspaces')}
    occupied_ids.update(int(r['workspaceString']) for r in h.query('workspacerules')
                        if r.get('workspaceString', '').isdigit())
    overflow = next(n for n in range(1, 2147483647) if n not in occupied_ids)
    for ws in s['workspaces']:
        check_displays()
        group = [c for c in saved if c['workspace']['id'] == ws['id'] and c['address'] in matched]
        if not group:
            continue
        live_ws = next((w for w in h.query('workspaces') if w['id'] == ws['id']), {})
        # Floating/unmapped windows do not participate in the tiling tree.
        extra = [c for c in h.query('clients') if c['workspace']['id'] == ws['id']
                 and c['address'] not in used and c.get('mapped') and not c.get('floating')]
        tiled = [c for c in group if not c.get('floating')]
        if not tiled:
            continue
        if live_ws.get('tiledLayout') == 'dwindle' and split_tree(tiled):
            for c in extra:
                if c.get('pinned'):
                    continue
                entry = {'address': c['address'], 'class': c['class'],
                         'from': ws['id'], 'to': overflow}
                # Write recovery intent before changing the desktop.
                atomic_json(directory / 'restore-extra-windows.json',
                            {'at': time.time(), 'windows': relocated + [entry]})
                move_window(c['address'], str(overflow), h)
                relocated.append(entry)
            extra = [c for c in h.query('clients') if c['workspace']['id'] == ws['id']
                     and c['address'] not in used and c.get('mapped') and not c.get('floating')]
        if live_ws.get('tiledLayout') == 'dwindle' and not extra:
            if not restore_layout(group, matched, h):
                layout_warnings.append(f'Workspace {ws["id"]}: non-binary layout; kept compositor tiling')
        elif tiled:
            layout_warnings.append(f'Workspace {ws["id"]}: kept current layout (extra windows or another layout engine)')
    for c in saved:
        if c['address'] in matched and (c.get('fullscreen') or c.get('fullscreenClient')):
            h.dispatch('window.fullscreen_state', {'window': 'address:' + matched[c['address']], 'internal': c['fullscreen'], 'client': c.get('fullscreenClient', 0)})
    # Restore the user's view after the placement work.
    for m in original_monitors:
        h.dispatch('focus', {'workspace': str(m['activeWorkspace']['id'])})
    if active and any(c['address'] == active for c in h.query('clients')):
        h.dispatch('focus', {'window': 'address:' + active})
    check_displays()
    result = {'message': f'Restored {profile["name"]}: {len(matched)} of {len(saved)} windows.', 'failed': failed, 'skipped': skipped,
              'layoutWarnings': layout_warnings, 'relocated': relocated, 'at': time.time()}
    if relocated:
        noun = 'window' if len(relocated) == 1 else 'windows'
        result['message'] += f' Moved {len(relocated)} extra {noun} to workspace {overflow}.'
    if layout_warnings:
        result['message'] += ' Layout incomplete; automatic saving paused. Retry restore or save to accept this arrangement.'
    atomic_json(directory / 'restore-report.json', result)
    if not failed and not skipped and not layout_warnings:
        (directory / 'restore-incomplete.json').unlink(missing_ok=True)
    return result
