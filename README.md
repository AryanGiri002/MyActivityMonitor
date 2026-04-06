# powermon

Live Apple Silicon system monitor — streams `powermetrics` to a browser dashboard over WebSocket.

<img width="1512" height="855" alt="image" src="https://github.com/user-attachments/assets/253c8c24-9de1-42af-af35-63e8261ea780" />
<br>
<img width="1509" height="857" alt="image" src="https://github.com/user-attachments/assets/c0c4c760-472c-4963-9421-4c2df8f1356b" />
<br>
<img width="1512" height="857" alt="image" src="https://github.com/user-attachments/assets/982815c2-7f8e-45ca-bf9c-fbe18dec2c52" />
<br>
<img width="1512" height="855" alt="image" src="https://github.com/user-attachments/assets/c380e34f-6205-4304-8ea4-351429d76bc1" />


## Quick Install (macOS Only)

```bash
./install.sh
```

## run

Start the dashboard from anywhere:
```bash
activity
```
This command will automatically request sudo, launch the websockets server, and auto-open `http://localhost:7070` inside your default browser!

### management

```bash
activity --upgrade    # Pulls the latest code from GitHub and updates your dashboard
activity --uninstall  # Safely removes the global 'activity' alias from your system
```

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
