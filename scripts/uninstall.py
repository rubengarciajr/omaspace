#!/usr/bin/python
"""Remove only the integration created by OmaSpace, retaining user session data."""
from pathlib import Path
import os
import subprocess
import time
import shutil
from shell_sync import configure as configure_shell_sync
ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share'))
subprocess.run(['systemctl', '--user', 'stop', 'omaspace-session.service'], check=False)
subprocess.run(['qs', 'kill', '-p', str(ROOT / 'ui')], check=False)
p = CONFIG / 'hypr/hyprland.lua'
s = p.read_text()
backup = ROOT / '.backups' / ('uninstall-' + time.strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True, exist_ok=True)
configure_shell_sync(ROOT, CONFIG, backup, enabled=False)
# Compatibility command names created by the OmaOrder → OmaSpace migration.
for name, target in [('omaorder', ROOT / 'bin-omaspace'), ('omaorder-start', HOME / '.local/bin/omaspace-start')]:
    alias = HOME / '.local/bin' / name
    if alias.is_symlink() and alias.resolve() == target.resolve():
        alias.unlink()
shutil.copy2(p, backup / 'hyprland.lua')
p.write_text(s.replace('\n-- OmaSpace workspace overview\nrequire("hypr.omaspace")\n', '\n').replace('require("hypr.omaspace")\n', ''))
for path in [CONFIG / 'hypr/omaspace.lua', CONFIG / 'systemd/user/omaspace-session.service',
             DATA / 'applications/omaspace.desktop', DATA / 'icons/hicolor/scalable/apps/omaspace.svg',
             HOME / '.local/bin/omaspace-start', HOME / '.local/bin/omaspace']:
    if path.exists():
        shutil.copy2(path, backup / str(path.relative_to(HOME)).replace('/', '__'))
        path.unlink()
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['hyprctl', 'reload'], check=True)
errors = subprocess.check_output(['hyprctl', 'configerrors'], text=True).strip()
if errors:
    raise RuntimeError(errors)
print('OmaSpace integration removed. Super+Up has its default binding again. Snapshots retained.')
