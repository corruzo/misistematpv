import asyncio
import inspect
import unittest

from app.controllers.notification_controller import websocket_events


class WebSocketRealtimeTest(unittest.TestCase):
    def test_websocket_endpoint_is_defined(self):
        self.assertTrue(inspect.iscoroutinefunction(websocket_events))


if __name__ == '__main__':
    unittest.main()