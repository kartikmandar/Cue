# Cue

Blind-first macOS accessibility copilot for the Cerebras x Google DeepMind Gemma 4 hackathon.

## Development

Use Pixi for all local environment, dependency, test, and run commands:

```bash
pixi install
pixi run test
```

Implementation tasks are tracked in the outer repo's `PLAN.md`.

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
