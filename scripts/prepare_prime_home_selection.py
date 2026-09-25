# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep Home's selection feedback for keypad navigation, not touch scrolling."""


def prepare(edit):
    edit('apps/home/app_cell.h', '  void reloadCell() override;', '''  void reloadCell() override;
  void setSelectionVisible(bool visible) {
    if(m_selectionVisible==visible) return;
    m_selectionVisible=visible;reloadCell();
  }''')
    edit('apps/home/app_cell.h', '  bool m_visible;',
         '  bool m_visible;\n  bool m_selectionVisible=false;')
    edit('apps/home/app_cell.cpp', '''void AppCell::reloadCell() {
  m_nameView.setTextColor(isHighlighted() ? (m_external_app ? Palette::HomeCellTextExternalActive : Palette::HomeCellTextActive) : (m_external_app ? Palette::HomeCellTextExternal : Palette::HomeCellText));
  m_nameView.setBackgroundColor(isHighlighted() ? Palette::HomeCellBackgroundActive : Palette::HomeCellBackground);
}''', '''void AppCell::reloadCell() {
  bool highlighted=m_selectionVisible && isHighlighted();
  m_nameView.setTextColor(highlighted ? (m_external_app ? Palette::HomeCellTextExternalActive : Palette::HomeCellTextActive) : (m_external_app ? Palette::HomeCellTextExternal : Palette::HomeCellText));
  m_nameView.setBackgroundColor(highlighted ? Palette::HomeCellBackgroundActive : Palette::HomeCellBackground);
}''')
    edit('apps/home/controller.h', '  bool handleHomeTouch(const Ion::Touch::Event &touch);', '''  static bool isHomeNavigationEvent(Ion::Events::Event event) {
    using namespace Ion::Events;
    return event==Left || event==Right || event==Up || event==Down ||
      event==ShiftLeft || event==ShiftRight || event==ShiftUp || event==ShiftDown ||
      event==AlphaLeft || event==AlphaRight || event==AlphaUp || event==AlphaDown;
  }
  void setHomeSelectionVisible(bool visible) {
    if(m_homeSelectionVisible==visible) return;
    m_homeSelectionVisible=visible;
    for(auto &cell : m_cells) cell.setSelectionVisible(visible);
    if(visible) {
      // Restore the retained selection even for an arrow at the grid edge,
      // and bring it back onscreen after a touch scroll.
      auto *table=m_view.selectableTableView();
      table->selectCellAtLocation(table->selectedColumn(),table->selectedRow(),false);
    }
  }
  bool m_homeSelectionVisible=false;
  bool handleHomeTouch(const Ion::Touch::Event &touch);''')
    edit('apps/home/controller.cpp', '''    if (event == home_fast_navigation_events[i]) {
      int row''', '''    if (event == home_fast_navigation_events[i]) {
      setHomeSelectionVisible(true);
      int row''')
    edit('apps/home/controller.cpp', '''  return false;
}

void Controller::didBecomeFirstResponder()''', '''  // A clipped arrow still changes touch/keyboard feedback and needs redraw.
  return isHomeNavigationEvent(event);
}

void Controller::didBecomeFirstResponder()''')
