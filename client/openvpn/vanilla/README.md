# Vanilla OpenVPN

No control-channel protection directive or static key. Profiles: `profiles/udp.ovpn` and `profiles/tcp.ovpn`. The TLS handshake remains observable; outer IP, port, transport, packet size, and timing remain observable. Run `sudo ./runner/vpnlab run openvpn --transport udp --control vanilla --sessions 1` from V2 root (use `tcp` for TCP).
