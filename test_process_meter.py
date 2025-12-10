# test_process_meter.py
#
# Stable tester with schema debugging:
#  - Verifies DB exists
#  - Opens ONE shared connection
#  - Prints actual DB schema (names + types)
#  - Loads first enabled meter
#  - Runs process_meter()
#  - Shows final CSV path or error

import os
from collector.db import open_db, get_enabled_meters
from collector.process_meter import process_meter


# -------------------------------------------------------------------
# Your REAL DB path (absolute path prevents PyCharm confusion)
# -------------------------------------------------------------------
DB_PATH = r"C:\Users\JohannBeyers\PycharmProjects\vuwatt_meter_ui\meters.db"


# -------------------------------------------------------------------
# Start-up checks
# -------------------------------------------------------------------
print(f"Opening DB: {DB_PATH}")
print("Absolute path:", os.path.abspath(DB_PATH))
print("DB exists on disk:", os.path.exists(DB_PATH))

if not os.path.exists(DB_PATH):
    print("\n❌ ERROR: DB file does not exist at this location!")
    print("Fix DB_PATH and try again.\n")
    raise SystemExit(1)


# -------------------------------------------------------------------
# Open *one* connection for the entire test
# -------------------------------------------------------------------
conn = open_db(DB_PATH)

# -------------------------------------------------------------------
# Show schema in full detail
# -------------------------------------------------------------------
cur = conn.execute("PRAGMA table_info(meters)")
rows = cur.fetchall()

print("\nDB Columns:")
for col in rows:
    print(f" - cid={col[0]} | name={col[1]} | type={col[2]} | notnull={col[3]} | dflt={col[4]} | pk={col[5]}")

# If the two required fields are missing, we know immediately.
print("\nSchema check:")
needed = {"last_record_index", "output_folder"}
existing = {col[1] for col in rows}
missing = needed - existing
if missing:
    print(f"❌ Missing required columns: {missing}")
else:
    print("✔ All required columns exist!")


# -------------------------------------------------------------------
# Main test logic
# -------------------------------------------------------------------
def main():
    print("\n========== TESTING process_meter() ==========\n")

    meters = get_enabled_meters(conn)

    if not meters:
        print("❌ No enabled meters found in SQLite!")
        return

    meter = meters[0]
    print(f"Testing meter: {meter.serial_number} @ {meter.ip_address}")

    try:
        csv_path = process_meter(meter, conn)
    except Exception as e:
        print("\n❌ ERROR during process_meter():")
        print(e)
        return

    print("\n========== RESULT ==========")
    if csv_path:
        print(f"CSV created: {csv_path}")
    else:
        print("No new data or process failed.")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
