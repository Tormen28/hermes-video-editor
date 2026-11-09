"""Read the gateway rendezvous records and time HTTP requests to the live gateway.

Usage: python probe_gateway.py [n]
Prints the port/host of the live gateway (from the OS-user rendezvous records)
and the latency of N HTTP requests to it.
"""
import glob
import json
import os
import sys
import time
import urllib.request

LOCK_GLOB = os.path.join(
    os.path.expanduser("~"), ".local", "state", "hermes", "gateway-locks", "host-*.json"
)


def records():
    out = []
    for path in glob.glob(LOCK_GLOB):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            out.append({"file": path, "error": repr(exc)})
            continue
        out.append(
            {
                "file": os.path.basename(path),
                "host": data.get("host"),
                "port": data.get("port"),
                "pid": data.get("pid"),
                "profiles": data.get("profiles"),
                "updatedAt": data.get("updatedAt"),
            }
        )
    return out


if __name__ == "__main__":
    for rec in records():
        print(json.dumps(rec, ensure_ascii=False))
