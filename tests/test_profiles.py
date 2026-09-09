import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import omaspace.core as core
from omaspace.__main__ import ProfileWatcher, restore_detected


def monitor(name, ident=0):
    return {'name': name, 'id': ident, 'width': 1920, 'height': 1080, 'scale': 1,
            'x': ident * 1920, 'y': 0, 'activeWorkspace': {'id': 1 if ident == 0 else 6}}


class Desktop:
    def __init__(self, names=('eDP-1', 'iPad')):
        self.monitors = [monitor(n, i) for i, n in enumerate(names)]
        secondary = 'DP-1' if 'DP-1' in names else 'iPad'
        self.rules = [{'workspaceString': str(n), 'monitor': 'eDP-1' if n <= 5 else secondary}
                      for n in range(1, 11)]
        self.workspaces = [{'id': n, 'name': str(n), 'monitor': 'eDP-1' if n <= 5 else secondary,
                            'tiledLayout': 'dwindle'} for n in range(1, 12)]
        self.clients = [self.client(1), self.client(12), self.client(-98)]
        self.workspaces += [{'id': 12, 'name': '12', 'monitor': 'eDP-1'},
                            {'id': -98, 'name': 'special:scratchpad', 'monitor': 'eDP-1'}]
        self.dispatched = []

    def client(self, ws):
        return {'address': '0x' + str(abs(ws)), 'class': 'foot', 'title': 'window',
                'workspace': {'id': ws, 'name': str(ws)}, 'monitor': 0,
                'at': [10, 30], 'size': [900, 1000], 'mapped': True, 'floating': False}

    def query(self, name):
        return copy.deepcopy({'monitors': self.monitors, 'workspacerules': self.rules,
                              'workspaces': self.workspaces, 'clients': self.clients}[name])

    def dispatch(self, method, args):
        self.dispatched.append((method, args))


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, value in [('STATE', Path(self.tmp.name) / 'state'),
                            ('CONFIG', Path(self.tmp.name) / 'config')]:
            p = patch.object(core, name, value)
            p.start()
            self.addCleanup(p.stop)
        for p in (patch.object(core, 'sunshine_connected', return_value=False),
                  patch.object(core, 'theme', return_value={}),
                  patch.object(core.DesktopRegistry, 'resolve', return_value=None)):
            p.start()
            self.addCleanup(p.stop)

    def test_laptop_has_five_main_workspaces_and_separate_open_extras(self):
        h = Desktop()
        state = core.state(h)
        self.assertEqual([w['id'] for w in state['workspaces']], list(range(1, 6)))
        self.assertEqual([w['id'] for w in state['auxiliaryWorkspaces']], [12, -98])
        self.assertEqual(state['profile']['name'], 'Laptop')
        self.assertEqual(state['profile']['outputs'], ['eDP-1'])
        h.monitors[0]['activeWorkspace']['id'] = 12
        self.assertEqual([w['id'] for w in core.state(h)['workspaces']], list(range(1, 6)))

    def test_external_and_ipad_profiles_are_distinct(self):
        docked = core.state(Desktop(('eDP-1', 'DP-1', 'iPad')))
        self.assertEqual(len(docked['workspaces']), 10)
        self.assertEqual(docked['profile']['outputs'], ['DP-1', 'eDP-1'])
        with patch.object(core, 'sunshine_connected', return_value=True):
            ipad = core.state(Desktop())
            both = core.state(Desktop(('eDP-1', 'DP-1', 'iPad')))
        self.assertEqual(len(ipad['workspaces']), 10)
        self.assertEqual(len({docked['profile']['id'], ipad['profile']['id'], both['profile']['id']}), 3)

    def test_profile_identity_ignores_order_numeric_ids_and_scale(self):
        a = [monitor('eDP-1'), monitor('DP-1', 1)]
        b = copy.deepcopy(a[::-1])
        b[0].update(id=99, scale=2)
        self.assertEqual(core.display_profile(a), core.display_profile(b))

    def test_disconnected_rules_hide_empty_fallback_workspaces(self):
        h = Desktop(('eDP-1',))
        for ws in h.workspaces:
            ws['monitor'] = 'eDP-1'
        self.assertEqual([w['id'] for w in core.state(h)['workspaces']], list(range(1, 6)))

    def test_save_profiles_and_manual_checkpoints_are_isolated(self):
        laptop = Desktop(('eDP-1',))
        dock = Desktop(('eDP-1', 'DP-1'))
        core.save_session(laptop)
        a = core.profile_directory(laptop.monitors)
        original = (a / 'session.json').read_bytes()
        core.save_session(dock)
        b = core.profile_directory(dock.monitors)
        dock_saved = (b / 'pinned-session.json').read_bytes()
        self.assertEqual((a / 'session.json').read_bytes(), original)
        laptop.clients[0]['title'] = 'changed title'
        core.save_session(laptop, automatic=True)
        self.assertEqual((a / 'pinned-session.json').read_bytes(), original)
        self.assertEqual((b / 'pinned-session.json').read_bytes(), dock_saved)
        self.assertEqual(len(core.state(laptop)['profiles']), 2)

    def test_unknown_profile_does_not_restore_other_displays(self):
        core.save_session(Desktop(('eDP-1', 'DP-1')))
        laptop = Desktop(('eDP-1',))
        with self.assertRaisesRegex(RuntimeError, 'No saved layout'):
            core.restore_session(laptop)
        self.assertEqual(laptop.dispatched, [])

    def test_legacy_migration_keeps_latest_and_pinned_display_sets(self):
        latest = {'version': 1, 'monitors': [monitor('eDP-1')], 'clients': [], 'savedAt': 1}
        pinned = dict(latest, monitors=[monitor('eDP-1'), monitor('DP-1', 1)])
        core.atomic_json(core.STATE / 'session.json', latest)
        core.atomic_json(core.STATE / 'pinned-session.json', pinned)
        core.migrate_profiles()
        self.assertEqual(core.read_json(core.STATE / 'session.json'), latest)
        self.assertEqual(core.read_json(core.STATE / 'pinned-session.json'), pinned)
        self.assertTrue((core.profile_directory(latest['monitors']) / 'session.json').exists())
        self.assertTrue((core.profile_directory(pinned['monitors']) / 'pinned-session.json').exists())
        self.assertTrue((core.profile_directory(pinned['monitors']) / 'session.json').exists())
        # Restarting migration cannot overwrite a newer profile.
        path = core.profile_directory(latest['monitors']) / 'session.json'
        core.atomic_json(path, {'savedAt': 2})
        core.migrate_profiles()
        self.assertEqual(core.read_json(path), {'savedAt': 2})

    def test_failed_restore_pauses_only_its_profile(self):
        laptop = Desktop(('eDP-1',))
        core.save_session(laptop)
        path = core.profile_directory(laptop.monitors) / 'session.json'
        saved = path.read_bytes()
        with patch('omaspace.__main__.restore_session', side_effect=RuntimeError('test failure')):
            restore_detected(laptop, laptop.monitors)
        core.save_session(laptop, automatic=True)
        self.assertEqual(path.read_bytes(), saved)
        core.save_session(Desktop(('eDP-1', 'DP-1')), automatic=True)
        self.assertEqual(len(core.state(laptop)['profiles']), 2)

    def test_monitor_change_rejects_stale_save_and_restore(self):
        h = Desktop(('eDP-1',))
        with self.assertRaisesRegex(RuntimeError, 'Displays changed'):
            core.save_session(h, expected_profile='old-profile')
        with self.assertRaisesRegex(RuntimeError, 'Displays changed'):
            core.restore_session(h, expected_profile='old-profile')
        self.assertEqual(h.dispatched, [])

    def test_no_display_does_not_create_empty_profile(self):
        with self.assertRaisesRegex(RuntimeError, 'No connected displays'):
            core.save_session(Desktop(()), automatic=True)
        self.assertFalse((core.STATE / 'profiles').exists())

    def test_restore_selects_matching_profile_and_report(self):
        laptop = Desktop(('eDP-1',))
        docked = Desktop(('eDP-1', 'DP-1'))
        core.save_session(laptop)
        core.save_session(docked)
        with patch.object(core, 'restore_layout', return_value=True):
            result = core.restore_session(laptop)
        self.assertIn('Restored Laptop:', result['message'])
        self.assertTrue((core.profile_directory(laptop.monitors) / 'restore-report.json').exists())
        self.assertFalse((core.profile_directory(docked.monitors) / 'restore-report.json').exists())

    def test_active_ipad_workspace_appears_only_when_streaming(self):
        h = Desktop(('eDP-1', 'DP-1', 'iPad'))
        h.monitors[2]['activeWorkspace']['id'] = 11
        h.workspaces[10]['monitor'] = 'iPad'
        self.assertNotIn(11, [w['id'] for w in core.state(h)['workspaces']])
        with patch.object(core, 'sunshine_connected', return_value=True):
            self.assertIn(11, [w['id'] for w in core.state(h)['workspaces']])

    def test_hotplug_debounce_does_not_save_departing_profile(self):
        watcher = ProfileWatcher('laptop')
        self.assertEqual(watcher.observe('dock', 10), 'settling')
        self.assertEqual(watcher.observe('dock', 14), 'settling')
        self.assertEqual(watcher.observe('laptop', 14.5), 'ready')
        self.assertEqual(watcher.observe('dock', 20), 'settling')
        self.assertEqual(watcher.observe('dock', 25), 'changed')
        self.assertEqual(watcher.observe('dock', 26), 'ready')


class SunshineTests(unittest.TestCase):
    def test_only_current_service_invocation_connection_counts(self):
        def run(argv, timeout):
            if argv[0] == 'systemctl':
                return 'ActiveState=active\nInvocationID=current'
            self.assertIn('_SYSTEMD_INVOCATION_ID=current', argv)
            return 'Info: CLIENT CONNECTED'
        with patch.object(core, 'run', side_effect=run):
            self.assertTrue(core.sunshine_connected())

    def test_disconnected_or_stopped_service_is_not_attached(self):
        with patch.object(core, 'run', side_effect=['ActiveState=active\nInvocationID=current',
                                                  'Info: CLIENT DISCONNECTED']):
            self.assertFalse(core.sunshine_connected())
        with patch.object(core, 'run', return_value='ActiveState=inactive\nInvocationID='):
            self.assertFalse(core.sunshine_connected())
