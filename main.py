import argparse
import csv
import math
-from datetime import datetime, timedelta
+from datetime import datetime
from pathlib import Path
from typing import Optional

@ @ -75, 6 +75, 9 @ @


def main() -> None:
    with AcuvimClient(args.host, port=args.port, unit=args.unit) as cli:
        _log("Connected.")


+
if args.sync_time:
    +            _sync_time_if_needed(cli, allowed_drift=args.allowed_drift)
+
# 1) Status
status = cli.read_log_status()
if status.record_size_bytes != 28:


    @ @-137

, 9 + 140, 43 @ @


def _parse_args() -> argparse.Namespace:
    p.add_argument("--minutes", type=int, default=60)

    p.add_argument("--output", type=Path, help="Optional explicit CSV filename")


+    p.add_argument(
    +        "--sync-time",
    +        action = "store_true",
+        help = "Check meter/system drift and update meter time when drift exceeds allowed seconds",
+    )
+    p.add_argument(
    +        "--allowed-drift",
    +        type = int,
+        default = 60,
+        help = "Maximum allowed drift in seconds before syncing meter time",
+    )

return p.parse_args()

+


def _sync_time_if_needed(cli: AcuvimClient, allowed_drift: int) -> float:
    +    meter_time = cli.read_meter_time()


+    system_time = datetime.now().replace(microsecond=0)
+
+    drift_seconds = abs((system_time - meter_time).total_seconds())
+    _log(
    +        "Time drift check: meter=%s, system=%s, drift=%.1fs"
    + % (meter_time, system_time, drift_seconds)
+    )
+
+
if drift_seconds > allowed_drift:
    +        _log(
        +            f"Drift {drift_seconds:.1f}s exceeds allowed {allowed_drift}s → syncing meter time"
        +)
+        cli.write_meter_time(system_time)
+        new_time = cli.read_meter_time()
+        _log(f"Meter time after sync: {new_time}")
+ else:
+        _log("Drift within limits → no sync required.")
+
+
return drift_seconds
+
+
if __name__ == "__main__":
    main()