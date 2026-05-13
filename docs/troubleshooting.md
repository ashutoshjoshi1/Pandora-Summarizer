# Troubleshooting

## Symptom → checklist

### Dashboard shows a unit as OFFLINE

1. Check `summary.status.offline_reason`.
2. SSH / RDP into the Pandora computer and look at
   `C:\ProgramData\PandoraFleetMonitor\logs\pandora-edge.log` — any errors?
3. Run `pandora-edge run --config <path>` interactively. If it succeeds, the
   scheduled task may have been disabled or the service account JSON moved.

### Dashboard shows a unit as PARTIAL

`summary.status.missing_expected_files` lists what wasn't found. Common cases:

| Missing       | Cause                                                       |
|---------------|-------------------------------------------------------------|
| `L0_or_partial_L0` | Blick didn't finish writing yesterday's L0; check Blick. |
| `logs`        | Wrong `oslog_dir` / `fslog_dir` / `pslog_dir` in config.    |

### `latest_weighting_factor` < 500 / Alignment WARNING/CRITICAL

`summary.alignment.alignment_comment` will read:

> "Scans are not good. Weighting factor for this routine is below 500. Check alignment."

This typically means the alignment routine ran but the FS scan returned a low
weighting. Action: re-run the alignment routine on the instrument; the next
daily summary will reflect the new value.

### Upload PARTIAL / FAILED

1. Open `summary.upload.failed_uploads` — each entry has the GCS object path
   and the error message.
2. Common causes: expired service account, bucket name typo, network outage,
   permissions changed on the bucket.
3. `summary.upload.retry_count` shows how many tenacity retries happened.
4. After fixing the underlying issue, re-run:
   ```
   pandora-edge run --date <YYYY-MM-DD> --config <path>
   ```
   Idempotency will only re-upload missing / failed objects.

### Edge service fails to start the scheduled task

```
schtasks.exe not found - are you on Windows?
```

You're running the CLI on macOS / Linux. The `install-task` /
`uninstall-task` commands are Windows-only.

### "File has not been read yet" / encoding errors in parsers

Parsers open files with `errors="replace"` so non-UTF8 bytes won't crash the
run. If you still see issues, check that the file isn't being held open by
Blick (the stability gate should normally catch this — see
`service.file_stability_seconds`).

### Files keep getting flagged in `summary.files.skipped_unstable`

A file's mtime is too recent. Possible causes:

- Blick is actively writing them (correct behavior to skip).
- System clock is off — verify `w32tm /query /status`.
- `service.file_stability_seconds` is set too aggressively (default 60 is safe).

### Dashboard is slow

The remote GCS reader caches list / read calls for `PANDORA_DASH_CACHE_SECONDS`
(default 60s). Lower it for fresher data, raise it for fewer GCS calls. Lots
of instruments → consider running the dashboard alongside (same region as) the
bucket.

### Pydantic validation errors when loading config

`pandora-edge validate-config` prints the offending field path. The most
common cases:

- `paths.l0_dir` does not exist as a directory at config load time — the
  current implementation only type-checks the path, so this is a runtime
  symptom (you'll see `files.l0.status = MISSING`).
- `service.retry_attempts < 1` — must be ≥ 1.

### `state.db` is locked

The edge service uses SQLite in single-process mode. If another `pandora-edge
run` is already running, wait for it to finish. If the lock persists after
crashes:

```powershell
del C:\ProgramData\PandoraFleetMonitor\state.db-journal
```

The main `.db` file is safe to keep — it's append-only run history.

## When in doubt

Three artifacts together usually answer "what happened on date X":

1. `C:\ProgramData\PandoraFleetMonitor\logs\pandora-edge.log` (latest run)
2. `gs://<bucket>/.../<id>/<date>/summary.json` (`service_status.errors`)
3. `gs://<bucket>/.../<id>/<date>/manifest.json` (what actually uploaded)

If all three agree, the issue is upstream (Blick, network, GCS). If they
disagree, file a bug — it's a service issue.
