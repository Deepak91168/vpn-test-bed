# Copy V2 to the Pi

Your Pi is `pi@10.184.121.210`. Run the first block **on the laptop**. `-J netmon` uses your laptop's `netmon` SSH alias as the jump host; you do not need to copy files manually on netmon. This copies only the V2 code, configs, and client credentials, leaving laptop experiment results behind.

**Already set up the Pi?** To copy just the revised default website list and current instructions, run on the laptop:

```bash
cd /home/deepak/vpn-testbed-v2
scp -J netmon traffic/web/sites.txt pi@10.184.121.210:~/vpn-testbed-v2/traffic/web/sites.txt
scp -J netmon README.md ISSUES.md SHIP_TO_PI.md pi@10.184.121.210:~/vpn-testbed-v2/
```

This changes only V2 files on the Pi. Existing experiment results keep their original site-list snapshot. The revised list later passed a Pi eight-mode run with 24/24 visits on 2026-10-03.

**Already set up the Pi and updating the runner?** Copy the revised runner and guide from the laptop. This includes the new Asia/Kolkata result name with planned N. Leave the Pi's `run.json` in place so its `host_config` still points to `hosts/raspberrypi.env`:

```bash
cd /home/deepak/vpn-testbed-v2
scp -J netmon runner/vpnlab pi@10.184.121.210:~/vpn-testbed-v2/runner/vpnlab
scp -J netmon README.md ISSUES.md SHIP_TO_PI.md pi@10.184.121.210:~/vpn-testbed-v2/
scp -J netmon experiments/openvpn/README.md pi@10.184.121.210:~/vpn-testbed-v2/experiments/openvpn/
```

Check the new name with **one** Pi session before a larger run:

```bash
cd ~/vpn-testbed-v2
chmod +x runner/vpnlab
sudo ./runner/vpnlab run openvpn --transport udp --control vanilla \
  --sessions 1 --visits 1 --sites-file traffic/web/smoke-sites.txt \
  --purpose name-check
RUN_DIR=$(ls -td results/*/*/*/* | head -1)
python3 - "$RUN_DIR" <<'PY'
import json, re, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
p = Path(sys.argv[1]); e = json.loads((p / 'experiment.yaml').read_text())
s = json.loads((p / 'summary.json').read_text())
t = json.loads((p / 'transfer.json').read_text())
m = json.loads((p / 'sessions/session_0001/metadata.json').read_text())
local = datetime.fromisoformat(e['start_time']).astimezone(ZoneInfo('Asia/Kolkata'))
prefix = f'name-check_{local:%y_%m_%d_%H%M}_1_'
assert re.fullmatch(re.escape(prefix) + r'[0-9a-f]{4}', p.name), p.name
assert p.parts[-4:-1] == (str(local.year), local.strftime('%B'), local.strftime('%d'))
assert e['result_timezone'] == 'Asia/Kolkata' and s['planned'] == 1
assert s['successful'] == 1 and s['web_successes'] == 1
assert t['transfer_success'] and t['checksum_verification_success']
assert t['remote_path'].endswith(f'/experiments/openvpn/{local.year}/{local:%B}/{local:%d}/{p.name}/')
assert (p / 'sessions/session_0001/client.pcap').stat().st_size > 24
assert m['web_visit_results'][0]['success'] and m['web_visit_results'][0]['http_code'] == '200'
assert m['web_visit_results'][0]['effective_url'] == 'https://www.wikipedia.org/'
print('new IST name, local date folder, website visit, and desktop copy verified:', p.name)
PY
ip netns list
```

The directory should resemble `name-check_26_10_03_1500_1_a7f2`; the time and short ID will differ. `ip netns list` should not show `vpnlabv2` afterward. The desktop path printed at the end should contain the same name under its Asia/Kolkata year/month/day. Existing result folders are untouched.

Then, **on the Pi**, either give N on the command line or edit its existing master config:

```bash
cd ~/vpn-testbed-v2
sudo ./runner/vpnlab run openvpn --transport all --control all --sessions 24 --shuffle
```

For config-only runs, edit `experiments/openvpn/run.json` on the Pi: set `"transport": "all"`, `"control": "all"`, `"sessions": 24`, and `"shuffle": true`; keep `"host_config": "hosts/raspberrypi.env"`. Then run `sudo ./runner/vpnlab run openvpn`. N=24 plans three of each of the eight modes. N=50 plans six modes with six sessions and two with seven, chosen by the recorded seed. Check `schedule.csv` and `configuration_summary.csv` in the result for exact assignments and outcomes. The Pi's older `sessions_per_config` field can stay in place; a numeric `sessions` takes precedence. Do not copy the laptop's `run.json` over the Pi's configured file.

To validate the updated total-N path with an **uneven** count, run this on the Pi after copying the runner (the known-site file was created in the earlier Pi checks):

```bash
cd ~/vpn-testbed-v2
sudo ./runner/vpnlab run openvpn --transport all --control all --sessions 9 --shuffle --seed 42 --visits 1 --sites-file traffic/web/smoke-sites.txt --purpose total-n-check
RUN_DIR=$(ls -td results/*/*/*/* | head -1)
python3 - "$RUN_DIR" <<'PY'
import csv, json, sys
from collections import Counter
from pathlib import Path
p = Path(sys.argv[1])
schedule = list(csv.DictReader((p / 'schedule.csv').open()))
counts = Counter((r['transport'], r['control_protection']) for r in schedule)
summary = json.loads((p / 'summary.json').read_text())
transfer = json.loads((p / 'transfer.json').read_text())
assert len(schedule) == summary['planned'] == 9
assert len(counts) == 8 and sorted(counts.values()) == [1] * 7 + [2]
assert transfer['transfer_success'] and transfer['checksum_verification_success']
print('total-N schedule and desktop transfer verified')
print('outcomes:', summary['successful'], 'successful,', summary['failed'], 'failed')
PY
cat "$RUN_DIR/configuration_summary.csv"
```

For a full web-success check, expect `successful=9` and `failed=0`; if a website or proxy fails, inspect each session's `web_visit_results` in `metadata.json`. The Pi completed this check on 2026-10-03 in `total-n-check_26_10_03_0910Z_4249`; all nine sessions and HTTPS visits succeeded, and the permanent desktop copy verified.

The updated runner defaults to mixed 0/1/2 rekey targets even when the Pi's existing `run.json` lacks the new `mixed_rekeys` key. Keep `"reneg_sec": null` in that file for automatic targets; a numeric value there (or `--reneg-sec R` on the CLI) uses one shared R instead. To disable the feature, add `"mixed_rekeys": false`. The schedule records each target and chosen interval, and per-session metadata records the actual count.

New experiments use `label_YY_MM_DD_HHMM_N_ID`, where the date and 24-hour time are in Asia/Kolkata and N is the planned total session count. For example, `mixed-rekeys_26_10_03_1430_24_a7f2`. The Pi's existing `purpose: standard` still selects the automatic label. Prior UTC-named result folders are unchanged.

```bash
cd /home/deepak/vpn-testbed-v2
ssh -J netmon pi@10.184.121.210 'mkdir -p ~/vpn-testbed-v2'
scp -J netmon -r client traffic experiments runner hosts README.md ISSUES.md SHIP_TO_PI.md STATUS.md pi@10.184.121.210:~/vpn-testbed-v2/
ssh -J netmon pi@10.184.121.210
```

Run the next block **on the Pi** after the SSH login. It installs the runner's dependencies, selects the Pi host config, keeps the copied client keys private, and sets up the Pi's SSH key for result transfer to the desktop.

```bash
cd ~/vpn-testbed-v2
sudo apt update
sudo apt install -y python3 openvpn tcpdump iproute2 curl rsync openssh-client
chmod +x runner/vpnlab client/openvpn/hooks/*.sh
chmod 600 client/openvpn/credentials/*
cp hosts/raspberrypi.env.example hosts/raspberrypi.env
sed -i 's|"host_config": "hosts/laptop.env"|"host_config": "hosts/raspberrypi.env"|' experiments/openvpn/run.json
test -f ~/.ssh/id_ed25519 || ssh-keygen -t ed25519
ssh-copy-id -i ~/.ssh/id_ed25519.pub deepaksingh@10.208.23.185
```

`rsync` is needed **on the Pi for experiment-result transfer**; copying the client above uses `scp`. The Pi must reach desktop `10.208.23.185` directly over its Wi-Fi network for both OpenVPN and result transfer. If `ssh-copy-id` cannot reach it, stop and fix that network path first. The desktop V2 server stays where it is.

Check the path, then run one short session **on the Pi**:

```bash
ip route get 10.208.23.185
ssh deepaksingh@10.208.23.185 hostname
sudo ./runner/vpnlab run openvpn --transport udp --control vanilla --sessions 1 --visits 1
```

The runner prompts for desktop sudo. After the run, inspect its newest result:

```bash
RUN_DIR=$(ls -td results/*/*/*/* | head -1)
cat "$RUN_DIR/summary.json"
cat "$RUN_DIR/transfer.json"
cat "$RUN_DIR/sessions/session_0001/web.log"
test -s "$RUN_DIR/sessions/session_0001/client.pcap" && echo 'PCAP present'
ip netns list
```

Expect `transfer_success` and `checksum_verification_success` to be true, and `vpnlabv2` to be absent after cleanup. A VPN connection or `P_DATA_V2` packet does not prove a website loaded: check `web_visit_results` in `sessions/session_0001/metadata.json` for `success: true` and the intended HTTPS URL. An older Pi UDP vanilla run had five failed visits from the original uncurated list; the revised list succeeded on 24/24 visits in the 2026-10-03 Pi mixed check. Edit `experiments/openvpn/run.json` and use [README.md](README.md) for larger runs.
