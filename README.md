# OpenVPN Traffic-Generation Testbed

Automated generation and packet capture of repeated OpenVPN sessions for traffic-fingerprinting research. Each run produces a set of complete, labelled sessions — **connection → handshake → encrypted data → teardown** — captured one pcap per session, with per-session and per-capture metadata.

This tool **generates and records** sessions. It performs no detection or fingerprinting itself.

| | |
|---|---|
| **Client** | Raspberry Pi `10.42.0.120` — runs the experiment (OpenVPN client + controller + capture) |
| **Server** | Desktop `genuine` `10.208.23.185`, `udp/1194` — tunnel gateway (later: GCP VM) |
| **Isolation** | Linux network namespace `vpn` — only experiment traffic is tunneled |
| **Entry point** | `sudo ./run_experiment.sh` (on the client) |

---

## Table of contents

- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Output & data schema](#output--data-schema)
- [Operations](#operations)
- [Changing endpoints (IP / host)](#changing-endpoints-ip--host)
- [Troubleshooting](#troubleshooting)
- [Notes](#notes)

---

## Architecture

```text
Pi (client)                                  Server (desktop / GCP VM)
+---------------------------+                +----------------------+
| run_experiment.sh         |                | openvpn (udp/1194)   |
|   session_controller.py   |  encrypted     |   decrypts           |
|     openvpn  ------------------------------->   NAT to Internet ----> web
|     tcpdump (real NIC) <----- udp/1194 flow |                      |
|     traffic_gen (netns)   |                +----------------------+
+---------------------------+
   one pcap per session = handshake + data + teardown
```

**Isolation model** — the client never disturbs its own networking (SSH, DNS, apt stay put):

- OpenVPN runs with `--ifconfig-noexec --route-noexec`, so it never edits the host routing table.
- The `--up` hook (`netns_up.sh`) moves the tun device into the `vpn` namespace and sets the default route **there**.
- Traffic is generated with `ip netns exec vpn …`, so it can only exit through the tunnel — there is no host route inside the namespace to leak onto.
- The OpenVPN **process** stays in the host namespace, so its encrypted UDP to the server crosses the real NIC — where `tcpdump` captures the full session.
- DNS inside the namespace uses `/etc/netns/vpn/resolv.conf` — no host DNS leak.

---

## Repository layout

### Client (`~/vpn-client/client/` on the Pi)

| File | Responsibility |
|---|---|
| `run_experiment.sh` | Entry point. Loads `config.env`, creates the `vpn` namespace + DNS, sets cleanup traps, ignores `SIGHUP` (survives SSH drop), launches the controller, tears the namespace down on exit. |
| `config.env` | The only file you normally edit — all settings. |
| `session_controller.py` | Core loop. Owns seeded randomness, the capture directory structure, and all metadata. |
| `netns_up.sh` | OpenVPN `--up` hook: moves tun into the namespace, assigns the pushed IP, sets the tunnel route, signals ready. **Must be executable.** |
| `netns_down.sh` | OpenVPN `--down` hook: clears the ready marker. **Must be executable.** |
| `traffic_gen.py` | One "visit" per request via `ip netns exec vpn`. Backends: `wget` (default), `curl`, `browser`. |
| `browse.py` | Headless-browser fetch; used only when `TRAFFIC_BACKEND=browser`. |
| `sites.txt` | Destination pool, one domain per line; sampled per request. |
| `client.ovpn` | OpenVPN client profile. Its `remote` line names the **server**; `proto`/`port` are parsed from it. |
| `ca.crt`, `client.crt`, `client.key` | TLS credentials referenced by `client.ovpn`. **Must sit alongside it.** |

Server-side scripts (`setup_server.sh`, `check_server.sh`, `server_capture.sh`) and stale `client_android_*.ovpn` profiles are harmless if present but unused on the Pi.

### Server (`~/vpn-lab/server/` on the desktop / GCP VM)

| File | Responsibility |
|---|---|
| `server.conf` | OpenVPN server config: port, proto, VPN subnet, cert paths. |
| `ca.crt`, `server.crt`, `server.key`, `dh.pem`, `ta.key` | Server TLS material referenced by `server.conf`. |
| `setup_server.sh` | Run once. Enables IP forwarding + NAT so tunnel clients reach the Internet. Idempotent; does not disturb normal server networking. |
| `check_server.sh` | Sanity check: listening?, forwarding on?, NAT rules present?, who's connected. |
| `server_capture.sh` | Optional second capture vantage on the server side. |

---

## Prerequisites

**Client (Pi):**

```bash
sudo apt-get update
sudo apt-get install -y openvpn wget tcpdump iproute2 python3 curl
# only if TRAFFIC_BACKEND=browser:
# pip install playwright && playwright install chromium
```

`client.ovpn` + `ca.crt` + `client.crt` + `client.key` must be in the client folder together.

**Server:** a working OpenVPN server (`server.conf` + certs). `iproute2` new enough for `ip -n` (Ubuntu 18.04+ / modern Pi OS).

---

## Quick start

**1. Server** — start it and enable forwarding/NAT:

```bash
cd ~/vpn-lab/server
sudo ss -lunp | grep 1194 || sudo openvpn --config server.conf --daemon \
  --log ~/vpn-lab/server/openvpn.log --status ~/vpn-lab/server/openvpn-status.log 5
bash setup_server.sh ~/vpn-lab/server/server.conf
```

**2. Client** — first-time setup, then run:

```bash
cd ~/vpn-client/client
chmod +x run_experiment.sh netns_up.sh netns_down.sh session_controller.py browse.py traffic_gen.py
ping -c2 10.208.23.185          # confirm the server is reachable
sudo ./run_experiment.sh        # expect: session_001: status=ok ip=10.8.0.2
```

> [!TIP]
> For a fast shakedown, set `SESSIONS=1` and `INTER_SESSION_DELAY_MIN/MAX=5` in `config.env` before the first run.

---

## Configuration

All settings live in `config.env` (sourced by `run_experiment.sh`, read by the controller). Nothing is hard-coded in the scripts.

| Setting | Default | Meaning |
|---|---|---|
| `SESSIONS` | `50` | Number of sessions to run. |
| `SEED` | *(empty)* | Fixed integer → reproducible run; empty → random (recorded in metadata). |
| `SESSION_DURATION_MIN` / `MAX` | `20` / `180` | Randomized session length (s). |
| `TRAFFIC_START_DELAY_MIN` / `MAX` | `2` / `15` | Delay after connect before traffic (s). |
| `INTER_SESSION_DELAY_MIN` / `MAX` | `180` / `180` | Gap between sessions (s). |
| `REQUESTS_MIN` / `MAX` | `3` / `12` | Randomized requests per session. |
| `REQUEST_INTERVAL_MIN` / `MAX` | `1` / `8` | Gap between requests (s). |
| `REQUEST_TIMEOUT` | `15` | Per-request timeout (s). |
| `TRAFFIC_BACKEND` | `wget` | `wget` \| `curl` \| `browser`. |
| `OVPN_CONFIG` | `./client.ovpn` | Client profile; server/proto/port parsed from it. |
| `NETNS` | `vpn` | Namespace name. |
| `VPN_DNS` | `1.1.1.1` | Resolver used inside the namespace. |
| `TUN_UP_TIMEOUT` | `60` | Max seconds to wait for the tunnel. |
| `CAPTURE` | `true` | Capture on/off. |
| `CAPTURE_IFACE` | `auto` | `auto` = NIC that reaches the server. |
| `SITES_FILE` | `./sites.txt` | Destination pool. |
| `OUTPUT_DIR` | `./experiment_out` | Output root. |

---

## Usage

```bash
sudo ./run_experiment.sh                                  # normal run
sudo nohup ./run_experiment.sh > run.out 2>&1 &           # unattended, survives SSH drop
```

**`Ctrl+C`** terminates gracefully: the current session's data is finalized, the capture `metadata.json` is written, the namespace is cleaned up, and the process exits. The next run creates a fresh `capture_*` directory.

---

## Output & data schema

`OUTPUT_DIR` (default `./experiment_out`). **Every run creates a new, independent `capture_<timestamp>/`** — a second run never mixes with the first (a `_2`, `_3` suffix is added if a name collides).

```text
experiment_out/
├── metadata.jsonl                 # GLOBAL index: one line per session, ALL captures
├── run/                           # internal scratch (ready/tuninfo/pid) — ignore
└── captures/
    ├── capture_2026-08-21_19-56-25/
    │   ├── metadata.json          # capture-level metadata
    │   ├── session_001/
    │   │   ├── session_001.pcap
    │   │   ├── session_001_openvpn.log
    │   │   └── session_metadata.json
    │   └── session_002/ …
    └── capture_2026-08-22_07-30-00/   # a later run — completely separate
        └── …
```

Session numbering restarts at `session_001` in every capture because the `capture_<timestamp>/` parent makes it unique.

**Capture-level** — `captures/capture_*/metadata.json` (written at start, finalized on normal end **and** on `Ctrl+C`):

```json
{
  "capture_id": "capture_2026-08-21_19-56-25",
  "start_time": "…", "end_time": "…", "duration_s": 2685.0,
  "total_sessions": 10, "stopped_by_user": true, "interface": "eth0",
  "config": { "seed": 10, "sessions_planned": 50, "server": "10.208.23.185",
              "proto": "udp", "port": "1194", "backend": "wget", "netns": "vpn" },
  "sessions": [ { "session_id": 1, "dir": "session_001", "status": "ok",
                  "connection_success": true, "packet_count": 812 } ]
}
```

**Session-level** — `captures/capture_*/session_NNN/session_metadata.json`:

```json
{
  "session_id": 1, "start_time": "…", "end_time": "…",
  "vpn_server": "10.208.23.185", "vpn_protocol": "OpenVPN", "proto": "udp", "port": "1194",
  "seed": 10, "planned_duration_s": 166, "traffic_start_delay_s": 7,
  "connection_success": true, "assigned_vpn_ip": "10.8.0.2", "vpn_gateway": "10.8.0.1",
  "connect_time_s": 1.2, "probe_http_code": "200",
  "status": "ok", "requests": [ { "dest": "https://bbc.com", "rc": 0, "t": 9.3 } ],
  "request_count": 10, "packet_count": 812, "vpn_terminated": true,
  "capture_id": "capture_2026-08-21_19-56-25",
  "files": [ "session_001.pcap", "session_001_openvpn.log", "session_metadata.json" ]
}
```

`status` ∈ `ok` | `connect_failed` | `tunnel_dropped`.

**Global index** — `experiment_out/metadata.jsonl`: one JSON object per line = every session across every capture, each tagged with its `capture_id`. Append-only; this is the "all sessions, all captures" list for analysis.

---

## Operations

### Server management

```bash
# is it listening?
sudo ss -lunp | grep 1194

# start (manual)
cd ~/vpn-lab/server
sudo openvpn --config server.conf --daemon \
  --log ~/vpn-lab/server/openvpn.log --status ~/vpn-lab/server/openvpn-status.log 5
```

**Auto-start on boot** (recommended — removes the most common failure, "server was off"):

```bash
sudo cp ~/vpn-lab/server/server.conf /etc/openvpn/server/lab.conf
sudo cp ~/vpn-lab/server/{ca.crt,server.crt,server.key,dh.pem,ta.key} /etc/openvpn/server/
sudo systemctl enable --now openvpn-server@lab
systemctl status openvpn-server@lab --no-pager
```

### Cold-start checklist (returning after a break)

1. Power on the server (or confirm the GCP VM is up).
2. Server: `sudo ss -lunp | grep 1194` — if empty, start it (above).
3. Server: `bash ~/vpn-lab/server/setup_server.sh ~/vpn-lab/server/server.conf` (idempotent).
4. `ssh deepak@10.42.0.120 && cd ~/vpn-client/client`.
5. `ping -c2 10.208.23.185` — must reply.
6. If files were freshly copied: `chmod +x` the scripts.
7. Set `config.env` (or `SESSIONS=1` for a test).
8. `sudo ./run_experiment.sh` — expect `session_001: status=ok ip=10.8.0.2`.

---

## Changing endpoints (IP / host)

### Client (Pi) IP changes — **edit nothing**

The client IP is not stored anywhere in the project (not in code, `config.env`, or `client.ovpn`). A new Pi IP only changes its outbound source address, which OpenVPN handles transparently. Just verify reachability:

```bash
ping -c2 10.208.23.185     # replies → run as normal; no reply → network/routing issue
```

The NIC name may change (`eth0` ↔ `wlan0`) — no action; `CAPTURE_IFACE=auto` re-detects it. Only external caveat: if you ever added a server firewall rule scoped to the Pi's **old** IP, update that rule.

### Server IP / host changes (e.g. desktop → GCP VM)

**Client** — edit one line in `client.ovpn`:

```text
remote <NEW_SERVER_IP> 1194
```

The capture filter (`host <server> and <proto> port <port>`) and capture interface both derive from this on the next run — no other client edits.

**New server** — one-time:

1. Install/configure OpenVPN reusing the **same** `ca`, `cert`/`key`, `ta.key`, cipher, and `port`/`proto` (so existing `client.ovpn` credentials still work). If you generate fresh certs instead, also copy the new `ca.crt`/`client.crt`/`client.key` to the Pi.
2. Open the port in the cloud firewall (GCP: allow `udp:1194` ingress; keep `tcp:22` for SSH).
3. Run `setup_server.sh`; start OpenVPN (ideally the systemd service above).
4. Confirm `sudo ss -lunp | grep 1194` shows it listening.

> [!NOTE]
> If port or protocol change, set them consistently in **both** `server.conf` and `client.ovpn`. The client capture filter follows `client.ovpn` automatically.

---

## Troubleshooting

Most issues are the server not running, or executable bits lost on copy.

| Symptom | Cause | Fix |
|---|---|---|
| `read UDPv4 [ECONNREFUSED]` | Server host reachable, but no OpenVPN listening (server down). | Start the server; verify `ss -lunp \| grep 1194`. |
| Fails in ~2s; `--up` error / `VPNLAB_NETNS unbound` | up-script env not delivered. | Use current `session_controller.py` (passes `--setenv`); ensure `netns_up/down` are executable. |
| Waits full ~60s then `tunnel did not establish` | No reply from server. | Server down / firewall / unreachable. `ping`; check `ss` on server. |
| `TLS handshake failed`, no initial packet | Control channel blocked, or cert/`tls-auth` mismatch. | Open `udp/1194`; verify certs and `tls-auth` match both sides. |
| Connects but `request_count: 0` / `probe_http_code: null` | Tunnel up but no egress. | Run `setup_server.sh` (forwarding/NAT). Docker hosts: put VPN `FORWARD` rules ahead of Docker's chain. |
| `permission denied` / `sudo: command not found` on `./run_experiment.sh` | Exec bit stripped when copied. | `chmod +x` the scripts (esp. `netns_up.sh` / `netns_down.sh`). |
| `Address already in use (errno=98)` on server start | Server already running. | Not an error — don't start a second. Or `pkill` then restart. |
| `ping` works but tunnel fails | `ping` answers from the OS, not the OpenVPN service. | Check `ss -lunp \| grep 1194` on the server. |
| `status: tunnel_dropped` mid-session | Network blip or server restarted. | Check server stability. It's logged and the run continues. |

**Layered checks — what each proves:**

- `ping <server>` — the machine is up and reachable (OS answers). Says nothing about OpenVPN.
- `ss -lunp | grep 1194` *(on server)* — the OpenVPN service is actually listening.
- Bare dial *(end-to-end — does the server answer the handshake)*:

```bash
sudo openvpn --config client.ovpn --dev null --ifconfig-noexec --route-noexec --verb 3
# "TLS: Initial packet from <server>" = answering
# "ECONNREFUSED"                      = server not running
# only retries, no initial packet     = firewall / unreachable
```

**Do the Pi's packets even reach the server?** Run on the server while dialing from the Pi:

```bash
sudo tcpdump -ni any udp port 1194 and host 10.42.0.120
# packets in but nothing back = server-side firewall drop
# nothing at all             = routing (packets not arriving)
```

**Read a failed session's own log:**

```bash
cat experiment_out/captures/capture_*/session_001/session_001_openvpn.log
```

---

## Notes

- `ping` proves the machine is up, not that OpenVPN is running — use `ss` on the server for the service.
- `nc -u -z` against OpenVPN usually prints nothing even when healthy; the bare dial is the real UDP test.
- One pcap per session already contains handshake + data + teardown (all on the same `udp/1194` flow) — don't split them.
- **Reproducibility:** set `SEED` to a fixed integer to replay identical timing and destination sequence; blank picks a random seed (recorded in the capture's `metadata.json`).
- Prefer **Ethernet** on the Pi for steadier capture timing; watch SD-card space and copy `experiment_out/` off periodically.
- OpenVPN over **TCP** works with no code change (the filter follows `client.ovpn`), but a TCP capture includes TCP's own overhead — a different fingerprint than UDP.
