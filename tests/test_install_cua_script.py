import os
import subprocess
from pathlib import Path


def test_install_cua_script_detects_current_cua_driver_bundle(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home_dir = tmp_path / "home"
    app_dir = home_dir / "Applications" / "CuaDriver.app"
    app_dir.mkdir(parents=True)
    open_log = tmp_path / "open.log"

    cua_driver = bin_dir / "cua-driver"
    cua_driver.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "doctor" ]]; then
  printf 'doctor ok\\n'
  exit 0
fi
printf 'unexpected cua-driver args: %s\\n' "$*" >&2
exit 64
""",
        encoding="utf-8",
    )
    cua_driver.chmod(0o755)

    open_stub = bin_dir / "open"
    open_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$1" >> "$CUA_OPEN_LOG"
""",
        encoding="utf-8",
    )
    open_stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["HOME"] = str(home_dir)
    env["CUA_OPEN_LOG"] = str(open_log)

    result = subprocess.run(
        ["bash", "scripts/install_cua_driver.sh"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Cua app bundle was not found" not in result.stdout
    assert "Opening Cua app: " in result.stdout
    opened_path = Path(open_log.read_text(encoding="utf-8").strip())
    assert opened_path.name == "CuaDriver.app"
    assert str(opened_path) in {"/Applications/CuaDriver.app", str(app_dir)}
