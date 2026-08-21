"""Pluggable traffic generator. Every request is executed with
`ip netns exec <netns> ...`, so it can ONLY leave through the tunnel — there is
no host route inside the namespace to leak onto.

Backends:
  wget    - fetches the page AND its sub-resources (--page-requisites, span
            hosts, --delete-after) => realistic browsing bursts. Default.
  curl    - single object fetch. Lightest, least browser-like.
  browser - headless Chromium via browse.py (most realistic; heaviest deps).
"""
import subprocess


def _norm(dest: str) -> str:
    return dest if dest.startswith(("http://", "https://")) else "https://" + dest


def _cmd(backend, url, timeout, python_bin, browse_script, dwell):
    if backend == "wget":
        return ["wget", "-e", "robots=off", "-p", "-H", "--delete-after",
                "-T", str(timeout), "-t", "1", "-q", url]
    if backend == "browser":
        return [python_bin, browse_script, url, str(dwell)]
    # curl (and fallback)
    return ["curl", "-sL", "-m", str(timeout), "-o", "/dev/null", url]


def fetch(netns, backend, dest, timeout, python_bin, browse_script, dwell):
    """Generate one 'visit' inside the namespace. Returns (returncode, url)."""
    url = _norm(dest)
    cmd = ["ip", "netns", "exec", netns, *_cmd(backend, url, timeout, python_bin, browse_script, dwell)]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode, url
