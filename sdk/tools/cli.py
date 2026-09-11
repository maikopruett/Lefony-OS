# SPDX-License-Identifier: GPL-3.0-or-later
"""Native app build tools. Never flashes hardware or implicitly publishes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from lfapp import PackageError, elf_segments, manifest, pack, unpack

SDK = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'sdk'
RUNTIME = SDK.parent / 'runtime'
DEFAULT_QEMU = RUNTIME / 'qemu-system-arm' if RUNTIME.exists() else SDK.parent / 'build/qemu-prime-g2/qemu-system-arm'
DEFAULT_FIRMWARE = RUNTIME / 'firmware.elf' if RUNTIME.exists() else SDK.parent / 'dist/lefony-os-prime-g2-vm-native.elf'
TRUST = sorted((SDK / 'trust').glob('*.pem'))



def build(project):
    metadata = manifest(json.loads((project / "app.json").read_text()))
    compiler = shutil.which("arm-none-eabi-g++")
    if not compiler:
        raise ValueError("arm-none-eabi-g++ is required; run doctor")
    version = subprocess.check_output([compiler, "-dumpfullversion"], text=True).strip()
    if version != "16.2.0":
        raise ValueError(f"experimental SDK pins GCC 16.2.0; found {version}")
    sources = sorted((project / "src").rglob("*.cpp"))
    if not sources:
        raise ValueError("no src/*.cpp sources")
    output = project / "build"
    output.mkdir(exist_ok=True)
    image = output / "app.elf"
    command = [compiler, "-std=c++17", "-mcpu=cortex-a7", "-marm", "-mfpu=neon-vfpv4", "-mfloat-abi=hard",
               "-Os", "-ffreestanding", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics",
               "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-fno-pic", "-fno-pie",
               "-ffunction-sections", "-fdata-sections", "-Wall", "-Wextra", "-Werror",
               "-nostdlib", "-nostartfiles", "-static", "-Wl,--build-id=none", "-Wl,--gc-sections",
               "-Wl,-z,max-page-size=4096", f"-Wl,-T,{SDK / 'cmake/app.ld'}",
               "-I", str(SDK / "include"), str(SDK / "lib/start.s"), *map(str, sources), "-lgcc", "-o", str(image)]
    debug_image = output / "app-debug.elf"
    command[-1] = str(debug_image)
    subprocess.run(command, check=True, cwd=project, timeout=120)
    # GCC gives temporary objects random names in the symbol table. Keep those
    # symbols for local debugging, but distribute deterministic load images.
    subprocess.run(["arm-none-eabi-objcopy", "--strip-all", str(debug_image), str(image)], check=True, timeout=30)
    elf_segments(image.read_bytes())
    (output / "build.json").write_text(json.dumps({"compiler": version, "abi": 1,
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest()}, indent=2)+"\n")
    return metadata, image


def package(project):
    metadata, image = build(project)
    destination = project / "build" / f"{metadata['id']}-{metadata['version']}.lfapp"
    destination.write_bytes(pack(metadata, image.read_bytes()))
    unpack(destination.read_bytes())
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    new = sub.add_parser("new")
    new.add_argument("directory", type=Path)
    for name in ("build", "package", "run", "test", "source"):
        child = sub.add_parser(name)
        if name in ("run", "test"):
            child.add_argument("--qemu", type=Path, default=DEFAULT_QEMU)
            child.add_argument("--firmware", type=Path, default=DEFAULT_FIRMWARE)
            child.add_argument("--headless", action="store_true")
    launch = sub.add_parser("launch")
    launch.add_argument("package", type=Path)
    launch.add_argument("--public-key", type=Path, action="append", default=TRUST)
    launch.add_argument("--headless", action="store_true")
    launch.add_argument("--test", action="store_true")
    launch.add_argument("--qemu", type=Path, default=DEFAULT_QEMU)
    launch.add_argument("--firmware", type=Path, default=DEFAULT_FIRMWARE)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("package", type=Path)
    inspect.add_argument("--public-key", type=Path, action="append", default=TRUST)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            compiler = shutil.which("arm-none-eabi-g++")
            version = subprocess.check_output([compiler, "-dumpfullversion"], text=True).strip() if compiler else "missing"
            print(json.dumps({"compiler": version, "required_compiler": "16.2.0", "abi": 1,
                              "physical_install": False, "source_bundles": True, "store_configuration": "not_checked"}, indent=2))
            return 0 if version == "16.2.0" else 1
        if args.command == "new":
            target = args.directory.resolve()
            if target.exists():
                raise ValueError("new project directory must not already exist")
            shutil.copytree(SDK / "templates/basic", target)
            (target / ".gitignore").write_text("/build/\n")
            print(target)
        elif args.command == "launch":
            from runner import run
            return run(args.package.resolve(), args.qemu.resolve(), args.firmware.resolve(), args.headless or args.test, args.test, args.public_key)
        elif args.command == "inspect":
            from signing import MAGIC, verify
            content = args.package.read_bytes()
            metadata, _ = verify(content, args.public_key) if content.startswith(MAGIC) else unpack(content)
            print(json.dumps(metadata, indent=2))
        elif args.command == "source":
            from source import collect
            data = collect(args.project.resolve())
            destination = args.project.resolve() / "build/app.lfsrc"
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(data)
            print(destination)
        elif args.command == "build":
            print(build(args.project.resolve())[1])
        else:
            path = package(args.project.resolve())
            print(path, flush=True)
            if args.command in ("run", "test"):
                from runner import run
                return run(path, args.qemu.resolve(), args.firmware.resolve(),
                           args.headless or args.command == "test", args.command == "test")
        return 0
    except (OSError, ValueError, RuntimeError, PackageError, subprocess.SubprocessError) as exc:
        print(f"lefony-sdk: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
