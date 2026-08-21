#!/usr/bin/env bash
# Run on the SERVER (desktop, 10.208.23.185). Reads server.conf to learn the
# proto/port/VPN-subnet, then enables forwarding + NAT so tunnel clients can
# reach the Internet. Does NOT change normal server networking. Idempotent.
#     bash setup_server.sh [path/to/server.conf]
set -euo pipefail

CONF="${1:-$HOME/vpn-lab/server/server.conf}"
[ -f "$CONF" ] || { echo "server.conf not found: $CONF  (pass its path as arg)"; exit 1; }

proto="$(awk '/^proto /{print $2; exit}' "$CONF")"; proto="${proto:-udp}"
port="$(awk '/^port /{print $2; exit}' "$CONF")";  port="${port:-1194}"
snet="$(awk '/^server /{print $2; exit}' "$CONF")"; snet="${snet:-10.8.0.0}"
smask="$(awk '/^server /{print $3; exit}' "$CONF")"; smask="${smask:-255.255.255.0}"

mask2cidr() { local m=$1 c=0 o; for o in ${m//./ }; do while [ "$o" -gt 0 ]; do c=$((c+(o&1))); o=$((o>>1)); done; done; echo "$c"; }
SUBNET="$snet/$(mask2cidr "$smask")"
WAN="$(ip route show default | awk '/default/{print $5; exit}')"
echo "proto=$proto port=$port subnet=$SUBNET wan=$WAN"

sudo sysctl -w net.ipv4.ip_forward=1 >/dev/null
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf \
  || echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf >/dev/null

sudo iptables -t nat -C POSTROUTING -s "$SUBNET" -o "$WAN" -j MASQUERADE 2>/dev/null \
  || sudo iptables -t nat -A POSTROUTING -s "$SUBNET" -o "$WAN" -j MASQUERADE
sudo iptables -C FORWARD -s "$SUBNET" -j ACCEPT 2>/dev/null \
  || sudo iptables -A FORWARD -s "$SUBNET" -j ACCEPT
sudo iptables -C FORWARD -d "$SUBNET" -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null \
  || sudo iptables -A FORWARD -d "$SUBNET" -m state --state ESTABLISHED,RELATED -j ACCEPT

if command -v ufw >/dev/null && sudo ufw status 2>/dev/null | grep -q "Status: active"; then
  sudo ufw allow "$port/$proto" || true
fi
echo "Server forwarding + NAT configured. Check with: bash check_server.sh"
