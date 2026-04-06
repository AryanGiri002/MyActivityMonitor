#!/usr/bin/env python3
"""
powermon - Apple Silicon live system monitor
Usage: sudo python3 server.py [--port 7070] [--interval 2000]
"""

import asyncio
import json
import re
import sys
import argparse
import os
from pathlib import Path

try:
    import websockets
    import websockets.server
except ImportError:
    print("Missing dependency. Run: pip3 install websockets")
    sys.exit(1)

parser = argparse.ArgumentParser()
parser.add_argument("--port",     type=int, default=7070)
parser.add_argument("--interval", type=int, default=2000)
args = parser.parse_args()

HTTP_PORT  = args.port
WS_PORT    = args.port + 1
INTERVAL   = max(1000, args.interval)
SCRIPT_DIR = Path(__file__).parent
INDEX_HTML = SCRIPT_DIR / "index.html"

connected_clients: set = set()
latest_sample: dict    = {}


def parse_block(text: str) -> dict:
    d = {}

    def fi(pattern, default=0):
        m = re.search(pattern, text)
        return int(m.group(1)) if m else default

    def ff(pattern, default=0.0):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else default

    def fs(pattern, default=""):
        m = re.search(pattern, text)
        return m.group(1) if m else default

    d["cpu_power"]      = fi(r"CPU Power:\s*(\d+)\s*mW")
    d["gpu_power"]      = fi(r"GPU Power:\s*(\d+)\s*mW")
    d["ane_power"]      = fi(r"ANE Power:\s*(\d+)\s*mW")
    d["combined_power"] = fi(
        r"Combined Power.*?:\s*(\d+)\s*mW",
        d["cpu_power"] + d["gpu_power"]
    )
    d["thermal"] = fs(r"Current pressure level:\s*(\w+)", "Unknown")
    batt = fi(r"percent_charge:\s*(\d+)", -1)
    d["battery"] = batt if batt >= 0 else None

    d["e_cluster_active"] = ff(r"E-Cluster HW active residency:\s*([\d.]+)%")
    d["e_cluster_freq"]   = fi(r"E-Cluster HW active frequency:\s*(\d+)\s*MHz")
    d["p_cluster_active"] = ff(r"P-Cluster HW active residency:\s*([\d.]+)%")
    d["p_cluster_freq"]   = fi(r"P-Cluster HW active frequency:\s*(\d+)\s*MHz")

    cores = []
    current_type = "E"
    for line in text.split("\n"):
        if "E-Cluster" in line:
            current_type = "E"
        elif "-Cluster" in line and "P" in line:
            current_type = "P"
            
        m1 = re.search(r"CPU (\d+) frequency:\s*(\d+) MHz", line)
        if m1:
            cores.append({"id": int(m1.group(1)), "freq": int(m1.group(2)), "active": 0.0, "type": current_type})
            
        m2 = re.search(r"CPU (\d+) active residency:\s*([\d.]+)%", line)
        if m2 and cores and cores[-1]["id"] == int(m2.group(1)):
            cores[-1]["active"] = float(m2.group(2))
            
    d["cores"] = cores

    d["gpu_freq"]   = fi(r"GPU HW active frequency:\s*(\d+)\s*MHz")
    d["gpu_active"] = ff(r"GPU HW active residency:\s*([\d.]+)%")
    d["gpu_idle"]   = ff(r"GPU idle residency:\s*([\d.]+)%")

    m = re.search(r"out:\s*([\d.]+) packets/s,\s*([\d.]+) bytes/s", text)
    d["net_out_pkts"]  = float(m.group(1)) if m else 0.0
    d["net_out_bytes"] = float(m.group(2)) if m else 0.0
    m = re.search(r"in:\s*([\d.]+) packets/s,\s*([\d.]+) bytes/s", text)
    d["net_in_pkts"]  = float(m.group(1)) if m else 0.0
    d["net_in_bytes"] = float(m.group(2)) if m else 0.0

    m = re.search(r"read:\s*([\d.]+) ops/s\s*([\d.]+) KBytes/s", text)
    d["disk_read_ops"] = float(m.group(1)) if m else 0.0
    d["disk_read_kb"]  = float(m.group(2)) if m else 0.0
    m = re.search(r"write:\s*([\d.]+) ops/s\s*([\d.]+) KBytes/s", text)
    d["disk_write_ops"] = float(m.group(1)) if m else 0.0
    d["disk_write_kb"]  = float(m.group(2)) if m else 0.0

    # FIX: use [\r\n]{2,} to handle both \n\n and \r\n\r\n block endings
    procs = []
    sec = re.search(
        r"\*\*\* Running tasks \*\*\*[\r\n]+(.+?)(?:[\r\n]{2,}|\Z)",
        text, re.DOTALL
    )
    if sec:
        for line in sec.group(1).splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 7:
                try:
                    procs.append({
                        "name": " ".join(parts[:-6]),
                        "cpu":  float(parts[-6]),
                        "user": float(parts[-5])
                    })
                except (ValueError, IndexError):
                    pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    d["processes"] = procs[:20]
    return d


async def handle_http(reader, writer):
    """Minimal HTTP server."""
    try:
        data = b""
        while b"\r\n\r\n" not in data and b"\n\n" not in data:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=5)
            if not chunk:
                break
            data += chunk
            if len(data) > 32768:
                break

        html = INDEX_HTML.read_bytes()
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
            b"Connection: close\r\nCache-Control: no-cache\r\nContent-Length: "
            + str(len(html)).encode() + b"\r\n\r\n" + html
        )
        await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def ws_handler(websocket, path=None):
    connected_clients.add(websocket)
    print(f"[powermon] browser connected ({len(connected_clients)} client(s))")
    try:
        if latest_sample:
            await websocket.send(json.dumps({"type": "sample", "data": latest_sample}))
        await websocket.wait_closed()
    except Exception:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[powermon] browser disconnected ({len(connected_clients)} client(s))")


async def run_powermetrics_once():
    """Run one powermetrics session. Returns when the process exits."""
    global latest_sample
    cmd = [
        "powermetrics",
        "--samplers", "cpu_power,gpu_power,thermal,battery,network,disk,tasks",
        "-i", str(INTERVAL),
        "-n", "-1",
    ]
    print(f"[powermon] starting powermetrics  interval={INTERVAL}ms")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,   # capture so we can print errors
        )
    except FileNotFoundError:
        print("[powermon] ERROR: powermetrics not found — are you on Apple Silicon macOS?")
        await asyncio.sleep(10)   # long back-off, nothing will change on its own
        return

    async def drain_stderr():
        """Forward powermetrics stderr lines so we can see why it exits."""
        async for line in proc.stderr:
            msg = line.decode("utf-8", errors="replace").rstrip()
            if msg:
                if "proc_pidpath" in msg or "Second underflow" in msg:
                    continue
                print(f"[powermetrics] {msg}")

    stderr_task = asyncio.create_task(drain_stderr())

    sep = "*** Sampled system activity"
    buffer = ""
    try:
        # FIX: read in large chunks, NOT line-by-line.
        # powermetrics outputs big multi-line blocks; readline() causes the
        # internal pipe buffer to fill up → SIGPIPE → clean exit (code 0).
        while True:
            chunk = await proc.stdout.read(131072)   # 128 KB at a time
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")

            # split completed blocks on the separator
            while True:
                idx = buffer.find(sep, len(sep))
                if idx == -1:
                    break
                block, buffer = buffer[:idx], buffer[idx:]
                if len(block) < 200:
                    continue
                try:
                    sample = parse_block(block)
                    if sample.get("cpu_power") is not None:
                        latest_sample = sample
                        payload = json.dumps({"type": "sample", "data": sample})
                        if connected_clients:
                            await asyncio.gather(
                                *[ws.send(payload) for ws in list(connected_clients)],
                                return_exceptions=True
                            )
                except Exception as e:
                    print(f"[powermon] parse error: {e}")
    finally:
        stderr_task.cancel()
        try:
            await stderr_task
        except asyncio.CancelledError:
            pass

    await proc.wait()
    print(f"[powermon] powermetrics exited (code {proc.returncode})")


async def run_powermetrics():
    """FIX: restart loop — keeps monitoring alive if powermetrics exits unexpectedly."""
    while True:
        try:
            await run_powermetrics_once()
        except Exception as e:
            print(f"[powermon] powermetrics error: {e}")
        print("[powermon] restarting powermetrics in 3 s…")
        await asyncio.sleep(3)


async def main():
    if not INDEX_HTML.exists():
        print(f"[powermon] ERROR: index.html not found at {INDEX_HTML}")
        sys.exit(1)

    # FIX: start HTTP + WS servers first, then launch powermetrics as a background
    # task so the servers stay up even if powermetrics fails or restarts.
    http_server = await asyncio.start_server(handle_http, "127.0.0.1", HTTP_PORT)
    async with http_server:
        print(f"[powermon] dashboard  →  http://localhost:{HTTP_PORT}")
        async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
            print(f"[powermon] websocket  →  ws://localhost:{WS_PORT}")
            # run as a task so an exception here doesn't tear down the servers
            pm_task = asyncio.create_task(run_powermetrics())
            try:
                await pm_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    if os.geteuid() != 0:
        print(f"[powermon] needs sudo — run:  sudo python3 {__file__}")
        sys.exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[powermon] stopped.")