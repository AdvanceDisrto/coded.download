"""Read-only localhost WebSocket state stream; no real-world actions or controls.

Run: python -m network.server --host 127.0.0.1 --port 8765
"""
import argparse
import asyncio
import json

from websockets.asyncio.server import serve
from core.simulation import WorldState, advance, snapshot


async def stream_state(connection, *, ticks: int = 0, interval: float = 1.0):
    state = WorldState()
    step = 0
    while ticks == 0 or step < ticks:
        await connection.send(json.dumps(snapshot(state), sort_keys=True))
        state = advance(state)
        step += 1
        if ticks == 0 or step < ticks:
            await asyncio.sleep(interval)


async def run(host: str = "127.0.0.1", port: int = 8765, ticks: int = 0, interval: float = 1.0):
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only loopback connections are allowed by this demo")
    async with serve(lambda conn: stream_state(conn, ticks=ticks, interval=interval), host, port,
                     max_size=65536, compression=None) as server:
        actual = server.sockets[0].getsockname()[1]
        print(f"CODED_WORLD_ENGINE_SIMULATION_ONLY ws://127.0.0.1:{actual}", flush=True)
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ticks", type=int, default=0, help="0 for continuous streaming")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.ticks < 0 or args.interval < 0 or not 0 <= args.port <= 65535:
        parser.error("invalid ticks, interval or port")
    try:
        asyncio.run(run(**vars(args)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
