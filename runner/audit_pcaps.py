#!/usr/bin/env python3
"""Read-only integrity and isolation audit of V2 OpenVPN experiment results."""
import argparse
import json
import subprocess
from pathlib import Path


def audit_session(metadata_path):
    session = metadata_path.parent
    meta = json.loads(metadata_path.read_text())
    pcap = session / 'client.pcap'
    record = {'session': str(session), 'status': meta.get('status'),
              'transport': meta.get('transport'), 'port': meta.get('server_port'),
              'connection_success': meta.get('connection_success'),
              'frames': 0, 'openvpn_frames': 0, 'data_frames': 0,
              'issues': [], 'notes': []}
    issues = record['issues']
    transport = meta.get('transport')
    host = meta.get('server_ip')
    port = meta.get('server_port')
    if transport not in ('tcp', 'udp') or not isinstance(host, str) or not isinstance(port, int):
        issues.append('invalid_capture_metadata')
        return record
    expected_filter = f'host {host} and {transport} port {port}'
    if meta.get('capture_filter') != expected_filter:
        issues.append('capture_filter_mismatch')
    if not pcap.is_file():
        (issues if meta.get('connection_success') else record['notes']).append('capture_not_started')
        return record
    if pcap.stat().st_size <= 24:
        (issues if meta.get('connection_success') else record['notes']).append('capture_has_no_packets')
        return record
    fields = ['frame.number', 'ip.src', 'ip.dst', 'tcp.srcport', 'tcp.dstport',
              'udp.srcport', 'udp.dstport', 'openvpn.opcode']
    cmd = ['tshark', '-r', str(pcap), '-d', f'{transport}.port=={port},openvpn',
           '-T', 'fields', '-E', 'separator=\t']
    for field in fields:
        cmd.extend(('-e', field))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        issues.append(f'capture_read_failed:{type(exc).__name__}')
        return record
    if result.returncode:
        issues.append('capture_read_failed')
        record['read_error'] = result.stderr.strip()[:300]
        return record
    wrong = 0
    for line in result.stdout.splitlines():
        parts = line.split('\t')
        if len(parts) != len(fields):
            issues.append('invalid_decoder_output')
            break
        _, src, dst, tcp_src, tcp_dst, udp_src, udp_dst, opcodes = parts
        record['frames'] += 1
        ports = (tcp_src, tcp_dst) if transport == 'tcp' else (udp_src, udp_dst)
        other_ports = (udp_src, udp_dst) if transport == 'tcp' else (tcp_src, tcp_dst)
        if host not in (src, dst) or str(port) not in ports or any(other_ports):
            wrong += 1
        if opcodes:
            record['openvpn_frames'] += 1
            if '0x09' in opcodes.split(','):
                record['data_frames'] += 1
    if wrong:
        issues.append(f'frames_outside_vpn_filter:{wrong}')
    if not record['frames']:
        issues.append('no_frames')
    if meta.get('connection_success') and not record['openvpn_frames']:
        issues.append('established_but_no_openvpn_decode')
    if meta.get('connection_success') and not record['data_frames']:
        issues.append('established_but_no_openvpn_data')
    recorded = meta.get('stats', {}).get('packet_count')
    if isinstance(recorded, int) and recorded != record['frames']:
        issues.append(f'packet_count_mismatch:recorded={recorded}')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='results/ or VPN-Storage/experiments/openvpn/')
    parser.add_argument('--output', type=Path, help='write full JSON report outside the result tree')
    args = parser.parse_args()
    root = args.root.resolve()
    experiments = sorted({p.parent for p in root.rglob('experiment.yaml')})
    sessions = []
    orphan_captures = []
    checksum_failures = []
    missing_manifests = []
    unprotected_files = []
    for exp in experiments:
        manifest = exp / 'checksums.sha256'
        if manifest.exists():
            protected = {line.split('  ', 1)[1] for line in manifest.read_text().splitlines()
                         if '  ' in line}
            for path in (exp / 'sessions').glob('session_*/*'):
                if path.name in ('client.pcap', 'metadata.json') and str(path.relative_to(exp)) not in protected:
                    unprotected_files.append(str(path))
            check = subprocess.run(['sha256sum', '-c', '--status', 'checksums.sha256'],
                                   cwd=exp, capture_output=True, text=True)
            if check.returncode:
                checksum_failures.append(str(exp))
        else:
            missing_manifests.append(str(exp))
        for metadata in sorted((exp / 'sessions').glob('session_*/metadata.json')):
            sessions.append(audit_session(metadata))
        for pcap in sorted((exp / 'sessions').glob('session_*/client.pcap')):
            if not (pcap.parent / 'metadata.json').exists():
                check = subprocess.run(['tshark', '-r', str(pcap), '-q'],
                                       capture_output=True, text=True, timeout=180)
                orphan_captures.append({'path': str(pcap), 'bytes': pcap.stat().st_size,
                                        'readable': check.returncode == 0})
    issue_sessions = [row for row in sessions if row['issues']]
    note_sessions = [row for row in sessions if row['notes']]
    report = {'root': str(root), 'experiments': len(experiments), 'sessions': len(sessions),
              'frames': sum(row['frames'] for row in sessions),
              'openvpn_frames': sum(row['openvpn_frames'] for row in sessions),
              'data_frames': sum(row['data_frames'] for row in sessions),
              'issue_sessions': issue_sessions, 'note_sessions': note_sessions,
              'checksum_failures': checksum_failures,
              'missing_manifests': missing_manifests, 'unprotected_files': unprotected_files,
              'orphan_captures': orphan_captures, 'sessions_detail': sessions}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'sessions_detail'}, indent=2))
    return 1 if (issue_sessions or checksum_failures or missing_manifests or
                 unprotected_files or orphan_captures) else 0


if __name__ == '__main__':
    raise SystemExit(main())
