# Automated OpenVPN session-generation testbed

One command over SSH generates N complete OpenVPN sessions. Each session is a
full lifecycle in ONE pcap: connection establishment -> TLS/control handshake ->
encrypted data traffic -> termination. No fingerprinting/detection logic — this
only produces the sessions for later analysis.

```
sudo ./run_experiment.sh
        |
        v
for each session:  capture on -> OpenVPN up -> wait til ESTABLISHED
                   -> tunneled traffic -> keep-alive -> OpenVPN down
                   -> verify terminated -> write metadata -> wait -> next
```

## Roles
- SERVER = desktop (10.208.23.185), already running OpenVPN. Ship the `server/`
  folder there.
- CLIENT = laptop, runs the whole experiment. Ship the `client/` folder there,
  with `client.ovpn` + `ca.crt` + `client.crt` + `client.key` beside the scripts.

---

## Isolation: why a network namespace (the important correction)

Your draft listed netns / dedicated user / policy routing as options. The
**network namespace is the simplest AND safest**, and it fixes a real hazard in
the naive approach:

- If OpenVPN runs normally, a pushed `redirect-gateway` rewrites the HOST's
  default route — that is exactly what would break your SSH / normal traffic.
- Policy routing by uid works but is "soft": a misconfigured rule, rp_filter, or
  a DNS query from the wrong process can leak onto the host path.

Here OpenVPN is started with `--ifconfig-noexec --route-noexec`, so it **never
touches the root namespace**. The `--up` script moves the tun device into an
isolated namespace (`vpn`) and sets the default route there. Result:

- The host's routing/DNS/SSH are physically untouched — there is no host route
  inside the namespace to leak onto, and no tunnel route in the host.
- Traffic is generated with `ip netns exec vpn ...`, so it can ONLY exit through
  the tunnel. This is the strongest form of "only VPN traffic goes to the VPN".
- The openvpn process stays in the root namespace, so its encrypted UDP to the
  server flows over the real NIC — where tcpdump captures the whole session.
- DNS is isolated too via `/etc/netns/vpn/resolv.conf` (no systemd-resolved leak).

## Selenium: not necessary (recommendation)

For OpenVPN fingerprinting the analyzer sees the ENCRYPTED flow; the OpenVPN
control/data channel looks the same whether the inner bytes came from Chrome or
wget. What changes the pattern is the volume/burstiness of inner traffic.

So the default backend is **wget with `--page-requisites`** (fetches the page
plus its CSS/JS/images — realistic browsing bursts), which is far lighter and
more reliable over SSH/headless than a browser. Switch `TRAFFIC_BACKEND` in
`config.env` to `curl` (single object) or `browser` (headless Chromium via
`browse.py`, most realistic, heaviest deps) if you want. All three run inside
the namespace, so traffic always traverses the tunnel.

---

## Ship & run

**On the server (once):**
```bash
cd server
bash setup_server.sh ~/vpn-lab/server/server.conf   # forwarding + NAT
bash check_server.sh                                 # sanity
```

**On the client:**
```bash
cd client
# put client.ovpn + ca.crt + client.crt + client.key here
sudo apt-get install -y openvpn wget tcpdump iproute2      # deps
# (only if TRAFFIC_BACKEND=browser:)  pip install playwright && playwright install chromium
nano config.env                                            # set SESSIONS, ranges, SEED...
sudo ./run_experiment.sh
# survive SSH drop:  sudo nohup ./run_experiment.sh > run.out 2>&1 &   (or use tmux)
```

You do NOT edit `client.ovpn` for routing — `--route-noexec` handles isolation,
so `redirect-gateway` in the profile is harmless.

## Output

```
experiment_out/
  experiment_manifest.json     # seed + resolved config (for reproducibility)
  metadata.jsonl               # one line per session
  captures/session_001.pcap    # full lifecycle, client<->server only
  results/session_001.json     # per-session metadata
  results/session_001_openvpn.log
```

Each `session_XXX.json` includes session_id, start/end time, vpn_server,
connection_success, assigned_vpn_ip, traffic_duration, request_count, pcap_file,
and the per-request log. Re-running with the same `SEED` reproduces the same
durations, delays, request counts, and destination sequence.

## Reproducibility

`SEED=` empty -> a random seed is chosen and written to `experiment_manifest.json`;
copy it back into `config.env` to replay. All per-session randomness is drawn in
a fixed order up front, so a mid-session failure never desyncs later sessions.

## Robustness / cleanup

- Establishment is event-driven: the controller waits for the `--up` script's
  ready signal AND a tun address (not a fixed sleep), up to `TUN_UP_TIMEOUT`.
- Every session uses try/finally: OpenVPN and tcpdump are always stopped, the
  tun is removed, and termination is verified and recorded.
- If the tunnel drops mid-session it's logged (`status: tunnel_dropped`) and the
  run continues.
- `run_experiment.sh` traps EXIT/INT/TERM to kill leftovers and delete the
  namespace; SIGHUP is ignored so an SSH drop won't kill the run.

## Notes
- Needs `iproute2` new enough for `ip -n` (Ubuntu 18.04+; fine on modern Pi OS).
- If the handshake never completes, check `tls-auth` — it's commented out in
  your `client.ovpn`; it must match the server.
- Moving to a Raspberry Pi: same `client/` folder, same commands.
