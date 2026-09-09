#!/usr/bin/env python3
"""Decode Prime G2 i.MX6ULL register captures into stable JSON/Markdown.

The decoder deliberately distinguishes captured facts from derived values.  It
accepts the ``NAME|address|width|value`` format emitted by the Linux capture
bundle and ignores comments or bounded-probe failure messages.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LINE = re.compile(r"^([A-Z0-9_]+)\|(0x[0-9a-fA-F]+)\|(8|16|32)\|(0x[0-9a-fA-F]+)$")


def bits(value: int, lsb: int, width: int = 1) -> int:
    return (value >> lsb) & ((1 << width) - 1)


def decode(name: str, value: int) -> dict[str, object]:
    d: dict[str, object] = {}
    if name == "LCDIF_CTRL":
        d = {"run": bool(bits(value, 0)), "data_format_24_bit": bool(bits(value, 1)),
             "word_length": bits(value, 8, 2), "lcd_databus_width": bits(value, 10, 2),
             "dotclk_mode": bool(bits(value, 17)), "bypass_count": bool(bits(value, 19)),
             "clkgate": bool(bits(value, 30)), "soft_reset": bool(bits(value, 31))}
    elif name == "LCDIF_CTRL1":
        d = {"reset": bool(bits(value, 0)), "frame_done_irq": bool(bits(value, 9)),
             "underflow_irq": bool(bits(value, 10)), "frame_done_irq_enable": bool(bits(value, 13)),
             "underflow_irq_enable": bool(bits(value, 14)), "byte_packing": bits(value, 16, 4),
             "fifo_clear": bool(bits(value, 21)), "recover_on_underflow": bool(bits(value, 24))}
    elif name == "LCDIF_CTRL2":
        d = {"outstanding_requests": bits(value, 21, 3), "odd_line_pattern": bits(value, 16, 3),
             "even_line_pattern": bits(value, 12, 3), "burst_len_8": bool(bits(value, 20))}
    elif name == "LCDIF_TRANSFER_COUNT":
        d = {"horizontal_transfer_count": bits(value, 0, 16),
             "vertical_transfer_count": bits(value, 16, 16)}
    elif name == "LCDIF_VDCTRL0":
        d = {"vsync_pulse_width": bits(value, 0, 18), "vsync_period_unit": bool(bits(value, 20)),
             "vsync_pulse_width_unit": bool(bits(value, 21)), "enable_present": bool(bits(value, 24)),
             "vsync_active_high": bool(bits(value, 27)), "hsync_active_high": bool(bits(value, 26)),
             "dotclk_active_falling": bool(bits(value, 25)), "enable_active_high": bool(bits(value, 28))}
    elif name == "LCDIF_VDCTRL1":
        d = {"vertical_period": bits(value, 0, 20)}
    elif name == "LCDIF_VDCTRL2":
        d = {"horizontal_period": bits(value, 0, 18), "hsync_pulse_width": bits(value, 18, 14)}
    elif name == "LCDIF_VDCTRL3":
        d = {"vertical_wait_count": bits(value, 0, 16), "horizontal_wait_count": bits(value, 16, 12)}
    elif name == "LCDIF_VDCTRL4":
        d = {"dotclk_horizontal_valid_data_count": bits(value, 0, 18),
             "sync_signals_on": bool(bits(value, 18)), "dotclk_delay": bits(value, 29, 3)}
    elif name.startswith("PWM7_"):
        if name == "PWM7_CR":
            d = {"enable": bool(bits(value, 0)), "repeat": bits(value, 1, 2), "software_reset": bool(bits(value, 3)),
                 "prescaler": bits(value, 4, 12), "clock_source": bits(value, 16, 2),
                 "output_polarity_inverted": bool(bits(value, 18))}
        elif name == "PWM7_SR":
            d = {"fifo_available": bits(value, 0, 3), "fifo_empty": bool(bits(value, 3)),
                 "rollover": bool(bits(value, 4)), "compare": bool(bits(value, 5))}
    elif name.startswith("GPIO"):
        d = {"set_bits": [i for i in range(32) if value & (1 << i)]}
        if name.endswith("_GDIR"):
            d["output_bits"] = d.pop("set_bits")
        elif name.endswith("_PSR"):
            d["high_input_bits"] = d.pop("set_bits")
        else:
            d["high_output_latches"] = d.pop("set_bits")
    elif name.startswith("CCM_CCGR"):
        d = {f"gate_{i}": bits(value, i * 2, 2) for i in range(16)}
    elif name == "CCM_CBCMR":
        d = {"lcdif_pre_clk_sel": bits(value, 23, 3), "periph2_clk2_sel": bits(value, 20, 2)}
    elif name == "CCM_CSCDR2":
        d = {"lcdif_podf": bits(value, 9, 3) + 1, "lcdif_pred": bits(value, 12, 3) + 1,
             "lcdif_pre_clk_sel": bits(value, 15, 3)}
    elif name == "SRC_SRSR":
        causes = ["ipg", "csu", "ipp_user", "wdog3", "jtag", "jtag_sw", "wdog1", "tempsense"]
        d = {causes[i]: bool(bits(value, i)) for i in range(len(causes))}
    elif name.startswith("KPP_"):
        if name == "KPP_KPCR":
            d = {"row_enable_mask": bits(value, 0, 8), "column_open_drain_mask": bits(value, 8, 8)}
        elif name == "KPP_KPSR":
            d = {"key_depress_sync": bool(bits(value, 0)), "key_release_sync": bool(bits(value, 1)),
                 "depress_irq_enable": bool(bits(value, 8)), "release_irq_enable": bool(bits(value, 9)),
                 "depress_status": bool(bits(value, 10)), "release_status": bool(bits(value, 11))}
        elif name == "KPP_KDDR":
            d = {"row_direction_mask": bits(value, 0, 8), "column_direction_mask": bits(value, 8, 8)}
        elif name == "KPP_KPDR":
            d = {"row_data": bits(value, 0, 8), "column_data": bits(value, 8, 8)}
    return d


def load_capture(path: Path) -> list[dict[str, object]]:
    records = []
    for raw in path.read_text(errors="replace").splitlines():
        match = LINE.match(raw.strip().lstrip("# "))
        if not match:
            continue
        name, address, width, raw_value = match.groups()
        value = int(raw_value, 16)
        records.append({"name": name, "address": address.lower(), "width": int(width),
                        "value": raw_value.lower(), "decoded": decode(name, value)})
    return records


def derive(records: list[dict[str, object]]) -> dict[str, object]:
    values = {r["name"]: int(str(r["value"]), 16) for r in records}
    out: dict[str, object] = {}
    if {"CCM_CBCMR", "CCM_CSCDR2", "LCDIF_VDCTRL1", "LCDIF_VDCTRL2"} <= values.keys():
        pred = bits(values["CCM_CSCDR2"], 12, 3) + 1
        podf = bits(values["CCM_CBCMR"], 23, 3) + 1
        pixel = 528_000_000 / pred / podf
        htotal = bits(values["LCDIF_VDCTRL2"], 0, 18)
        vtotal = bits(values["LCDIF_VDCTRL1"], 0, 20)
        out.update(pixel_clock_hz=pixel, refresh_hz=pixel / htotal / vtotal)
    if {"PWM7_SAR", "PWM7_PR"} <= values.keys():
        out["backlight_duty_percent"] = 100.0 * values["PWM7_SAR"] / (values["PWM7_PR"] + 2)
    if "LCDIF_TRANSFER_COUNT" in values:
        transfer = bits(values["LCDIF_TRANSFER_COUNT"], 0, 16)
        out["serial_rgb_cycles_per_pixel"] = 3
        out["physical_width"] = transfer // 3
        out["physical_height"] = bits(values["LCDIF_TRANSFER_COUNT"], 16, 16)
    return out


def capture_directory(path: Path) -> dict[str, object]:
    records = []
    for source in sorted(path.glob("registers-*.txt")):
        for record in load_capture(source):
            record["source"] = source.name
            records.append(record)
    derived = derive(records)
    framebuffer = path / "framebuffer.txt"
    if framebuffer.exists():
        match = re.search(r"# D:\s*([0-9.]+)\s*MHz", framebuffer.read_text(errors="replace"))
        if match:
            pixel = float(match.group(1)) * 1_000_000
            derived["pixel_clock_hz"] = pixel
            derived["pixel_clock_source"] = "observed fbset mode"
            values = {r["name"]: int(str(r["value"]), 16) for r in records}
            if {"LCDIF_VDCTRL1", "LCDIF_VDCTRL2"} <= values.keys():
                derived["refresh_hz"] = pixel / bits(values["LCDIF_VDCTRL2"], 0, 18) / bits(values["LCDIF_VDCTRL1"], 0, 20)
    return {"schema": "mahalo.prime-g2.registers.v1", "capture": path.name,
            "records": records, "derived": derived}


def markdown(doc: dict[str, object]) -> str:
    lines = [f"# Prime G2 decoded registers — {doc['capture']}", "",
             "Captured register values are facts; the final section is calculated from those facts.", "",
             "| Register | Address | Value | Decoded |", "|---|---:|---:|---|"]
    for r in doc["records"]:
        fields = ", ".join(f"{k}={v}" for k, v in r["decoded"].items()) or "—"
        lines.append(f"| {r['name']} | `{r['address']}` | `{r['value']}` | {fields} |")
    lines += ["", "## Derived", ""]
    lines += [f"- `{k}`: {v}" for k, v in doc["derived"].items()]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("capture", type=Path)
    p.add_argument("--json", type=Path)
    p.add_argument("--markdown", type=Path)
    args = p.parse_args()
    doc = capture_directory(args.capture)
    rendered = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered)
    else:
        print(rendered, end="")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
