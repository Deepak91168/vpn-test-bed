#!/usr/bin/env bash
# Quick server-side sanity check. Run on the SERVER.
#     bash check_server.sh [path/to/server.conf]
CONF="${1:-$HOME/vpn-lab/server/server.conf}"
port="$(awk '/^port /{print $2; exit}' "$CONF" 2>/dev/null)"; port="${port:-1194}"
proto="$(awk '/^proto /{print $2; exit}' "$CONF" 2>/dev/null)"; proto="${proto:-udp}"

echo "== OpenVPN listening on $proto/$port =="
if [ "$proto" = "tcp" ]; then sudo ss -ltnp 2>/dev/null | grep ":$port" || echo "  NOT listening"
else sudo ss -lunp 2>/dev/null | grep ":$port" || echo "  NOT listening"; fi

echo "== ip_forward (want 1) =="
cat /proc/sys/net/ipv4/ip_forward

echo "== NAT MASQUERADE rules =="
sudo iptables -t nat -S POSTROUTING | grep MASQUERADE || echo "  none"

echo "== connected clients =="
if [ -f "$(dirname "$CONF")/openvpn-status.log" ]; then
  sed -n '1,25p' "$(dirname "$CONF")/openvpn-status.log"
else
  echo "  no openvpn-status.log"
fi
