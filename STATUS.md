# VPN testbed V2 status — 2026-10-03

## Pi Ctrl+C validation
- `openvpn-pi-interrupt-check-20261002T201647-76aa` planned two UDP vanilla sessions. The first completed successfully with one web visit, 207 captured packets, and six rekeys; Ctrl+C interrupted the second after VPN establishment and one attempted web visit.
- The experiment status is `interrupted`: one completed successful session, one `manual_interrupt` session, zero failed sessions. Both session metadata files have end times and `server_stop_ok: true`; both PCAPs are readable (207 and 19 packets), with zero packets outside `host 10.208.23.185 and udp port 1194`.
- The V2 server is no longer running. Desktop transfer and all checksums verified. The user then confirmed `ip netns list` was empty and `ip route get 10.208.23.185` still used `wlan0` via `10.184.96.1` with Pi source `10.184.121.210`.

## Pi all-eight mixed validation
- `openvpn-pi-eight-check-20261002T195725-c0b2` completed one session in each of the eight UDP/TCP × vanilla/tls-auth/tls-crypt/tls-crypt-v2 modes. All 8 VPN sessions and all 24 Wikipedia HTTPS visits succeeded with HTTP 200; each session recorded 3 or 4 completed rekeys using R=3 and S=12 (29 total).
- Client PCAPs contain 3,146 packets in total. `tcpdump` found zero packets outside the profile-derived desktop IP/protocol/port filter in every PCAP. All eight by-configuration links resolve to their session directories; all eight V2 server stops were recorded.
- Seed 42 produced eight unique scheduled modes. Seven post-session waits were recorded, from 2.174 to 3.838 seconds; there was no final wait. Desktop transfer and all checksums verified. Pi Ctrl+C cleanup and post-run namespace absence were verified later, as recorded above.

## Pi timed rekey and repeated website visits
- Latest Pi run `openvpn-standard-20261002T195029-454b` used UDP vanilla, `reneg_sec: 3`, and `session_seconds: 12`. All three `https://www.wikipedia.org/` visits returned HTTPS 200 with 93,955 response bytes each. The tunnel stayed up 12.032 seconds.
- Client log has five `Control Channel: TLS` entries: one initial handshake plus four completed rekeys, matching metadata. The client PCAP has 355 filtered frames, including 270 decoded `P_DATA_V2` frames; every outer frame has desktop `10.208.23.185` as an endpoint and UDP port 1194. Transfer and desktop checksums verified.
- This confirmed repeated page fetches and timed rekeying through the Pi VPN for UDP vanilla. The workload is curl with redirects, not a browser that renders JavaScript or clicks links. The other seven Pi modes and Pi interrupt cleanup were verified later, as recorded above.

## Pi successful website smoke run
- `openvpn-standard-20261002T194556-f430` connected UDP vanilla, visited `https://www.wikipedia.org/` through the desktop proxy with HTTP 200 and 93,955 response bytes, captured 104 packets, and transferred with verified checksums.
- Its recorded `reneg_sec` was `null` and `session_seconds` was `0`. `rekeys=0` is expected for this 2.677-second session; no short renewal interval was requested. The runner and V2 server selector both pass `--reneg-sec R R` when R is supplied. Pi timed rekeying still awaits a Pi run.

## Pi web run after proxy recovery
- Pi run `openvpn-standard-20261002T194036-6d29` completed three UDP vanilla VPN connections, captured 112, 55, and 90 filtered packets, and transferred to desktop with verified checksums.
- Six planned HTTPS visits produced one success: `https://myfritz.net` redirected to `https://www.myfritz.net/devices/` and returned HTTP 200 with 6,885 response bytes. Four technical domains received proxy CONNECT 404; `dzen.ru` ended in a TLS error after redirect. Each session was marked failed because at least one visit failed.
- This establishes that the Pi VPN web path can reach a public HTTPS site through the desktop proxy. It does not validate all top-100 domains or the other seven OpenVPN modes on Pi.

## 2026-10-03 desktop Internet check
- Direct desktop HTTPS to Wikipedia and Python.org timed out at TCP connect.
- Desktop `curl -q --proxy http://proxy21.iitd.ac.in:3128 --compressed -L` completed HTTPS CONNECT and returned HTTP 200 for both sites. Retrieved pages had titles `Wikipedia` and `Welcome to Python.org`, with no IIT Delhi proxy login marker. Curl used normal TLS certificate verification.
- No proxy login or configuration change was attempted. The later Pi run above confirms one successful web visit; the earlier Pi `CONNECT ... 302` result remains a valid record of that earlier failure.

## Raspberry Pi smoke run
- The user confirmed `ip route get 10.208.23.185` via Pi `wlan0` and `ssh deepaksingh@10.208.23.185 hostname` returned `genuine`.
- Pi run `openvpn-standard-20261002T192621-3b7c` established UDP vanilla in 1.387 s. Its tunnel interface was `tunvpn` at `10.8.0.2`; OpenVPN logged `Initialization Sequence Completed` and exited cleanly. The physical-interface PCAP used `host 10.208.23.185 and udp port 1194`, held 33 packets, and decoded 15 `P_DATA_V2` messages.
- The session was marked failed only because `https://nginx.org` received `curl: (56) CONNECT tunnel failed, response 302` from the desktop-side proxy (`web_failure` / `proxy_connect_failed`). No website load was verified.
- Desktop transfer succeeded and `sha256sum -c checksums.sha256` passed for the stored result. Pi namespace cleanup was not independently checked; only one of eight modes has been run on Pi.

## Final handoff audit
- Added `ISSUES.md` with the active proxy limitation, the correction to historical web-success interpretation, Pi test gap, and curl/top-100 workload limits.
- Added `SHIP_TO_PI.md` with copy, host setup, reachability, smoke run, and acceptance checks. The root README now links to it and explains how to check a web visit before a larger run.
- Rechecked runner Python syntax, master JSON, client/server shell syntax, executable bits, the latest two proxy-failure classifications, the desktop result path, and remote checksums of the latest failed-web experiment. No eight-mode rerun was performed for this audit.
- Final static check confirmed all eight client/server profile paths, 100 unique HTTPS entries, default three visits and 2–6 second delay, CLI help, and documentation links. Removed only `runner/__pycache__/vpnlabcpython-312.pyc`; preserved all experiment results.
- At handoff time Pi execution was pending; the Raspberry Pi smoke run above now confirms one UDP vanilla connection and verified desktop transfer.
- Simplified the Pi shipping guide after receiving the exact Pi login `pi@10.184.121.210`: two laptop commands use `ssh -J netmon` and `scp -J netmon` to copy only V2 code/configs/credentials directly through the jump host. No archive or manual netmon copy is needed. Runtime `rsync` to desktop storage remains part of the experiment.

## Web-origin verification correction
- On 2026-10-02, the desktop VPN exit could not reach public sites directly; its campus proxy redirected HTTP to a login page and rejected HTTPS CONNECT with 302. The 2026-10-03 proxy check above now succeeds. No proxy login was attempted by this testbed work.
- Earlier reported web-success counts in this file reflect HTTP responses from the proxy; they do **not** verify visits to the intended websites. Their OpenVPN connectivity, encrypted packet captures, renewals, transfer, and checksum findings remain valid.
- The runner now rejects proxy login responses and records requested/final URL and failure reason. Live checks `openvpn-proxy-login-verification-20261002T230103-5b9d` and `openvpn-https-origin-verification-20261002T230131-c2b9` both recorded web failure and transferred with verified checksums.
- Wireshark/tshark decoded `P_DATA_V2` in all eight PCAPs of `openvpn-validation-mixed-20261002T183759-6605` (38–41 OpenVPN data messages per session). TCP/443 requires `-d tcp.port==443,openvpn` to decode as OpenVPN. The two newer proxy-failure PCAPs each contain one `P_DATA_V2` message. A data message proves tunnel payload was exchanged, not successful retrieval of the chosen site.

## Completed
- New laptop tree: `/home/deepak/vpn-testbed-v2`; new desktop server tree: `/home/deepaksingh/vpn-testbed-v2/server/openvpn`.
- Copied client/server credentials; verified certificate chains, key pairs, and tls-auth key match. The two restricted desktop crypt keys were copied with desktop sudo, leaving originals untouched.
- Created matching UDP/1194 and TCP/443 profiles for vanilla, tls-auth, tls-crypt, and tls-crypt-v2.
- Sequential CLI switches only V2 server processes, moves the TUN device into `vpnlabv2`, runs web visits there, captures with exact host/protocol/port BPF, records seeded schedule, statistics, actual delays, checksums, and transfers to desktop storage.
- Future WireGuard, commercial VPN CLI/UI, and OpenVPN obfuscation placeholders are empty.

## Validated
- Bash syntax, Python compile, profile mapping/reference checks, certificate verification, and PCAP parser checks passed.
- All eight modes established the VPN in seeded mixed run `openvpn-validation-mixed-20261002T183759-6605` (587 captured packets, transfer/checksums verified). Its old 8/8 web-success count included proxy responses and is not origin-visit evidence.
- Default delay tested in `openvpn-final-validation-20261002T184644-42d4` (2/2 successful, actual delay 2.209 s, transfer/checksums verified).
- Ctrl+C during delay: `openvpn-interrupt-validation-20261002T183926-5176` marked interrupted; one valid session and verified partial transfer.
- Ctrl+C during active web session: `openvpn-interrupt-active-20261002T184315-be32` marked the session/experiment interrupted, preserved partial web counts and 184-packet PCAP, stopped server, and verified transfer.
- Inverse BPF read of interrupted TCP PCAP found zero non-VPN packets. Laptop route to server remained via `wlp4s0`; `vpnlabv2` and `/etc/netns/vpnlabv2/resolv.conf` were absent after cleanup. No desktop OpenVPN process remained.

## Notes
- `hosts/laptop.env` has the campus DNS and web proxy. The proxy blocked earlier web visits but worked in the 2026-10-03 desktop check; update the host config when the desktop exit network changes or when moving to Raspberry Pi.
- The runner prompts once for desktop sudo and uses the current invoking user's SSH identity; it does not store passwords.
- Desktop forwarding/NAT was enabled at runtime for 10.8.0.0/24. No old setup files or GitHub repository were modified.

## 2026-10-02 update: top-100 web sites and key renewal
- `traffic/web/sites.txt` now pins Tranco standard list Y83YG ranks 1–100, retrieved 2026-10-02. Runs choose URLs independently with seeded randomness, save every planned choice in `schedule.csv`, and copy the exact list into the experiment.
- `--reneg-sec R` passes `--reneg-sec R R` to both V2 peers in all eight modes. `--session-seconds S` spreads web visits across a minimum connected duration. Metadata and summaries count renewals from completed control-channel TLS handshakes after the initial handshake.
- Mixed rekey test `openvpn-reneg-mixed-validation-20261002T223019-7c30`: all eight VPN modes connected, transfer/checksums verified. Its old 16/16 web-success count is not origin-visit evidence. Reading each client log showed two subsequent TLS control-channel handshakes per mode. An initial counter based only on client soft-reset messages undercounted server-initiated renewals; that parser was corrected.
- Default-mode VPN test `openvpn-top100-default-check-20261002T223307-b2df` connected without an explicit R; its web result predates origin validation. Final counter/timing test `openvpn-final-timing-check-20261002T223513-b0a0` recorded two renewals, correct web/tunnel timestamps, 0 inverse-BPF packets, and verified desktop checksums; its web-success result also predates origin validation.
- Recomputed the seeded mixed schedule: all eight configuration positions and 16 URL draws match, and the result's copied 100-site list matches its recorded SHA-256.
- The root README explains prerequisites, the complete pipeline, commands, interpretation, and storage; `SHIP_TO_PI.md` has the exact Pi copy/setup steps. The later Pi smoke run above confirmed one mode.
- Campus proxy responses may represent a proxy page rather than the intended origin; web logs and raw PCAP remain the evidence. Tranco includes infrastructure domains as well as normal homepages.
- Timed-hold Ctrl+C test `openvpn-reneg-interrupt-check-20261002T223804-5c0d`: marked session and experiment interrupted, kept one completed web visit and four observed renewals, closed the 133-packet PCAP, verified desktop checksums, removed namespace/DNS, preserved normal host route, and stopped the V2 server.

## 2026-10-02 final controls
- Added `experiments/openvpn/run.json` as the editable master experiment config. `sudo ./runner/vpnlab run openvpn` uses it; CLI options override it. Default is one UDP vanilla session with three seeded random site visits.
- Empty `WEB_PROXY` now explicitly removes inherited proxy variables and uses curl's no-proxy mode. A live direct test to `http://goo.gl` timed out on this campus network and was correctly marked `web_failure`; the partial result transferred with verified checksums. The configured campus proxy remains necessary here for tested web access.
- Confirmed `traffic/web/sites.txt` has exactly 100 unique URLs and contains neither `example.com` nor the IITD site.
- Config-only live test `openvpn-standard-20261002T225209-09b2`: 1/1 UDP vanilla VPN session, transfer/checksums verified. Its old 3/3 web-success count is not origin-visit evidence.
- Root README now maps files to roles and gives config values for single, grouped, mixed, and key-renewal runs plus Pi setup.

## 2026-10-03 update: curated default website list
- Replaced the original ranks 1–100 domain list in `traffic/web/sites.txt` with 100 unique HTTPS homepages selected in Tranco Y83YG rank order through rank 259. Each selected homepage passed two desktop-proxy checks for HTTPS 200, HTML, a page title, valid TLS, and a substantive response. The first check passed only 50 of the old top 100 domains.
- Updated `README.md`, `traffic/web/README.md`, `ISSUES.md`, and `SHIP_TO_PI.md` with the selection result and a short Pi update command. Old result snapshots remain unchanged.
- Remaining: copy the revised list to the Pi and perform a short default-list Pi workload. Live website/proxy availability can change; inspect per-visit metadata after each run.

## 2026-10-03 update: operator README and result interpretation
- Reorganized the root `README.md` into nine numbered sections covering the data path, directory/file roles, master config, CLI examples, mixed-run counts, session files, and an end section for desktop server files and stored results.
- Confirmed the desktop permanent copy of Pi eight-mode run `openvpn-pi-eight-check-20261002T195725-c0b2` contains the summary, per-mode breakdown, client PCAP, client OpenVPN log, and web log. There is no archived per-session server PCAP or server log; the desktop server runtime log is overwritten when another V2 profile starts.
- Checked README code fences and referenced local files. Documentation only; no experiment was rerun and the Pi copy of the README is not yet updated.

## 2026-10-03 update: verified Pi final run and mixed rekey targets
- Inspected desktop storage for Pi run `openvpn-pi-final-check-20261003T072927-7aac`: all eight configurations succeeded; 24/24 web visits returned HTTP 200 at website URLs; 32 renewals total (four each) with explicit R=3 and 12-second tunnels. All eight PCAPs matched their strict UDP/TCP BPF filters; desktop checksums verified; all V2 server stop commands succeeded and the V2 PID was absent afterward. The user has not yet supplied the Pi post-run namespace/route output.
- Added default all-eight mixed scheduling of balanced 0/1/2 **target** renewals when no explicit R is set. The scheduler records per-session target and interval in `schedule.csv` and metadata; observed renewal counts remain authoritative. Explicit `--reneg-sec R` preserves the previous shared-R behavior; `--no-mixed-rekeys` disables automatic targets.
- Python compilation and seeded schedule checks passed for one, two, and 25 sessions per mode (8, 16, and 200 sessions); each mode's target counts differ by at most one, and the target assignment varies reproducibly with the seed. The subsequent Pi live run verified the scheduler; see below.

## 2026-10-03 update: shorter, readable run names
- New client runs use `label_YY_MM_DD_HHMMZ_ID`, for example `mixed-rekeys_26_10_03_0728Z_d4c1`. The label is automatic for single, grouped, and mixed modes unless `purpose` is customized; legacy Pi `purpose: standard` also gets the automatic label. UTC is used consistently for the date folders, basename, and recorded timestamps.
- Confirmed Pi run `openvpn-pi-mixed-rekeys-20261003T082835-d4c1` in desktop storage: 8/8 successful sessions, 24/24 successful visits, target counts 3/3/2 for 0/1/2, observed counts 3/4/1, successful transfer, and desktop SHA-256 verification.
- The shorter naming change touches only the V2 client runner, its master config, and documentation. Desktop transfer follows the experiment directory name without server changes. Old result folders remain untouched. Live Pi validation followed; see below.
- Static checks passed for runner syntax, valid master JSON, derived and custom labels, compatibility with the Pi's older `purpose: standard`, the requested UTC `YY_MM_DD_HHMMZ` format, and the client/desktop date-path calculation. README and Pi guide code fences are balanced. A one-session Pi run is sufficient to check naming and transfer live; the eight VPN modes were already validated.

## 2026-10-03 update: Pi live validation of the shorter name
- Confirmed desktop copy `udp-vanilla_26_10_03_0842Z_55c2` under the expected UTC date path. Its label and 08:42 UTC start time match `experiment.yaml`.
- The Pi UDP vanilla session succeeded. Its one visit to `https://wordpress.org/` returned HTTP 200 with 165,094 response bytes. The client PCAP has 110 packets and 58,597 file bytes; inverse BPF reading found zero unrelated packets. Client/web logs and by-configuration link exist; V2 server stop succeeded and its PID file is absent.
- Desktop `transfer.json` reports success and checksum verification; a fresh `sha256sum -c checksums.sha256` also passed. No server code or old result folder was modified. The Pi's post-run namespace and route were not directly inspected in this particular naming test; those checks passed in the earlier Pi interruption validation.

## 2026-10-03 update: exact total mixed-session counts
- Added `--sessions N` as an exact total across selected modes; `sessions_per_config` retains its per-mode meaning. For 25 sessions over eight modes, a seeded selection gives seven modes 3 sessions and one mode 4, then the complete order is shuffled. Both the schedule and `configuration_summary.csv` record the actual planned counts.
- Added optional `sessions` to the master JSON config and documented the 25-total versus 25-per-mode commands. Static planning checks passed for 8, 25, and 200 sessions, including deterministic seeded selection and mixed 0/1/2 rekey targets. Pi live validation of this new total-count option is pending after copying the updated runner.

## 2026-10-03 update: total N is the operator default
- The laptop V2 master config now uses `sessions: 1` and `shuffle: true`. For every selection, `sessions: N` means N total, evenly divided across the selected modes. The old per-config CLI option remains for compatibility but is no longer the documented default. Existing Pi `run.json` must be edited locally or overridden with `--sessions N`; do not overwrite its Pi host config with the laptop file.
- The CLI now prints the seeded per-mode plan before the desktop password prompt and per-mode planned/started/outcome counts at the end. `schedule.csv` and `configuration_summary.csv` remain the durable record. README, OpenVPN experiment README, and Pi guide explain config-only and CLI runs.
- Compilation, JSON validation, and CLI help checks passed. Direct scheduler checks with seed 42 passed for 50 single-mode, 50 all-UDP, 50 all-TCP, 50 across two transports for one control, 24/25/50 all-eight mixed, and the legacy 200 per-config case. Verified exact total, even allocation, full coverage, deterministic schedule, and balanced 0/1/2 mixed targets with the correct R mapping. A live Pi run with the updated total-N runner is still pending after transfer; do not describe these planning checks as an end-to-end Pi test.
- Tried read-only SSH to Pi through the laptop's `netmon` alias; noninteractive authentication to `netmon@10.238.80.90` was denied because it needs a password. No Pi files were changed, and no V2 experiment was started for this update. The Pi operator must copy the updated runner/docs and run the small eight-mode check described in `SHIP_TO_PI.md`.

## 2026-10-03 update: Pi total-N live check
- User ran `total-n-check_26_10_03_0910Z_4249` on Pi with seed 42 and `--sessions 9`: eight modes appeared, UDP/tls-auth received the one extra session, and all nine sessions succeeded.
- Read the permanent desktop copy: 9/9 Wikipedia HTTPS visits returned HTTP 200 at the requested final URL, with 93,955 response bytes each and no reported web failures. The workload used the configured desktop proxy. Nine client PCAPs contain 1,281 packets total; inverse BPF inspection found zero unrelated packets, and all nine by-configuration links resolved.
- Read and verified all 63 SHA-256 entries in the desktop result against the copied files; none missing or mismatched. Transfer flags were both true. Observed rekeys totaled eight; one UDP vanilla session targeted two but observed one. This is a documented timing limit, not a session failure.
- This live check validates the total-N path and remote result storage. The Pi's namespace and route after this particular run were not directly inspected here; earlier interruption checks confirmed cleanup and normal `wlan0` route.
- Reorganized the root README into a linked nine-section operator guide: prerequisites, directory roles, config-only runs, pipeline, command cookbook with expected counts, site list, result interpretation, verified Pi example, and desktop server/storage. Added copy-paste checks for per-visit outcomes, PCAP filters, and desktop checksums. Updated `SHIP_TO_PI.md` and `ISSUES.md` to reflect the successful N=9 Pi run. The new README is still on the laptop until copied to Pi.

## 2026-10-03 update: latest Pi runs and final result naming
- Read the three newer desktop results: `mixed-rekeys_26_10_03_0914Z_6a34` completed 24/24 sessions and 72/72 HTTP 200 visits across all eight modes; `udp-all_26_10_03_1102Z_9a1f` completed 24/25 successful sessions with one `webex.com` HTTP 403 among 75 visits; `udp-all_26_10_03_1113Z_e79e` was interrupted after 11 of 25 planned sessions, preserving 10 successful and one interrupted session plus 108/108 successful attempted visits. All 60 client PCAPs matched their recorded filters and the desktop copies' 387 recorded checksums matched. The interruption and isolated website failure were classified correctly.
- New V2 result names now use `label_YY_MM_DD_HHMM_N_ID` with Asia/Kolkata 24-hour local time and planned total N. Date folders use the same local date; existing names and folders remain unchanged. `experiment.yaml` keeps the UTC `start_time` and adds `result_timezone: Asia/Kolkata`.
- Python syntax, CLI help, master JSON, and README/Pi-guide link and shell-snippet checks passed. Fixed-time path tests passed for ordinary time, midnight rollover, year rollover, N=1/24/50, and desktop transfer path construction. A live Pi run with the new naming runner is still pending after copying the runner; `SHIP_TO_PI.md` has a one-session verification command and checks.
