# SPDX-License-Identifier: GPL-3.0-or-later
"""Add a bounded, non-mutating OS clipboard snapshot in the pinned core.

Embedded Upsilon code retains CC-BY-NC-SA-4.0. The normal storedText method
inserts Poincare placeholders and is unsuitable for a plain-text snapshot.
"""
import argparse
from pathlib import Path


def prepare(source):
    container = source / 'apps/apps_container.cpp'
    old_dispatch = 'bool AppsContainer::dispatchEvent(Ion::Events::Event event) {'
    new_dispatch = '''#if defined(PLATFORM_PRIME_G2)
extern "C" bool prime_g2_native_clipboard_shortcuts();
extern "C" bool prime_g2_present_developer_keys();
extern "C" bool prime_g2_present_archive_approval();
#endif
''' + old_dispatch + '''
#if defined(PLATFORM_PRIME_G2)
  if (event == Ion::Events::NativeKeyApproval) return prime_g2_present_developer_keys();
  if (event == Ion::Events::NativeArchiveApproval) return prime_g2_present_archive_approval();
  // API 10 apps opt into Shift+OK as Cut. The physical Prime has no EXE
  // matrix position; other apps retain normal Shift+OK evaluation.
  if (event == Ion::Events::ShiftOK && prime_g2_native_clipboard_shortcuts())
    event = Ion::Events::Cut;
#endif'''
    content = container.read_text()
    if content.count(new_dispatch) != 1:
        if content.count(old_dispatch) != 1:
            raise ValueError('Unexpected native system dispatch context')
        container.write_text(content.replace(old_dispatch, new_dispatch))
    path = source / 'escher/include/escher/clipboard.h'
    content = path.read_text()
    old = '  const char * storedText();'
    new = old + '''
#if defined(PLATFORM_PRIME_G2)
  int snapshotText(char *buffer, int capacity) const {
    int length = 0;
    while (length < k_bufferSize && m_textBuffer[length]) length++;
    if (!buffer || length == k_bufferSize || capacity <= length) return -1;
    for (int i = 0; i <= length; i++) buffer[i] = m_textBuffer[i];
    return length;
  }
#endif'''
    if content.count(new) == 1:
        return
    if content.count(old) != 1:
        raise ValueError('Unexpected native clipboard context')
    path.write_text(content.replace(old, new))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    prepare(parser.parse_args().source.resolve())
