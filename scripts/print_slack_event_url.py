#!/usr/bin/env python3
"""Print the Slack Event Subscriptions URL exposed by a local ngrok tunnel."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    try:
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3) as response:  # nosec B310
            payload = json.load(response)
    except urllib.error.URLError as exc:
        print(f"Cannot reach the local ngrok agent: {exc}", file=sys.stderr)
        return 1
    urls = [
        str(tunnel.get("public_url") or "").rstrip("/")
        for tunnel in payload.get("tunnels") or []
        if str(tunnel.get("public_url") or "").startswith("https://")
    ]
    if not urls:
        print("No HTTPS ngrok tunnel was found.", file=sys.stderr)
        return 1
    print(urls[0] + "/slack/events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
