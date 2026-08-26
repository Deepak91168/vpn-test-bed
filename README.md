# OpenVPN Traffic-Generation Testbed

Automated generation and packet capture of repeated OpenVPN sessions for traffic-fingerprinting research. Each run produces a set of complete, labelled sessions — **connection → handshake → encrypted data → teardown** — captured one pcap per session, with per-session and per-capture metadata.

This tool **generates and records** sessions. It performs no detection or fingerprinting itself.

> **Transports:** the core below documents the default **UDP** transport. **TCP mode (port 443)** is an additive option and is documented in full in the [Appendix — TCP Mode](#appendix--tcp-mode-port-443) at the end. The UDP setup is unchanged by it.

| | |
|---|---|
| **Client** | Raspberry Pi — runs the experiment (OpenVPN client + controller + capture) |
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
- [Appendix — TCP Mode (port 443)](#appendix--tcp-mode-port-443)

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

The capture filter is derived from the active profile as `host <server> and <proto> port <port>`.

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
| `run_experiment.sh` | Entry point. Loads `config.env`, creates the `vpn` namespace + DNS, sets cleanup traps, ignores `SIGHUP` (survives SSH drop), launches the controller, tears the namespace down on exit. Also accepts an optional `udp`/`tcp` argument (see appendix). |
| `config.env` | The only file you normally edit — all settings. |
| `session_controller.py` | Core loop. Owns seeded randomness, the capture directory structure, and all metadata. |
| `netns_up.sh` | OpenVPN `--up` hook: moves tun into the namespace, assigns the pushed IP, sets the tunnel route, signals ready. **Must be executable.** |
| `netns_down.sh` | OpenVPN `--down` hook: clears the ready marker. **Must be executable.** |
| `traffic_gen.py` | One "visit" per request via `ip netns exec vpn`. Backends: `wget` (default), `curl`, `browser`. |
| `browse.py` | Headless-browser fetch; used only when `TRAFFIC_BACKEND=browser`. |
| `sites.txt` | Destination pool, one domain per line; sampled per request. |
| `client.ovpn` | OpenVPN client profile (UDP). Its `remote` line names the **server**; `proto`/`port` are parsed from it. |
| `ca.crt`, `client.crt`, `client.key` | TLS credentials referenced by the profile(s). **Must sit alongside them.** |

*(For TCP, an additional `client-tcp.ovpn` is used — see the appendix.)*

### Server (`~/vpn-lab/server/` on the desktop / GCP VM)

| File | Responsibility |
|---|---|
| `server.conf` | OpenVPN server config: port, proto, VPN subnet, cert paths (UDP). |
| `ca.crt`, `server.crt`, `server.key`, `dh.pem`, `ta.key` | Server TLS material referenced by `server.conf`. |
| `setup_server.sh` | Run once. Enables IP forwarding + NAT so tunnel clients reach the Internet. Idempotent; does not disturb normal server networking. |
| `check_server.sh` | Sanity check: listening?, forwarding on?, NAT rules present?, who's connected. |
| `server_capture.sh` | Optional second capture vantage on the server side. |

*(For TCP, an additional `server-tcp.conf` is used — see the appendix.)*

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
sudo ./run_experiment.sh                                  # normal run (UDP)
sudo nohup ./run_experiment.sh > run.out 2>&1 &           # unattended, survives SSH drop
```

*(To run over TCP: `sudo ./run_experiment.sh tcp` — see the appendix.)*

**`Ctrl+C`** terminates gracefully: the current session's data is finalized, the capture `metadata.json` is written, the namespace is cleaned up, and the process exits. The next run creates a fresh `capture_*` directory.

---

## Output & data schema

`OUTPUT_DIR` (default `./experiment_out`). **Every run creates a new, independent `capture_<timestamp>/`** — a second run never mixes with the first (a `_2`, `_3` suffix is added if a name collides). *(When a transport is selected, the name is `capture_<transport>_<timestamp>` — see appendix.)*

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
  "transport": "udp",
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
  "vpn_server": "10.208.23.185", "vpn_protocol": "OpenVPN",
  "transport": "udp", "proto": "udp", "port": "1194",
  "seed": 10, "planned_duration_s": 166, "traffic_start_delay_s": 7,
  "connection_success": true, "assigned_vpn_ip": "10.8.0.2", "vpn_gateway": "10.8.0.1",
  "connect_time_s": 1.2, "probe_http_code": "200",
  "status": "ok", "requests": [ { "dest": "https://bbc.com", "rc": 0, "t": 9.3 } ],
  "request_count": 10, "packet_count": 812, "vpn_terminated": true,
  "capture_id": "capture_2026-08-21_19-56-25",
  "files": [ "session_001.pcap", "session_001_openvpn.log", "session_metadata.json" ]
}
```

`transport` ∈ `udp` | `tcp`; `status` ∈ `ok` | `connect_failed` | `tunnel_dropped`. `transport` is derived from the profile that actually ran, so it cannot drift.

**Global index** — `experiment_out/metadata.jsonl`: one JSON object per line = every session across every capture, each tagged with `transport` and `capture_id`. Append-only.

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
4. `ssh deepak@<pi-ip> && cd ~/vpn-client/client`.
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

The NIC name may change (`eth0` ↔ `wlan0`) — no action; `CAPTURE_IFACE=auto` re-detects it.

### Server IP / host changes (e.g. desktop → GCP VM)

**Client** — edit one line in `client.ovpn` *(and `client-tcp.ovpn` if you use TCP)*:

```text
remote <NEW_SERVER_IP> 1194
```

The capture filter and interface derive from this on the next run — no other client edits. On the new server: reuse the same `ca`/`cert`/`key`/`ta.key`/cipher, open the port(s) in the firewall, run `setup_server.sh`, and start OpenVPN.

---

## Troubleshooting

Most issues are the server not running, or executable bits lost on copy.

| Symptom | Cause | Fix |
|---|---|---|
| `read UDPv4 [ECONNREFUSED]` | Server host reachable, but no OpenVPN listening (server down). | Start the server; verify `ss -lunp \| grep 1194`. |
| Fails in ~2s; `--up` error / `VPNLAB_NETNS unbound` | up-script env not delivered. | Use current `session_controller.py` (passes `--setenv`); ensure `netns_up/down` are executable. |
| Waits full ~60s then `tunnel did not establish` | No reply from server. | Server down / firewall / unreachable. `ping`; check `ss` on server. |
| `TLS handshake failed`, no initial packet | Control channel blocked, or cert/`tls-auth` mismatch. | Open the port; verify certs and `tls-auth` match both sides. |
| Connects but `request_count: 0` / `probe_http_code: null` | Tunnel up but no egress. | Run `setup_server.sh` (forwarding/NAT). Docker hosts: VPN `FORWARD` rules ahead of Docker's chain. |
| `permission denied` / `sudo: command not found` on `./run_experiment.sh` | Exec bit stripped when copied. | `chmod +x` the scripts (esp. `netns_up.sh` / `netns_down.sh`). |
| `Address already in use (errno=98)` on server start | Server already running. | Not an error — don't start a second. Or `pkill` then restart. |
| `ping` works but tunnel fails | `ping` answers from the OS, not the OpenVPN service. | Check `ss -lunp \| grep 1194` on the server. |
| `status: tunnel_dropped` mid-session | Network blip or server restarted. | Check server stability. It's logged and the run continues. |

**Layered checks — what each proves:**

- `ping <server>` — the machine is up and reachable (OS answers). Says nothing about OpenVPN.
- `ss -lunp | grep 1194` *(on server)* — the OpenVPN service is actually listening.
- Bare dial *(end-to-end)*: `sudo openvpn --config client.ovpn --dev null --ifconfig-noexec --route-noexec --verb 3`
  — `TLS: Initial packet from <server>` = answering; `ECONNREFUSED` = server not running.

**Validate capture completeness:** compare `tcpdump -r <pcap> | wc -l` against `packet_count` in the session metadata; confirm `tcpdump`'s `dropped by kernel` count is 0 (SD-card write speed under heavy traffic is the realistic way to lose packets on a Pi).

---

## Notes

- `ping` proves the machine is up, not that OpenVPN is running — use `ss` on the server for the service.
- `nc -u -z` against OpenVPN usually prints nothing even when healthy; the bare dial is the real UDP test.
- One pcap per session already contains handshake + data + teardown (all on the same 5-tuple) — don't split them.
- **Reproducibility:** set `SEED` to a fixed integer to replay identical timing and destination sequence; blank picks a random seed (recorded in the capture's `metadata.json`).
- Prefer **Ethernet** on the Pi for steadier capture timing; watch SD-card space and copy `experiment_out/` off periodically.

<br>

---
---

# Appendix — TCP Mode (port 443)

Everything above describes the default **UDP** transport. **TCP mode is additive** — the UDP setup keeps working unchanged, and you switch per run. This appendix is self-contained and intentionally repeats the essentials so it can be read on its own.

## Why TCP mode

OpenVPN can run over TCP; on port **443** the flow resembles HTTPS. This is useful for studying the OpenVPN-over-TCP fingerprint and censorship-resistant ("looks like TLS on 443") configurations. The TCP capture is a **different fingerprint** from UDP by design (see the comparison at the end).

## How switching works

```bash
sudo ./run_experiment.sh udp     # → client.ovpn      → capture_udp_<ts>/ → filter: udp port 1194
sudo ./run_experiment.sh tcp     # → client-tcp.ovpn  → capture_tcp_<ts>/ → filter: tcp port 443
sudo ./run_experiment.sh         # no arg → OVPN_CONFIG from config.env (UDP). Unchanged behaviour.
```

The argument only selects the profile and a capture label. The controller then **parses `proto` and `port` from the chosen profile**, so the capture filter automatically becomes `host <server> and tcp port 443` — no per-run code edits. (`proto tcp` and `proto tcp-client` are equivalent in a client config.)

## Files (TCP)

| File | Contents |
|---|---|
| `client-tcp.ovpn` | `proto tcp` (== `tcp-client`), `remote <server> 443`, **same** `ca`/`cert`/`key`/cipher as `client.ovpn`. |
| `server-tcp.conf` | `proto tcp`, `port 443`, subnet **`10.9.0.0/24`** (distinct from UDP's `10.8.0.0/24` so both run at once), separate `status`/`log`. |

**Safest way to create the client profile** (copies your exact working UDP profile, changes only what TCP needs):

```bash
cd ~/vpn-client/client
cp client.ovpn client-tcp.ovpn
sed -i -e 's/^proto udp/proto tcp/' -e 's/^remote \(.*\) 1194/remote \1 443/' client-tcp.ovpn
```

## Server setup (TCP runs ALONGSIDE UDP)

```bash
cd ~/vpn-lab/server
# create server-tcp.conf from your working UDP config:
cp server.conf server-tcp.conf
sed -i -e 's/^proto udp/proto tcp/' -e 's/^port 1194/port 443/' \
       -e 's/^server 10\.8\.0\.0/server 10.9.0.0/' server-tcp.conf

# start it (in addition to the UDP daemon):
sudo openvpn --config server-tcp.conf --daemon --log openvpn-tcp.log --status openvpn-status-tcp.log 5

# NAT for the TCP subnet, and open the port:
bash setup_server.sh server-tcp.conf
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || true

# confirm it is listening (NOTE: -ltnp for TCP, not -lunp):
sudo ss -ltnp | grep :443
```

The distinct `10.9.0.0/24` subnet (and its own tun device, auto-assigned) lets the UDP and TCP servers coexist without a pool/interface clash. On the eventual GCP VM, also allow **`tcp:443`** ingress in the cloud firewall.

## What the capture contains (complete, and no noise)

Filter (auto-derived): **`host <server> and tcp port 443`**. Because OpenVPN-over-TCP rides a single 5-tuple, this captures the **entire** session on one flow:

- **TCP connection setup** — `SYN` → `SYN,ACK` → `ACK`.
- **OpenVPN control channel** — a real TLS session (`Client Hello`, `Server Hello`, `Application Data`), carrying `P_CONTROL_*` / `P_ACK_V1`.
- **Encrypted data** — `P_DATA_V2`.
- **Keepalives and rekeys** — periodic, on the same flow.
- **Teardown** — `FIN`/`RST` at disconnect.

These TCP setup/ACK/teardown packets **are part of the session** and are deliberately kept — they *are* the TCP fingerprint. There is **no noise**: anything not to/from `<server>:443` fails the filter and is never written.

**Precision assumption (stated honestly):** this is exact *because* the lab server runs only OpenVPN on `443`. If that same IP also served real HTTPS on `443`, that traffic would match too — not the case here, but it's an environmental guarantee, not packet-content verification.

**Reconnects are covered:** the filter pins the **server** port (`443`), not the client's random ephemeral source port, so a reconnect (which gets a new source port) is still captured.

## Storage & metadata labels (TCP)

- **Capture directory:** `capture_tcp_<timestamp>` (UDP runs are `capture_udp_<timestamp>`) — the two are always separated on disk.
- **`metadata.json`** (capture-level): `"transport": "tcp"`, and `proto`/`port` inside `config`.
- **`session_metadata.json`**: `"transport": "tcp"`, `proto`/`port`, and `assigned_vpn_ip` from the TCP subnet (e.g. `10.9.0.2`).
- **`metadata.jsonl`**: every row carries `transport` + `capture_id`.
- `transport` is derived from the profile that actually ran, so it can't drift from reality.

## Reading a TCP capture in Wireshark

A TCP pcap looks different from UDP — this is expected, not a fault.

- **Label it as OpenVPN:** right-click a packet → **Decode As…** → TCP port `443` → **OpenVPN**. The Protocol column then shows `P_CONTROL_HARD_RESET_*`, `P_ACK_V1`, `P_DATA_V2`.
- **Why packets show as `TCP` / `TLSv1.3` / `OpenVPN`** — Wireshark labels each packet by the **highest layer it can decode**:
  - `TCP` with `Len=0` = a **bare acknowledgement** (no payload). Nothing to decode — **not** a missing OpenVPN packet.
  - `TLSv1.3` (`Client Hello`, `Application Data`) = the OpenVPN **control channel**, which really is a TLS session. `[OpenVPN Message segment of a reassembled PDU]` means an OpenVPN message spans several TCP segments.
  - `OpenVPN` = packets whose opcode is directly visible (`P_DATA_V2`, etc.).
- **The server IS responding** even though roughly half its packets are small `Len=0` ACKs. Its real OpenVPN replies (e.g. `P_CONTROL_HARD_RESET_SERVER_V2`, `Server Hello`) are the `Len>0` packets. Useful filters:
  - `tcp.len > 0` — hide the empty ACKs, show only packets with payload.
  - `openvpn && ip.src == 10.208.23.185` — only the server's OpenVPN messages.
- **Ephemeral source port** (e.g. `36848 → 443`) is normal — the OS picks a random high source port per connection; only the server port (`443`) is fixed. This is exactly why the capture filter pins the server port, not the client port.

## TCP-specific troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| TCP run immediately fails / resets | No OpenVPN listening on `443`. | `sudo ss -ltnp \| grep :443`; start `server-tcp.conf`. |
| TCP connects at transport but no OpenVPN handshake | Reached a **non-OpenVPN** service on `443` (e.g. a web server). | Ensure `443` on the server is the OpenVPN TCP instance. |
| `profile not found: ./client-tcp.ovpn` | Profile missing on the Pi. | Create it (see above). |
| No egress on TCP (`request_count: 0`) | NAT not set for the TCP subnet. | `bash setup_server.sh server-tcp.conf` (covers `10.9.0.0/24`). |
| Can't reach `443` at all | Host or cloud firewall. | Open `tcp:443` (host `iptables`/`ufw`; GCP ingress rule). |

## Validate completeness (TCP)

- `tcpdump -r <pcap> | wc -l` matches `packet_count` in `session_metadata.json`.
- The pcap **starts with `SYN`** and **ends with `FIN`/`RST`** — that bracket means the whole connection was captured.
- `tcpdump`'s `dropped by kernel` = 0.

## UDP vs TCP at a glance

| Aspect | UDP | TCP |
|---|---|---|
| Port / subnet | `1194` / `10.8.0.0/24` | `443` / `10.9.0.0/24` |
| Connection setup | none | `SYN` / `SYN,ACK` / `ACK` |
| Acknowledgements | none | ~half the packets are bare `Len=0` ACKs |
| Framing | OpenVPN payload in nearly every packet | OpenVPN inside TLS records, segmented/reassembled |
| Teardown | none (just stops) | `FIN` / `RST` |
| Capture filter | `host <server> and udp port 1194` | `host <server> and tcp port 443` |
| Wireshark labels | mostly `OpenVPN` | mix of `TCP` / `TLSv1.3` / `OpenVPN` |

The difference is **signal, not noise** — it's the reason to capture both.