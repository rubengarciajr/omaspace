import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

from .core import (CONFIG, ROOT, STATE, Hypr, atomic_json, lock, move_window,
                   move_workspace, read_json, restore_session, run, save_session,
                   settings, state, swap_windows, connected_monitors, display_profile,
                   profile_directory, migrate_profiles)


class ProfileWatcher:
    """Debounce hotplug separately from ordinary changes to window geometry."""
    def __init__(self, active):
        self.active = active
        self.candidate = active
        self.since = time.monotonic()

    def observe(self, key, now):
        if key != self.candidate:
            self.candidate, self.since = key, now
        if key != self.active:
            if now - self.since < 5:
                return 'settling'
            self.active = key
            return 'changed'
        return 'ready'


class CheckpointTracker:
    """Save size/state adjustments promptly, while letting app startup settle."""
    def __init__(self, clients=()):
        self.last = self.signature(clients) if clients else None
        self.candidate = None
        self.since = 0

    @staticmethod
    def signature(clients):
        windows = sorted((c for c in clients if c['workspace']['id'] > 0 and c.get('mapped', True)),
                         key=lambda c: c['address'])
        structure = tuple((c['address'], c['workspace']['id'], c.get('monitor')) for c in windows)
        geometry = [(c['at'], c['size'], c.get('floating', False),
                     c.get('fullscreen', 0), c.get('fullscreenClient', 0)) for c in windows]
        return structure, hashlib.sha256(json.dumps(geometry).encode()).hexdigest()

    def ready(self, clients, now):
        signature = self.signature(clients)
        if signature != self.candidate:
            self.candidate, self.since = signature, now
        delay = 2 if self.last and self.last[0] == signature[0] else 15
        return signature != self.last and now - self.since >= delay

    def saved(self):
        self.last = self.candidate


def restore_detected(h, monitors):
    directory = profile_directory(monitors)
    if monitors and (directory / 'session.json').exists():
        try:
            restore_session(h, expected_profile=display_profile(monitors)['id'])
        except Exception as e:
            atomic_json(directory / 'restore-incomplete.json', {'message': str(e)})
            atomic_json(directory / 'restore-report.json', {'message': str(e), 'failed': [str(e)], 'at': time.time()})


def daemon(no_restore=False):
    """Periodic recovery checkpoints; lifetime follows graphical-session.target."""
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with lock('daemon'):
        with lock():
            migrate_profiles()
        session = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
        if not session:
            raise RuntimeError('Start OmaSpace from the Hyprland session.')
        stamp = STATE / 'login.json'
        previous = read_json(stamp, {})
        if previous.get('signature') != session and not no_restore:
            # Let Omarchy's monitor mapping and app autostarts finish first.
            for _ in range(25):
                if stopped:
                    return
                time.sleep(1)
            if settings().get('autoRestore', True):
                with lock():
                    h = Hypr()
                    restore_detected(h, connected_monitors(h.query('monitors')))
        atomic_json(stamp, {'signature': session})
        monitors = connected_monitors(Hypr().query('monitors'))
        watcher = ProfileWatcher(display_profile(monitors)['id'])
        checkpoint = CheckpointTracker(read_json(profile_directory(monitors) / 'session.json', {}).get('clients', []))
        while not stopped:
            try:
                h = Hypr()
                monitors = connected_monitors(h.query('monitors'))
                key = display_profile(monitors)['id']
                transition = watcher.observe(key, time.monotonic())
                if transition != 'ready':
                    checkpoint = CheckpointTracker(read_json(profile_directory(monitors) / 'session.json', {}).get('clients', []))
                    if transition == 'changed' and not no_restore and settings().get('autoProfileRestore', True):
                        with lock():
                            restore_detected(h, monitors)
                elif monitors and settings().get('autosave', True) and not (profile_directory(monitors) / 'restore-incomplete.json').exists():
                    clients = [c for c in h.query('clients') if c.get('monitor') in {m['id'] for m in monitors}]
                    if checkpoint.ready(clients, time.monotonic()):
                        with lock():
                            save_session(h, automatic=True, expected_profile=key)
                        checkpoint.saved()
            except Exception as e:
                print(f'OmaSpace checkpoint: {e}', file=sys.stderr, flush=True)
            if not stopped:
                time.sleep(1)


def main():
    p = argparse.ArgumentParser(description='OmaSpace — arrange windows, move whole workspaces, restore sessions.')
    p.add_argument('command', nargs='?', default='toggle', choices=['toggle', 'open', 'close', 'state', 'save', 'restore', 'restore-pinned', 'move-window', 'move-workspace', 'swap-windows', 'focus-workspace', 'focus-window', 'settings', 'daemon'])
    p.add_argument('args', nargs='*')
    p.add_argument('--no-restore', action='store_true')
    opts = p.parse_args()
    try:
        if opts.command in ('toggle', 'open', 'close'):
            config = str(ROOT / 'ui')
            if opts.command != 'close':
                run(['qs', '-p', config, '-d', '-n'])
            for _ in range(20):
                try:
                    run(['qs', 'ipc', '-p', config, 'call', 'omaspace', opts.command])
                    return
                except RuntimeError:
                    time.sleep(.1)
            raise RuntimeError('OmaSpace could not open. Check: qs log -p ' + config)
        if opts.command == 'daemon':
            daemon(opts.no_restore)
            return
        if opts.command == 'state':
            result = state()
        else:
            with lock():
                cmd, a = opts.command, opts.args
                if cmd == 'save':
                    result = save_session(expected_profile=a[0] if a else None)
                elif cmd in ('restore', 'restore-pinned'):
                    result = restore_session(pinned=cmd == 'restore-pinned', expected_profile=a[0] if a else None)
                elif cmd == 'move-window':
                    result = move_window(*a)
                elif cmd == 'move-workspace':
                    result = move_workspace(*a)
                elif cmd == 'swap-windows':
                    result = swap_windows(*a)
                elif cmd == 'focus-window':
                    Hypr().dispatch('focus', {'window': 'address:' + a[0]})
                    result = {'message': 'Window focused.'}
                elif cmd == 'focus-workspace':
                    if a[0].startswith('special:'):
                        Hypr().dispatch('workspace.toggle_special', a[0].removeprefix('special:'))
                    else:
                        Hypr().dispatch('focus', {'workspace': a[0]})
                    result = {'message': 'Workspace focused.'}
                elif cmd == 'settings':
                    if len(a) != 2 or a[0] not in ('autoRestore', 'autoProfileRestore', 'autosave') or a[1] not in ('true', 'false'):
                        raise ValueError('Usage: omaspace settings autoRestore|autoProfileRestore|autosave true|false')
                    cfg = settings()
                    cfg[a[0]] = a[1] == 'true'
                    atomic_json(CONFIG / 'settings.json', cfg)
                    result = {'message': 'Setting saved.'}
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as e:
        print(json.dumps({'error': str(e)}), flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
