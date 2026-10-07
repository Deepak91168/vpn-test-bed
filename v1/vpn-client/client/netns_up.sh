#!/usr/bin/env bash
# OpenVPN --up script. Runs in the ROOT namespace with the tunnel parameters in
# the environment. It moves the freshly-created tun device INTO the isolated
# namespace and configures it there, so the tunnel exists only inside $NETNS.
# The openvpn process itself stays in the root namespace (its encrypted UDP to
# the server flows over the real NIC, where tcpdump captures it).
set -u

NS="${VPNLAB_NETNS:-vpn}"
READY="${VPNLAB_READY:-/tmp/vpnlab_ready}"
TUNINFO="${VPNLAB_TUNINFO:-/tmp/vpnlab_tuninfo}"
dev="${dev:-${1:-}}"

mask2cidr() {  # dotted mask -> prefix length (contiguous masks)
  local m=$1 c=0 o
  for o in ${m//./ }; do
    while [ "$o" -gt 0 ]; do c=$((c + (o & 1))); o=$((o >> 1)); done
  done
  echo "$c"
}

# 1) move the device into the namespace
ip link set dev "$dev" netns "$NS"
ip -n "$NS" link set dev lo up
[ -n "${tun_mtu:-}" ] && ip -n "$NS" link set dev "$dev" mtu "$tun_mtu" || true

# 2) address it (handles both 'topology subnet' and net30/p2p)
if [ -n "${ifconfig_netmask:-}" ]; then
  pfx="$(mask2cidr "$ifconfig_netmask")"
  ip -n "$NS" addr add "${ifconfig_local}/${pfx}" dev "$dev"
else
  ip -n "$NS" addr add "${ifconfig_local}" peer "${ifconfig_remote}" dev "$dev"
fi
ip -n "$NS" link set dev "$dev" up

# 3) default route through the tunnel, INSIDE the namespace only
if [ -n "${route_vpn_gateway:-}" ]; then
  ip -n "$NS" route replace default via "${route_vpn_gateway}" dev "$dev"
else
  ip -n "$NS" route replace default dev "$dev"
fi

# 4) publish tunnel info + signal "ready" to the controller
{ echo "dev=$dev"; echo "vpn_ip=${ifconfig_local:-}"; echo "gateway=${route_vpn_gateway:-}"; } > "$TUNINFO"
: > "$READY"
exit 0