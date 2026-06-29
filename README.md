# Cue

Blind-first macOS accessibility copilot for the Cerebras x Google DeepMind Gemma 4 hackathon.

## Development

Use Pixi for all local environment, dependency, test, and run commands:

```bash
pixi install
pixi run test
pixi run test-mac
```

Implementation tasks are tracked in the outer repo's `PLAN.md`.

## Native App

Run the macOS shell from Xcode through Pixi:

```bash
pixi run xcode
```

The app opens to the Cue command palette. Use text input by default; voice mode
is shown but remains disabled unless local speech/input support is enabled. The
palette previews a workflow, asks for approval, executes one step at a time,
shows focus, policy, verification, privacy, timing, and redacted audit state,
and narrates preview or verification text when speech is enabled.

Open the palette with `Shift` + `Command` + `Space` while the app is running, or
from the menu-bar item.

## Cua Driver

Install or verify Cua Driver through Pixi:

```bash
pixi run install-cua
```

Run the driver diagnostics through Pixi:

```bash
pixi run doctor
```

`pixi run doctor` reports the Cua doctor result plus app, window, screen, focus,
and cursor probes. If macOS Accessibility or Screen Recording permissions are
not granted yet, use the exact diagnostic output from `pixi run doctor` to
complete the permission path, then run it again.

## Packaging

Build and package the Release app through Pixi:

```bash
pixi run package
```

The package task uses `xcodebuild` and writes `dist/CueApp.zip`. Build output,
`dist/`, and derived data stay ignored by Git.
