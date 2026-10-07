#!/usr/bin/env bash
# OPTIONAL second capture vantage, on the SERVER. Captures the same encrypted
# flow from the server side (all clients). The client-side per-session pcaps are
# usually enough; use this only if you want a server-side view too.
#     sudo bash server_capture.sh [path/to/server.conf] [out.pcap]
set -euo pipefail
CONF="${1:-$HOME/vpn-lab/server/server.conf}"
port="$(awk '/^port /{print $2; exit}' "$CONF" 2>/dev/null)"; port="${port:-1194}"
proto="$(awk '/^proto /{print $2; exit}' "$CONF" 2>/dev/null)"; proto="${proto:-udp}"
WAN="$(ip route show default | awk '/default/{print $5; exit}')"
OUT="${2:-server_capture_$(date +%Y%m%d_%H%M%S).pcap}"
echo "Capturing $proto/$port on $WAN -> $OUT   (Ctrl-C to stop)"
sudo tcpdump -i "$WAN" -U -w "$OUT" "$proto port $port"
