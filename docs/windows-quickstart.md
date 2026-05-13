# Windows quickstart

Drop the package on a Pandora computer and run **one** script. The whole
installation takes about 2 minutes.

## What you need before you start

1. The Pandora computer is on Windows 10 or newer.
2. **Python 3.11 or newer** is installed system-wide.
   - Get it from <https://www.python.org/downloads/>.
   - Tick **"Add python.exe to PATH"** in the installer.
3. You can open **PowerShell as Administrator** on this machine.
4. You have the **GCS service-account JSON** file for the writer account
   (the one with `storage.objectAdmin` on your bucket).

## Step 1 - copy the package

Copy this entire folder onto the Pandora computer. Anywhere works (e.g. a
USB stick to `C:\Users\Public\Pandora-Summarizer\`). The installer will move
files into a permanent location for you.

## Step 2 - run the installer

1. Open **PowerShell as Administrator** (right-click PowerShell -> *Run as
   administrator*).
2. `cd` into the folder you just copied:

   ```powershell
   cd C:\Users\Public\Pandora-Summarizer
   ```

3. The first time on a fresh machine you may need to allow script execution
   for this PowerShell session only:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

4. Run the installer:

   ```powershell
   .\setup.ps1
   ```

The script will walk you through every step and tell you exactly what it is
doing. When it pauses to open `config.yaml` in Notepad, edit:

- `instrument.id` (e.g. `Pandora024`)
- `instrument.display_name`, `instrument.location_name`, `instrument.timezone`
- `paths.*` - point them at this machine's actual Blick folders
- `gcs.bucket` - your GCS bucket name
- `service.run_time_local` - daily run time in local time, e.g. `"06:00"`

Save and close Notepad. The script continues automatically.

When it pauses for `sa.json`, drop the service-account key here:

```
C:\ProgramData\PandoraFleetMonitor\sa.json
```

Then press Enter.

That's it. The script:

- Detects your Python, creates a venv, installs the package.
- Validates your config and runs one dry-run end-to-end.
- Registers the daily Scheduled Task named **`PandoraEdgeService`**.
- Tightens the ACL on `sa.json` to SYSTEM + Administrators.

## Step 3 - verify

Still in the elevated PowerShell:

```powershell
# the task is registered, next-run time is shown
schtasks /Query /TN PandoraEdgeService /V /FO LIST

# tail the log
Get-Content C:\ProgramData\PandoraFleetMonitor\logs\pandora-edge.log -Tail 40
```

To trigger a run **right now** without waiting for the daily time:

```powershell
& 'C:\ProgramData\PandoraFleetMonitor\.venv\Scripts\pandora-edge.exe' `
    run --config C:\ProgramData\PandoraFleetMonitor\config.yaml
```

You can also right-click the task in Task Scheduler -> **Run**.

After it completes, the new `summary.json` will be at:

```
gs://<bucket>/pandora-fleet-monitoring/<instrument_id>/<date>/summary.json
```

## Common mistakes

| Symptom                                                | Fix                                                                                       |
|--------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `setup.ps1 : File cannot be loaded...not digitally signed` | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.                |
| Installer says "must be run elevated"                  | Right-click PowerShell -> *Run as administrator*. Not just any PowerShell.                |
| "Could not find Python 3.11 or newer"                  | Install Python from python.org, **with** *Add to PATH*. Or pass `-PythonExe "C:\path\to\python.exe"`. |
| Notepad opens but task isn't registered after          | You probably closed PowerShell before the script finished. Re-run `setup.ps1` - it's idempotent. |
| Task is there but nothing runs at 06:00                | The local clock is wrong, or `Action` references a missing path. Check `schtasks /Query /TN PandoraEdgeService /V /FO LIST`. |

## Uninstall

```powershell
# remove only the scheduled task, keep logs and state
.\teardown.ps1

# nuke everything
.\teardown.ps1 -RemoveAll
```

## Re-run later (after fixing config)

`setup.ps1` is idempotent. Edit `config.yaml`, then run `setup.ps1` again -
it will skip the venv if it exists, refresh the package, re-validate, and
re-register the task with the latest run time.

## Where everything lives after install

```
C:\ProgramData\PandoraFleetMonitor\
    app\                   <- the Python package (mirror of this repo)
    .venv\                 <- Python virtualenv
    config.yaml            <- edited config
    sa.json                <- service-account key (ACL: SYSTEM + Admins)
    state.db               <- SQLite run history
    logs\pandora-edge.log  <- rotating log
    staging\               <- per-run staging area before upload
```
