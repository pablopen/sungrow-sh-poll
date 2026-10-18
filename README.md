# sungrow-sh-poll

Live terminal dashboard and one-shot register dump for Sungrow SH hybrid
inverters (SHx.0RS / SHx.0RT) over Modbus TCP. No cloud, no iSolarCloud
account: it talks to the inverter's WiNet/LAN port directly.

```
 SH5.0RS · SN XXXXXXXXXXX · 5.0 kW nominal
 ──────────────────────────────────────────────────────────────────────────
 PV        2840 W ↑35     MPPT1 312.4 V ↑0.8   / 5.2 A ↑0.1    MPPT2 298.7 V        / 4.1 A
 AC out    1920 W ↑35     231.6 V         8.3 A         50.01 Hz         PF 0.999
 Load      1180 W         grid export 740 W ↑35     to grid 740 W   ↓35     import today 0.3 kWh
 Battery   -890 W         SOC 71.4 % ↑0.1   ETA 1h38m  SOH 100.0 %         24.5 °C         105.8 V
 Today   PV 11.2 kWh ↑0.1    import 0.3 kWh         export 4.6 kWh         self 58.9 %
 State   Running · PV generating, Battery charging, Exporting to grid
 EMS     Self-consumption · SoC 0.0-100.0 % · export limit 5.000 kW (Disabled)
 11:42:07 · every 1s · cycle 118 ms · poll 1532 · 9 changed · OK · [+/- interval, q quit]
```

## Why

The official app and iSolarCloud show the inverter with a delay of minutes and
hide most of what it measures. These scripts read the inverter once a second on
the LAN, which is what I use to watch the house in real time, to verify what the
registers really contain, and to measure how the device behaves (read sizes,
timings, signs, noise floor). That knowledge can be used to build or improve
integrations with home automation systems: every register in `registers.py`
has been checked against a live unit, and the behaviour notes below say what
the documentation does not.

## What is in the box

- `poll.py`: redraws a fixed panel in place every second (adjustable at runtime
  with `+` / `-`, `q` quits). Changed values are highlighted and keep an
  arrow with the last delta. Shows PV, AC, load, grid import/export, battery
  with an ETA to full/empty, daily counters, running state, and optionally the
  EMS settings. Every poll is appended to a daily CSV under `data/`.
- `dump.py`: prints every decoded register once, grouped by section. Add
  `--settings` to also read the inverter clock and EMS settings (holding
  registers, which are 10 to 20 times slower on this device).
- `sungrow/`: the small library both scripts use. `registers.py` is the
  register map and enum tables, `client.py` the block reader and decoders,
  `logger.py` the daily CSV logger.

## Install

The repo is set up for [mise](https://mise.jdx.dev), which installs Python and
[uv](https://docs.astral.sh/uv/) and runs the tasks; uv installs the dependencies
the first time a task runs. With mise installed, from the repo folder:

```sh
mise trust                        # allow this repo's mise.toml
mise install                      # Python 3.13 + uv
mise host <inverter-ip>           # creates .env with HOST=<inverter-ip>
```

Without mise: `uv run poll.py --host <inverter-ip>` does the same with uv alone,
or use any Python 3.11+ with `pip install pymodbus` and run the scripts with
`python` (nothing loads `.env` for you).

## Usage

`.env` holds the inverter's LAN address (`HOST=<inverter-ip>`, written by
`mise host`); mise loads it for every task, and git ignores it. You need
to find that address first: look for the WiNet-S dongle in your router's list
of connected devices, and give it a fixed DHCP lease so it does not change.
Then:

```sh
mise poll                         # live dashboard, logs to data/
mise poll -- --interval 2 --settings-every 60   # EMS settings every 60 polls
mise poll -- --count 10 --no-log
mise dump                         # one-shot register dump
mise dump -- --settings           # also clock + EMS holding registers
```

`--host` on the command line overrides `.env`. The inverter must have
Modbus TCP enabled on port 502 (device id 1), which is the default on the
WiNet-S dongle. The dashboard reacts to `+` / `-` (poll interval) and `q`.

## Logging

`poll.py` writes one row per successful poll to `data/poll-YYYY-MM-DD.csv`,
rotating at midnight, with an absolute timestamp on every row because the
interval can change at runtime. Device identity (serial, firmware versions,
model) goes once per day into `data/poll-YYYY-MM-DD.meta.json`. If the column
set changes between runs the old file is renamed `*.old-schema.csv` rather
than mixed. The `data/` folder is gitignored.

## Register map and device behaviour

Addresses in `registers.py` are 1-based as in the Sungrow documentation; the
client subtracts one on the wire. Values are read in contiguous blocks, one
Modbus request each:

| block  | start | count | type    | contents                                            |
| ------ | ----- | ----- | ------- | --------------------------------------------------- |
| sys    | 4954  | 83    | input   | versions, serial, device info, PV, grid AC          |
| batt   | 5214  | 29    | input   | battery power, grid frequency                       |
| meter  | 5601  | 39    | input   | meter powers, battery details                       |
| backup | 5726  | 9     | input   | backup power / voltage / frequency                  |
| rt     | 13000 | 48    | input   | states, energy counters, SOC, currents              |
| clock  | 5000  | 6     | holding | inverter real-time clock                            |
| ems    | 13050 | 51    | holding | EMS mode, SoC limits, export limit, battery command |

### Fast reads, slow settings

The live values are all input registers, and the five blocks above are the
fewest requests that cover them: each block is one contiguous range, and the
gaps between blocks are wider than the inverter's per-request limit. A full
cycle of the five input blocks takes about 115 ms on a persistent connection,
which leaves plenty of room for the default 1 s poll.

The clock and EMS settings (EMS mode, SoC limits, export limit, battery
command) are holding registers, and on this device each holding read takes
120 to 450 ms, ten to twenty times an input read. Reading them every cycle
would roughly triple the cycle time for values that almost never change, so
`poll.py` does not read them unless asked: `--settings-every N` refreshes
them every N polls and keeps the last values in the panel and in the CSV in
between. `dump.py` likewise skips them unless given `--settings`.

### Measured on the SH5.0RS

Things the documentation does not say:

- Reads are capped at about 100 registers per request. Input reads take 15 to
  25 ms each, holding reads 120 to 450 ms each.
- The inverter serves one Modbus transaction at a time. A second client
  polling concurrently gets connection resets; `poll.py` reconnects on its own.
- `battery_power` is negative while charging. `export_power` (13010) is
  signed: positive exporting, negative importing.
- The panel's "balance" line is derived (`load_power - total_active_power`);
  anything inside the measured ±40 W noise floor reads as balanced.
- U32 values are little-endian word order (low word first).

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
