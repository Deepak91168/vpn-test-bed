# VPN testbed V2: OpenVPN web experiments

V2 runs one OpenVPN session at a time from this client to the desktop at `10.208.23.185`. It supports UDP or TCP with vanilla TLS, `tls-auth`, `tls-crypt`, or `tls-crypt-v2`. The old VPN setup and GitHub repository are not part of this workflow.

Start here to run experiments. See [ISSUES.md](ISSUES.md) for current limits and [SHIP_TO_PI.md](SHIP_TO_PI.md) for first-time Pi setup or copying updates.

## Contents

1. [Before a run](#1-before-a-run)
2. [Directory map and file roles](#2-directory-map-and-file-roles)
3. [Edit one config and run](#3-edit-one-config-and-run)
4. [What happens in one experiment](#4-what-happens-in-one-experiment)
5. [Command cookbook](#5-command-cookbook)
6. [The 100-site list](#6-the-100-site-list)
7. [Result files and how to read them](#7-result-files-and-how-to-read-them)
8. [Verified Pi run and expected outcomes](#8-verified-pi-run-and-expected-outcomes)
9. [Desktop server and permanent results](#9-desktop-server-and-permanent-results)

**Where the evidence ends up:** a session's `client.pcap`, OpenVPN client log, web log, and metadata are first written under `results/` on the Pi/laptop. At finalization, the entire experiment is copied to `/home/deepaksingh/VPN-Storage/experiments/openvpn/` on the desktop and checksums are verified. The desktop also has a server runtime log, but this version does not archive a separate server PCAP or server log for each session. See [desktop server and permanent results](#9-desktop-server-and-permanent-results).

```text
curl web request inside Pi/laptop vpnlabv2 namespace
  → OpenVPN tunnel over Pi/laptop Wi-Fi or Ethernet
  → desktop OpenVPN server → desktop proxy when configured → website

Pi/laptop filtered client.pcap + client/web logs + metadata
  → temporary client results/ → verified desktop VPN-Storage copy
```

**Current network status (2026-10-03):** direct public HTTPS from the desktop still times out, while its configured proxy reaches tested websites. A nine-session Pi check succeeded on all eight modes and nine HTTPS Wikipedia visits; a later 24-session mixed run succeeded on 72/72 visits from the revised 100-site list. Website and proxy availability can change. Verify each run using the saved final URL and HTTP outcome; see [the verified result](#8-verified-pi-run-and-expected-outcomes) and [known limits](ISSUES.md).

OpenVPN `P_DATA_V2` packets confirm encrypted tunnel data, including traffic to/from the proxy. Use `web.log` and `metadata.json` to establish whether the requested website actually responded.

## 1. Before a run

The client needs Linux, root privileges, OpenVPN, `iproute2`, `tcpdump`, `curl`, `rsync`, and SSH. The desktop needs OpenVPN, SSH, forwarding/NAT for `10.8.0.0/24`, and the V2 server profiles and credentials. On the desktop, `server/openvpn/scripts/setup_network.sh` enables runtime forwarding/NAT if needed. The client must be able to reach the desktop IP and authenticate over SSH using a key. The CLI prompts once for the desktop sudo password; it keeps that password in memory only.

Check the route and SSH connection before starting:

```bash
ip route get 10.208.23.185
ssh deepaksingh@10.208.23.185 'hostname'
```

For a first Pi session after [Pi setup](SHIP_TO_PI.md), run from its V2 root:

```bash
cd ~/vpn-testbed-v2
sudo ./runner/vpnlab run openvpn --transport udp --control vanilla --sessions 1
```

The plan should say `plan=1` and `udp/vanilla=1`. With the default `visits: 3`, a fully successful run reports one successful session and three successful HTTPS fetches in `summary.json`. The command inherits DNS, proxy, sites, and timeouts from the Pi's config files. The CLI prompts for the desktop sudo password. See [result checks](#7-result-files-and-how-to-read-them) after it finishes.

On the Pi, review `hosts/raspberrypi.env`; on the laptop, review `hosts/laptop.env`. These files set the DNS server used inside the VPN namespace and the optional web proxy. This campus connection uses `10.208.20.2` and `proxy21.iitd.ac.in:3128`. With `WEB_PROXY=` empty, curl attempts a direct connection **through the VPN tunnel and desktop exit**, regardless of the client's own Wi-Fi Internet access. It ignores inherited proxy settings and does not fall back to a proxy. Direct web access must be allowed by the desktop's network. Each attempted URL, final URL, HTTP result, and failure reason is recorded. Default HTTPS visits use curl's TLS certificate validation.

## 2. Directory map and file roles

The same client structure is under `/home/deepak/vpn-testbed-v2` on the laptop and `~/vpn-testbed-v2` on the Pi. Edit the files on the machine that will actually run the experiment.

```text
vpn-testbed-v2/
├── README.md                       this run and result guide
├── SHIP_TO_PI.md                    Pi copy and setup instructions
├── ISSUES.md                        current limits and older-result caveats
├── STATUS.md                        implementation and test history
├── experiments/openvpn/run.json     master experiment settings
├── hosts/                           per-client network and SSH settings
├── traffic/web/sites.txt            default website list
├── client/openvpn/                  client profiles, credentials, TUN hooks
├── client/wireguard/                 future placeholder
├── client/commercial-vpn/            future placeholders
├── runner/vpnlab                    experiment CLI
└── results/                         temporary local experiment results
```

| File or directory | Purpose |
| --- | --- |
| `experiments/openvpn/run.json` | **Edit this on the machine that will run the experiment** to select modes, session count, visits, seed, rekey interval, duration, URL list, and result label. |
| `hosts/raspberrypi.env` on Pi; `hosts/laptop.env` on laptop | Edit only when that client's VPN DNS, desktop-side web proxy, or SSH identity needs to change. Select the file with `host_config` in `run.json`. |
| `traffic/web/sites.txt` | Curated 100-site HTTPS URL pool. For a different workload, create a separate plain-text URL file and set `sites_file` in `run.json`; one HTTPS URL per line. |
| `runner/vpnlab` | The single CLI that schedules, runs, finalizes, and transfers experiments. |
| `client/openvpn/vanilla/profiles/` | UDP and TCP `.ovpn` client profiles without extra control protection. |
| `client/openvpn/control-protection/<mode>/profiles/` | UDP and TCP `.ovpn` profiles for `tls-auth`, `tls-crypt`, and `tls-crypt-v2`. |
| `client/openvpn/credentials/` | Copied client certificates and keys; keep private. |
| `client/openvpn/hooks/netns_up.sh` and `netns_down.sh` | Move/configure the VPN TUN device in `vpnlabv2` and clean it up. |
| Desktop `server/openvpn/` | Matching `.conf` profiles, copied server credentials, profile selector, forwarding/NAT script, and current runtime log. |
| `results/` | Temporary local results; the verified permanent copy is in desktop `VPN-Storage`. |

The eight client `.ovpn` profiles and matching desktop `.conf` profiles are selected automatically from `transport` and `control`. **Do not edit profile files or `runner/vpnlab` to switch configurations.** `hosts/desktop.env` is reference information; routine experiment settings come from `run.json` and the selected client host file.

`traffic/web/README.md` explains the URL pool; the README in each OpenVPN mode folder explains that mechanism. WireGuard, commercial VPN, UI automation, and obfuscations are empty future areas. The runner currently supports only the eight OpenVPN modes.

## 3. Edit one config and run

On the **Pi**, edit its own copy of the master config and run it:

```bash
cd ~/vpn-testbed-v2
nano experiments/openvpn/run.json
sudo ./runner/vpnlab run openvpn
```

On the laptop, the same relative path is `/home/deepak/vpn-testbed-v2/experiments/openvpn/run.json`. **Editing the laptop file does not change the Pi's file.** The supplied master config chooses one UDP vanilla session with three random visits; Pi setup changes `host_config` to `hosts/raspberrypi.env`. If your Pi already has an older `run.json`, keep its Pi host setting and add `"sessions": N` and `"shuffle": true` there. Keep JSON valid (quoted strings, lowercase `true`/`false`, no comments or trailing commas). CLI options override its values for one run; `--config PATH` selects another JSON config.

### Which setting to change

| In `experiments/openvpn/run.json` | What it controls |
| --- | --- |
| `transport`: `udp`, `tcp`, or `all` | Which transport(s) to run. Both use server port 1194, with separate UDP and TCP sockets. |
| `control`: `vanilla`, `tls-auth`, `tls-crypt`, `tls-crypt-v2`, or `all` | Control-channel protection. `vanilla` means no extra control protection. |
| `sessions`: positive integer | **Total N** across the selected configurations. One mode gets all N; multiple modes divide N as evenly as possible. N must be at least the number of modes. |
| `shuffle`: `true`/`false`; `seed`: integer or `null` | `true` randomizes session order. A fixed seed reproduces the assignment, order, URL draws, and delays. `null` selects and records a fresh seed. |
| `visits`: positive integer; `sites_file`: path | How many URLs to draw per session and which plain-text URL pool to draw from. Draws may repeat. Paths in this JSON are relative to the V2 root. |
| `reneg_sec`: positive integer or `null`; `session_seconds`: number | An explicit R requests a renewal every R seconds on **both peers**; hold the tunnel for at least S seconds. In all-eight mixed runs, `reneg_sec: null` instead enables the `mixed_rekeys` behavior below. |
| `mixed_rekeys`: `true`/`false` | With `true`, all-eight mixed runs when `reneg_sec` is `null` balance **target** counts 0, 1, and 2 within each mode. The runner holds each tunnel at least 12 seconds if S is zero; it records the chosen target and per-session R. It has no effect on a single mode or smaller group. |
| `delay_min`, `delay_max` | Seeded random wait after each session except the last; default 2–6 seconds. |
| `host_config` | `hosts/raspberrypi.env` on Pi or `hosts/laptop.env` on laptop. |
| `purpose` | `auto` names the selected mode (`udp-vanilla`, `tcp-all`, `mixed-rekeys`, etc.). Set a short custom label if desired; use lowercase letters, digits, and hyphens. |
| `web_timeout`, `connect_timeout` | Seconds allowed for one web request and VPN connection. |
| `capture_interface`: `null` normally | Auto-detect the physical interface via `ip route get`; specify a name only when detection is wrong. |
| `desktop` | SSH login/IP of the V2 server; leave `deepaksingh@10.208.23.185` for this topology. |

In the selected `hosts/*.env`, `VPN_DNS` is namespace DNS, `WEB_PROXY` is the proxy reached **through the VPN and desktop**, and optional `SSH_IDENTITY` is the client's private SSH key path for server control and result transfer. The Pi's Wi-Fi Internet does not replace desktop-side Internet access. For this network, keep the configured proxy; direct desktop public HTTPS currently times out.

For web research, run one short session first and check `summary.json` for `web_successes`, then check the session's `metadata.json` → `web_visit_results` for the requested URL, effective URL, HTTP code, and `success: true`. A successful VPN connection or `P_DATA_V2` packet alone is not a successful website visit. A session is marked failed if any planned visit fails, even when other visits succeed. Use `--sites-file PATH` to choose another website list; see [ISSUES.md](ISSUES.md).

| Experiment | Set `transport` | Set `control` | Other settings |
| --- | --- | --- | --- |
| One configuration | `udp` or `tcp` | One of `vanilla`, `tls-auth`, `tls-crypt`, `tls-crypt-v2` | `sessions: 50` gives 50 of that mode |
| All UDP modes | `udp` | `all` | `sessions: 50` gives 12 or 13 per mode |
| All TCP modes | `tcp` | `all` | `sessions: 50` gives 12 or 13 per mode |
| Vanilla on TCP and UDP | `all` | `vanilla` | `sessions: 50` gives 25 per transport |
| One protection mode on TCP and UDP | `all` | One selected control | `sessions: 50` gives 25 per transport |
| All eight modes | `all` | `all` | `sessions: 24` gives 3 each; `sessions: 50` gives 6 or 7 per mode; default mixed rekey targets are 0/1/2 |
| Key-renewal study | Any selection | Any selection | `reneg_sec: R`, `session_seconds` longer than R; increase `visits` for traffic across the hold |

### Config-only example: 24 mixed sessions on Pi

In the Pi's `experiments/openvpn/run.json`, set these values (other supported fields may remain). Keep the Pi `host_config` path:

```json
{
  "transport": "all",
  "control": "all",
  "sessions": 24,
  "shuffle": true,
  "seed": 42,
  "visits": 3,
  "sites_file": "traffic/web/sites.txt",
  "reneg_sec": null,
  "mixed_rekeys": true,
  "session_seconds": 0,
  "host_config": "hosts/raspberrypi.env",
  "purpose": "auto"
}
```

Then run `sudo ./runner/vpnlab run openvpn` from `~/vpn-testbed-v2`. This plans 24 sessions, three of each mode, with randomized order and seeded 0/1/2 target rekeys. To run **50 TCP tls-auth sessions** from the same file, change only `transport` to `tcp`, `control` to `tls-auth`, and `sessions` to `50`. For single or smaller grouped runs, `mixed_rekeys` has no effect. CLI flags override the same fields for one run without editing the JSON. For a shared rekey interval, set `reneg_sec` to a positive R and `session_seconds` long enough to observe it.

## 4. What happens in one experiment

1. The CLI expands the selected configurations into a balanced list, shuffles it if requested, and uses one seed to choose each session's web URLs and post-session waits. The full order and selected URLs go into `schedule.csv`; a copy of `sites.txt` goes into the result.
2. For each session, the client asks the desktop to start only the matching V2 server profile. The selector checks port conflicts and never stops a non-V2 process.
3. The client finds the physical interface with `ip route get`, starts `tcpdump` with a filter for the desktop IP and active UDP/TCP port, then starts OpenVPN in the host namespace. This captures the handshake through teardown while excluding SSH and unrelated host traffic.
4. OpenVPN runs with `--ifconfig-noexec --route-noexec`. Its hook moves the TUN interface into `vpnlabv2`, assigns the VPN address and default route there, and uses namespace-specific DNS. The host's normal routes remain in place.
5. Only the experiment's `curl` visits run with `ip netns exec vpnlabv2`. The host's SSH, DNS, updates, and other traffic remain outside. `--session-seconds S` spreads visits across at least S connected seconds; without it, visits run back to back.
6. The runner stops the client and V2 server, closes the PCAP, writes metadata/statistics, then waits a seeded random 2–6 seconds before the next session by default. It does not wait after the last session.
7. Completion, Ctrl+C, SIGTERM, and handled failures all finalize available results, make checksums, copy to the desktop, verify checksums there, and remove the namespace. The desktop storage is the permanent copy.

Only one run should be active at a time. A fixed `vpnlabv2` namespace and the desktop ports prevent concurrent V2 sessions.

## 5. Command cookbook

Run these **on the Pi** from `~/vpn-testbed-v2` (or from the V2 root on another client). **Choose one experiment command at a time; do not paste every example as a batch.** `--sessions N` always means **N total**. The printed `plan=` line shows the count for every selected mode before any VPN starts. CLI options override the Pi's `run.json` for that command; settings you do not pass still come from that file.

### One exact configuration

```bash
cd ~/vpn-testbed-v2
sudo ./runner/vpnlab run openvpn --transport udp --control vanilla --sessions 10
sudo ./runner/vpnlab run openvpn --transport tcp --control tls-auth --sessions 10
```

The first command schedules ten UDP vanilla sessions; the second schedules ten TCP tls-auth sessions. Run one line at a time. Replace `control` with `tls-crypt` or `tls-crypt-v2` for those mechanisms.

### A four-mode transport group or two-mode control group

```bash
sudo ./runner/vpnlab run openvpn --transport udp --control all --sessions 50 --shuffle
sudo ./runner/vpnlab run openvpn --transport tcp --control all --sessions 50 --shuffle
sudo ./runner/vpnlab run openvpn --transport all --control vanilla --sessions 50 --shuffle
sudo ./runner/vpnlab run openvpn --transport all --control tls-crypt --sessions 50 --shuffle
```

The first two select four modes each and assign 12 or 13 sessions per mode. The third runs vanilla over both UDP and TCP, 25 sessions each. The fourth does the same for tls-crypt; substitute `tls-auth` or `tls-crypt-v2` to study either of those controls over both transports. Only one experiment runs at a time.

### All eight modes

```bash
sudo ./runner/vpnlab run openvpn --transport all --control all --sessions 24 --shuffle
sudo ./runner/vpnlab run openvpn --transport all --control all --sessions 50 --shuffle --seed 42
```

Run one line at a time. N=24 gives **three of each mode**. N=50 gives **six of each plus one extra to two seeded modes**. Shuffling randomizes the complete session order; it does not change the counts. With `reneg_sec: null` and `mixed_rekeys: true` in the master config, these all-eight runs also assign 0/1/2 **target** renewals. `--seed 42` makes the count assignment, order, URL choices, and delays reproducible. Omit it for a fresh recorded seed.

### Small total-N validation with a known website

```bash
sudo ./runner/vpnlab run openvpn \
  --transport all --control all --sessions 9 --shuffle --seed 42 \
  --visits 1 --sites-file traffic/web/smoke-sites.txt \
  --purpose total-n-check
```

This selects all eight modes and assigns the ninth session to one mode. With seed 42, the extra session is UDP/tls-auth. The known-site file contains `https://www.wikipedia.org/`; create it with `printf 'https://www.wikipedia.org/\n' > traffic/web/smoke-sites.txt` if missing. `--visits 1` requests one fetch per session. `--purpose` makes the result folder start with `total-n-check`.

### Shared key-renewal interval R

```bash
sudo ./runner/vpnlab run openvpn \
  --transport all --control all --sessions 8 --shuffle \
  --reneg-sec 30 --session-seconds 95 --visits 8
```

This requests R=30 seconds on both OpenVPN peers, keeps each tunnel connected for at least 95 seconds, and spreads eight website visits across that hold. An explicit `--reneg-sec` overrides the automatic mixed 0/1/2 targets. For a short known-site check, replace R with `3`, the hold with `12`, and add `--sites-file traffic/web/smoke-sites.txt`. To run mixed modes with ordinary OpenVPN rekey timing instead, use `--no-mixed-rekeys` with `reneg_sec: null` in the config.

### Change workload or result label for one run

```bash
sudo ./runner/vpnlab run openvpn \
  --transport udp --control tls-crypt-v2 --sessions 5 \
  --sites-file traffic/web/sites.txt --visits 3 \
  --seed 42 --purpose udp-crypt-v2-study
```

This runs five UDP tls-crypt-v2 sessions, drawing three URLs independently for each session from the 100-site list. A URL can repeat. `--purpose` changes only the human-readable result label. The default is already three visits from `traffic/web/sites.txt`; the flags above show how to override those fields. Use `--delay-min 2 --delay-max 6` to set the inter-session wait explicitly; those are already the defaults. The older `--sessions-per-config 25` option remains for intentionally scheduling 25 **of each** selected mode (200 for all eight); use `--sessions 25` for 25 total.

### Key flags at a glance

| Flag | Effect |
| --- | --- |
| `--transport udp\|tcp\|all` | Choose one or both transports. |
| `--control vanilla\|tls-auth\|tls-crypt\|tls-crypt-v2\|all` | Choose one or all control-protection modes. |
| `--sessions N` | Total sessions, distributed evenly; N must be at least the number of selected modes. |
| `--shuffle`, `--seed 42` | Randomize order and optionally reproduce the plan. |
| `--visits N`, `--sites-file PATH` | Number of HTTPS fetches per session and URL pool. |
| `--reneg-sec R`, `--session-seconds S` | Shared rekey interval and minimum connected time. |
| `--mixed-rekeys` / `--no-mixed-rekeys` | Enable or disable automatic 0/1/2 target rekeys for all-eight runs without explicit R. |
| `--purpose LABEL` | Choose a readable run name prefix. |
| `--host-config PATH` | Choose the client's DNS, proxy, and SSH identity file. |

### How to interpret rekeys

`--reneg-sec R` requests an OpenVPN key renewal every R seconds on both peers. It renews ephemeral **data-channel session keys**; the static `ta.key` and `tls-crypt` keys stay the same. `rekeys=0` in a short single-mode run with no explicit R is normal and does not mean the initial VPN handshake failed. `--session-seconds S` keeps the tunnel connected for at least S seconds and spreads the visits across that interval.

For all-eight runs with `reneg_sec: null` and `mixed_rekeys: true`, the runner balances **targets** 0, 1, and 2 within each mode. With the default 12-second connected hold, target 0 uses the ordinary interval, target 1 uses R=9, and target 2 uses R=6. The chosen target and R are in `schedule.csv` and session metadata. Terminal `rekeys=N` and metadata `renegotiation_events` count **observed renewals after the initial handshake**. They are counts, not seconds. OpenVPN timing can produce fewer or more renewals than targeted: in the verified nine-session Pi run, one session targeted two but observed one. Use the observed count in analysis; the PCAP and client OpenVPN log are the packet and handshake evidence.

## 6. The 100-site list

`traffic/web/sites.txt` contains 100 unique HTTPS homepages selected in rank order from [Tranco list Y83YG](https://tranco-list.eu/list/Y83YG) ranks 1–259. On 2026-10-03, each selected domain returned an HTTPS 200 HTML page with a title and valid TLS certificate in **two** desktop-proxy checks. The Pi then succeeded on 24/24 seeded visits from the revised list in the eight-mode final check. Infrastructure hosts, obvious error/challenge pages, duplicate final hosts, `example.com`, and the IITD site were excluded. The old uncurated ranks 1–100 list had only 50 passing domains in the first check. Website availability and proxy behavior can change; confirm real visits in each run's per-visit metadata. Each experiment copies its exact URL list and planned choices, so old results keep their original list. There is no automatic list refresh.

## 7. Result files and how to read them

Local results are temporary under `results/<year>/<Month>/<day>/<experiment-id>/`. The verified permanent copy is under `/home/deepaksingh/VPN-Storage/experiments/openvpn/<year>/<Month>/<day>/<experiment-id>/` on the desktop. **New runs use Asia/Kolkata (IST) for the date folders and name**, independent of the Pi's system timezone.

New names follow `label_YY_MM_DD_HHMM_N_ID`. For example, `mixed-rekeys_26_10_03_1430_24_a7f2` means a mixed rekey run begun at **14:30 IST** on 2026-10-03, with **24 planned sessions**; `a7f2` distinguishes runs in the same minute. N is the intended total, even if the run is interrupted early. The label is automatic unless you set `purpose` or `--purpose`; examples include `udp-vanilla`, `tcp-tls-auth`, `udp-all`, `both-tls-crypt`, and `mixed-rekeys`. `experiment.yaml` records `result_timezone: Asia/Kolkata` and `start_time` with an explicit UTC offset; session timestamps also retain explicit UTC offsets. Existing result folders keep their original names and dates.

An experiment directory, for example `mixed-rekeys_26_10_03_1430_24_a7f2/`, contains:

```text
experiment-id/
├── README.md                   short note written with this result
├── experiment.yaml             controls, seed, chosen URL-list hash
├── environment.json            client host and relevant software versions
├── sites.txt                   exact URL pool used in this experiment
├── schedule.csv                every planned session, mode, URLs, and rekey target/R
├── summary.json                total experiment counts and measurements
├── summary.csv                 the same summary for a spreadsheet
├── configuration_summary.csv   one row for each selected UDP/TCP + protection mode
├── failures.csv                failed or interrupted started sessions
├── checksums.sha256            hashes of transferred result files
├── transfer.json               copy and desktop verification outcome
├── by-configuration/           links to sessions grouped by mode, no PCAP copies
└── sessions/session_0001/
    ├── metadata.json           mode, status, timing, URLs, failure reason, rekeys
    ├── stats.json              VPN, web, and packet-capture measurements
    ├── client.pcap             encrypted VPN packets captured at the client
    ├── openvpn-client.log      client handshake, rekey, and error details
    ├── web.log                 requested URLs and curl outcomes
    └── capture.log             tcpdump diagnostics
```

The `sessions/` folder has one directory for each **started** session. `by-configuration/udp/tls-auth/session_0001`, for example, links back to the actual session folder; it does not duplicate files. An older result may have fewer metadata fields because the runner was updated over time.

### Counts in mixed experiments

`sessions` is the **total** across selected combinations. The runner divides N by the number of modes; a seeded draw assigns any remainder one session at a time to distinct modes. For eight modes, N=24 gives 3 each; N=50 gives six modes 6 and two modes 7. For four UDP or four TCP modes, N=50 gives two modes 12 and two modes 13. For two transports of one control mode, N=50 gives 25 each. For one mode, N=50 gives 50. N must be at least the number of selected modes, so each appears. With `shuffle: true` the full list is then shuffled. Before connecting, the runner prints the seed and planned count for each selected mode; at the end it prints planned, started, successful, failed, and interrupted counts per mode. `schedule.csv` preserves the complete order and URL choices, even if the run is interrupted. The older `--sessions-per-config N` option remains available for runs that intentionally request N of **each** mode; it overrides a configured `sessions` value for that command only.

In `configuration_summary.csv`, each selected mode has its own `planned`, `started`, `successful`, `failed`, and `interrupted` counts. `summary.json` totals the whole run. `completed = successful + failed`; interrupted is separate. A run can have `status=completed` while some individual sessions failed. `success_rate` uses **started** sessions as the denominator. If interrupted, `started` can be smaller than `planned`. `failures.csv` lists failed and interrupted sessions with a reason.

### Session evidence

In `metadata.json`, `connection_success` says the VPN tunnel established. `web_visit_results` then records each `requested_url`, `effective_url`, HTTP code, curl exit code, response bytes, `success`, and `failure_reason`. All planned visits must pass for the session to be `successful`. A proxy login page or failed CONNECT is a web failure even if VPN packets were captured. Curl success means an HTTP(S) fetch passed the runner's checks; it is not browser rendering or interaction.

`stats.json` separates `vpn`, `web`, and `capture`. The capture block includes packet count, measured packet bytes, direction totals (`client_to_server_*` and `server_to_client_*`), timing, packet sizes, and PCAP file size. Packet bytes and PCAP file size differ because the file has headers. These directions come from the **client capture**, not a second server capture. The PCAP filter is `host 10.208.23.185 and udp port 1194` or `host 10.208.23.185 and tcp port 1194`, derived from the active profile. Older TCP results retain their original port 443 metadata and captures. `P_DATA_V2` indicates encrypted tunnel data; use URL metadata and web logs to judge web requests.

`renegotiation_events` counts observed later control-channel TLS handshakes after the initial VPN connection. Terminal `rekeys=N` is that count, **not seconds**. `rekey_target` is the mixed schedule's aim; `reneg_sec=R` is the actual requested interval for that session. If observed and target differ, use the observed value in analysis. `transfer.json` has `transfer_success` and `checksum_verification_success`; both should be true for a verified desktop copy. If transfer fails, the local partial result remains for recovery.

### Inspect a finished run on the client

From the Pi or laptop that ran the experiment, select the newest run (or set `RUN_DIR` to a specific result directory):

```bash
RUN_DIR=$(ls -td results/*/*/*/* | head -1)
cat "$RUN_DIR/summary.json"
cat "$RUN_DIR/configuration_summary.csv"
cat "$RUN_DIR/transfer.json"
head -n 10 "$RUN_DIR/schedule.csv"
cat "$RUN_DIR/sessions/session_0001/metadata.json"
ls -lh "$RUN_DIR/sessions/session_0001/client.pcap"
ip netns list
ip route get 10.208.23.185
```

The summary reports total planned/started/successful/failed/interrupted sessions and web attempts/successes/failures. The configuration CSV shows the same counts per selected mode. The schedule shows every planned mode and URL before the run, including sessions never started after an interruption. The session metadata shows the requested/final URL and whether the fetch succeeded. `client.pcap` must exist for a started session. After the run, `ip netns list` should not show `vpnlabv2`; on this Pi, the route to the desktop should still use `wlan0` via its normal gateway.

For a compact website check without reading each JSON file manually:

```bash
python3 - "$RUN_DIR" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
s = json.loads((p / 'summary.json').read_text())
t = json.loads((p / 'transfer.json').read_text())
print('sessions:', s['successful'], 'successful /', s['planned'], 'planned')
print('web:', s['web_successes'], 'successful /', s['web_attempts'], 'attempted')
print('desktop transfer:', t['transfer_success'], 'checksums:', t['checksum_verification_success'])
for f in sorted((p / 'sessions').glob('session_*/metadata.json')):
    m = json.loads(f.read_text())
    for v in m.get('web_visit_results', []):
        print(f.parent.name, v['http_code'], v['success'], v['effective_url'])
PY
```

For a fully successful N-session run with `visits: 3`, expect `successful=N` and `web_successes=3×N`. A failed site or proxy connection can lower those counts without invalidating the captured VPN packets. `transfer_success` and `checksum_verification_success` should both be `True` for the desktop copy.

To check that each started session has a PCAP and that its packets match the recorded server/port filter, run this on the client with the same `RUN_DIR`:

```bash
python3 - "$RUN_DIR" <<'PY'
import json, subprocess, sys
from pathlib import Path
p = Path(sys.argv[1]); checked = 0
for f in sorted((p / 'sessions').glob('session_*/metadata.json')):
    m = json.loads(f.read_text()); cap = f.parent / 'client.pcap'
    assert cap.is_file() and cap.stat().st_size > 24, cap
    r = subprocess.run(['tcpdump', '-nn', '-r', str(cap),
                        f"not ({m['capture_filter']})"], capture_output=True, text=True)
    assert r.returncode == 0 and not r.stdout.strip(), (cap, r.stderr, r.stdout[:200])
    checked += 1
print('PCAPs matching their VPN filters:', checked)
PY
```

For a completed nine-session run, expect `PCAPs matching their VPN filters: 9`. This checks isolation of the capture, while the website fields above check the actual HTTPS fetches.

For a full PCAP and checksum audit, run `python3 runner/audit_pcaps.py "$RUN_DIR" --output /tmp/vpnlab-pcap-audit.json` on the client. The desktop has the same auditor at `/home/deepaksingh/vpn-testbed-v2/audit_pcaps.py`; run it against the permanent experiment directory printed after transfer. It reads every PCAP with TShark, verifies each frame's desktop endpoint, transport, and port, counts decoded OpenVPN and `P_DATA_V2` frames, checks recorded packet totals, and verifies `checksums.sha256`. A valid completed run has empty `issue_sessions`, `checksum_failures`, `missing_manifests`, `unprotected_files`, and `orphan_captures`. `note_sessions` lists sessions stopped before any capture could be made. For a new TCP/1194 run, confirm every session reports `transport: tcp` and `port: 1194` with OpenVPN data frames.

### Independently check the desktop copy

Use the chosen `RUN_DIR` from above. This command verifies the permanent desktop files against that experiment's checksum manifest:

```bash
RUN_REL=${RUN_DIR#results/}
ssh deepaksingh@10.208.23.185 "cd /home/deepaksingh/VPN-Storage/experiments/openvpn/$RUN_REL && sha256sum -c checksums.sha256 >/dev/null && echo checksums_OK"
```

## 8. Verified Pi run and expected outcomes

The Pi ran the [nine-session total-N command](#small-total-n-validation-with-a-known-website) on 2026-10-03. The permanent desktop result is `total-n-check_26_10_03_0910Z_4249`. These findings come from reading its stored files, not only the terminal output:

| Check | Verified result |
| --- | --- |
| Schedule | Nine sessions across all eight modes; UDP/tls-auth got two, every other mode one. Seed 42 and the complete order are in `schedule.csv`. |
| VPN sessions | 9 started, 9 successful, 0 failed or interrupted. |
| Website fetches | 9/9 returned HTTPS 200 at the requested final URL `https://www.wikipedia.org/`, with 93,955 response bytes each and no web failures. The configured desktop proxy carried the requests. |
| Client captures | Nine nonempty PCAPs, 1,281 packets total. Reading each with the inverse of its recorded BPF filter returned zero unrelated packets. |
| Rekeys | Eight observed renewals total. One UDP vanilla session targeted two and observed one; target and observed counts are separate fields. |
| Navigation and storage | All nine `by-configuration` links resolved. All 63 desktop SHA-256 entries matched; transfer and verification flags are true. |

The `SUCCESSFUL` terminal status means all requested curl visits for that session passed the runner's HTTP, redirect, and proxy-login checks. It does not mean a browser rendered the page. This particular run did not include a direct post-run inspection of the Pi namespace or route; an earlier Pi interruption check showed the namespace removed and the ordinary `wlan0` route intact. See [STATUS.md](STATUS.md) for older eight-mode, default-site, and Ctrl+C validation history.

A later 24-session mixed Pi run completed **24/24 sessions and 72/72 HTTPS visits** using the revised 100-site pool. Of two subsequent 25-session UDP runs, one had a single `webex.com` HTTP 403 failure, and the other was interrupted after 11 sessions; both retained filtered captures and verified desktop copies. See [ISSUES.md](ISSUES.md) for the website limitation and [STATUS.md](STATUS.md) for the exact run IDs.

## 9. Desktop server and permanent results

The desktop has **two different directories**:

| Desktop path | What it contains |
| --- | --- |
| `/home/deepaksingh/vpn-testbed-v2/server/openvpn/` | Server implementation: eight matching `.conf` profiles, copied credentials, V2 selector and NAT scripts, and current runtime state. |
| `/home/deepaksingh/VPN-Storage/experiments/openvpn/` | Permanent copies of the **client-generated experiment results**. This is where you analyze finished runs. |

The server profiles mirror the client layout: `vanilla/profiles/{udp,tcp}.conf` and `control-protection/<mode>/profiles/{udp,tcp}.conf`. The runner asks `scripts/select_profile.sh` to select one matching profile per session. The selector checks whether the required port is free and stops only its own V2 process. `scripts/setup_network.sh` sets forwarding/NAT for `10.8.0.0/24` when needed.

The server selector writes its current OpenVPN log to `server/openvpn/runtime/openvpn.log` and its active PID to `runtime/openvpn.pid`. **The log is replaced when another V2 profile starts**; the PID file is removed when that session stops. These are operational diagnostics, not an experiment archive. A session's `server_stop_ok` in client metadata only says the stop command returned successfully.

The permanent desktop experiment folder contains the transferred `client.pcap`, `openvpn-client.log`, `web.log`, metadata, summaries, and checksums. V2 currently does **not** collect a separate server-side PCAP or archive a per-session server OpenVPN log. Thus `server_to_client_*` and `client_to_server_*` in `stats.json` describe directions seen in the **client's** filtered capture. They are not independent server measurements. For a failed connection, inspect the session's archived client log and failure reason first; inspect the server runtime log only if another session has not replaced it.

To inspect a permanent run on the desktop, use the `remote=` path printed by the client. For example, the verified Pi nine-session run is here:

```bash
ssh deepaksingh@10.208.23.185
cd /home/deepaksingh/VPN-Storage/experiments/openvpn/2026/October/03/total-n-check_26_10_03_0910Z_4249
cat summary.json
cat configuration_summary.csv
cat transfer.json
cat sessions/session_0001/metadata.json
sha256sum -c checksums.sha256
```

For another run, replace that `cd` path with the `remote=` path printed at the end of its run, omitting the `deepaksingh@10.208.23.185:` prefix. `summary.json` gives totals; `configuration_summary.csv` gives per-mode counts; session metadata and web logs show whether requested pages succeeded; `client.pcap` and `stats.json` show the VPN packets captured on the Pi/laptop.
