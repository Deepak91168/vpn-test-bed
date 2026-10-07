# tls-crypt-v2

This mechanism uses a per-client wrapped control-channel key. Directive: `tls-crypt-v2 credentials/tls-crypt-v2-client.key`. Required key: `tls-crypt-v2-client.key (server needs tls-crypt-v2-server.key)`. Profiles: `profiles/udp.ovpn`, `profiles/tcp.ovpn`. On the wire it hides control-channel TLS payloads and uses a client-specific key; outer IP, port, transport, packet size, and timing remain observable. Run `sudo ./runner/vpnlab run openvpn --transport udp --control tls-crypt-v2 --sessions 1` from V2 root (use `tcp` for TCP).
