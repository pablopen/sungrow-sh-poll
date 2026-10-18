# SPDX-License-Identifier: GPL-3.0-or-later
"""Live console dashboard for a Sungrow hybrid inverter.

Polls the 5 fast input-register blocks on one persistent connection
(~115ms/cycle measured) and redraws the panel in place.
"""

import argparse
import csv
import logging
import os
import select
import sys
import termios
import time
import tty
from datetime import datetime
from pathlib import Path

from pymodbus.exceptions import ModbusException

from sungrow import (
    INPUT_BLOCKS,
    SETTINGS_BLOCKS,
    PollLog,
    SungrowClient,
    decode_power_flow,
    device_map,
    ems_mode_map,
    enabled_map,
    fmt,
    running_state_map,
)
from sungrow.registers import REGISTERS

SETTINGS_KEYS = [name for name, (block, *_) in REGISTERS.items() if block in SETTINGS_BLOCKS]

HIDE_CURSOR, SHOW_CURSOR = "\x1b[?25l", "\x1b[?25h"
# Wrapping a too-long panel line onto a second row breaks the fixed-height
# in-place redraw; disable terminal autowrap (clip instead) while running.
WRAP_OFF, WRAP_ON = "\x1b[?7l", "\x1b[?7h"

parser = argparse.ArgumentParser(description="Sungrow inverter live dashboard")
parser.add_argument("--host", default=os.environ.get("HOST"),
                    help="inverter IP address (default: HOST from .env)")
parser.add_argument("--interval", type=float, default=1.0,
                    help="seconds between polls (default 1; adjustable at runtime with +/-)")
parser.add_argument("--count", type=int, default=0, help="stop after N polls (0 = run forever)")
parser.add_argument(
    "--settings-every", type=int, default=0, metavar="N",
    help="refresh EMS settings every N polls (slow holding registers; default 0 = never)",
)
parser.add_argument(
    "--no-log", dest="log", action="store_false",
    help="disable the default logging of every poll to data/poll-YYYY-MM-DD.csv",
)
args = parser.parse_args()
if not args.host:
    parser.error("--host is required (or set HOST in .env)")

# pymodbus logs connection failures to stderr, which would corrupt the
# in-place panel; the status line already reports them.
logging.getLogger("pymodbus").setLevel(logging.CRITICAL)


HIGHLIGHT, RESET = "\x1b[1;33m", "\x1b[0m"


def battery_eta(v):
    """ETA to 100% while charging / 0% while discharging at the current rate.
    battery_power is negative while charging on this device (verified live)."""
    p, soc, cap = v["battery_power"], v["battery_soc"], v["battery_capacity"]
    if None in (p, soc, cap) or p == 0:
        return ""
    if p < 0:
        remaining_kwh = (100.0 - soc) / 100.0 * cap  # to 100%
    else:
        remaining_kwh = soc / 100.0 * cap            # to 0%
    hours = remaining_kwh / (abs(p) / 1000.0)
    if hours > 48:  # trickle rates give meaningless multi-day ETAs
        return ""
    return f"{int(hours)}h{int(hours % 1 * 60):02d}m"


def build_panel(v, s, changed, directions, eta, status):
    """v: live input values, s: cached settings, changed: value names that
    differ from the previous cycle (highlighted), directions: name ->
    (arrow, delta) of the last observed change (persists across cycles),
    eta: cached battery ETA text, status: bottom line."""

    def cv(name, unit="", decimals=1, width=0):
        text = fmt(v[name], unit, decimals)
        if width:
            text = f"{text:>{width}}"
        arrow, delta = directions.get(name, ("", None))
        marker = f"{arrow}{abs(delta):.{decimals}f}" if delta is not None else ""
        text += f" {marker:<6}"
        return f"{HIGHLIGHT}{text}{RESET}" if name in changed else text

    def balance():
        # Derived: load - AC out = what the grid covers (or absorbs).
        # Values inside the measured ±40W noise floor read as balanced.
        b = v.get("grid_balance")
        if b is None:
            text = "balance N/A"
        elif b > 0:
            text = f"from grid {b:.0f} W"
        elif b < 0:
            text = f"to grid {-b:.0f} W"
        else:
            text = "balanced 0 W"
        arrow, delta = directions.get("grid_balance", ("", None))
        marker = f"{arrow}{abs(delta):.0f}" if delta is not None else ""
        text = f"{text:<15} {marker:<6}"
        return f"{HIGHLIGHT}{text}{RESET}" if "grid_balance" in changed else text

    def grid_flow():
        # export_power (13010) is signed: positive = exporting, negative =
        # importing. Label by sign and show the magnitude.
        ep = v["export_power"]
        word = "import" if ep is not None and ep < 0 else "export"
        value = fmt(abs(ep) if ep is not None else None, "W", 0)
        arrow, delta = directions.get("export_power", ("", None))
        marker = f"{arrow}{abs(delta):.0f}" if delta is not None else ""
        text = f"{word} {value} {marker:<6}"
        return f"{HIGHLIGHT}{text}{RESET}" if "export_power" in changed else text

    model = device_map.get(v.get("device_type_code"), "SUNGROW")
    header = f" {model} · SN {v.get('serial_number') or 'N/A'} · {fmt(v.get('nominal_power'), 'kW')} nominal"

    if s:
        soc_range = f"SoC {fmt(s['min_soc'], '')}-{fmt(s['max_soc'], '%')}"
        limit = f"export limit {fmt(s['export_limit'], 'kW', 3)} ({enabled_map.get(s['export_limit_mode'], 'N/A')})"
        ems = f"{ems_mode_map.get(s['ems_mode'], 'N/A')} · {soc_range} · {limit}"
    elif args.settings_every:
        ems = "(waiting for first read)"
    else:
        ems = "(not read; use --settings-every N)"

    state = running_state_map.get(v.get("running_state"), "N/A")
    if {"running_state", "power_flow_state"} & changed:
        state_text = f"{HIGHLIGHT}{state} · {decode_power_flow(v.get('power_flow_state'))}{RESET}"
    else:
        state_text = f"{state} · {decode_power_flow(v.get('power_flow_state'))}"

    return [
        header,
        " " + "─" * 74,
        f" PV      {cv('pv_total', 'W', 0, 8)}  MPPT1 {cv('mppt1_voltage', 'V')} / {cv('mppt1_current', 'A')}  MPPT2 {cv('mppt2_voltage', 'V')} / {cv('mppt2_current', 'A')}",
        f" AC out  {cv('total_active_power', 'W', 0, 8)}  {cv('phase_a_voltage', 'V')}  {cv('phase_a_current', 'A')}  {cv('grid_frequency', 'Hz', 2)}  PF {cv('power_factor', '', 3)}",
        f" Load    {cv('load_power', 'W', 0, 8)}  grid {grid_flow()}  {balance()}  import today {cv('daily_import_energy', 'kWh')}",
        f" Battery {cv('battery_power', 'W', 0, 8)}  SOC {cv('battery_soc', '%')}{f' ETA {eta}' if eta else '':<11} SOH {cv('battery_soh', '%')}  {cv('battery_temp', '°C')}  {cv('battery_voltage', 'V')}",
        f" Today   PV {cv('daily_pv_gen', 'kWh')}  import {cv('daily_import_energy', 'kWh')}  export {cv('daily_export_energy', 'kWh')}  self {cv('self_consumption', '%')}",
        f" State   {state_text}",
        f" EMS     {ems}",
        f" {status}",
    ]


def render(lines, in_place):
    if in_place:
        sys.stdout.write(f"\x1b[{len(lines)}A")
    for line in lines:
        sys.stdout.write(line + "\x1b[K\n")
    sys.stdout.flush()


# Values shown live in the panel; changes are detected (and counted) on these.
DISPLAYED = {
    "pv_total", "mppt1_voltage", "mppt1_current", "mppt2_voltage", "mppt2_current",
    "total_active_power", "phase_a_voltage", "phase_a_current", "grid_frequency", "power_factor",
    "load_power", "export_power", "grid_balance", "daily_import_energy",
    "battery_power", "battery_soc", "battery_soh", "battery_temp", "battery_voltage",
    "daily_pv_gen", "daily_export_energy", "self_consumption",
    "running_state", "power_flow_state",
}

poll_log = PollLog() if args.log else None
client = SungrowClient(args.host)
connected = False
values = {name: None for name in REGISTERS} | {"grid_balance": None}
prev_values = None
changed = set()
directions = {}
settings = {}
eta = ""
drawn = False
polls = 0
running = True

# Runtime keys need raw keypresses (no Enter); only when attached to a tty.
interactive = sys.stdin.isatty()
saved_term = termios.tcgetattr(sys.stdin) if interactive else None
if interactive:
    tty.setcbreak(sys.stdin.fileno())


def wait(seconds):
    """Sleep up to `seconds`; in a tty, react to +/- (interval) and q (quit)
    immediately instead of waiting out the full sleep."""
    global running
    end = time.perf_counter() + seconds
    while running:
        remaining = end - time.perf_counter()
        if remaining <= 0:
            return
        if not interactive:
            time.sleep(remaining)
            return
        ready, _, _ = select.select([sys.stdin], [], [], remaining)
        if not ready:
            return
        key = sys.stdin.read(1)
        if key == "+":
            args.interval = min(16.0, args.interval * 2)
            return  # re-render now so the new interval shows immediately
        if key == "-":
            args.interval = max(0.125, args.interval / 2)
            return
        if key == "q":
            running = False


sys.stdout.write(HIDE_CURSOR + WRAP_OFF)
try:
    while running and (args.count == 0 or polls < args.count):
        t0 = time.perf_counter()
        try:
            if not connected:
                if not client.connect():
                    raise ConnectionError("connect failed")
                connected = True

            read_settings = args.settings_every and polls % args.settings_every == 0
            blocks = INPUT_BLOCKS + SETTINGS_BLOCKS if read_settings else INPUT_BLOCKS
            values = client.read(blocks)
            if None not in (values["load_power"], values["total_active_power"]):
                values["grid_balance"] = values["load_power"] - values["total_active_power"]
            else:
                values["grid_balance"] = None
            if read_settings:
                settings = {k: values[k] for k in SETTINGS_KEYS}

            if prev_values is None:
                changed = set()
            else:
                changed = {k for k in DISPLAYED if values[k] != prev_values[k]}
                for k in changed:
                    old, new = prev_values[k], values[k]
                    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                        directions[k] = ("↑" if new > old else "↓", new - old)
            if prev_values is None or {"battery_power", "battery_soc"} & changed:
                eta = battery_eta(values)
            prev_values = values

            cycle_ms = (time.perf_counter() - t0) * 1000
            polls += 1
            if poll_log:
                # settings cache fills the columns of blocks not read this cycle
                poll_log.write(datetime.now(), args.interval, cycle_ms,
                               {**values, **settings})
            status = (f"{datetime.now():%H:%M:%S} · every {args.interval:g}s · cycle {cycle_ms:3.0f} ms · "
                      f"poll {polls} · {len(changed)} changed · OK"
                      + (" · [+/- interval, q quit]" if interactive else ""))
            render(build_panel(values, settings, changed, directions, eta, status), drawn)
            drawn = True
        except (ModbusException, OSError, ConnectionError) as e:
            client.close()
            connected = False
            status = f"{datetime.now():%H:%M:%S} · connection lost ({type(e).__name__}) · reconnecting…"
            render(build_panel(values, settings, set(), directions, eta, status), drawn)
            drawn = True
            wait(1)
            continue

        wait(max(0.0, args.interval - (time.perf_counter() - t0)))
except KeyboardInterrupt:
    pass
finally:
    if saved_term is not None:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, saved_term)
    sys.stdout.write(SHOW_CURSOR + WRAP_ON)
    sys.stdout.flush()
    if poll_log:
        poll_log.close()
    client.close()
