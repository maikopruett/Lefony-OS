#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Notebook pixel scrolling through Goodix, with ARM clipping and release parity."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, identity, write_json
from cli import package
from files_device import FileClient
from preview import inspect_layout
from replay import Controls
from runner import exercise
from workspace import opened
from sdk_notebook_probe import wait_notebook


def document(count):
    return b'LFNOTE3\nL\n0 0 07\n' + b''.join(f'{i}+100\n'.encode() for i in range(count))


def ink_mask(image):
    # Selection changes the background (and antialias colors), while the
    # foreground glyph coverage must remain identical after translation.
    background = max(image.getcolors(image.width * image.height))[1]
    mask = bytes(pixel != background for pixel in image.getdata())
    assert any(mask), 'Expected a visible portion of the glyph'
    return mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    sdk_identity = identity(ROOT / 'sdk')
    report = {'schema': 1, 'status': 'running', 'physical': 'not_tested',
              'firmware_sha256': digest(args.firmware), 'qemu_sha256': digest(qemu),
              'sdk_sha256': sdk_identity, 'cases': []}
    write_json(output / 'report.json', report)
    try:
        with tempfile.TemporaryDirectory(prefix='sdk-list-scroll-') as temp:
            project = Path(temp) / 'External Notebook é'
            shutil.copytree(ROOT / 'sdk/examples/notebook', project,
                            ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json'))
            for profile in ('debug', 'release'):
                artifact = package(project, profile)
                retained = output / profile
                retained.mkdir(exist_ok=True)
                for name in ('app-debug.elf', 'build.json', artifact.name):
                    shutil.copyfile(project / 'build' / name, retained / name)
                symbols = subprocess.check_output(['arm-none-eabi-nm', str(retained / 'app-debug.elf')], text=True)
                assert ('lefony_ui_debug' in symbols) == (profile == 'debug')
                for name, count in (('long', 12), ('short', 2), ('empty', 0)):
                    folder = retained / name
                    folder.mkdir(exist_ok=True)
                    fixture = folder / 'input.txt'
                    fixture.write_bytes(document(count))
                    case = {'profile': profile, 'name': name, 'steps': [], 'status': 'running'}
                    report['cases'].append(case)
                    write_json(output / 'report.json', report)

                    def prepare(client):
                        FileClient(client).import_file('notebook', 'notebook.txt', fixture)

                    def controls(channel):
                        normal = Controls(channel, folder)
                        frames = {}
                        records = case['steps']

                        def step(action, value):
                            normal.run({'steps': [{action: value}]}, records)

                        def touch(*contacts):
                            step('touch', [list(c) for c in contacts])

                        def tap(x, y):
                            touch((1, x, y))
                            touch()

                        def snapshot(label, *, rows=None, field=None, focused=None, dragging=False):
                            wait_notebook(normal, records)
                            step('capture', label)
                            with Image.open(folder / (label + '.ppm')) as image:
                                frames[label] = image.copy()
                                image.save(folder / (label + '.png'))
                            if rows is not None and 'initial' in frames:
                                assert frames[label].crop((12, 8, 210, 36)).tobytes() == frames['initial'].crop((12, 8, 210, 36)).tobytes(), label + ': unexpected navigation'
                            if profile == 'debug':
                                target = folder / label
                                target.mkdir(exist_ok=True)
                                layout = inspect_layout(normal, retained / 'app-debug.elf', target)
                                nodes = {node['id']: node for node in layout['nodes']}
                                assert not layout['overflow']
                                if rows is not None:
                                    actual = [node for node in layout['nodes'] if node['kind'] == 'list row']
                                    assert [(node['id'] - 100, node['bounds'][1]) for node in actual] == rows, (label, actual)
                                    for node in actual:
                                        y = node['bounds'][1]
                                        assert node['bounds'] == (12, y, 296, 36)
                                        assert node['clip'] == (12, max(60, y), 296, min(176, y + 36) - max(60, y))
                                        assert node['file'].endswith('src/main.cpp') and node['line'] > 0
                                    assert (63 in nodes) == (count > 3), label
                                    if 63 in nodes:
                                        assert nodes[63]['kind'] == 'scrollbar'
                                        assert bool(nodes[63]['state'] & 4) == dragging
                                    assert nodes[50]['name'] == 'Notebook'
                                if field is not None:
                                    assert nodes[10]['name'] == field and nodes[50]['name'] == 'Edit expression'
                                if focused is not None:
                                    assert [n['id'] for n in layout['nodes'] if n['state'] & 2] == [focused], label
                            print('FRAME:', profile, name, label, flush=True)

                        try:
                            snapshot('initial', rows=[(i, 60 + i * 40) for i in range(min(count, 3))])
                            if count == 12:
                                # The four-pixel gap must not open a neighboring row.
                                tap(80, 97)
                                snapshot('gap', rows=[(0, 60), (1, 100), (2, 140)])
                                assert frames['initial'].tobytes() == frames['gap'].tobytes()
                                touch((1, 80, 75))
                                snapshot('pressed', rows=[(0, 60), (1, 100), (2, 140)], focused=100)
                                assert frames['pressed'].crop((12, 60, 308, 96)).tobytes() != frames['initial'].crop((12, 60, 308, 96)).tobytes()
                                touch((1, 80, 58))
                                snapshot('drag17', rows=[(0, 43), (1, 83), (2, 123), (3, 163)], focused=100, dragging=True)
                                # Unselected row text translates exactly, without reflow.
                                assert frames['initial'].crop((20, 144, 290, 174)).tobytes() == frames['drag17'].crop((20, 127, 290, 157)).tobytes()
                                # The clipped focused row retains its vertical border but
                                # must not acquire a horizontal border at the viewport top.
                                assert frames['drag17'].getpixel((295, 60)) == frames['initial'].getpixel((295, 80))
                                assert frames['drag17'].getpixel((13, 60)) != frames['drag17'].getpixel((295, 60))
                                for area in ((0, 0, 320, 60), (0, 176, 320, 240)):
                                    assert frames['initial'].crop(area).tobytes() == frames['drag17'].crop(area).tobytes()
                                touch()
                                snapshot('released17', rows=[(0, 43), (1, 83), (2, 123), (3, 163)], focused=100)
                                assert frames['drag17'].crop((12, 60, 308, 176)).tobytes() == frames['released17'].crop((12, 60, 308, 176)).tobytes()
                                # A subsequent tap can open the partially visible last row.
                                tap(80, 169)
                                snapshot('partial-editor', field='3+100', focused=10)
                                step('key', 'back')
                                snapshot('back', rows=[(1, 60), (2, 100), (3, 140)], focused=103)
                                assert ink_mask(frames['drag17'].crop((20, 167, 290, 176))) == ink_mask(frames['back'].crop((20, 144, 290, 153)))
                                step('key', 'down')
                                snapshot('keyboard-next', rows=[(2, 60), (3, 100), (4, 140)], focused=104)
                                for _ in range(3):
                                    touch((1, 80, 150)); touch((1, 80, 5)); touch()
                                snapshot('bottom', rows=[(9, 60), (10, 100), (11, 140)], focused=111)
                                assert frames['initial'].getpixel((313, 60)) == frames['bottom'].getpixel((313, 175))
                                assert frames['initial'].getpixel((313, 175)) == frames['bottom'].getpixel((313, 60))
                                assert frames['initial'].getpixel((313, 60)) != frames['initial'].getpixel((313, 175))
                                step('key', 'down')
                                snapshot('footer', rows=[(9, 60), (10, 100), (11, 140)], focused=2)
                                step('key', 'up')
                                snapshot('keyboard-return', rows=[(9, 60), (10, 100), (11, 140)], focused=111)
                                # Releasing over the footer after a captured drag cannot
                                # activate New, theme change or export.
                                for _ in range(3):
                                    touch((1, 80, 70)); touch((1, 80, 235)); touch()
                                snapshot('top', rows=[(0, 60), (1, 100), (2, 140)])
                                touch((1, 80, 75)); touch((1, 89, 76)); touch()
                                snapshot('horizontal-cancel', rows=[(0, 60), (1, 100), (2, 140)], focused=100)
                                touch((1, 80, 140)); touch((1, 80, 100))
                                touch((1, 80, 100), (2, 180, 110)); touch((1, 80, 100)); touch()
                                snapshot('multitouch-cancel', rows=[(1, 60), (2, 100), (3, 140)])
                                touch((1, 80, 140)); touch((1, 80, 105)); touch((2, 80, 105)); touch()
                                snapshot('identity-cancel', rows=[(1, 25), (2, 65), (3, 105), (4, 145)])
                                touch((1, 80, 140)); touch((1, 80, 125)); touch((1, 319, 125)); touch()
                                snapshot('outside-cancel', rows=[(2, 50), (3, 90), (4, 130), (5, 170)])
                                tap(80, 100)
                                snapshot('fresh-tap', field='3+100', focused=10)
                                step('key', 'back')
                                snapshot('fresh-back', rows=[(2, 50), (3, 90), (4, 130), (5, 170)], focused=103)
                                # A keyboard event cancels the captured gesture, even if
                                # its release later arrives over a different control.
                                touch((1, 80, 100)); touch((1, 80, 80)); step('key', 'down'); touch()
                                snapshot('key-cancel', rows=[(2, 30), (3, 70), (4, 110), (5, 150)], focused=104)
                                touch((1, 80, 120)); touch((1, 80, 80)); step('key', 'home'); touch()
                                step('relaunch', True)
                                snapshot('relaunch', rows=[(0, 60), (1, 100), (2, 140)], focused=100)
                                tap(80, 75)
                                snapshot('relaunch-tap', field='0+100', focused=10)
                            else:
                                touch((1, 80, 75)); touch((1, 80, 235)); touch()
                                snapshot('clamped-down', rows=[(i, 60 + i * 40) for i in range(count)])
                                touch((1, 80, 75)); touch((1, 80, 0)); touch()
                                snapshot('clamped-up', rows=[(i, 60 + i * 40) for i in range(count)])
                                assert frames['initial'].tobytes() == frames['clamped-up'].tobytes()
                                if count:
                                    tap(80, 110)
                                    snapshot('short-editor', field='1+100', focused=10)
                            normal.key('home')
                            channel.wait_for_storage()
                            destination = folder / 'notebook.txt'
                            FileClient(channel.app_client).export_file('notebook', 'notebook.txt', destination)
                            assert destination.read_bytes() == fixture.read_bytes(), 'Scrolling altered the saved document'
                        finally:
                            normal.close()

                    with opened(project, name + '-' + profile) as (workspace, _):
                        result = exercise(artifact, qemu, args.firmware, controls=controls,
                                          workspace=workspace, prepare_workspace=prepare)
                    assert result['result'] == 1 and result['os_responsive'], result
                    case.update(status='passed', runtime=result)
                    write_json(output / 'report.json', report)
                    print('PASS:', profile, name, flush=True)
            matching = []
            for path in sorted((output / 'debug').rglob('*.ppm')):
                other = output / 'release' / path.relative_to(output / 'debug')
                with Image.open(path) as a, Image.open(other) as b:
                    assert a.size == b.size and a.tobytes() == b.tobytes(), str(path)
                matching.append(str(path.relative_to(output / 'debug')))
        assert sdk_identity == identity(ROOT / 'sdk'), 'SDK changed during qualification'
        report.update(status='passed', matching_frames=matching, sources={
            str(path.relative_to(ROOT)): digest(path) for path in
            [Path(__file__), ROOT / 'sdk/include/lefony/ui_model.h', ROOT / 'sdk/include/lefony/ui_widgets.h',
             ROOT / 'sdk/include/lefony/ui_controls.h', ROOT / 'sdk/examples/notebook/src/main.cpp']})
        write_json(output / 'report.json', report)
    except Exception as exc:
        report.update(status='failed', error=str(exc))
        write_json(output / 'report.json', report)
        raise


if __name__ == '__main__':
    main()
