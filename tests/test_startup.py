import asyncio
import unittest

from sr1egamebot.startup import StartupError, start_bot


class FakeClient:
    def __init__(self):
        self.ready = asyncio.Event()
        self.stop = asyncio.Event()
        self.token = None
        self.closed = False

    async def start(self, token):
        self.token = token
        self.ready.set()
        await self.stop.wait()

    async def wait_until_ready(self):
        await self.ready.wait()

    async def close(self):
        self.closed = True
        self.stop.set()


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_ready_after_database_initialization(self):
        calls = []
        client = FakeClient()

        async def connect():
            calls.append("connect")

        async def initialize():
            calls.append("initialize")

        async def close_database():
            calls.append("close-database")

        task = await start_bot(client=client, token="test-token", connect_database=connect,
                               initialize=initialize, close_database=close_database)
        self.assertEqual(client.token, "test-token")
        self.assertEqual(calls, ["connect", "initialize"])
        self.assertFalse(task.done())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_database_failure_cleans_up_and_hides_connection_details(self):
        client = FakeClient()
        error = RuntimeError("mongodb://user:secret@private-host")
        calls = []

        async def connect():
            raise error

        async def initialize():
            calls.append("initialize")

        async def close_database():
            calls.append("close-database")

        with self.assertRaises(StartupError) as raised:
            await start_bot(client=client, token="test-token", connect_database=connect,
                            initialize=initialize, close_database=close_database,
                            stop_reminders=lambda: calls.append("stop-reminders"))
        self.assertIs(raised.exception.__cause__, error)
        self.assertNotIn("secret", str(raised.exception))
        self.assertEqual(calls, ["stop-reminders", "close-database"])
        self.assertTrue(client.closed)
