# tls-auth

This mechanism authenticates control packets with an HMAC. Directive: `tls-auth credentials/ta.key 1`. Required key: `ta.key`. Profiles: `profiles/udp.ovpn`, `profiles/tcp.ovpn`. On the wire it adds HMAC protection; TLS handshake is still visible; outer IP, port, transport, packet size, and timing remain observable. Run `sudo ./runner/vpnlab run openvpn --transport udp --control tls-auth --sessions 1` from V2 root (use `tcp` for TCP).
