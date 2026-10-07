#!/usr/bin/env python3
"""Visit one site and generate realistic traffic. Run AS the vpnuser so the
traffic is policy-routed through the tunnel.

    sudo -u vpnuser python3 browse.py https://example.com 30

Uses Playwright (headless Chromium). One-time setup, as vpnuser:
    pip install playwright && playwright install chromium
"""
import sys
import time

from playwright.sync_api import sync_playwright


def visit(url: str, dwell: float, headless: bool = True) -> None:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=60_000)
        except Exception as exc:  # keep the experiment moving on flaky sites
            print(f"[browse] load warning for {url}: {exc}", file=sys.stderr)
        # Light interaction so the flow isn't a single page load
        end = time.time() + dwell
        while time.time() < end:
            try:
                page.mouse.wheel(0, 1200)
            except Exception:
                pass
            time.sleep(2)
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: browse.py <url> <dwell_seconds> [headless=1]")
    url_arg = sys.argv[1]
    dwell_arg = float(sys.argv[2])
    headless_arg = sys.argv[3] != "0" if len(sys.argv) > 3 else True
    visit(url_arg, dwell_arg, headless_arg)
