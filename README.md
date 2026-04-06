# powermon

Live Apple Silicon system monitor — streams `powermetrics` to a browser dashboard over WebSocket.

## Quick Install (macOS Only)

```bash
./install.sh
```

## run

```bash
activity
```

This command will automatically request sudo, launch the websockets server, and auto-open `http://localhost:7070` inside your default browser!

## options

```bash
sudo python3 server.py --port 8080       # custom port (WebSocket = port+1)
sudo python3 server.py --interval 1000   # sample every 1 second (default: 2000ms)
sudo python3 server.py --port 8080 --interval 1000
```

## what it shows

- **Power tab** — CPU / GPU / ANE / Combined power draw over time
- **CPU tab** — E-cluster & P-cluster active residency, per-core breakdown with live bars
- **GPU tab** — active residency % and frequency over time (dual Y-axis)
- **Network / Disk tab** — packets/s and ops/s over time
- **Processes tab** — top 20 processes, sortable + filterable, live updated

## notes

- Requires `sudo` because `powermetrics` does
- Only works on Apple Silicon (M1/M2/M3/M4)
- The browser auto-reconnects if the server restarts
- `--interval` minimum is 1000ms (powermetrics limit)
