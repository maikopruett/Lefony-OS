#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run actual mixed C/C++ packages through signed install and normal input."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from cli import package
from build import write_json
from replay import Controls
from runner import exercise
from workspace import opened
from source import collect, extract


def main():
    output = ROOT / 'build/sdk-c-qualification'
    output.mkdir(parents=True, exist_ok=True)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    firmware = ROOT / 'dist/lefony-os-prime-g2-vm-native.elf'
    cases = []
    with tempfile.TemporaryDirectory(prefix='lefony C é ') as directory:
        project = Path(directory)
        (project / 'src').mkdir()
        write_json(project / 'app.json', {'abi': 1, 'id': 'c-proof', 'name': 'C proof',
                   'version': '0.1.0', 'license': 'CC-BY-NC-SA-4.0'})
        (project / 'src/main.c').write_text('''
#include <lefony/app_c.h>
_Static_assert(sizeof(lefony_rect_t) == 20, "rectangle wire");
_Static_assert(sizeof(lefony_text_t) == 24, "text wire");
_Static_assert(sizeof(lefony_data_transfer_t) == 12, "data wire");
extern unsigned cpp_value(unsigned value);
static uint32_t value;
void lefony_event(lefony_event_t event, uint32_t first, uint32_t second) {
  (void)second;
  _Static_assert(_Generic(event, uint32_t: 1, default: 0), "C11 frontend");
  if (event == LEFONY_START) {
    value = 0;
    int32_t result = lefony_read_data(0, &value, sizeof(value));
    if (result < 0) value = 0;
    if (lefony_service(1, (const void *)0x82000000) != -4) __asm__ volatile("udf #0");
  }
  if (event == LEFONY_KEY && first == LEFONY_KEY_CONFIRM) {
    value = cpp_value(17);
    if (value != 72 || lefony_write_data(0, &value, sizeof(value)) != sizeof(value)) __asm__ volatile("udf #0");
  }
  lefony_rect_t rectangle = {.x=0, .y=0, .width=320, .height=240,
                            .color=value == 72 ? LEFONY_GREEN : LEFONY_WHITE};
  if (lefony_fill(rectangle) < 0) __asm__ volatile("udf #0");
  (void)lefony_millis();
}
''')
        (project / 'src/helper.cpp').write_text('''
template<typename T> constexpr T transform(T value) { return value * 4 + 4; }
extern "C" unsigned cpp_value(unsigned value) { return transform(value); }
''')
        write_json(project / 'project.json', {'schema': 1, 'sources': ['src/main.c', 'src/helper.cpp'],
                   'defines': {'LEFONY_C_PROJECT': 1}, 'c_flags': ['-fwrapv']})
        (project / 'src/unused.c').write_text('Excluded platform source must not be compiled.\n')
        original = package(project).read_bytes()
        snapshot = collect(project, 2)
        restored = project / 'restored'
        extract(snapshot, restored)
        artifact = package(restored)
        assert artifact.read_bytes() == original
        assert collect(restored, 2) == snapshot
        project = restored
        for cold in range(2):
            def controls(channel, cold=cold):
                normal = Controls(channel, output)
                try:
                    steps = []
                    if cold == 0:
                        steps += [{'capture': 'initial'}, {'pixel': ['initial', 20, 20, [255,255,255]]},
                                  {'key': 'ok'}]
                    steps += [{'capture': f'cold-{cold}'},
                              {'pixel': [f'cold-{cold}', 20, 20, [33,166,66]]}]
                    normal.run({'steps': steps}, [])
                finally:
                    normal.close()
            with opened(project, 'c-persistence') as (workspace, _):
                result = exercise(artifact, qemu, firmware, workspace=workspace, controls=controls)
                assert result['result'] == 1 and result['os_responsive']
                cases.append(result)
        write_json(output / 'report.json', {'schema': 1, 'status': 'passed',
                   'validation': 'developer-local', 'physical': 'not_tested',
                   'language_profile': 'Configured C11 and C++17; source 2 roundtrip; ABI 1 callbacks',
                   'build': json.loads((project / 'build/build.json').read_text()), 'cases': cases})
        publication = output / 'publication/build'
        publication.mkdir(parents=True, exist_ok=True)
        (publication / artifact.name).write_bytes(artifact.read_bytes())
        (publication / 'app.lfsrc').write_bytes(snapshot)
    print('PASS: configured C11/C++17 source 2 roundtrip, signed installation, normal key input, checked services and cold persistence')


if __name__ == '__main__':
    main()
