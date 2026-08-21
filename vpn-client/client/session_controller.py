#!/usr/bin/env python3
"""Per-session OpenVPN controller.

For each session: start capture -> start OpenVPN (tunnel lands in an isolated
namespace) -> wait for real establishment (event-driven, not a fixed sleep) ->
generate tunneled traffic -> keep alive a randomized duration -> disconnect ->
verify termination -> write metadata -> inter-session wait. One pcap per session
covers the whole lifecycle. Reproducible under a fixed seed. Run as root via
run_experiment.sh, which builds the namespace and handles global teardown.
"""
import json
import os
import random
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import traffic_gen

HERE = Path(__file__).resolve().parent
NETNS = os.environ.get("NETNS", "vpn")
OUTPUT = Path(os.environ.get("OUTPUT_DIR", "./experiment_out"))
RUN_DIR = OUTPUT / "run"
CAPTURES_ROOT = OUTPUT / "captures"
READY = Path(os.environ.get("VPNLAB_READY", str(RUN_DIR / "ready")))
TUNINFO = Path(os.environ.get("VPNLAB_TUNINFO", str(RUN_DIR / "tuninfo")))
OVPN = os.environ.get("OVPN_CONFIG", "./client.ovpn")
UP = HERE / "netns_up.sh"
DOWN = HERE / "netns_down.sh"
TUN_DEV = "tunvpn"

_stop = False


def _on_sig(signum, frame):
    global _stop
    _stop = True


signal.signal(signal.SIGINT, _on_sig)
signal.signal(signal.SIGTERM, _on_sig)
try:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)  # survive SSH disconnect
except Exception:
    pass


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def env(k, d=None):
    return os.environ.get(k, d)


def envi(k, d):
    v = os.environ.get(k)
    return int(v) if v not in (None, "") else d


def netns_run(args, **kw):
    return subprocess.run(["ip", "netns", "exec", NETNS, *args], **kw)


def parse_ovpn(path):
    host, proto, port = "", "udp", "1194"
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if s.startswith("remote "):
            p = s.split()
            host = p[1]
            if len(p) >= 3 and p[2].isdigit():
                port = p[2]
            if len(p) >= 4:
                proto = p[3]
        elif s.startswith("proto "):
            proto = s.split()[1]
        elif s.startswith("port "):
            port = s.split()[1]
    proto = "tcp" if proto.startswith("tcp") else "udp"
    if not host:
        sys.exit(f"no 'remote' line found in {path}")
    return host, proto, port


def detect_iface(server_ip):
    ci = env("CAPTURE_IFACE", "auto")
    if ci and ci != "auto":
        return ci
    r = subprocess.run(["ip", "route", "get", server_ip], capture_output=True, text=True)
    t = r.stdout.split()
    if "dev" in t:
        return t[t.index("dev") + 1]
    sys.exit("could not auto-detect capture interface; set CAPTURE_IFACE in config.env")


def start_capture(iface, server_ip, proto, port, pcap):
    bpf = f"host {server_ip} and {proto} port {port}"
    p = subprocess.Popen(["tcpdump", "-i", iface, "-U", "-w", str(pcap), bpf],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (RUN_DIR / "tcpdump.pid").write_text(str(p.pid))
    time.sleep(1.0)  # let tcpdump bind before the handshake starts
    return p


def start_openvpn(logf):
    for f in (READY, TUNINFO):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
    netns_run(["ip", "link", "del", TUN_DEV],
              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # clear stale tun
    cmd = ["openvpn", "--config", OVPN, "--dev", TUN_DEV,
           "--ifconfig-noexec", "--route-noexec",   # never touch the ROOT namespace
           "--script-security", "2",
           # OpenVPN sanitizes the script environment, so hand these to the
           # up/down scripts explicitly via --setenv (inherited env is dropped):
           "--setenv", "VPNLAB_NETNS", NETNS,
           "--setenv", "VPNLAB_READY", str(READY),
           "--setenv", "VPNLAB_TUNINFO", str(TUNINFO),
           "--up", str(UP), "--down", str(DOWN), "--up-restart"]
    lf = open(logf, "w")
    p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=dict(os.environ))
    (RUN_DIR / "openvpn.pid").write_text(str(p.pid))
    return p, lf


def wait_ready(proc, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if _stop or proc.poll() is not None:
            return False
        if READY.exists():
            r = netns_run(["ip", "-4", "addr", "show", TUN_DEV], capture_output=True, text=True)
            if "inet " in r.stdout:
                return True
        time.sleep(0.5)
    return False


def read_tuninfo():
    d = {}
    if TUNINFO.exists():
        for line in TUNINFO.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                d[k] = v
    return d


def probe():
    r = netns_run(["curl", "-s", "-m", "8", "-o", "/dev/null", "-w", "%{http_code}",
                   "https://example.com"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def stop_proc(p, timeout=15):
    if p is None:
        return
    try:
        p.send_signal(signal.SIGTERM)
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
    except ProcessLookupError:
        pass


def sleep_interruptible(secs, proc):
    end = time.time() + secs
    while time.time() < end:
        if _stop or (proc is not None and proc.poll() is not None):
            return
        time.sleep(0.5)


def count_packets(pcap):
    """Best-effort packet count via tcpdump (already a dependency). None on error."""
    try:
        p = Path(pcap)
        if not p.exists() or p.stat().st_size == 0:
            return 0
        r = subprocess.run(["tcpdump", "-r", str(pcap), "-nn"],
                           capture_output=True, text=True)
        return sum(1 for _ in r.stdout.splitlines())
    except Exception:
        return None


def main():
    # --- one unique, independent directory per capture run --------------------
    capture_id = "capture_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    capture_dir = CAPTURES_ROOT / capture_id
    _n = 1
    while capture_dir.exists():          # guarantee a brand-new dir (never reuse)
        _n += 1
        capture_dir = CAPTURES_ROOT / f"{capture_id}_{_n}"
    for d in (OUTPUT, RUN_DIR, capture_dir):
        d.mkdir(parents=True, exist_ok=True)
    capture_start = time.time()
    completed_sessions = []

    sessions = envi("SESSIONS", 50)
    seed_env = env("SEED", "")
    seed = int(seed_env) if seed_env not in (None, "") else random.SystemRandom().randint(0, 2**31 - 1)
    rng = random.Random(seed)

    dmin, dmax = envi("SESSION_DURATION_MIN", 20), envi("SESSION_DURATION_MAX", 180)
    tmin, tmax = envi("TRAFFIC_START_DELAY_MIN", 2), envi("TRAFFIC_START_DELAY_MAX", 15)
    imin, imax = envi("INTER_SESSION_DELAY_MIN", 180), envi("INTER_SESSION_DELAY_MAX", 180)
    rmin, rmax = envi("REQUESTS_MIN", 3), envi("REQUESTS_MAX", 12)
    rimin, rimax = envi("REQUEST_INTERVAL_MIN", 1), envi("REQUEST_INTERVAL_MAX", 8)
    backend = env("TRAFFIC_BACKEND", "wget")
    req_timeout = envi("REQUEST_TIMEOUT", 15)
    browse_dwell = envi("BROWSE_DWELL", 20)
    pybin = env("PYTHON", "/usr/bin/python3")
    tun_timeout = envi("TUN_UP_TIMEOUT", 60)
    capture_on = env("CAPTURE", "true").lower() in ("1", "true", "yes")

    sites = [l.strip().split(",")[-1] for l in Path(env("SITES_FILE", "./sites.txt")).read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    if not sites:
        sys.exit("sites file is empty")

    server_ip, proto, port = parse_ovpn(OVPN)
    iface = detect_iface(server_ip) if capture_on else None

    capture_meta = {
        "capture_id": capture_id,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "end_time": None,
        "duration_s": None,
        "total_sessions": 0,
        "interface": iface,
        "config": {"seed": seed, "sessions_planned": sessions, "server": server_ip,
                   "proto": proto, "port": port, "backend": backend, "netns": NETNS},
    }
    capture_meta_path = capture_dir / "metadata.json"
    capture_meta_path.write_text(json.dumps(capture_meta, indent=2))
    log(f"capture={capture_id} dir={capture_dir}")
    log(f"seed={seed} sessions={sessions} server={server_ip} {proto}/{port} iface={iface} backend={backend}")

    for i in range(1, sessions + 1):
        if _stop:
            break
        # Pre-draw ALL randomness in a fixed order -> same seed reproduces the run
        sdur = rng.randint(dmin, dmax)
        tsd = rng.randint(tmin, tmax)
        isd = rng.randint(imin, imax)
        nreq = rng.randint(rmin, rmax)
        plan = [(rng.choice(sites), rng.randint(rimin, rimax)) for _ in range(nreq)]

        sid = f"session_{i:03d}"
        sess_dir = capture_dir / sid           # sessions live inside THIS capture only
        sess_dir.mkdir(parents=True, exist_ok=True)
        pcap = sess_dir / f"{sid}.pcap"
        ovpn_log = sess_dir / f"{sid}_openvpn.log"
        t0 = time.time()
        meta = {"session_id": i, "start_time": datetime.now(timezone.utc).isoformat(),
                "vpn_server": server_ip, "vpn_protocol": "OpenVPN", "proto": proto, "port": port,
                "seed": seed, "planned_duration_s": sdur, "traffic_start_delay_s": tsd,
                "inter_session_delay_s": isd, "planned_requests": nreq,
                "connection_success": False, "assigned_vpn_ip": None,
                "pcap_file": pcap.name, "requests": []}
        log(f"=== {sid} ({i}/{sessions}) dur={sdur}s reqs={nreq} ===")

        cap = ov = lf = None
        try:
            if capture_on:
                cap = start_capture(iface, server_ip, proto, port, pcap)
            ov, lf = start_openvpn(ovpn_log)

            if not wait_ready(ov, tun_timeout):
                meta["status"] = "connect_failed"
                log(f"{sid}: tunnel did not establish")
            else:
                info = read_tuninfo()
                meta.update(connection_success=True,
                            assigned_vpn_ip=info.get("vpn_ip"),
                            vpn_gateway=info.get("gateway"),
                            connect_time_s=round(time.time() - t0, 2),
                            probe_http_code=probe())
                sleep_interruptible(tsd, ov)                 # randomized start delay
                deadline = t0 + sdur
                for dest, interval in plan:                  # generate requests
                    if _stop or ov.poll() is not None or time.time() >= deadline:
                        break
                    rc, url = traffic_gen.fetch(NETNS, backend, dest, req_timeout,
                                                pybin, str(HERE / "browse.py"), browse_dwell)
                    meta["requests"].append({"dest": url, "rc": rc, "t": round(time.time() - t0, 2)})
                    sleep_interruptible(interval, ov)
                while not _stop and ov.poll() is None and time.time() < deadline:  # keep alive
                    time.sleep(1)
                meta["status"] = "tunnel_dropped" if ov.poll() is not None else "ok"
        finally:
            stop_proc(ov)
            if lf:
                lf.close()
            time.sleep(1)
            meta["vpn_terminated"] = ov is None or ov.poll() is not None
            netns_run(["ip", "link", "del", TUN_DEV],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stop_proc(cap)
            meta["end_time"] = datetime.now(timezone.utc).isoformat()
            meta["traffic_duration"] = round(time.time() - t0, 2)
            meta["request_count"] = len(meta["requests"])
            meta["packet_count"] = count_packets(pcap) if capture_on else None
            meta["capture_id"] = capture_id
            files = []
            if pcap.exists():
                files.append(pcap.name)
            if ovpn_log.exists():
                files.append(ovpn_log.name)
            files.append("session_metadata.json")
            meta["files"] = files
            (sess_dir / "session_metadata.json").write_text(json.dumps(meta, indent=2))
            with (OUTPUT / "metadata.jsonl").open("a") as fh:   # global index: all sessions, all captures
                fh.write(json.dumps(meta) + "\n")
            completed_sessions.append({"session_id": i, "dir": sid,
                                       "status": meta.get("status"),
                                       "connection_success": meta.get("connection_success"),
                                       "packet_count": meta.get("packet_count")})
            log(f"{sid}: status={meta.get('status')} ip={meta.get('assigned_vpn_ip')} "
                f"reqs={meta['request_count']} dir={sess_dir}")

        if i < sessions and not _stop:
            log(f"inter-session wait {isd}s")
            slept = 0
            while slept < isd and not _stop:
                time.sleep(1)
                slept += 1

    # --- finalize capture metadata (reached on normal end AND on Ctrl+C) ------
    capture_meta["end_time"] = datetime.now(timezone.utc).isoformat()
    capture_meta["duration_s"] = round(time.time() - capture_start, 2)
    capture_meta["total_sessions"] = len(completed_sessions)
    capture_meta["stopped_by_user"] = _stop
    capture_meta["sessions"] = completed_sessions
    capture_meta_path.write_text(json.dumps(capture_meta, indent=2))
    log(f"capture {capture_id} finalized: {len(completed_sessions)} session(s) -> {capture_dir}")
    log("experiment complete")


if __name__ == "__main__":
    main()