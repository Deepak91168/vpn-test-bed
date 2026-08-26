#!/usr/bin/env bash
# One command to run the whole experiment over SSH:
#     sudo ./run_experiment.sh
# For a run that survives the SSH session closing, use tmux or:
#     sudo nohup ./run_experiment.sh > run.out 2>&1 &
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

[ "$(id -u)" -eq 0 ] || { echo "Run as root:  sudo ./run_experiment.sh"; exit 1; }
[ -f config.env ] || { echo "config.env not found in $HERE"; exit 1; }
set -a; . ./config.env; set +a

# --- transport mode: `./run_experiment.sh [udp|tcp]` -------------------------
# No argument => unchanged behaviour (uses OVPN_CONFIG from config.env).
MODE="${1:-}"
case "$MODE" in
  udp) export OVPN_CONFIG=./client.ovpn;     export CAPTURE_LABEL=udp ;;
  tcp) export OVPN_CONFIG=./client-tcp.ovpn; export CAPTURE_LABEL=tcp ;;
  "")  : ;;  # keep config.env's OVPN_CONFIG (backward compatible)
  *)   echo "usage: $0 [udp|tcp]"; exit 1 ;;
esac
[ -f "$OVPN_CONFIG" ] || { echo "profile not found: $OVPN_CONFIG (create it — see README TCP section)"; exit 1; }
[ -n "$MODE" ] && echo "[run] transport mode: $MODE  profile: $OVPN_CONFIG"

NETNS="${NETNS:-vpn}"
OUTPUT_DIR="${OUTPUT_DIR:-./experiment_out}"
RUN_DIR="$OUTPUT_DIR/run"
mkdir -p "$OUTPUT_DIR" "$RUN_DIR"

# exported for the openvpn up/down scripts
export VPNLAB_NETNS="$NETNS"
export VPNLAB_READY="$RUN_DIR/ready"
export VPNLAB_TUNINFO="$RUN_DIR/tuninfo"

cleanup() {
  set +e
  if ip netns list 2>/dev/null | grep -qw "$NETNS"; then
    for p in $(ip netns pids "$NETNS" 2>/dev/null); do kill "$p" 2>/dev/null; done
    ip netns del "$NETNS" 2>/dev/null
  fi
  rm -rf "/etc/netns/$NETNS"
  for pf in "$RUN_DIR/openvpn.pid" "$RUN_DIR/tcpdump.pid"; do
    [ -f "$pf" ] && kill "$(cat "$pf")" 2>/dev/null
    rm -f "$pf"
  done
}
trap cleanup EXIT INT TERM
trap '' HUP        # keep running if the SSH session drops

# (re)create the isolated namespace with its own DNS (through the tunnel)
ip netns del "$NETNS" 2>/dev/null || true
ip netns add "$NETNS"
ip netns exec "$NETNS" ip link set lo up
mkdir -p "/etc/netns/$NETNS"
echo "nameserver ${VPN_DNS:-1.1.1.1}" > "/etc/netns/$NETNS/resolv.conf"

echo "[run] namespace '$NETNS' ready — starting session controller"
"${PYTHON:-/usr/bin/python3}" session_controller.py
echo "[run] done — cleaning up"