import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from rfid_agent.queue import ScanQueue


class RfidAgentQueueTest(unittest.TestCase):
    def make_queue(self, limit=10):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return ScanQueue(Path(directory.name) / 'agent.sqlite3', limit)

    def test_queue_is_fifo_and_acknowledges_only_explicitly(self):
        queue = self.make_queue()
        queue.enqueue('op-00000000000001', 'CARD-1', '2026-08-27T10:00:00+00:00')
        queue.enqueue('op-00000000000002', 'CARD-2', '2026-08-27T10:00:01+00:00')

        rows = queue.pending()
        self.assertEqual([row[2] for row in rows], ['CARD-1', 'CARD-2'])
        queue.mark_attempt(rows[0][0], 'timeout')
        self.assertEqual(queue.pending()[0][2], 'CARD-1')
        queue.acknowledge(rows[0][0])
        self.assertEqual(queue.pending()[0][2], 'CARD-2')

    def test_rejected_scan_is_removed_without_blocking_next_item(self):
        queue = self.make_queue()
        queue.enqueue('op-00000000000001', 'CARD-1', '2026-08-27T10:00:00+00:00')
        queue.enqueue('op-00000000000002', 'CARD-2', '2026-08-27T10:00:01+00:00')
        first = queue.pending()[0]

        queue.reject(first[0], first[1], first[2], first[3], 409, 'Lectura duplicada')

        self.assertEqual(queue.pending()[0][2], 'CARD-2')
        import sqlite3
        with closing(sqlite3.connect(queue.path)) as connection:
            rejected = connection.execute('SELECT card_code, status_code FROM rejected_scans').fetchall()
        self.assertEqual(rejected, [('CARD-1', 409)])

    def test_queue_limit_does_not_discard_oldest_scan(self):
        queue = self.make_queue(limit=1)
        queue.enqueue('op-00000000000001', 'CARD-1', '2026-08-27T10:00:00+00:00')
        with self.assertRaisesRegex(RuntimeError, 'límite'):
            queue.enqueue('op-00000000000002', 'CARD-2', '2026-08-27T10:00:01+00:00')
        self.assertEqual([row[2] for row in queue.pending()], ['CARD-1'])


if __name__ == '__main__':
    unittest.main()
