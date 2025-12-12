# Acuvim Collector

This project retrieves historical logs from an Acuvim CL meter and writes them to a TSV-formatted CSV file. It can optionally check meter/system time drift and sync the meter clock before collecting data.

## Quickstart
1. Install dependencies (SQLAlchemy is pinned for Python 3.13 compatibility; reinstall if you had an older env):
   ```bash
   pip install -r requirements.txt
   ```
2. Collect the last 60 minutes of data (default):
   ```bash
   python main.py --host <METER_IP> --unit <UNIT_ID> --serial <SERIAL>
   ```
3. Collect all available data:
   ```bash
   python main.py --host <METER_IP> --unit <UNIT_ID> --serial <SERIAL> --mode all
   ```
4. Check and optionally sync meter time (drift > 60s by default):
   ```bash
   python main.py --host <METER_IP> --unit <UNIT_ID> --serial <SERIAL> --sync-time
   ```
   Add `--verbose` to see the drift measurement, sync decision, and log status details in the terminal.
   To also run collection with drift checking in one command, append `--sync-time` (optionally `--allowed-drift 60`) and `--verbose` to any run.

### Time sync-only shortcut
If you just want to check/sync the meter clock without changing the collection window, reuse your normal command and add
`--sync-time` (optionally adjust `--allowed-drift`, default 60 seconds). Example:

```bash
python main.py --host 192.168.68.43 --unit 1 --serial CLD54061244 --mode last --minutes 5 --output test.tsv --sync-time --verbose
```

In the output you should see a drift line (meter vs system) and either a “syncing meter time” message or “drift within
limits → no sync required.”

## Meter management UI (FastAPI)
You can manage a fleet of meters using the bundled FastAPI UI under `meter_ui/`. It stores meters in `meters.db` (SQLite) and lets you add/edit/delete meters, test Modbus reachability, and view meter time.

1) Install dependencies (already covered in the main requirements):
   ```bash
   pip install -r requirements.txt
   ```

2) Start the UI locally:
   ```bash
   uvicorn meter_ui.main:app --reload --host 0.0.0.0 --port 8000
   ```

3) Open http://localhost:8000 in your browser.

4) Add meters with serial/IP/unit/model/site info. The “Test Device” button will attempt to read the meter time registers (0x1040–0x1045) to confirm connectivity.

Database fields include `serial_number`, `ip_address`, `unit_id`, `enabled`, `last_collected`, `last_timesync`, `last_drift_seconds`, `last_record_index`, and `output_folder` so the collector service can resume from the last pointer per meter.

If you hit a SQLAlchemy `TypingOnly` assertion on Python 3.13, reinstall with the pinned dependencies and confirm versions:

```bash
pip install --upgrade --force-reinstall -r requirements.txt
python scripts/check_env_versions.py
```

SQLAlchemy should report `>=2.0.36` and `typing_extensions` should be present.

## Verify your local code matches this repo (PyCharm or terminal)

1. In the project root, run `git status`. A clean tree means your files match this repo snapshot.
2. If you suspect drift, run `git fetch` and compare (`git diff origin/work...`) or `git pull` to update.
3. Open `requirements.txt` to confirm the SQLAlchemy pin (`>=2.0.36,<3.0.0`) and `typing_extensions` entry.
4. If PyCharm uses its own virtualenv, re-run `pip install -r requirements.txt` inside that venv so dependencies align.

## Pushing to your Git remote
This repository currently has no remote configured. To push your work to GitHub or another server:
1. Add your remote URL:
   ```bash
   git remote add origin <YOUR-REPO-URL>
   ```
2. Verify it is set:
   ```bash
   git remote -v
   ```
3. Push the current branch (sets upstream the first time):
   ```bash
   git push -u origin work
   ```
After the upstream is set, subsequent pushes can be done with:
```bash
git push
```

## Editing files in this environment
If you want to make changes directly inside this workspace (without a GUI IDE):

1. Open a file with a terminal editor:
   * Nano: `nano <file>` (easy mode, use `Ctrl+O` to save, `Ctrl+X` to exit)
   * Vim: `vim <file>` (powerful but has a learning curve)
2. Check what changed:
   ```bash
   git status
   git diff
   ```
3. Stage and commit your changes:
   ```bash
   git add <file(s)>
   git commit -m "Your message"
   ```
4. Push to your remote (once a remote is configured):
   ```bash
   git push
   ```

If you prefer a graphical editor, open this folder in VS Code, PyCharm, or another IDE on your machine and work normally; the Git co
mmands above still apply for committing and pushing.

## Viewing the full `acuvim.py` source
If your terminal or tooling truncates the `acuvim.py` file, print it with line numbers in manageable chunks:

```bash
cd /workspace/acuvim-collector
sed -n '1,400p' acuvim.py | nl -ba
```

Adjust the `1,400` range as needed (e.g., `401,800`) to view later sections.
