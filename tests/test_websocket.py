import asyncio
import json
import unittest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from network.server import stream_state, run


class WebSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_packets_over_local_websocket(self):
        async with serve(lambda c: stream_state(c, ticks=2, interval=0), "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as client:
                a = json.loads(await client.recv())
                b = json.loads(await client.recv())
                self.assertEqual(a["origin"], "SYNTHETIC_SIMULATION")
                self.assertEqual(a["world"]["tick"], 0)
                self.assertEqual(b["world"]["tick"], 1)

    async def test_nonloopback_rejected(self):
        with self.assertRaises(ValueError):
            await run(host="0.0.0.0", port=0)
