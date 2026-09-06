import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import omaspace.core as core

class CoreTests(unittest.TestCase):
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
