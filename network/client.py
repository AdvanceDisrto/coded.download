"""Read exactly two synthetic world-state messages. Run after network.server."""
import asyncio
import json
from websockets.asyncio.client import connect


async def main():
    async with connect("ws://127.0.0.1:8765") as ws:
        for _ in range(2):
            print(json.dumps(json.loads(await ws.recv()), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
