"""Install/remove OmaSpace's user-owned Omarchy workspace-cache service."""
import json
from pathlib import Path
import shutil

PLUGIN_ID = 'omaspace.workspace-sync'
OCCUPIED = 'readonly property bool occupied: workspace !== null && workspace.toplevels.values.length > 0'
NATIVE_OCCUPIED = 'readonly property bool occupied: workspace !== null && Number(workspace.lastIpcObject.windows || 0) > 0 // OmaSpace: native count after workspace ID changes'


def configure_cloned_widgets(config, backup, enabled):
    # Quickshell's toplevel refresh can leave entries in the old workspace.
    # Use the native count in existing user clones; never edit packaged widgets
    # or replace a user's custom occupancy expression.
    for manifest in (config / 'omarchy/plugins').glob('*/manifest.json'):
        metadata = json.loads(manifest.read_text())
        if metadata.get('omarchy', {}).get('clonedFrom') != 'omarchy.workspaces':
            continue
        entry = metadata.get('entryPoints', {}).get('barWidget')
        if not entry:
            continue
        widget = (manifest.parent / entry).resolve()
        if not widget.is_relative_to((config / 'omarchy/plugins').resolve()):
            continue
        original = widget.read_text()
        updated = original.replace(OCCUPIED, NATIVE_OCCUPIED) if enabled else original.replace(NATIVE_OCCUPIED, OCCUPIED)
        if original != updated:
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(widget, backup / (manifest.parent.name + '__' + widget.name))
            widget.write_text(updated)


def configure(root, config, backup, enabled):
    plugin = config / 'omarchy/plugins' / PLUGIN_ID
    source = root / 'packaging/shell-sync'
    settings = config / 'omarchy/shell.json'
    data = json.loads(settings.read_text()) if settings.exists() else {'version': 1}
    entries = data.get('plugins', [])
    if not isinstance(entries, list):
        raise RuntimeError('Unexpected Omarchy plugins configuration; left unchanged.')
    if plugin.exists() or plugin.is_symlink():
        if not plugin.is_symlink() or plugin.resolve() != source.resolve():
            raise RuntimeError(f'Refusing to replace unrelated plugin: {plugin}')
    if enabled:
        plugin.parent.mkdir(parents=True, exist_ok=True)
        if not plugin.is_symlink():
            plugin.symlink_to(source, target_is_directory=True)
        if not any((p.get('id') if isinstance(p, dict) else p) == PLUGIN_ID for p in entries):
            data['plugins'] = entries + [{'id': PLUGIN_ID}]
        if PLUGIN_ID in data.get('disabledPlugins', []):
            data['disabledPlugins'] = [p for p in data['disabledPlugins'] if p != PLUGIN_ID]
    else:
        data['plugins'] = [p for p in entries if (p.get('id') if isinstance(p, dict) else p) != PLUGIN_ID]
        if plugin.is_symlink():
            plugin.unlink()
    updated = json.dumps(data, indent=2) + '\n'
    if not settings.exists() or json.loads(settings.read_text()) != data:
        if settings.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(settings, backup / 'omarchy__shell.json')
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(updated)
    configure_cloned_widgets(config, backup, enabled)
