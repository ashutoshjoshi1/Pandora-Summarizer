# Install Pandora Fleet Monitoring on a Pandora Computer

**Read this first.** No coding knowledge needed. Total time on each
computer: about **10 minutes**.

At the end of this, the Pandora computer will automatically:

1. Read yesterday's Blick files every morning.
2. Build a summary of what happened (online status, warnings, errors,
   alignment health, etc.).
3. Upload the summary plus selected files to your team's Google Cloud
   Storage bucket so the dashboard can see this Pandora.

---

## What you bring with you to each Pandora computer

- [ ] **This folder**, copied onto a USB stick (or a network share you can
      reach from the Pandora computer).
- [ ] **One file from your team lead**: the GCS service-account key.
      It will be named something like `sa.json` or
      `pandora-edge-key.json`.
- [ ] The **Instrument ID** for this specific Pandora (e.g. `Pandora024`).
- [ ] The **location name** (e.g. `GSFC`).
- [ ] The **time zone** of this location (e.g. `America/New_York`).
- [ ] The **GCS bucket name** to upload into (e.g. `log_web`).
- [ ] A **list of the Blick folder paths** on this computer:
  - L0 folder (e.g. `C:\Blick\data\L0`)
  - alignment folder (e.g. `C:\Blick\data\alignments`)
  - oslog, fslog, pslog folders under `C:\Blick\log\`
  - figures folder under `C:\Blick\data\alignments\figures`

If you do not have a value for one of those, ask your team lead before you
start. Filling them in once correctly saves coming back later.

---

## Step 1 - Install Python on the Pandora computer

The Pandora computer probably does not have Python yet. We need it.

1. On the Pandora computer, open a web browser and go to:
   <https://www.python.org/downloads/windows/>
2. Click **"Download Windows installer (64-bit)"** under the latest
   Python 3.11, 3.12, or 3.13 release.
3. Run the installer.
4. **CRUCIAL**: tick the checkbox **"Add python.exe to PATH"** at the
   bottom of the very first installer screen, then click **"Install Now"**.
5. When it finishes, click **"Close"**.

**To check that Python was installed correctly**, press the Windows key,
type `cmd`, and press Enter. In the black window that opens, type:

```
python --version
```

and press Enter. You should see something like `Python 3.12.4`. If you see
`'python' is not recognized`, the PATH checkbox was not ticked - rerun the
Python installer and tick it.

Close the black window.

---

## Step 2 - Copy this folder to the Pandora computer

1. Plug your USB stick into the Pandora computer (or open the network
   share that has this folder).
2. Copy the entire `Pandora-Summarizer` folder to somewhere on the
   Pandora computer's hard drive. **A good place is:**

   ```
   C:\Users\Public\Pandora-Summarizer
   ```

   Anywhere works. After install we will copy what we need to a permanent
   location automatically.

---

## Step 3 - Drop in the GCS service-account key

1. On the Pandora computer, open **File Explorer**.
2. Go to `C:\ProgramData\`.
3. If a folder called `PandoraFleetMonitor` does **not** yet exist,
   create it (right-click -> New -> Folder -> name it
   `PandoraFleetMonitor`).
4. Copy the service-account JSON file from your USB stick into this folder.
5. Rename it to exactly `sa.json` so the final path is:

   ```
   C:\ProgramData\PandoraFleetMonitor\sa.json
   ```

> The `ProgramData` folder can be hidden by default. If you cannot see it,
> in File Explorer go to **View -> Show -> Hidden items** and tick it.

---

## Step 4 - Run the installer

1. Open the `Pandora-Summarizer` folder you copied in Step 2.
2. **Double-click** the file named:

   ```
   Run-Setup.bat
   ```

3. Windows will show a UAC prompt asking "Do you want to allow this app
   to make changes?". Click **Yes**.
4. A blue PowerShell window will open and start walking through the
   installation. It will print lines like:

   ```
   ==[ 1. Verify admin rights ]==
       OK: Running elevated as ...

   ==[ 2. Locate Python 3.11+ ]==
       OK: Found Python 3.12.4 at ...
   ```

   Just watch and let it run.

> **Heads up on first install:** the installer will backfill every day
> from **2026-01-01** through yesterday. On a fresh Pandora this can
> take a long time (often several hours, depending on file sizes and
> internet speed). Leave the window open until it prints
> *"Installer finished."* If you close it partway, just re-run
> `Run-Setup.bat` — days that already uploaded are skipped.
>
> If you need a different start date, run the installer from an admin
> PowerShell instead:
>
> ```powershell
> .\setup.ps1 -BackfillStart 2026-03-01
> ```
>
> Use `-SkipBackfill` to skip the historical sweep entirely.

### When the installer pauses to open Notepad

The installer will open `config.yaml` in Notepad. **Edit these fields**
to match this Pandora:

```yaml
instrument:
  id: Pandora024                  # <- change to this Pandora's ID
  display_name: Pandora024        # <- friendly name
  location_name: GSFC             # <- your site name
  timezone: America/New_York      # <- this site's time zone

paths:
  blick_root: C:\Blick            # <- if Blick is installed elsewhere, change all of these
  l0_dir: C:\Blick\data\L0
  alignment_dir: C:\Blick\data\alignments
  oslog_dir: C:\Blick\log\oslog
  fslog_dir: C:\Blick\log\fslog
  pslog_dir: C:\Blick\log\pslog
  figures_dir: C:\Blick\data\alignments\figures

gcs:
  bucket: log_web                 # <- the GCS bucket name from your team lead
  prefix: pandora-fleet-monitoring
  service_account_json: C:\ProgramData\PandoraFleetMonitor\sa.json

service:
  run_time_local: "06:00"         # <- when the daily run fires (24h, local time)
```

**To save your changes**: in Notepad, click **File -> Save**, then close
Notepad. The installer continues automatically once Notepad closes.

### If the installer pauses asking for sa.json

If you skipped Step 3, the installer will say:

```
WARN: Expected service-account file not found:
    C:\ProgramData\PandoraFleetMonitor\sa.json
```

Drop the JSON file at that exact path now (see Step 3), then press Enter
in the PowerShell window.

### End of installer

When everything succeeds, you will see a **green** summary block listing
where everything was installed. The very last line of the script is:

```
*** Installer finished. ***
```

Then `Press any key to continue . . .`. Press any key to close the window.

---

## Step 5 - Test it once, right now

1. In the same `Pandora-Summarizer` folder, **double-click**:

   ```
   Run-Pandora-Now.bat
   ```

2. It will run the pipeline immediately (not waiting for the 06:00 daily
   trigger). You should see lines like:

   ```
   INFO pandora_edge.orchestrator :: run finished:
       Pandora024 2026-05-12 status=COMPLETED attempt=1 score=95/GREEN
   ```

3. Press any key to close the window.

### What does success look like?

- The `status=COMPLETED` line above.
- A new file in your team's GCS bucket at:

  ```
  gs://<bucket>/pandora-fleet-monitoring/<your-instrument-id>/<yesterday's-date>/summary.json
  ```

  Ask your team lead to confirm they see this in the dashboard.

### What does failure look like?

- `status=FAILED` or `status=PARTIAL` in the output.
- An error like "no module named ..." or "schtasks failed".

If something is wrong, **copy the entire window contents** (right-click ->
Mark, drag to select all, Enter to copy) and send it to your team lead
along with this file:

```
C:\ProgramData\PandoraFleetMonitor\logs\pandora-edge.log
```

A `PARTIAL` result on the very first run is **normal** if Blick has not
yet produced yesterday's complete files. Tomorrow's automatic run will be
the real test.

---

## Step 6 - Confirm the daily schedule is in place

1. Press the Windows key, type `Task Scheduler`, press Enter.
2. In the left pane, click **"Task Scheduler Library"**.
3. In the middle pane, look for an entry named **`PandoraEdgeService`**.
4. You should see:
   - **Status:** Ready
   - **Triggers:** At 06:00 every day (or whatever time you set in the
     config).
   - **Last Run Time / Last Run Result:** populated after the first run.

If `PandoraEdgeService` is missing, the installer did not finish
successfully - rerun `Run-Setup.bat` from the start.

You can close Task Scheduler.

---

## Step 7 - Move on to the next Pandora computer

That's it for this one. The daily schedule will run on its own from now
on.

Repeat Steps 1 through 6 on every other Pandora computer using its own
instrument ID, location, time zone, and the same `sa.json` key.

---

## If something is wrong

### "I don't see PandoraEdgeService in Task Scheduler"

The installer did not finish. Rerun `Run-Setup.bat`. If it fails again,
copy the entire PowerShell window output and send it to your team lead.

### "Run-Pandora-Now.bat says 'The service has not been installed yet'"

You skipped Step 4. Run `Run-Setup.bat` first.

### "PowerShell window flashes open then closes"

You may have double-clicked `setup.ps1` directly instead of
`Run-Setup.bat`. Always use the `.bat` file - it handles admin elevation
and execution policy for you.

### "Python is not recognized"

Reinstall Python from python.org and tick **"Add python.exe to PATH"**.
Then rerun `Run-Setup.bat`.

### "The installer says it can't find sa.json"

Make sure the file is at exactly:

```
C:\ProgramData\PandoraFleetMonitor\sa.json
```

(not in a subfolder, not with a different name, not on the USB stick.)

### Need to uninstall

Double-click **`Run-Uninstall.bat`**. By default it leaves logs and
history alone. To wipe everything, open PowerShell as admin and run:

```powershell
.\teardown.ps1 -RemoveAll
```

---

## Quick reference card (print this)

| Task                              | Double-click            |
|-----------------------------------|-------------------------|
| First-time install on this PC     | `Run-Setup.bat`         |
| Trigger the pipeline immediately  | `Run-Pandora-Now.bat`   |
| Remove the daily schedule         | `Run-Uninstall.bat`     |

| What                              | Where                                                      |
|-----------------------------------|------------------------------------------------------------|
| Service-account key               | `C:\ProgramData\PandoraFleetMonitor\sa.json`               |
| Config                            | `C:\ProgramData\PandoraFleetMonitor\config.yaml`           |
| Daily log                         | `C:\ProgramData\PandoraFleetMonitor\logs\pandora-edge.log` |
| Scheduled task name               | `PandoraEdgeService` in Task Scheduler                     |
| GCS upload location               | `gs://<bucket>/pandora-fleet-monitoring/<id>/<date>/`      |
