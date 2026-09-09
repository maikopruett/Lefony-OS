from pathlib import Path
import json
import io
import re
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import capture_prime_g2_rom_usb as capture


class ClockCaptureTests(unittest.TestCase):
    def test_native_whitelist_matches_python(self):
        source = (ROOT / 'scripts/capture_prime_g2_rom_hid.c').read_text()
        for profile, prefix in (('src', 'src'), ('clocks', 'clock'), ('nand-status', 'nand'), ('dma-status', 'dma')):
            addresses = re.search(rf'{prefix}_addresses\[\] = \{{(.*?)\}};', source, re.S)[1]
            names = re.search(rf'{prefix}_names\[\] = \{{(.*?)\}};', source, re.S)[1]
            actual = dict(zip(re.findall(r'"([A-Z0-9_]+)"', names),
                              [int(value, 16) for value in re.findall(r'0x[0-9a-f]+', addresses)]))
            self.assertEqual(actual, capture.REGISTER_PROFILES[profile])
        self.assertEqual(len(capture.REGISTER_PROFILES['clocks']), 14)
        self.assertTrue(all(0x020c4000 <= address <= 0x020c8100
                            for address in capture.REGISTER_PROFILES['clocks'].values()))

    def test_unknown_profile_rejected_before_usb(self):
        with mock.patch.object(capture, 'LibUSB') as usb:
            with self.assertRaises(KeyError):
                capture.capture_registers('0x01808000')
            usb.assert_not_called()

    def test_macos_native_profile_selection_without_privilege(self):
        for profile, key, flags in (('src', 'src_registers', []),
                                    ('clocks', 'clock_registers', ['--clocks']),
                                    ('nand-status', 'nand_registers', ['--nand-status']),
                                    ('dma-status', 'dma_registers', ['--dma-status'])):
            result = {'fixture': profile}
            with mock.patch.object(capture.sys, 'platform', 'darwin'), \
                 mock.patch.object(Path, 'is_file', return_value=True), \
                 mock.patch.object(Path, 'stat', return_value=SimpleNamespace(st_mtime_ns=1)), \
                 mock.patch.object(capture.subprocess, 'run', return_value=SimpleNamespace(
                     stdout=json.dumps({key: result}))) as run:
                self.assertEqual(capture.capture_registers(profile), result)
                command = run.call_args.args[0]
                self.assertEqual(command[1:], flags)
                self.assertNotIn('sudo', command)

    def test_src_api_remains_compatible(self):
        with mock.patch.object(capture, 'capture_registers', return_value={'src': 1}) as registers:
            self.assertEqual(capture.capture_src(), {'src': 1})
            registers.assert_called_once_with('src')

    def test_nand_gate_guard_requires_every_gate(self):
        def enabled(ccgr4, ccgr6):
            return capture.nand_clocks_enabled({'CCM_CCGR4': {'value': hex(ccgr4)},
                                                'CCM_CCGR6': {'value': hex(ccgr6)}})
        self.assertTrue(enabled(0xff00f3ff, 0x00fc33c3))
        self.assertFalse(enabled(0, 0))
        for shift in (12, 24, 26, 28, 30):
            self.assertFalse(enabled(0xff003000 & ~(3 << shift), 0x3c0))
            self.assertFalse(enabled(0xff003000 & ~(2 << shift), 0x3c0))
        for shift in (6, 8):
            self.assertFalse(enabled(0xff003000, 0x3c0 & ~(3 << shift)))
        # Native guard runs before issuing the first NAND-window request.
        source = (ROOT / 'scripts/capture_prime_g2_rom_hid.c').read_text()
        guard = source.index('if (nand && i == 2')
        self.assertLess(guard, source.index('uint8_t command[17]'))
        self.assertIn('0xff003000u', source[guard:guard + 220])
        self.assertIn('0x3c0u', source[guard:guard + 220])

    def test_dma_gate_guard(self):
        for gate in (0, 0x10, 0x20, 0x30):
            self.assertEqual(capture.dma_clock_enabled({'CCM_CCGR0': {'value': hex(gate)}}),
                             gate == 0x30)
        source = (ROOT / 'scripts/capture_prime_g2_rom_hid.c').read_text()
        self.assertLess(source.index('if (dma && i == 1'), source.index('uint8_t command[17]'))

    def test_dma_chain_bounds_and_idle_guard(self):
        words = list(capture.dma_chain_window(0x00901f08, 0))
        self.assertEqual((len(words), words[0], words[-1]), (256, 0x00901c08, 0x00902004))
        for cursor, semaphore in ((0, 0), (0x80000000, 0), (0x00900000, 0),
                                  (0x0091ff04, 0), (0x00901f09, 0), (0x00901f08, 0x10000)):
            with self.assertRaises(capture.USBError):
                capture.dma_chain_window(cursor, semaphore)
        self.assertEqual(list(capture.dma_chain_window(0x00900300, 0))[0], 0x00900000)
        self.assertEqual(list(capture.dma_chain_window(0x0091ff00, 0))[-1], 0x0091fffc)

    def test_existing_output_rejected_before_device_access(self):
        with mock.patch.object(sys, 'argv', ['capture', '--output', str(Path(__file__))]), \
             mock.patch.object(sys, 'stderr', io.StringIO()), \
             mock.patch.object(capture, 'capture') as device:
            with self.assertRaises(SystemExit) as error:
                capture.main()
            self.assertEqual(error.exception.code, 2)
            device.assert_not_called()

    def test_output_and_check_rejected_before_device_access(self):
        with mock.patch.object(sys, 'argv', ['capture', '--output', 'unused', '--check', 'unused']), \
             mock.patch.object(sys, 'stderr', io.StringIO()), \
             mock.patch.object(capture, 'capture') as device:
            with self.assertRaises(SystemExit) as error:
                capture.main()
            self.assertEqual(error.exception.code, 2)
            device.assert_not_called()


if __name__ == '__main__':
    unittest.main()
