# SPDX-License-Identifier: GPL-3.0-or-later
"""Modbus TCP client for Sungrow hybrid inverters: block reads + value decoding."""

from pymodbus.client import ModbusTcpClient

from .registers import BLOCKS, INPUT_BLOCKS, REGISTERS


def reg(address):
    """Doc register addresses are 1-based; Modbus needs 0-based."""
    return address - 1


def u16(regs, addr):
    return regs.get(addr)


def s16(regs, addr):
    v = regs.get(addr)
    if v is None:
        return None
    return v - 65536 if v > 32767 else v


def u32(regs, addr):
    # Sungrow U32: little-endian word order (low word first, high word second)
    lo, hi = regs.get(addr), regs.get(addr + 1)
    if lo is None or hi is None:
        return None
    return (hi << 16) + lo


def s32(regs, addr):
    v = u32(regs, addr)
    if v is None:
        return None
    return v - 0x100000000 if v >= 0x80000000 else v


def string(regs, addr, length):
    chars = []
    for i in range(length):
        r = regs.get(addr + i)
        if r is None:
            return None
        chars.append(chr((r >> 8) & 0xFF))
        chars.append(chr(r & 0xFF))
    return "".join(chars).strip("\x00")


def scale(x, factor):
    return x / factor if x is not None else None


def _decode(regs, addr, kind):
    if kind == "u16":
        return u16(regs, addr)
    if kind == "s16":
        return s16(regs, addr)
    if kind == "u32":
        return u32(regs, addr)
    if kind == "s32":
        return s32(regs, addr)
    if kind.startswith("string:"):
        return string(regs, addr, int(kind.split(":")[1]))
    raise ValueError(f"unknown register kind: {kind}")


class SungrowClient:
    def __init__(self, host, port=502, device_id=1, timeout=3):
        self._client = ModbusTcpClient(host, port=port, timeout=timeout)
        self.device_id = device_id

    def connect(self):
        return self._client.connect()

    def close(self):
        self._client.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def read_block(self, name):
        """One Modbus request; {1-based address: raw value}, or {} on error."""
        start, count, holding = BLOCKS[name]
        fn = (self._client.read_holding_registers if holding
              else self._client.read_input_registers)
        rr = fn(address=reg(start), count=count, device_id=self.device_id)
        if rr.isError():
            return {}
        return {start + i: r for i, r in enumerate(rr.registers)}

    def read(self, block_names=INPUT_BLOCKS):
        """Read the given blocks (one request each) and decode all values.

        Returns {value_name: value} for every entry in REGISTERS; values whose
        block was not requested (or whose read failed) are None.
        """
        raw = {name: self.read_block(name) for name in block_names}
        values = {}
        for name, (block, addr, kind, factor) in REGISTERS.items():
            v = _decode(raw.get(block, {}), addr, kind)
            values[name] = scale(v, factor) if factor else v
        return values
