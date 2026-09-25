"""Apply the Prime Settings extension and generate its build identity.

Operates on a prepared Upsilon tree; never resets or cleans a checkout.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "ports/lefony-prime-g2"


def prepare_contributors(settings: Path):
    replacements = {
        "main_controller.h": [
            ("s_contributorsChildren[18]", "s_contributorsChildren[19]"),
        ],
        "main_controller.cpp": [
            ("s_contributorsChildren[18] = {", "s_contributorsChildren[19] = {SettingsMessageTree(I18n::Message::MaikoPruett), "),
        ],
        "sub_menu/contributors_controller.cpp": [
            ("s_numberOfDevelopers = 18;", "s_numberOfDevelopers = 19;"),
            ("s_developersUsernames[s_numberOfDevelopers] = {\n", "s_developersUsernames[s_numberOfDevelopers] = {\n  I18n::Message::PMaikoPruett,\n"),
            ("if (index < s_numberOfUpsilonDevelopers) {", "if (index == 0) {\n    myTextCell->setTextColor(Palette::AccentText);\n  } else if (index <= s_numberOfUpsilonDevelopers) {"),
        ],
    }
    for name, changes in replacements.items():
        path = settings / name
        text = path.read_text()
        for old, new in changes:
            if text.count(new) == 1:
                continue
            if text.count(old) != 1:
                raise ValueError(f"Unexpected contributors context in {name}")
            text = text.replace(old, new, 1)
        path.write_text(text)


def prepare(source: Path, stamp: str | None = None):
    # Durable native USB page and USB-powered display policy.
    if (source / "apps/apps_container.cpp").exists():
        shutil.copy2(PORT / "apps/lefony_usb_page.h", source / "apps/lefony_usb_page.h")
        container = source / "apps/apps_container.cpp"
        text = container.read_text()
        if '#include "lefony_usb_page.h"' not in text:
            text = '#include "lefony_usb_page.h"\n' + text
        if 'addTimer(lefonyUSBPageTimer());' not in text:
            text = text.replace('addTimer(&m_batteryTimer);',
                                'addTimer(lefonyUSBPageTimer());\n  addTimer(&m_batteryTimer);')
        container.write_text(text)
        dimming = source / "apps/backlight_dimming_timer.cpp"
        text = dimming.read_text()
        if 'prime_g2_update_in_progress' not in text:
            text = 'extern "C" bool prime_g2_update_in_progress();\n' + text
            text = text.replace('bool BacklightDimmingTimer::fire(){',
                'bool BacklightDimmingTimer::fire(){\n  if (prime_g2_update_in_progress()) return false;')
        dimming.write_text(text)
        if 'prime_g2_external_power_present' not in text:
            text = 'extern "C" bool prime_g2_external_power_present();\n' + text
            text = text.replace('if (prime_g2_update_in_progress()) return false;',
                'if (prime_g2_update_in_progress() || prime_g2_external_power_present()) return false;')
        # Touch must also interrupt a battery-powered dimming animation.
        text = text.replace('if (e.isKeyboardEvent()){',
            'if (e.isKeyboardEvent() || e == Ion::Events::Touch){')
        dimming.write_text(text)
    release_version = os.environ.get("LEFONY_RELEASE_VERSION")
    if release_version:
        from prime_g2_update_capsule import parse_version
        components = parse_version(release_version)
        (source / "ion/src/prime_g2/release_version.h").write_text(
            "#pragma once\n#define LEFONY_UPDATE_VERSION {" +
            ", ".join(str(n) for n in components) + "}\n")
    version = (PORT / "LEFONY_VERSION").read_text().strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?", version):
        raise ValueError("Invalid Lefony version")
    digest = hashlib.sha256()
    for path in sorted(PORT.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(PORT)).encode() + b"\0")
            digest.update(path.read_bytes())
    stamp = stamp or datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")
    if not re.fullmatch(r"[0-9]{6}-[0-9]{6}", stamp):
        raise ValueError("Invalid build timestamp")
    build_id = f"{stamp}-{digest.hexdigest()[:6]}"
    settings = source / "apps/settings"
    declaration = settings / "main_controller.h"
    text = declaration.read_text()
    if "s_modelAboutChildren[12]" not in text and "s_modelAboutChildren[13]" not in text:
        if text.count("s_modelAboutChildren[10]") != 1:
            raise ValueError("Unexpected About menu declaration")
        declaration.write_text(text.replace("s_modelAboutChildren[10]", "s_modelAboutChildren[12]"))
    model = settings / "main_controller.cpp"
    text = model.read_text()
    if "SettingsMessageTree(I18n::Message::LefonyBuildId)" not in text:
        old = "s_modelAboutChildren[10]"
        if text.count(old) != 1:
            raise ValueError("Unexpected About menu model")
        text = text.replace(old, "s_modelAboutChildren[12]")
        old = "SettingsMessageTree(I18n::Message::Contributors, s_contributorsChildren)"
        if text.count(old) != 1:
            raise ValueError("Unexpected Contributors menu")
        text = text.replace(old, "SettingsMessageTree(I18n::Message::LefonyBuildId), "
                            "SettingsMessageTree(I18n::Message::LefonyEnterRecovery), " + old)
        model.write_text(text)
    # Upgrade both a fresh ten-row tree and the earlier twelve-row candidate.
    for path in (declaration, model):
        text = path.read_text()
        text = text.replace("s_modelAboutChildren[12]", "s_modelAboutChildren[13]")
        if path == model and "SettingsMessageTree(I18n::Message::LefonyUsbStatus)" not in text:
            text = text.replace("SettingsMessageTree(I18n::Message::LefonyEnterRecovery)",
                                "SettingsMessageTree(I18n::Message::LefonyUsbStatus), "
                                "SettingsMessageTree(I18n::Message::LefonyEnterRecovery)")
        path.write_text(text)
    for path in (PORT / "apps/settings/sub_menu").iterdir():
        shutil.copy2(path, settings / "sub_menu" / path.name)
    prepare_contributors(settings)
    translations = settings / "base.universal.i18n"
    messages = {
        "MaikoPruett": "Maiko Pruett",
        "PMaikoPruett": "@maikopruett",
        "LefonyBuildId": "Build ID",
        "LefonyUsbStatus": "USB status",
        "LefonyEnterRecovery": "Enter recovery mode",
        "LefonyRecoveryWarning1": "Restart into recovery mode?",
        "LefonyRecoveryWarning2": "To return to Lefony OS,",
        "LefonyRecoveryWarning3": "press RESET again or wait",
        "LefonyRecoveryWarning4": "3 minutes.",
        "LefonyRecoveryUpgrade1": "Update the bootloader first",
        "LefonyRecoveryUpgrade2": "at lefony.com.",
        "LefonyRecoveryFailed": "Recovery request failed",

    }
    text = translations.read_text()
    for key, value in messages.items():
        line = f"{key} = {json.dumps(value)}"
        if re.search(rf"^{key}\s*=", text, re.M):
            text = re.sub(rf"^{key}\s*=.*$", lambda _: line, text, flags=re.M)
        else:
            text = text.rstrip() + "\n" + line + "\n"
    translations.write_text("\n".join(line for line in text.splitlines() if line.strip()) + "\n")
    identity = source / "ion/src/prime_g2/lefony_build_identity.h"
    identity.write_text("#pragma once\n" +
                        f"#define LEFONY_OS_VERSION {json.dumps(version)}\n" +
                        f"#define LEFONY_BUILD_ID {json.dumps(build_id)}\n")
    return {"version": version, "build_id": build_id, "port_sha256": digest.hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source.resolve()), indent=2))
