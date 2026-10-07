# tls-crypt

This mechanism authenticates and encrypts the control channel. Directive: `tls-crypt credentials/tls-crypt.key`. Required key: `tls-crypt.key`. Profiles: `profiles/udp.ovpn`, `profiles/tcp.ovpn`. On the wire it hides control-channel TLS payloads; outer IP, port, transport, packet size, and timing remain observable. Run `sudo ./runner/vpnlab run openvpn --transport udp --control tls-crypt --sessions 1` from V2 root (use `tcp` for TCP).
