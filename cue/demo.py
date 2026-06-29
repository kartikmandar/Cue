"""Deterministic local demo launcher for Cue."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_ASSETS_DIR = PROJECT_ROOT / "demo_assets"

INACCESSIBLE_FORM_PATH = DEMO_ASSETS_DIR / "inaccessible_form.html"
LOCAL_DASHBOARD_PATH = DEMO_ASSETS_DIR / "local_dashboard.html"
SAMPLE_BRIEF_PATH = DEMO_ASSETS_DIR / "sample_brief.txt"
SAMPLE_CONTRACT_PATH = DEMO_ASSETS_DIR / "sample_contract.txt"
PROJECT_DESCRIPTION_PATH = DEMO_ASSETS_DIR / "demo_project_description.txt"
DEMO_SCRIPT_PATH = DEMO_ASSETS_DIR / "demo_script.md"
HACKATHON_PDF_PATH = DEMO_ASSETS_DIR / "Gemma 4 Hackathon Instruction Document.pdf"


@dataclass(frozen=True)
class DemoTarget:
    key: str
    label: str
    path: Path | None = None
    app_name: str | None = None


@dataclass(frozen=True)
class DemoOpenResult:
    key: str
    ok: bool
    command: tuple[str, ...]
    reason: str


DEMO_TARGETS: dict[str, DemoTarget] = {
    "demo-form": DemoTarget(
        key="demo-form",
        label="weakly labeled local demo form",
        path=INACCESSIBLE_FORM_PATH,
    ),
    "dashboard": DemoTarget(
        key="dashboard",
        label="local dashboard HTML",
        path=LOCAL_DASHBOARD_PATH,
    ),
    "sample-brief": DemoTarget(
        key="sample-brief",
        label="sample work brief",
        path=SAMPLE_BRIEF_PATH,
    ),
    "hackathon-pdf": DemoTarget(
        key="hackathon-pdf",
        label="official hackathon PDF copy",
        path=HACKATHON_PDF_PATH,
    ),
    "textedit": DemoTarget(
        key="textedit",
        label="TextEdit document workflow target",
        app_name="TextEdit",
    ),
    "terminal": DemoTarget(
        key="terminal",
        label="Terminal read-only handoff target",
        app_name="Terminal",
    ),
}

DEFAULT_DEMO_SEQUENCE = (
    "sample-brief",
    "hackathon-pdf",
    "dashboard",
    "demo-form",
    "textedit",
    "terminal",
)

_Opener = Callable[[], DemoOpenResult]


def open_demo_form() -> DemoOpenResult:
    return _open_path(DEMO_TARGETS["demo-form"])


def open_dashboard() -> DemoOpenResult:
    return _open_path(DEMO_TARGETS["dashboard"])


def open_sample_brief() -> DemoOpenResult:
    return _open_path(DEMO_TARGETS["sample-brief"])


def open_hackathon_pdf() -> DemoOpenResult:
    return _open_path(DEMO_TARGETS["hackathon-pdf"])


def open_textedit() -> DemoOpenResult:
    return _open_app(DEMO_TARGETS["textedit"])


def open_terminal() -> DemoOpenResult:
    return _open_app(DEMO_TARGETS["terminal"])


TARGET_OPENERS: dict[str, _Opener] = {
    "demo-form": open_demo_form,
    "dashboard": open_dashboard,
    "sample-brief": open_sample_brief,
    "hackathon-pdf": open_hackathon_pdf,
    "textedit": open_textedit,
    "terminal": open_terminal,
}


def run_demo(
    targets: Sequence[str] | None = None,
    *,
    dry_run: bool = False,
) -> list[DemoOpenResult]:
    selected = tuple(targets or DEFAULT_DEMO_SEQUENCE)
    _validate_targets(selected)

    if dry_run:
        return [_dry_run_result(DEMO_TARGETS[key]) for key in selected]

    return [TARGET_OPENERS[key]() for key in selected]


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list:
        for key, target in DEMO_TARGETS.items():
            print(f"{key}: {target.label}")
        return 0

    try:
        results = run_demo(args.targets, dry_run=args.dry_run)
    except ValueError as exc:
        parser.error(str(exc))

    if args.dry_run:
        print("Dry run: no apps or files were opened.")

    for result in results:
        status = "ok" if result.ok else "error"
        command = " ".join(result.command)
        print(f"{status}: {result.key}: {command} - {result.reason}")

    return 0 if all(result.ok for result in results) else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cue-demo",
        description="Open Cue's deterministic local demo assets and safe demo apps.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help=(
            "Optional target keys to open. Defaults to the full safe demo sequence. "
            "Use --list to see keys."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the fixed open commands without launching apps or files.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available deterministic demo targets.",
    )
    return parser


def _open_path(target: DemoTarget) -> DemoOpenResult:
    if target.path is None:
        return DemoOpenResult(
            key=target.key,
            ok=False,
            command=(),
            reason="Demo target has no local file path.",
        )
    if not target.path.exists():
        return DemoOpenResult(
            key=target.key,
            ok=False,
            command=("open", str(target.path)),
            reason=f"Missing demo asset: {target.path}",
        )
    return _run_open(target.key, ["open", str(target.path)])


def _open_app(target: DemoTarget) -> DemoOpenResult:
    if target.app_name is None:
        return DemoOpenResult(
            key=target.key,
            ok=False,
            command=(),
            reason="Demo target has no app name.",
        )
    return _run_open(target.key, ["open", "-a", target.app_name])


def _run_open(key: str, command: list[str]) -> DemoOpenResult:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except FileNotFoundError as exc:
        return DemoOpenResult(
            key=key,
            ok=False,
            command=tuple(command),
            reason=f"macOS open command unavailable: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        return DemoOpenResult(
            key=key,
            ok=False,
            command=tuple(command),
            reason=f"macOS open timed out after {exc.timeout}s.",
        )

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "no stderr/stdout").strip()
        return DemoOpenResult(
            key=key,
            ok=False,
            command=tuple(command),
            reason=f"macOS open failed: {details}",
        )

    return DemoOpenResult(
        key=key,
        ok=True,
        command=tuple(command),
        reason="Opened fixed local demo target.",
    )


def _dry_run_result(target: DemoTarget) -> DemoOpenResult:
    if target.path is not None:
        command = ("open", str(target.path))
    elif target.app_name is not None:
        command = ("open", "-a", target.app_name)
    else:
        command = ()

    return DemoOpenResult(
        key=target.key,
        ok=True,
        command=command,
        reason=f"Would open {target.label}.",
    )


def _validate_targets(targets: Sequence[str]) -> None:
    unknown = [target for target in targets if target not in DEMO_TARGETS]
    if unknown:
        valid = ", ".join(DEMO_TARGETS)
        raise ValueError(
            f"Unknown demo target(s): {', '.join(unknown)}. Valid targets: {valid}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
