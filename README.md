# Pandora Summarizer

Daily uploader for Pandora instrument data products (L0, L1, alignment, figures, summary) to Google Cloud Storage. See [DESIGN.md](DESIGN.md) for full architecture.

## Status

M1 — skeleton, config, local state DB, orchestrator, stubbed steps. Not yet runnable end-to-end against a real Pandora instrument.

## Quick start (dev)

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp config/config.example.yaml config/config.yaml
pandora-summarizer run --date 2026-05-07 --config config/config.yaml --dry-run
pytest
```

## CLI

```
pandora-summarizer run [--date YYYY-MM-DD] [--config PATH] [--dry-run]
pandora-summarizer status [--config PATH]
```

`--date` defaults to yesterday in the configured instrument timezone.
`--dry-run` runs the orchestrator without invoking BlickP or uploading to GCS.

## Layout

See [DESIGN.md §9](DESIGN.md#9-repository--service-structure).

## Operations

- [Windows installation & operations guide](docs/windows-service-guide.md) — install, schedule, monitor, troubleshoot.
