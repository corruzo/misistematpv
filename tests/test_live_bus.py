import threading
import time
import unittest

from app.services.live_bus import current_live_version, notify_live_change, wait_for_live_change


class LiveBusTest(unittest.TestCase):
    def test_wait_returns_when_a_change_is_published(self):
        previous = current_live_version()
        thread = threading.Thread(target=lambda: (time.sleep(0.01), notify_live_change()))
        thread.start()
        current = wait_for_live_change(previous, 1)
        thread.join()
        self.assertNotEqual(current, previous)

    def test_wait_times_out_without_database_access(self):
        previous = current_live_version()
        started = time.monotonic()
        current = wait_for_live_change(previous, 0.01)
        elapsed = time.monotonic() - started
        self.assertEqual(current, previous)
        self.assertGreaterEqual(elapsed, 0.005)


if __name__ == '__main__':
    unittest.main()