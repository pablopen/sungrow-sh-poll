# SPDX-License-Identifier: GPL-3.0-or-later
"""Sungrow SHx.0RS/RT register map: block layout, value definitions, enum maps.

Register addresses are 1-based as in the Sungrow documentation; the client
converts to 0-based on the wire.
"""

# Contiguous ranges read in one Modbus request each. The device caps reads at
# ~100 registers and the gaps between blocks exceed that, so these 5 input
# blocks are the minimum request count. Input reads take ~15-25ms each;
# holding reads (clock/ems) take 120-450ms each.
#
# name: (start_address, count, holding)
BLOCKS = {
    "sys":    (4954, 83, False),   # versions, serial, device info, PV, grid AC
    "batt":   (5214, 29, False),   # battery power, grid frequency
    "meter":  (5601, 39, False),   # meter powers, battery details
    "backup": (5726, 9, False),    # backup power/voltage/frequency
    "rt":     (13000, 48, False),  # states, energy counters, SOC, currents
    "clock":  (5000, 6, True),     # inverter real-time clock
    "ems":    (13050, 51, True),   # EMS settings, battery command
}

INPUT_BLOCKS = ("sys", "batt", "meter", "backup", "rt")
SETTINGS_BLOCKS = ("clock", "ems")

# value_name: (block, address, kind, scale_divisor)
# kind: u16 | s16 | u32 | s32 | string:<words>; scale None = raw value
REGISTERS = {
    # System info
    "serial_number":        ("sys", 4990, "string:10", None),
    "arm_version":          ("sys", 4954, "string:15", None),
    "dsp_version":          ("sys", 4969, "string:15", None),
    "device_type_code":     ("sys", 5000, "u16", None),
    "nominal_power":        ("sys", 5001, "u16", 10),      # 0.1kW -> kW
    "output_type_raw":      ("sys", 5002, "u16", None),
    "inside_temp":          ("sys", 5008, "s16", 10),      # 0.1°C

    # PV - MPPT inputs
    "mppt1_voltage":        ("sys", 5011, "u16", 10),      # 0.1V
    "mppt1_current":        ("sys", 5012, "u16", 10),      # 0.1A
    "mppt2_voltage":        ("sys", 5013, "u16", 10),      # 0.1V
    "mppt2_current":        ("sys", 5014, "u16", 10),      # 0.1A
    "pv_total":             ("sys", 5017, "u32", None),    # 1W

    # Grid AC
    "phase_a_voltage":      ("sys", 5019, "u16", 10),      # 0.1V
    "phase_b_voltage":      ("sys", 5020, "u16", 10),      # 0.1V
    "phase_c_voltage":      ("sys", 5021, "u16", 10),      # 0.1V
    "reactive_power":       ("sys", 5033, "s32", None),    # 1Var
    "power_factor":         ("sys", 5035, "s16", 1000),    # 0.001
    "grid_frequency":       ("batt", 5242, "u16", 100),    # 0.01Hz

    # Meter (valid when smart energy meter connected)
    "meter_power":          ("meter", 5601, "s32", None),  # 1W
    "meter_phase_a_power":  ("meter", 5603, "s32", None),  # 1W
    "meter_phase_b_power":  ("meter", 5605, "s32", None),  # 1W
    "meter_phase_c_power":  ("meter", 5607, "s32", None),  # 1W

    # Battery (recommended registers)
    "battery_power":        ("batt", 5214, "s32", None),   # 1W
    "battery_current":      ("meter", 5631, "s16", 10),    # 0.1A
    "battery_voltage":      ("rt", 13020, "u16", 10),      # 0.1V
    "battery_soc":          ("rt", 13023, "u16", 10),      # 0.1%
    "battery_soh":          ("rt", 13024, "u16", 10),      # 0.1%
    "battery_temp":         ("rt", 13025, "s16", 10),      # 0.1°C
    "battery_capacity":     ("meter", 5639, "u16", 100),   # 0.01kWh
    "max_charge_current":   ("meter", 5635, "u16", None),  # 1A
    "max_discharge_current": ("meter", 5636, "u16", None), # 1A
    "bdc_rated_power":      ("meter", 5628, "u16", 10),    # 0.1kW

    # Load / Grid power
    "load_power":           ("rt", 13008, "s32", None),    # 1W
    "export_power":         ("rt", 13010, "s32", None),    # 1W

    # Energy totals
    "daily_output_energy":  ("sys", 5003, "u16", 10),      # 0.1kWh
    "total_output_energy":  ("sys", 5004, "u32", 10),      # 0.1kWh
    "daily_pv_gen":         ("rt", 13002, "u16", 10),      # 0.1kWh
    "total_pv_gen":         ("rt", 13003, "u32", 10),      # 0.1kWh
    "daily_export_pv":      ("rt", 13005, "u16", 10),      # 0.1kWh
    "total_export_pv":      ("rt", 13006, "u32", 10),      # 0.1kWh
    "daily_batt_charge":    ("rt", 13012, "u16", 10),      # 0.1kWh
    "total_batt_charge":    ("rt", 13013, "u32", 10),      # 0.1kWh
    "daily_direct_consump": ("rt", 13017, "u16", 10),      # 0.1kWh
    "total_direct_consump": ("rt", 13018, "u32", 10),      # 0.1kWh
    "daily_batt_discharge": ("rt", 13026, "u16", 10),      # 0.1kWh
    "total_batt_discharge": ("rt", 13027, "u32", 10),      # 0.1kWh
    "daily_import_energy":  ("rt", 13036, "u16", 10),      # 0.1kWh
    "total_import_energy":  ("rt", 13037, "u32", 10),      # 0.1kWh
    "daily_charge_energy":  ("rt", 13040, "u16", 10),      # 0.1kWh
    "total_charge_energy":  ("rt", 13041, "u32", 10),      # 0.1kWh
    "daily_export_energy":  ("rt", 13045, "u16", 10),      # 0.1kWh
    "total_export_energy":  ("rt", 13046, "u32", 10),      # 0.1kWh
    "self_consumption":     ("rt", 13029, "u16", 10),      # 0.1%

    # Phase currents
    "phase_a_current":      ("rt", 13031, "s16", 10),      # 0.1A
    "phase_b_current":      ("rt", 13032, "s16", 10),      # 0.1A
    "phase_c_current":      ("rt", 13033, "s16", 10),      # 0.1A
    "total_active_power":   ("rt", 13034, "s32", None),    # 1W

    # Running state
    "running_state":        ("rt", 13000, "u16", None),
    "power_flow_state":     ("rt", 13001, "u16", None),

    # Inverter real-time clock (holding registers)
    "clock_year":           ("clock", 5000, "u16", None),
    "clock_month":          ("clock", 5001, "u16", None),
    "clock_day":            ("clock", 5002, "u16", None),
    "clock_hour":           ("clock", 5003, "u16", None),
    "clock_minute":         ("clock", 5004, "u16", None),
    "clock_second":         ("clock", 5005, "u16", None),

    # Backup
    "total_backup_power":   ("backup", 5726, "s32", None), # 1W
    "phase_a_backup_volt":  ("backup", 5731, "u16", 10),   # 0.1V
    "backup_frequency":     ("backup", 5734, "u16", 100),  # 0.01Hz

    # EMS settings (holding registers)
    "ems_mode":             ("ems", 13050, "u16", None),   # see ems_mode_map
    "max_soc":              ("ems", 13058, "u16", 10),     # 0.1%
    "min_soc":              ("ems", 13059, "u16", 10),     # 0.1%
    "export_limit":         ("ems", 13074, "u16", 1000),   # 0.001kW -> kW
    "export_limit_mode":    ("ems", 13087, "u16", None),   # 0xAA=Enabled, 0x55=Disabled
    "backup_mode":          ("ems", 13075, "u16", None),   # 0xAA=Enabled, 0x55=Disabled
    "reserved_soc":         ("ems", 13100, "u16", 10),     # 0.1%

    # Battery charge/discharge command (active control registers)
    "batt_cmd":             ("ems", 13051, "u16", None),   # 0xAA=Charge, 0xBB=Discharge, 0xCC=Stop
    "batt_cmd_power":       ("ems", 13052, "u16", None),   # 1W setpoint (EMS mode = Forced)
}


# ---------------- ENUM MAPS ----------------

device_map = {
    0xD17: "SH3.0RS",  0xD0D: "SH3.6RS",  0xD18: "SH4.0RS",
    0xD0F: "SH5.0RS",  0xD10: "SH6.0RS",
    0xD1A: "SH8.0RS",  0xD1B: "SH10RS",
    0xE00: "SH5.0RT",  0xE01: "SH6.0RT",
    0xE02: "SH8.0RT",  0xE03: "SH10RT",
    0xE10: "SH5.0RT-20", 0xE11: "SH6.0RT-20",
}

output_type_map = {0: "Single Phase", 1: "3P4L", 2: "3P3L"}
ems_mode_map = {0: "Self-consumption", 2: "Forced", 3: "External EMS", 4: "VPP"}
running_state_map = {
    0x0000: "Running",          0x1200: "Initial Standby",
    0x1300: "Key Stop",         0x1400: "Standby",
    0x1500: "Emergency Stop",   0x1600: "Starting",
    0x5500: "Fault",            0x8000: "Stop",
    0x8100: "Derating Running", 0x8200: "Dispatch Running",
    0x9100: "Alarm Running",
}

batt_cmd_map = {0xAA: "Charge", 0xBB: "Discharge", 0xCC: "Stop"}
enabled_map = {0xAA: "Enabled", 0x55: "Disabled"}

# Power Flow State (13001) is a bitmask, not an enum.
power_flow_bits = [
    (0x01, "PV generating"),
    (0x02, "Battery charging"),
    (0x04, "Battery discharging"),
    (0x08, "Load active"),
    (0x10, "Exporting to grid"),
    (0x20, "Importing from grid"),
]


def decode_power_flow(state):
    if state is None:
        return "N/A"
    flags = [name for bit, name in power_flow_bits if state & bit]
    return ", ".join(flags) if flags else "Idle"
