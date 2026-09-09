import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'vm/audit-prime-g2-boot.py'
spec = importlib.util.spec_from_file_location('prime_boot_audit', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class BootAuditTests(unittest.TestCase):
    def test_absolute_addresses_and_host_access_are_not_physical_proof(self):
        result = audit.summarize([
            "memory_region_ops_read cpu 0 mr 0x123 addr 0x10 value 0x0 size 4 name 'gpmi'",
            "memory_region_ops_write cpu -1 mr 0x123 addr 0x20 value 0x0 size 4 name 'gpmi'",
            "memory_region_ops_read cpu 0 mr 0x123 addr 0x10 value 0x0 size 4 name 'gpmi'",
            'unimplemented access', 'unimplemented access'])
        self.assertEqual(result['regions']['gpmi'], {
            'read': 2, 'write': 1, 'cpu_indices': [-1, 0], 'addresses': ['0x10', '0x20']})
        self.assertEqual(result['non_mmio_log_lines'], {'unimplemented access': 2})
        self.assertIn('not region offsets', result['warning'])
        self.assertEqual(result['top_accesses'][0], {
            'region': 'gpmi', 'address': '0x10', 'operation': 'read', 'cpu_index': 0, 'count': 2})

    def test_empty_trace_is_not_coverage(self):
        self.assertEqual(audit.summarize([])['regions'], {})
