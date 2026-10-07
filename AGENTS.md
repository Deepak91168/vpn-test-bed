# V2 VPN testbed context for future agents

This file describes the current V2 experiment workflow. Read `README.md` for operation, `SHIP_TO_PI.md` for the current Pi update, `ISSUES.md` for known limits, and `STATUS.md` for dated test evidence. The `v1/` tree on the Pi is historical and separate from V2.

## Machines and paths

| Role | Path |
| --- | --- |
| Laptop client and source for Pi updates | `/home/deepak/vpn-testbed-v2` |
| Raspberry Pi client | `/home/pi/vpn-testbed-v2` |
| Desktop OpenVPN server | `/home/deepaksingh/vpn-testbed-v2/server/openvpn` |
| Permanent experiment archive on desktop | `/home/deepaksingh/VPN-Storage/experiments/openvpn` |

The current desktop VPN endpoint is `10.208.23.185`. The Pi is reachable directly from the laptop at `10.42.0.120` on the current link; an older route through the `netmon` SSH jump host is also described in `SHIP_TO_PI.md`. Do not put passwords, private keys, or certificates in documentation.

## What V2 runs

`runner/vpnlab` schedules one OpenVPN session at a time. It supports TCP and UDP, each with `vanilla`, `tls-auth`, `tls-crypt`, and `tls-crypt-v2` control protection: eight configurations in total. Both transports use port **1194**. TCP and UDP are distinct protocols, so sharing the port number does not combine their sessions. Client profiles are in `client/openvpn/vanilla/profiles/` and `client/openvpn/control-protection/<mode>/profiles/`; matching desktop server profiles are in `server/openvpn/`. The runner selects a profile from the requested transport and control mode. Existing client credentials are in `client/openvpn/credentials/`.

The master settings are `experiments/openvpn/run.json`. On the Pi its `host_config` must point to `hosts/raspberrypi.env`; the laptop uses `hosts/laptop.env`. Host files supply network, proxy, and SSH settings. `traffic/web/sites.txt` is the normal URL pool; `traffic/web/smoke-sites.txt` is the one-site check. Preserve the Pi's existing `run.json`, host file, credentials, and results when copying a port update.

For each session the runner selects the desktop server profile over SSH, starts OpenVPN, moves the TUN interface into the `vpnlabv2` network namespace, and requests websites with curl there. It runs tcpdump on the client's physical interface with a capture filter of `host <desktop IP> and <tcp|udp> port 1194`. This excludes other client/server ports such as SSH and HTTP. The port and IP filter alone cannot prove a packet is OpenVPN; the client log, decoded OpenVPN packets, tunnel data, and web result provide that evidence. A fresh TCP capture should include its connection handshake and one TCP conversation. The runner stops the server profile and removes the namespace after the session/experiment.

## Results and checks

Each experiment first appears under local `results/YYYY/Month/DD/<run>/`. It contains `schedule.csv`, summaries, configuration counts, `checksums.sha256`, `transfer.json`, and session folders. Each completed session normally has `client.pcap`, `metadata.json`, `stats.json`, `openvpn-client.log`, `capture.log`, and `web.log`. `by-configuration/` contains links to the same sessions. The runner copies the experiment to desktop `VPN-Storage` and verifies SHA-256 checksums. The desktop server runtime log is not a per-session archive; there is no separate server PCAP per session.

Use `runner/audit_pcaps.py` to read back a completed experiment: it checks the manifest, capture readability, filter isolation, OpenVPN decoding, and packet counts. A copy also exists on the desktop at `/home/deepaksingh/vpn-testbed-v2/audit_pcaps.py`. For website success, inspect the requested/final URL and HTTP status in session metadata, not only a tunnel packet or proxy response.

## Verified state and Pi port update

On 2026-10-08 the laptop and desktop completed four TCP/1194 modes plus UDP/1194 vanilla. The Pi then completed the same five-mode check in `pi-tcp1194-check_26_10_08_0119_4_5103` and `pi-udp1194-check_26_10_08_0119_1_6bf1`, followed by all four UDP modes in `pi-udp1194-all-check_26_10_08_0126_4_4c96`. Every tested session established OpenVPN, returned HTTP 200 from the intended Wikipedia URL, produced a readable capture with zero packets outside the recorded IP/protocol/port filter, and reached the desktop archive with matching checksums. Each TCP capture held one stream beginning with SYN, SYN/ACK, ACK. The Pi had no remaining `vpnlabv2` namespace or OpenVPN process after the runs. Thus all eight Pi modes have fresh port-1194 coverage.

The Pi tree supplied by the user contains `runner/vpnlab`, `traffic/web/smoke-sites.txt`, the client credentials, host settings, historical results, and `v1/`. The port update copied only the four TCP client profiles and current guidance/audit files listed at the top of `SHIP_TO_PI.md`. The Pi runner and its `run.json` were left in place. The short Pi TCP and UDP checks and desktop PCAP audit passed. Keep historical captures and metadata unchanged.
