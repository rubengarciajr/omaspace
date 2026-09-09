import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import omaspace.core as core

class CoreTests(unittest.TestCase):
    monitors = [{'id': 0, 'name': 'eDP-1', 'activeWorkspace': {'id': 1}}]

    def restore_fixture(self, saved, live, layout='dwindle'):
        monitors = self.monitors
        class Fake:
            def query(self, name):
                return copy.deepcopy({'clients': live, 'monitors': monitors, 'workspacerules': [],
                                      'workspaces': [{'id': 1, 'tiledLayout': layout}]}[name])
            def dispatch(self, method, args):
                if method == 'window.move' and 'workspace' in args:
                    for c in live:
                        if 'address:' + c['address'] == args['window']:
                            c['workspace']['id'] = int(args['workspace'])
        core.atomic_json(core.profile_directory(monitors) / 'session.json',
                         {'version': 1, 'savedAt': 1, 'clients': saved,
                          'workspaces': [{'id': 1}]})
        with patch.object(core, 'state', return_value={}):
            return core.restore_session(Fake())

    def client(self, address, title, cls='foot'):
        return {'address': address, 'class': cls, 'title': title, 'workspace': {'id': 1, 'name': '1'},
                'mapped': True, 'floating': False, 'rect': [0, 0, 1, 1]}

    def test_layout_warning_protects_saved_session(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'STATE', Path(tmp)):
            result = self.restore_fixture([self.client('a', 'A')], [self.client('b', 'A')], 'master')
            self.assertTrue(result['layoutWarnings'])
            self.assertTrue((core.profile_directory(self.monitors) / 'restore-incomplete.json').exists())
            self.assertIn('automatic saving paused', result['message'])

    def test_exact_titles_reserved_before_fallback_matching(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'STATE', Path(tmp)), \
                patch.object(core, 'restore_layout', return_value=True) as rebuild:
            self.restore_fixture([self.client('a', 'old'), self.client('b', 'B')],
                                 [self.client('x', 'B'), self.client('y', 'new')])
            self.assertEqual(rebuild.call_args.args[1], {'b': 'x', 'a': 'y'})

    def test_extra_tiled_window_relocated_before_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'STATE', Path(tmp)), \
                patch.object(core, 'restore_layout', return_value=True):
            live = [self.client('x', 'A'), self.client('y', 'Extra', 'other-app')]
            result = self.restore_fixture([self.client('a', 'A')], live)
            self.assertEqual(live[1]['workspace']['id'], 2)
            self.assertEqual(result['relocated'][0]['address'], 'y')
            self.assertFalse(result['layoutWarnings'])
            self.assertFalse((core.profile_directory(self.monitors) / 'restore-incomplete.json').exists())

    def test_extra_floating_window_does_not_block_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'STATE', Path(tmp)), \
                patch.object(core, 'restore_layout', return_value=True) as rebuild:
            extra = self.client('y', 'Extra', 'other-app')
            extra['floating'] = True
            result = self.restore_fixture([self.client('a', 'A')], [self.client('x', 'A'), extra])
            rebuild.assert_called_once()
            self.assertEqual(result['relocated'], [])
            self.assertEqual(extra['workspace']['id'], 1)

    def test_lua_injection_and_unicode_are_data(self):
        value = 'hello"; os.execute("bad") --\n\\文'
        encoded = core.lua(value)
        self.assertTrue(encoded.startswith('"') and encoded.endswith('"'))
        self.assertNotIn('os.execute', encoded)
        self.assertNotIn('\n', encoded)
        self.assertIn('\\034', encoded)

    def test_reject_nonfinite_numbers(self):
        with self.assertRaises(ValueError):
            core.lua(float('nan'))

    def test_atomic_session_replaces_and_is_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.json'
            core.atomic_json(path, {'version': 1, 'title': '文'})
            core.atomic_json(path, {'version': 2})
            self.assertEqual(json.loads(path.read_text()), {'version': 2})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_binary_layout_recovery_preserves_asymmetric_split(self):
        clients = [{'address': 'a', 'rect': [0, 0, .4, .4]},
                   {'address': 'b', 'rect': [0, .4, .4, .6]},
                   {'address': 'c', 'rect': [.4, 0, .6, 1]}]
        tree = core.split_tree(clients)
        self.assertEqual(tree['axis'], 0)
        self.assertAlmostEqual(tree['ratio'], .4)
        self.assertEqual(tree['a']['axis'], 1)
        self.assertEqual(tree['b'], {'leaf': 'c'})

    def test_overlapping_layout_has_no_invented_tree(self):
        self.assertIsNone(core.split_tree([{'address': 'a', 'rect': [0, 0, 1, 1]}, {'address': 'b', 'rect': [0, 0, 1, 1]}]))

    def test_partial_overlap_does_not_produce_a_broken_tree(self):
        clients = [{'address': 'a', 'rect': [0, 0, .5, 1]},
                   {'address': 'b', 'rect': [.5, 0, .5, 1]},
                   {'address': 'c', 'rect': [.5, 0, .5, 1]}]
        self.assertIsNone(core.split_tree(clients))

    def test_closed_window_never_dispatches(self):
        class Fake:
            def query(self, _): return []
            def dispatch(self, *_): raise AssertionError('must not dispatch')
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            core.move_window('0x123', '2', Fake())

    def test_pin_requires_explicit_unpin(self):
        class Fake:
            def query(self, _): return [{'address': '0x123', 'pinned': True}]
        with self.assertRaisesRegex(RuntimeError, 'Unpin'):
            core.move_window('0x123', '2', Fake())

    def test_special_and_named_selectors(self):
        self.assertEqual(core.selector({'id': -98, 'name': 'special:scratchpad'}), 'special:scratchpad')
        self.assertEqual(core.selector({'id': -1337, 'name': 'Work'}), 'name:Work')
        self.assertEqual(core.selector({'id': 10, 'name': '10'}), '10')

    def test_window_selector_input_is_checked(self):
        class Fake:
            def query(self, _): return [{'address': '0x123'}]
            def dispatch(self, *_): raise AssertionError('must not dispatch')
        with self.assertRaises(ValueError):
            core.move_window('0x123', '2; exit', Fake())

    def test_operation_lock_excludes_second_writer(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'STATE', Path(tmp)):
            with core.lock():
                with self.assertRaisesRegex(RuntimeError, 'Another'):
                    with core.lock(): pass

if __name__ == '__main__':
    unittest.main()
