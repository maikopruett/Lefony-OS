"""Checked integration of the physical LCD refresh menu into Brightness Settings."""
from pathlib import Path
import argparse


def prepare(source):
    def edit(name, old, new):
        path = source / name
        text = path.read_text()
        if new in text:
            return
        if text.count(old) != 1:
            raise ValueError(f"Unexpected brightness context {name}: {old}")
        path.write_text(text.replace(old, new))

    edit('apps/settings/main_controller.cpp', 's_brightnessChildren[4]', 's_brightnessChildren[5]')
    edit('apps/settings/main_controller.h', 's_brightnessChildren[4]', 's_brightnessChildren[5]')
    edit('apps/settings/main_controller.cpp', 'SettingsMessageTree(I18n::Message::BrightnessShortcut)}',
         'SettingsMessageTree(I18n::Message::BrightnessShortcut), SettingsMessageTree(I18n::Message::LefonyRefreshRate)}')
    base = 'apps/settings/sub_menu/brightness_controller.'
    edit(base + 'h', 'k_totalNumberOfCell = 4', 'k_totalNumberOfCell = 5')
    edit(base + 'h', '  MessageTableCellWithGauge m_brightnessCell;',
         '  MessageTableCellWithChevron<> m_refreshCell;\n  MessageTableCellWithGauge m_brightnessCell;')
    edit(base + 'cpp', '#include "brightness_controller.h"',
         '#include "brightness_controller.h"\n#include "lefony_refresh_controller.h"')
    edit(base + 'cpp', '    &m_BrightnessShortcutCell\n', '    &m_BrightnessShortcutCell,\n    &m_refreshCell\n')
    edit(base + 'cpp', '  if(index == 0){', '''  if (index == 4) {
    m_refreshCell.setMessage(I18n::Message::LefonyRefreshRate);
    m_refreshCell.setMessageFont(KDFont::LargeFont);
    return;
  }
  if(index == 0){''')
    edit(base + 'cpp', 'bool BrightnessController::handleEvent(Ion::Events::Event event) {',
         '''bool BrightnessController::handleEvent(Ion::Events::Event event) {
    if (selectedRow() == 4 && (event == Ion::Events::OK || event == Ion::Events::EXE || event == Ion::Events::Right)) {
      showLefonyRefreshController();
      return true;
    }''')
    path = source / 'apps/settings/base.universal.i18n'
    text = path.read_text()
    if 'LefonyRefreshRate =' not in text:
        path.write_text(text.rstrip() + '\nLefonyRefreshRate = "LCD refresh rate"\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    prepare(parser.parse_args().source.resolve())
