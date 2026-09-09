import copy
import unittest

from omaspace.__main__ import CheckpointTracker


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.clients = [{'address': 'a', 'workspace': {'id': 1}, 'monitor': 0,
                         'at': [0, 0], 'size': [800, 600], 'floating': False},
                        {'address': 'b', 'workspace': {'id': 1}, 'monitor': 0,
                         'at': [800, 0], 'size': [800, 600], 'floating': False}]
        self.tracker = CheckpointTracker(self.clients)

    def test_resize_saves_promptly_after_drag_stops(self):
        self.clients[0]['size'][0] += 100
        self.assertFalse(self.tracker.ready(self.clients, 10))
        self.clients[0]['size'][0] += 100
        self.assertFalse(self.tracker.ready(self.clients, 11))
        self.assertFalse(self.tracker.ready(self.clients, 12))
        self.assertTrue(self.tracker.ready(self.clients, 13))
        self.tracker.saved()
        self.assertFalse(self.tracker.ready(self.clients, 20))

    def test_startup_and_closed_windows_still_wait_for_stability(self):
        for clients in (self.clients[:1], self.clients + [dict(self.clients[0], address='c')]):
            tracker = CheckpointTracker(self.clients)
            self.assertFalse(tracker.ready(clients, 10))
            self.assertFalse(tracker.ready(clients, 12))
            self.assertTrue(tracker.ready(clients, 25))

    def test_fullscreen_and_float_state_changes_trigger_checkpoint(self):
        for field in ('fullscreen', 'fullscreenClient', 'floating'):
            clients = copy.deepcopy(self.clients)
            clients[0][field] = 1
            tracker = CheckpointTracker(self.clients)
            self.assertFalse(tracker.ready(clients, 10))
            self.assertTrue(tracker.ready(clients, 12))

    def test_client_order_does_not_trigger_checkpoint(self):
        self.assertFalse(self.tracker.ready(self.clients[::-1], 10))
        self.assertFalse(self.tracker.ready(self.clients[::-1], 100))

    def test_workspace_change_keeps_longer_settling_time(self):
        self.clients[0]['workspace']['id'] = 2
        self.assertFalse(self.tracker.ready(self.clients, 10))
        self.assertFalse(self.tracker.ready(self.clients, 12))
        self.assertTrue(self.tracker.ready(self.clients, 25))
