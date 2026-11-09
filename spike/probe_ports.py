import urllib.request

for port in (50646, 55860, 63621):
    for path in ("/", "/health", "/api/health", "/status", "/api/status"):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
            with urllib.request.urlopen(req, timeout=2) as r:
                body = r.read()[:200]
                print(port, path, r.status, body)
        except Exception as exc:  # noqa: BLE001
            print(port, path, "ERR", getattr(exc, "code", type(exc).__name__))
