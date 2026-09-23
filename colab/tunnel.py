"""Open a public tunnel to a local port on Google Colab.

Tries, in order:
1. cloudflared quick tunnel (no account, most reliable on Colab)
2. ssh -R localhost.run (no install, needs ssh)
Prints the public URL so you can open the Forge web UI from any device.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.request

PORT = int(os.environ.get("FORGE_PORT", sys.argv[1] if len(sys.argv) > 1 else 8000))


def _cf_url(log_path: str, timeout: float = 30.0) -> str | None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with open(log_path, "r", errors="ignore") as f:
                for line in f:
                    m = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
                    if m:
                        return m.group(1)
        except OSError:
            pass
        time.sleep(0.5)
    return None


def cloudflared() -> str | None:
    if subprocess.run(["which", "cloudflared"], capture_output=True).returncode != 0:
        url = ("https://github.com/cloudflare/cloudflared/releases/latest/download/"
               "cloudflared-linux-amd64")
        subprocess.run(["curl", "-sL", "-o", "/usr/local/bin/cloudflared", url], check=True)
        os.chmod("/usr/local/bin/cloudflared", 0o755)
    log = "/tmp/cf.log"
    open(log, "w").close()
    with open(log, "w") as lf:
        subprocess.Popen(["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
                         stdout=lf, stderr=subprocess.STDOUT)
    return _cf_url(log)


def localhost_run() -> str | None:
    try:
        proc = subprocess.Popen(["ssh", "-R", "80:localhost:%d" % PORT, "-o", "StrictHostKeyChecking=no",
                                 "nokey@localhost.run"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        start = time.time()
        while time.time() - start < 25:
            line = proc.stdout.readline()
            m = re.search(r"(https://[a-z0-9.]+\.lhr\.life)", line)
            if m:
                return m.group(1)
        return None
    except Exception:
        return None


def main() -> None:
    print(f"[tunnel] exposing http://localhost:{PORT} ...")
    url = cloudflared() or localhost_run()
    if url:
        print("\n" + "=" * 60)
        print(f"  ✅  Roblox UI Forge is live at:\n  {url}")
        print("=" * 60)
    else:
        print("[tunnel] could not open a tunnel; use the local address instead.")


if __name__ == "__main__":
    main()
