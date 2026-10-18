# SPDX-License-Identifier: GPL-3.0-or-later
"""One-shot full register dump of a Sungrow hybrid inverter."""

import argparse
import os

from sungrow import (
    INPUT_BLOCKS,
    SETTINGS_BLOCKS,
    SungrowClient,
    batt_cmd_map,
    decode_power_flow,
    device_map,
    ems_mode_map,
    enabled_map,
    fmt,
    output_type_map,
    running_state_map,
)

parser = argparse.ArgumentParser(description="Sungrow inverter register dump")
parser.add_argument("--host", default=os.environ.get("HOST"),
                    help="inverter IP address (default: HOST from .env)")
parser.add_argument(
    "--settings", action="store_true",
    help="also read inverter clock + EMS settings (holding registers; "
         "~10-20x slower than input registers on this device)",
)
args = parser.parse_args()
if not args.host:
    parser.error("--host is required (or set HOST in .env)")

blocks = INPUT_BLOCKS + SETTINGS_BLOCKS if args.settings else INPUT_BLOCKS
with SungrowClient(args.host) as client:
    v = client.read(blocks)

device_type_name = device_map.get(v["device_type_code"], f"Unknown (0x{v['device_type_code']:04X})" if v["device_type_code"] else "N/A")
output_type_name = output_type_map.get(v["output_type_raw"], f"Unknown ({v['output_type_raw']})" if v["output_type_raw"] is not None else "N/A")
ems_mode_name = ems_mode_map.get(v["ems_mode"], f"Unknown ({v['ems_mode']})" if v["ems_mode"] is not None else "N/A")
running_state_name = running_state_map.get(v["running_state"], f"Unknown (0x{v['running_state']:04X})" if v["running_state"] is not None else "N/A")
backup_mode_name = enabled_map.get(v["backup_mode"], f"Unknown ({v['backup_mode']})" if v["backup_mode"] is not None else "N/A")

print("\n===== SUNGROW INVERTER - FULL REGISTER DUMP =====\n")

print("--- DEVICE INFO ---")
print(f"  Device Type        : {device_type_name}")
print(f"  Serial Number      : {v['serial_number']}")
print(f"  Nominal Power      : {fmt(v['nominal_power'], 'kW')}")
print(f"  Output Type        : {output_type_name}")
print(f"  ARM Version        : {v['arm_version']}")
print(f"  DSP Version        : {v['dsp_version']}")
print(f"  Inside Temperature : {fmt(v['inside_temp'], '°C')}")
print(f"  Running State      : {running_state_name} (0x{v['running_state']:04X})" if v["running_state"] is not None else "  Running State      : N/A")
print(f"  Power Flow State   : {decode_power_flow(v['power_flow_state'])} (0x{v['power_flow_state']:04X})" if v["power_flow_state"] is not None else "  Power Flow State   : N/A")
clock = (v["clock_year"], v["clock_month"], v["clock_day"], v["clock_hour"], v["clock_minute"], v["clock_second"])
if None not in clock:
    print("  Inverter Clock     : {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*clock))
elif not args.settings:
    print("  Inverter Clock     : (skipped, use --settings)")
else:
    print("  Inverter Clock     : N/A")

print("\n--- PV ---")
print(f"  MPPT1 Voltage      : {fmt(v['mppt1_voltage'], 'V')}")
print(f"  MPPT1 Current      : {fmt(v['mppt1_current'], 'A')}")
print(f"  MPPT2 Voltage      : {fmt(v['mppt2_voltage'], 'V')}")
print(f"  MPPT2 Current      : {fmt(v['mppt2_current'], 'A')}")
print(f"  Total PV Power     : {fmt(v['pv_total'], 'W', 0)}")

print("\n--- GRID / AC ---")
print(f"  Phase A Voltage    : {fmt(v['phase_a_voltage'], 'V')}")
print(f"  Phase B Voltage    : {fmt(v['phase_b_voltage'], 'V')}")
print(f"  Phase C Voltage    : {fmt(v['phase_c_voltage'], 'V')}")
print(f"  Phase A Current    : {fmt(v['phase_a_current'], 'A')}")
print(f"  Phase B Current    : {fmt(v['phase_b_current'], 'A')}")
print(f"  Phase C Current    : {fmt(v['phase_c_current'], 'A')}")
print(f"  Grid Frequency     : {fmt(v['grid_frequency'], 'Hz', 2)}")
print(f"  Power Factor       : {fmt(v['power_factor'], '', 3)}")
print(f"  Reactive Power     : {fmt(v['reactive_power'], 'Var', 0)}")
print(f"  Total Active Power : {fmt(v['total_active_power'], 'W', 0)}")

print("\n--- LOAD / EXPORT ---")
print(f"  Load Power         : {fmt(v['load_power'], 'W', 0)}")
print(f"  Export Power       : {fmt(v['export_power'], 'W', 0)}")

print("\n--- METER ---")
print(f"  Meter Power        : {fmt(v['meter_power'], 'W', 0)}")
print(f"  Meter Phase A      : {fmt(v['meter_phase_a_power'], 'W', 0)}")
print(f"  Meter Phase B      : {fmt(v['meter_phase_b_power'], 'W', 0)}")
print(f"  Meter Phase C      : {fmt(v['meter_phase_c_power'], 'W', 0)}")

print("\n--- BATTERY ---")
print(f"  Battery Power      : {fmt(v['battery_power'], 'W', 0)}")
print(f"  Battery Voltage    : {fmt(v['battery_voltage'], 'V')}")
print(f"  Battery Current    : {fmt(v['battery_current'], 'A')}")
print(f"  Battery SOC        : {fmt(v['battery_soc'], '%')}")
print(f"  Battery SOH        : {fmt(v['battery_soh'], '%')}")
print(f"  Battery Temp       : {fmt(v['battery_temp'], '°C')}")
print(f"  Battery Capacity   : {fmt(v['battery_capacity'], 'kWh', 2)}")
print(f"  BDC Rated Power    : {fmt(v['bdc_rated_power'], 'kW')}")
print(f"  Max Charge I (BMS) : {fmt(v['max_charge_current'], 'A', 0)}")
print(f"  Max Discharge I    : {fmt(v['max_discharge_current'], 'A', 0)}")

print("\n--- BACKUP ---")
print(f"  Total Backup Power : {fmt(v['total_backup_power'], 'W', 0)}")
print(f"  Phase A Backup V   : {fmt(v['phase_a_backup_volt'], 'V')}")
print(f"  Backup Frequency   : {fmt(v['backup_frequency'], 'Hz', 2)}")

print("\n--- EMS SETTINGS ---")
if args.settings:
    print(f"  EMS Mode           : {ems_mode_name}")
    print(f"  Max SoC            : {fmt(v['max_soc'], '%')}")
    print(f"  Min SoC            : {fmt(v['min_soc'], '%')}")
    print(f"  Reserved SoC       : {fmt(v['reserved_soc'], '%')}")
    export_limit_name = enabled_map.get(v["export_limit_mode"], f"Unknown ({v['export_limit_mode']})" if v["export_limit_mode"] is not None else "N/A")
    print(f"  Export Power Limit : {fmt(v['export_limit'], 'kW', 3)} ({export_limit_name})")
    print(f"  Backup Mode        : {backup_mode_name}")
    batt_cmd_name = batt_cmd_map.get(v["batt_cmd"], f"Unknown (0x{v['batt_cmd']:04X})" if v["batt_cmd"] is not None else "N/A")
    print(f"  Battery Command    : {batt_cmd_name}")
    print(f"  Battery Cmd Power  : {fmt(v['batt_cmd_power'], 'W', 0)}")
else:
    print("  (skipped, use --settings)")

print("\n--- ENERGY DAILY ---")
print(f"  Output Energy      : {fmt(v['daily_output_energy'], 'kWh')}")
print(f"  PV Generation      : {fmt(v['daily_pv_gen'], 'kWh')}")
print(f"  Export from PV     : {fmt(v['daily_export_pv'], 'kWh')}")
print(f"  Battery Charge(PV) : {fmt(v['daily_batt_charge'], 'kWh')}")
print(f"  Battery Discharge  : {fmt(v['daily_batt_discharge'], 'kWh')}")
print(f"  Total Charge       : {fmt(v['daily_charge_energy'], 'kWh')}")
print(f"  Direct Consumption : {fmt(v['daily_direct_consump'], 'kWh')}")
print(f"  Import Energy      : {fmt(v['daily_import_energy'], 'kWh')}")
print(f"  Export Energy      : {fmt(v['daily_export_energy'], 'kWh')}")
print(f"  Self-consumption   : {fmt(v['self_consumption'], '%')}")

print("\n--- ENERGY TOTAL ---")
print(f"  Output Energy      : {fmt(v['total_output_energy'], 'kWh')}")
print(f"  PV Generation      : {fmt(v['total_pv_gen'], 'kWh')}")
print(f"  Export from PV     : {fmt(v['total_export_pv'], 'kWh')}")
print(f"  Battery Charge(PV) : {fmt(v['total_batt_charge'], 'kWh')}")
print(f"  Battery Discharge  : {fmt(v['total_batt_discharge'], 'kWh')}")
print(f"  Total Charge       : {fmt(v['total_charge_energy'], 'kWh')}")
print(f"  Direct Consumption : {fmt(v['total_direct_consump'], 'kWh')}")
print(f"  Import Energy      : {fmt(v['total_import_energy'], 'kWh')}")
print(f"  Export Energy      : {fmt(v['total_export_energy'], 'kWh')}")

print()
