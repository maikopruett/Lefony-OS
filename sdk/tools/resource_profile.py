# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit VM observations, bound to verified LFAPP0 bytes across loads."""
import hashlib
import re
import struct
from signing import MAGIC, PREFIX_BYTES

SNAPSHOT = struct.Struct('<20I32s')
FIELDS = ('version', 'bytes', 'flags', 'loads', 'finished_loads', 'entries',
          'samples', 'stack_pointer_bytes', 'stack_written_bytes', 'stack_capacity_bytes',
          'heap_reserved_peak_bytes', 'services', 'frames', 'max_slice_ms', 'faults',
          'failure_result', 'code_bytes', 'static_data_bytes', 'fault_pc', 'fault_event', 'lfapp_sha256')


def arm(channel, verified_package):
    # exercise() authenticates the envelope first. Signing does not change the
    # executable identity, so raw preview and installed packages share a target.
    inner = verified_package[PREFIX_BYTES:] if verified_package.startswith(MAGIC) else verified_package
    target = hashlib.sha256(inner).hexdigest()
    if channel.command('APP PROFILE VERSION') != 'VALUE 1':
        raise RuntimeError('Resource profiling requires matching VM firmware with profile version 1')
    if channel.command('APP PROFILE ARM ' + target) != 'OK':
        raise RuntimeError('Could not arm resource profiling before app load')
    import heap_profile
    location=heap_profile.address(inner)
    channel.heap_profile_address=location
    if location is not None:heap_profile.arm(channel,location)
    return target


def snapshot(channel, target):
    reply = channel.command('APP PROFILE SNAPSHOT')
    if not re.fullmatch(r'DATA [0-9a-f]{224}', reply):
        raise RuntimeError('Invalid VM resource snapshot')
    values = dict(zip(FIELDS, SNAPSHOT.unpack(bytes.fromhex(reply[5:]))))
    values['lfapp_sha256'] = values['lfapp_sha256'].hex()
    flags = values.pop('flags')
    version, size = values.pop('version'), values.pop('bytes')
    if (version != 1 or size != SNAPSHOT.size or flags & ~15 or not flags & 1
            or values['lfapp_sha256'] != target or values['stack_capacity_bytes'] != 65536
            or values['stack_pointer_bytes'] > 65536 or values['stack_written_bytes'] > 65536
            or values['finished_loads'] > values['loads']
            or values['heap_reserved_peak_bytes'] not in (0, 8380416)
            or values['code_bytes'] > 1048576 or values['static_data_bytes'] > 974848):
        raise RuntimeError('VM resource snapshot does not match the requested app or contract')
    if not values['loads'] or not values['entries'] or not values['samples']:
        raise RuntimeError('No execution was observed for the requested resource-profile app')
    if values['failure_result'] >= 2**31:
        values['failure_result'] -= 2**32
    if bool(values['faults']) != (values['failure_result'] < 0):
        raise RuntimeError('Inconsistent VM resource failure counters')
    observed = max(values['stack_pointer_bytes'], values['stack_written_bytes'])
    values.update(schema=1, status='observed', method='paint-and-exception-sp',
                  scope='matching-package-loads-through-runner-cleanup',
                  currently_loaded=bool(flags & 2), stack_pointer_out_of_bounds=bool(flags & 4),
                  counters_saturated=bool(flags & 8), stack_observed_bytes=observed,
                  stack_peak_bytes=None, heap_peak_bytes=None,
                  stack_observed_near_capacity=observed >= 65536 * .9,
                  physical='not_tested', timing='instrumented-emulator-only')
    location=getattr(channel,'heap_profile_address',None)
    if location is not None:
        import heap_profile
        values['heap']=heap_profile.snapshot(channel,target,location,values['loads'])
        if values['heap']['status']=='observed':
            values['heap_peak_bytes']=values['heap']['allocated_peak_bytes']
    return values
