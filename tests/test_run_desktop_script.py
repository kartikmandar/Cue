import os
import shutil
import socket
import subprocess
import textwrap
import time
import tomllib
from pathlib import Path


def unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_file(path: Path, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return path.exists()


def test_pixi_desktop_task_runs_backend_and_app_together():
    data = tomllib.loads(Path("pixi.toml").read_text(encoding="utf-8"))

    assert data["tasks"]["desktop"] == "./scripts/run_desktop.sh"


def test_run_desktop_starts_backend_waits_for_health_and_opens_app(tmp_path):
    root = tmp_path / "cue"
    script_dir = root / "scripts"
    script_dir.mkdir(parents=True)
    shutil.copy("scripts/run_desktop.sh", script_dir / "run_desktop.sh")

    backend = script_dir / "run_backend.sh"
    backend.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            exec python - "$CUE_API_HOST" "$CUE_API_PORT" <<'PY'
            import json
            import sys
            from http.server import BaseHTTPRequestHandler, HTTPServer

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path != "/health":
                        self.send_response(404)
                        self.end_headers()
                        return
                    body = json.dumps(
                        {"status": "ok", "app": "cue", "yolo_mode": False}
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, format, *args):
                    return

            HTTPServer((sys.argv[1], int(sys.argv[2])), Handler).serve_forever()
            PY
            """
        ),
        encoding="utf-8",
    )
    backend.chmod(0o755)

    app_path = root / "build" / "mac" / "Build" / "Products" / "Release" / "CueApp.app"
    app_path.mkdir(parents=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    open_log = tmp_path / "open.log"
    open_stub = bin_dir / "open"
    open_stub.write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\nprintf \'%s\\n\' "$1" >> "$OPEN_LOG"\n',
        encoding="utf-8",
    )
    open_stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["CUE_API_HOST"] = "127.0.0.1"
    env["CUE_API_PORT"] = str(unused_port())
    env["OPEN_LOG"] = str(open_log)

    proc = subprocess.Popen(
        ["bash", str(script_dir / "run_desktop.sh")],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert wait_for_file(open_log), "Cue app was not opened"
    finally:
        proc.terminate()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=5)

    assert open_log.read_text(encoding="utf-8").strip() == str(app_path)
