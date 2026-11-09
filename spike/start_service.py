"""Arranca el servicio del spike DESACOPLADO del proceso que lo invoca.

Motivo: el servicio lanzado desde un terminal de agente muere cuando el proceso
padre termina (árbol de procesos). El pane entonces muestra «Failed to fetch».

Uso:  python start_service.py [--port 8765]
Verificación:  curl -s http://127.0.0.1:8765/health
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "logs", "service.stdout.log")

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        with open(LOG, "ab") as log:
            proc = subprocess.Popen(
                [sys.executable, os.path.join(HERE, "service.py"), "--port", str(args.port)],
                cwd=HERE,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
            )
    except OSError:
        # Si el job no permite desacoplar del todo, reintenta con breakaway.
        with open(LOG, "ab") as log:
            proc = subprocess.Popen(
                [sys.executable, os.path.join(HERE, "service.py"), "--port", str(args.port)],
                cwd=HERE,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                creationflags=flags | CREATE_BREAKAWAY_FROM_JOB,
                close_fds=True,
            )
    print(f"servicio lanzado pid={proc.pid} puerto={args.port} log={LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
