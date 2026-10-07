#!/usr/bin/env bash
# OpenVPN --down script. The tun device disappears with the namespace teardown
# handled by the controller/run_experiment.sh, so this just clears the ready
# marker. Kept minimal on purpose.
set -u
rm -f "${VPNLAB_READY:-/tmp/vpnlab_ready}"
exit 0