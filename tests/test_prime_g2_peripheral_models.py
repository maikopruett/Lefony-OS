import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("traces", ROOT / "scripts/compare_prime_g2_traces.py")
traces = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(traces)


def test_physical_and_emulator_display_contracts_match():
    physical = json.loads((ROOT / "hardware/prime_g2/decoded/20260831T154107Z.json").read_text())
    emulator = json.loads((ROOT / "hardware/prime_g2/emulator-contract.json").read_text())
    contract = json.loads((ROOT / "hardware/prime_g2/differential-contract.json").read_text())
    assert traces.compare(physical, emulator, contract) == []


def test_all_requested_qemu_models_are_wired_and_migratable():
    source = (ROOT / "vm/qemu/prime_g2_peripherals.c").read_text()
    glue = (ROOT / "vm/patches/qemu-prime-g2-peripherals.patch").read_text()
    for device in ("TYPE_PRIME_G2_KPP", "TYPE_PRIME_G2_GOODIX",
                   "TYPE_PRIME_G2_ILITEK",
                   "TYPE_PRIME_G2_PF1550", "TYPE_PRIME_G2_NAND"):
        assert device in source
        assert device in glue
    assert "TYPE_PRIME_G2_USBOTG" in source
    assert "VMSTATE_UINT64(pressed" in source
    assert "VMSTATE_UINT8_ARRAY(regs, PrimeGoodixState, 0x10000)" in source
    assert "s->move_steps = (s->start_x != s->end_x" in source
    assert "s->start_x + dx * s->move_step / divisor" in source
    assert "VMSTATE_UINT8_V(move_steps, PrimeGoodixState, 2)" in source
    assert 'DEFINE_PROP_BOOL("drive-irq", PrimeGoodixState, drive_irq, true)' in source
    assert "s->drive_irq ? level : 0" in source
    acknowledge = source.index("if (reg == 0x814e && data == 0)")
    schedule = source.index("timer_mod(s->release_timer", acknowledge)
    rearm = source.index("prime_goodix_irq(s, 1);", acknowledge)
    assert rearm < schedule
    assert "PRIME_ILITEK_PACKET_BYTES 43" in source
    assert "s->packet[0] = 0x5a" in source
    assert "s->packet[PRIME_ILITEK_PACKET_BYTES - 1] = -sum" in source
    assert "prime_ilitek_raw_x" in source
    assert "prime_ilitek_begin_swipe" in source
    assert "prime_ilitek_prepare_reply" in source
    assert "s->reply[0] = 0x5a;" in source
    assert "s->command = data" in source
    assert 'object_class_property_add(oc, "host-x1", "uint16"' in source
    assert 'object_class_property_add(oc, "host-ms", "uint16"' in source
    assert 'DEFINE_PROP_BOOL("present", PrimeIlitekState, present, true)' in source
    assert "if (!s->present &&" in source
    assert 'qdev_init_gpio_out_named(DEVICE(obj), &s->irq, "irq", 1)' in source
    assert "qemu_set_irq(s->irq, 1);" in source
    assert "qemu_set_irq(s->irq, 0);" in source
    assert "VMSTATE_TIMER_PTR(move_timer, PrimeIlitekState)" in source
    assert "VMSTATE_UINT8_ARRAY(page_cache,PrimeNANDState,2112)" in source
    assert "VMSTATE_UINT8_ARRAY(page_data,PrimeNANDState" in source
    assert "prime_nand_program_page" in source
    assert "prime_nand_erase_block" in source
    assert "prime_nand_decode_stock_record" in source
    assert "PRIME_NAND_OVERLAY_MAGIC" in source
    assert "prime_nand_overlay_replay" in source
    assert 'DEFINE_PROP_STRING("stock-overlay"' in source
    assert "PRIME_NAND_SPARSE_PAGES 65536" in source
    assert "program_overlay_full" in source
    assert "s->command==0x60" in source
    assert "ERASE1 is followed by three row cycles" in source
    assert "GPMI_MODE_WRITE 0" in source
    assert "capture the clean payload and metadata" in source
    assert "APBH_CH0_CURCMDAR 0x100" in source
    assert "return s->last_descriptor" in source
    assert "PRIME_CAPTURE_METADATA_BYTES 10" in source
    assert "memcpy(destination,record,PRIME_NAND_PAGE_BYTES)" in source
    assert "prime_nand_capture_layout" in source
    assert "prime_nand_swap_marker" in source
    assert "*marker=payload*8+2048*8-begin" in source
    assert "if(!s->apbh_sema||!(bits&APBH_CCW_CHAIN))" in source
    assert "prime_usb_host_setup" in source
    assert "prime_usb_host_in" in source
    assert "prime_usb_host_out" in source
    assert "queue-head overlay" in source
    assert "prime_usb_write32(qh + 4, td)" in source
    assert "prime_usb_write32(qh + 8, next)" in source
    assert "prime_usb_write32(qh + 12, token)" in source
    assert "prime_usb_endpoint_bit" in source
    assert "!(s->endptstat & endpoint_bit)" in source
    assert "PRIME is a" in source and "doorbell and self-clears" in source
    assert "s->endptprime &= ~v" in source
    assert 'g_str_has_prefix(line, "EPIN ")' in source
    assert 'g_str_has_prefix(line, "EPOUT ")' in source
    assert 'qdev_init_gpio_out_named(DEVICE(obj), s->cable, "cable", 2)' in source
    assert "qemu_set_irq(s->cable[0], 1)" in source
    assert "qemu_set_irq(s->cable[1], 1)" in source
    usb_glue = (ROOT / "vm/patches/qemu-prime-g2-usbotg-device.patch").read_text()
    assert 'qdev_connect_gpio_out_named(DEVICE(usbdev), "cable", 0' in usb_glue
    assert "qdev_get_gpio_in(DEVICE(&s->gpio[0]), 0)" in usb_glue
    assert "qdev_get_gpio_in(DEVICE(&s->gpio[0]), 3)" in usb_glue
    assert "VMSTATE_BOOL(connected, PrimeUSBOTGState)" in source


def test_stock_vm_routes_gic_spis_to_cpu0():
    patch = (ROOT / "vm/patches/qemu-prime-g2-stock-boot.patch").read_text()
    assert "HP_PRIME_G2_GICD_ITARGETSR" in patch
    assert "hp_prime_g2_route_spis" in patch
    assert "qemu_register_reset(hp_prime_g2_route_spis, NULL)" in patch


def test_prime_nand_boot_rom_executes_the_captured_boot_contract():
    source = (ROOT / "vm/qemu/prime_g2_peripherals.c").read_text()
    header = (ROOT / "vm/qemu/prime_g2_peripherals.h").read_text()
    patch = (ROOT / "vm/patches/qemu-prime-g2-nand-rom.patch").read_text()
    builder = (ROOT / "vm/build-prime-g2-qemu.sh").read_text()
    qualification = (ROOT / "vm/test-prime-g2-nand-rom-boot.py").read_text()
    for token in (
        "PRIME_ROM_FCB_FINGERPRINT",
        "PRIME_ROM_DBBT_FINGERPRINT",
        "PRIME_ROM_IVT_HEADER",
        "prime_rom_execute_dcd",
        "PRIME_ROM_DCD_WRITE_TAG",
        "address_space_write(&address_space_memory,address",
        "prime_rom_load_firmware(s,fw1",
        "prime_rom_load_firmware(s,fw2",
        "Large-page NAND marks a factory/runtime bad block",
    ):
        assert token in source
    assert "prime_g2_nand_rom_load" in header
    assert "hp_prime_g2_nand_boot" in patch
    assert "hp_prime_g2_enter_sdp" in patch
    assert "NAND_ROM_PATCH" in builder
    assert "test_secondary_firmware_fallback" in qualification
    assert "test_physical_bad_block_marker_is_skipped" in qualification
    assert "test_invalid_fcb_falls_back_to_sdp" in qualification
    assert "test_visible_runtime" in qualification


def test_stock_vm_models_prime_gpt_oscillator_divide_by_eight():
    patch = (ROOT / "vm/patches/qemu-prime-g2-stock-boot.patch").read_text()
    assert "CLK_HIGH_DIV,  /* 101 reference 24 MHz oscillator / 8 */" in patch
    assert "freq = CKIH_FREQ / 8;" in patch


def test_stock_snvs_high_power_rtc_alarm_model_is_persisted():
    patch = (ROOT / "vm/patches/qemu-prime-g2-snvs-hprtc.patch").read_text()
    builder = (ROOT / "vm/build-prime-g2-qemu.sh").read_text()
    for token in (
        "SNVS_HPRTCMR",
        "SNVS_HPRTCLR",
        "SNVS_HPTAMR",
        "SNVS_HPTALR",
        "VMSTATE_TIMER_PTR_V(hp_alarm_timer",
        "VMSTATE_UINT64_V(hp_tick_offset",
        "VMSTATE_TIMER_PTR_V(hp_periodic_timer",
        "imx7_snvs_get_hp_count",
        "timer_new_ns(rtc_clock, imx7_snvs_alarm",
        "timer_new_ns(rtc_clock, imx7_snvs_periodic",
        "HPCR_PI_FREQ_SHIFT",
        "HPSR_PI",
        "s->hpsr &= ~v",
    ):
        assert token in patch
    assert ".version_id = 6" in patch
    assert "SNVS_HPRTC_PATCH" in builder
    assert "qemu-prime-g2-snvs-hprtc.patch" in builder


def test_stock_snvs_interrupt_uses_architectural_gic_input():
    patch = (ROOT / "vm/patches/qemu-prime-g2-snvs-pwrkey.patch").read_text()
    alarm_patch = (ROOT / "vm/patches/qemu-prime-g2-snvs-hprtc.patch").read_text()
    assert "qdev_get_gpio_in(gic, FSL_IMX6UL_SNVS_IRQ)" in patch
    assert "qdev_get_gpio_in(cpu, ARM_CPU_IRQ)" not in patch
    assert "qdev_get_gpio_in(gic, FSL_IMX6UL_SRTC_IRQ)" in alarm_patch
    assert "qemu_set_irq(s->alarm_irq" in alarm_patch
    assert "HPSR_HPTA | HPSR_PI" in alarm_patch


def test_stock_pwm7_counter_advances_for_display_startup_delay():
    patch = (ROOT / "vm/patches/qemu-prime-g2-pwm-counter.patch").read_text()
    builder = (ROOT / "vm/build-prime-g2-qemu.sh").read_text()
    for token in (
        "prime_pwm_enable_ns",
        "offset == 0x14",
        "66000000ULL",
        "NANOSECONDS_PER_SECOND * prescaler",
        "VMSTATE_INT64_V(prime_pwm_enable_ns",
        ".version_id = 3",
    ):
        assert token in patch
    assert "PWM_COUNTER_PATCH" in builder
    assert "qemu-prime-g2-pwm-counter.patch" in builder


def test_nand_geometry_and_partition_evidence():
    contract = json.loads((ROOT / "hardware/prime_g2/emulator-contract.json").read_text())
    nand = contract["nand"]
    assert nand["size"] == sum(part[2] for part in nand["partitions"])
    assert (nand["page_size"], nand["oob_size"], nand["erase_size"]) == (2048, 64, 131072)
    assert nand["contents"] == "erased-synthetic-no-HP-firmware"


def test_native_vm_uses_modeled_kpp_path():
    keyboard = (ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/keyboard.cpp").read_text()
    emulator = (ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/emulator.cpp").read_text()
    proxy = (ROOT / "vm/input-proxy.py").read_text()
    runner = (ROOT / "vm/run-native-vm.sh").read_text()
    assert "scanMatrix(matrix)" in keyboard
    assert "return PrimeG2::Emulator::keyboardState();" not in keyboard
    assert "PrimeG2::reg16(PrimeG2::KPP + 0x08)" not in emulator
    assert "KPP_INGRESS = 0x020B8008" in proxy
    assert "writew 0x{KPP_INGRESS:x}" in proxy
    assert "-qtest" in runner


def test_stock_research_vm_exposes_private_qmp_control_socket():
    runner = (ROOT / "vm/run-hp-prime-stock-vm.sh").read_text()
    assert 'QMP_SOCKET="$RUN_DIR/qmp.sock"' in runner
    assert '-qmp "unix:$QMP_SOCKET,server=on,wait=off"' in runner
    assert 'GDB_SOCKET="$RUN_DIR/gdb.sock"' in runner
    assert '-gdb "unix:$GDB_SOCKET,server=on,wait=off"' in runner
    assert '-global prime-g2-goodix-gt5688.drive-irq=off' in runner
    assert 'prime-g2-ilitek-ili2117.present=off' in runner


def test_built_qemu_peripheral_mmio_black_box():
    if not (ROOT / "build/qemu-prime-g2/qemu-system-arm").exists():
        return
    subprocess.run([sys.executable, str(ROOT / "vm/test-prime-g2-peripherals.py")],
                   cwd=ROOT, check=True, timeout=20, capture_output=True, text=True)
