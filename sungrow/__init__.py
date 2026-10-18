# SPDX-License-Identifier: GPL-3.0-or-later
from .client import SungrowClient
from .logger import PollLog
from .registers import (
    INPUT_BLOCKS,
    SETTINGS_BLOCKS,
    batt_cmd_map,
    decode_power_flow,
    device_map,
    ems_mode_map,
    enabled_map,
    output_type_map,
    running_state_map,
)


def fmt(val, unit="", decimals=1):
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f} {unit}".strip()
