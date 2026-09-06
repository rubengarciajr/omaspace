#!/usr/bin/python
"""Idempotent per-user install; source and backups remain in this project."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import time
from shell_sync import configure as configure_shell_sync

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state'))
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share'))
BACKUP = ROOT / '.backups' / time.strftime('%Y%m%d-%H%M%S')

def write(path, text, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        BACKUP.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, BACKUP / (str(path.relative_to(HOME)).replace('/', '__')))
    path.write_text(text)
    if executable:
        path.chmod(0o755)

def link(path, target):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() and path.resolve() == target.resolve():
        return
    if path.exists() or path.is_symlink():
        raise RuntimeError(f'Refusing to replace unrelated path: {path}')
    path.symlink_to(target)

for command in ['hyprctl', 'qs', 'python', 'gio', 'fc-match']:
    if not shutil.which(command):
        raise RuntimeError(f'Missing dependency: {command}')

for component in ['Style.qml', 'Color.qml']:
    if not (Path('/usr/share/omarchy/shell/Commons') / component).is_file():
        raise RuntimeError('OmaSpace requires the installed Omarchy shell shared style components.')

# Check exact API support before touching the compositor configuration.
if subprocess.check_output(['hyprctl', 'repl', 'return type(hl.dsp.workspace.change_id)'], text=True).strip() != 'function':
    raise RuntimeError('OmaSpace requires Hyprland with Lua workspace.change_id (tested on 0.56.2).')

for name, location in [('state', STATE / 'omaspace'), ('config', CONFIG / 'omaspace')]:
    target = ROOT / '.local' / name
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not location.exists():
        legacy = location.with_name('omaorder')
        link(location, legacy.resolve() if legacy.exists() else target)
configure_shell_sync(ROOT, CONFIG, BACKUP, enabled=True)
link(HOME / '.local/bin/omaspace', ROOT / 'bin-omaspace')
write(HOME / '.local/bin/omaspace-start', '#!/bin/sh\n# Called inside the current Hyprland login.\nsystemctl --user import-environment HYPRLAND_INSTANCE_SIGNATURE WAYLAND_DISPLAY XDG_CURRENT_DESKTOP\nexec systemctl --user restart omaspace-session.service\n', True)
unit = '''[Unit]
Description=OmaSpace session memory
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart="%h/.local/bin/omaspace" daemon
Restart=on-failure
RestartSec=10
TimeoutStopSec=5
UMask=0077

[Install]
WantedBy=graphical-session.target
'''
write(CONFIG / 'systemd/user/omaspace-session.service', unit)
write(CONFIG / 'hypr/omaspace.lua', (ROOT / 'packaging/omaspace.lua').read_text())
main = CONFIG / 'hypr/hyprland.lua'
require = 'require("hypr.omaspace")'
if require not in main.read_text():
    write(main, main.read_text().rstrip() + '\n\n-- OmaSpace workspace overview\n' + require + '\n')
icon = DATA / 'icons/hicolor/scalable/apps/omaspace.svg'
write(icon, (ROOT / 'packaging/omaspace.svg').read_text())
write(DATA / 'applications/omaspace.desktop', f'''[Desktop Entry]
Type=Application
Name=OmaSpace
Comment=Arrange windows, move workspaces, and remember your session
Exec="{HOME / '.local/bin/omaspace'}" toggle
Icon=omaspace
Terminal=false
Categories=Utility;System;
Keywords=workspaces;windows;overview;session;
''')
subprocess.run(['hyprctl', 'reload'], check=True)
errors = subprocess.check_output(['hyprctl', 'configerrors'], text=True).strip()
if errors:
    raise RuntimeError('Hyprland configuration errors: ' + errors)
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'import-environment', 'HYPRLAND_INSTANCE_SIGNATURE', 'WAYLAND_DISPLAY'], check=True)
# Mark this session already initialized: installing never relaunches the current desktop.
import sys
sys.path.insert(0, str(ROOT))
from omaspace.core import atomic_json, save_session
atomic_json(STATE / 'omaspace/login.json', {'signature': os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')})
if not (STATE / 'omaspace/session.json').exists():
    print(save_session()['message'])
subprocess.run(['systemctl', '--user', 'start', 'omaspace-session.service'], check=True)
print('Installed. Press Super+Up to open OmaSpace. Backups:', BACKUP)
