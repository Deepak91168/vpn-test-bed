# OpenVPN client

Eight profiles combine UDP/TCP with vanilla, tls-auth, tls-crypt, and tls-crypt-v2. Credentials are copied into `credentials/`. The runner starts OpenVPN in the host namespace with route/ifconfig disabled; hooks move only the TUN interface into `vpnlabv2`. Run with `sudo ./runner/vpnlab run openvpn ...` from the V2 root.
