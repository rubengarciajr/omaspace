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
                   settings, state, swap_windows)


def daemon(no_restore=False):
    """Periodic recovery checkpoints; lifetime follows graphical-session.target."""
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with lock('daemon'):
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
            if settings().get('autoRestore', True) and (STATE / 'session.json').exists():
                try:
                    with lock():
                        restore_session()
                except Exception as e:
                    atomic_json(STATE / 'restore-report.json', {'message': str(e), 'failed': [str(e)], 'at': time.time()})
        atomic_json(stamp, {'signature': session})
        last_digest, candidate, stable_since = '', '', time.monotonic()
        while not stopped:
            try:
                if settings().get('autosave', True) and not (STATE / 'restore-incomplete.json').exists():
                    h = Hypr()
                    clients = h.query('clients')
                    signature = [(c['address'], c['workspace']['id'], c['at'], c['size'], c['floating'])
                                 for c in clients if c['workspace']['id'] > 0]
                    digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
                    if digest != candidate:
                        candidate, stable_since = digest, time.monotonic()
                    if digest != last_digest and time.monotonic() - stable_since >= 15:
                        with lock():
                            save_session(h, automatic=True)
                        last_digest = digest
            except Exception as e:
                print(f'OmaSpace checkpoint: {e}', file=sys.stderr, flush=True)
            for _ in range(5):
                if stopped:
                    return
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
                    result = save_session()
                elif cmd in ('restore', 'restore-pinned'):
                    result = restore_session(pinned=cmd == 'restore-pinned')
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
                    if len(a) != 2 or a[0] not in ('autoRestore', 'autosave') or a[1] not in ('true', 'false'):
                        raise ValueError('Usage: omaspace settings autoRestore|autosave true|false')
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
