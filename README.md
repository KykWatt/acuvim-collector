# Acuvim Collector

This project retrieves historical logs from an Acuvim CL meter and writes them to a TSV-formatted CSV file. It can optionally check meter/system time drift and sync the meter clock before collecting data.

## Quickstart
1. Install dependencies:
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

### Time sync-only shortcut
If you just want to check/sync the meter clock without changing the collection window, reuse your normal command and add
`--sync-time` (optionally adjust `--allowed-drift`, default 60 seconds). Example:

```bash
python main.py --host 192.168.68.43 --unit 1 --serial CLD54061244 --mode last --minutes 5 --output test.tsv --sync-time --verbose
```

In the output you should see a drift line (meter vs system) and either a “syncing meter time” message or “drift within
limits → no sync required.”

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
