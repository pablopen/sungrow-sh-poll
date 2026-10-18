# SPDX-License-Identifier: GPL-3.0-or-later
"""CSV logging of decoded poll values for later analysis."""

import csv
import json
from pathlib import Path

from .registers import REGISTERS

DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "data"

# Device identity: cannot change while polling, so logged once per daily file
# in a .meta.json sidecar instead of on every row.
STATIC_FIELDS = ["serial_number", "arm_version", "dsp_version",
                 "device_type_code", "nominal_power", "output_type_raw"]

VALUE_FIELDS = [k for k in REGISTERS if k not in STATIC_FIELDS]


class PollLog:
    """Daily-rotating CSV of the decoded state, one row per successful poll.

    Each row carries an absolute wall-clock timestamp: the poll interval is
    adjustable at runtime (0.125-16s), so time is never reconstructible from
    row position. Static device identity goes to <prefix>-YYYY-MM-DD.meta.json.

    Defaults log the Sungrow register set as poll-*.csv; other devices pass
    their own prefix, value field names, and static (per-day sidecar) fields.
    """

    def __init__(self, log_dir=DEFAULT_LOG_DIR, prefix="poll",
                 fields=VALUE_FIELDS, static_fields=STATIC_FIELDS):
        self._dir = Path(log_dir)
        self._prefix = prefix
        self._static_fields = static_fields
        self._log_fields = ["ts", "interval_s", "cycle_ms", *fields]
        self._file = None
        self._writer = None
        self._day = None
        self._meta_written = False

    def _open_day(self, day):
        self.close()
        self._dir.mkdir(exist_ok=True)
        path = self._dir / f"{self._prefix}-{day}.csv"
        header = ",".join(self._log_fields)
        if path.exists() and path.stat().st_size > 0:
            with open(path) as f:
                existing = f.readline().rstrip("\n")
            if existing != header:
                # schema changed since this file was started: archive, don't mix
                path.rename(path.with_name(f"{self._prefix}-{day}.old-schema.csv"))
        fresh = not path.exists() or path.stat().st_size == 0
        self._file = open(path, "a", newline="")
        self._writer = csv.writer(self._file)
        if fresh:
            self._writer.writerow(self._log_fields)
        self._day = day
        self._meta_written = (self._dir / f"{self._prefix}-{day}.meta.json").exists()

    def _write_meta(self, now, values):
        static = {k: values.get(k) for k in self._static_fields}
        if all(v is None for v in static.values()):
            return  # first read failed; retry on a later row
        meta = {"started": now.isoformat(timespec="seconds"), **static}
        with open(self._dir / f"{self._prefix}-{self._day}.meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        self._meta_written = True

    def write(self, now, interval, cycle_ms, values):
        """Append one row. `values` is a {register_name: value} dict; missing
        or None entries are logged as empty cells."""
        day = now.strftime("%Y-%m-%d")
        if day != self._day:  # first write, or crossed midnight
            self._open_day(day)
        if not self._meta_written:
            self._write_meta(now, values)
        row = [now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}",
               f"{interval:g}", f"{cycle_ms:.0f}"]
        row += ["" if values.get(k) is None else values[k] for k in self._log_fields[3:]]
        self._writer.writerow(row)
        self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
