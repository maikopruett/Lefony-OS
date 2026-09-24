# SPDX-License-Identifier: GPL-3.0-or-later
"""Checked Home-only drag reordering; does not alter other tables' gestures."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]

def prepare(root,apps,edit):
    names=apps.split('=',1)[1].split()[:-1]
    if len(names)>32 or any(not name.replace('_','').isalnum() for name in names):
        raise ValueError('Unexpected built-in app IDs')
    (root/'apps/native_apps/home_builtin_ids.h').write_text(
        '// Generated stable built-in identities from the checked platform list.\n'
        'static constexpr const char *HomeBuiltinIds[]={'+','.join('"#'+n+'"' for n in names)+'};\n')
    shutil.copyfile(ROOT/'ports/lefony-prime-g2/apps/prime_home_order_impl.h',root/'apps/prime_home_order_impl.h')
    edit('apps/home/controller.cpp','#include "../global_preferences.h"',
         '#include "../global_preferences.h"\n#include <ion/timing.h>\n#include <algorithm>')
    edit('apps/home/controller.cpp','namespace Home {','namespace Home {\n#include <apps/prime_home_order_impl.h>')
    edit('apps/home/controller.h','  int numberOfIcons() const;', '''  bool handleHomeTouch(const Ion::Touch::Event &touch);
  bool refreshHomeDrag();
  void updateHomeDrag(bool scroll);
  void cancelHomeDrag();
  void reloadHomeDrag();
  int homeTouchIndex(int x,int y,bool clamp);
  bool m_homeTouchTracking=false,m_homeDragging=false;
  int m_homeDragStart=-1,m_homeDragPosition=-1,m_homeTouchX=0,m_homeTouchY=0;
  uint64_t m_homeTouchTime=0,m_homeScrollTime=0;
  const Image *m_homeDragIcon=nullptr;
  int numberOfIcons() const;''')
    edit('apps/home/controller.h','    BackgroundView * backgroundView();',
         '    BackgroundView * backgroundView();\n    void showDraggedIcon(const Image *image,int x,int y);\n    void invalidateDrag() { markRectAsDirty(bounds()); }')
    edit('apps/home/controller.h','    SelectableTableViewWithBackground m_selectableTableView;', '''    class HomeTable : public SelectableTableViewWithBackground {
    public:
      using SelectableTableViewWithBackground::SelectableTableViewWithBackground;
      bool handleTouch(const Ion::Touch::Event &touch) override {
        if(static_cast<Controller *>(parentResponder())->handleHomeTouch(touch)) return true;
        return SelectableTableViewWithBackground::handleTouch(touch);
      }
    };
    HomeTable m_selectableTableView;
    ImageView m_dragImage;''')
    edit('apps/home/controller.cpp','''int Controller::ContentView::numberOfSubviews() const {
  return 1;
}''','''int Controller::ContentView::numberOfSubviews() const {
  return 2;
}''')
    edit('apps/home/controller.cpp','''  assert(index == 0);
  return &m_selectableTableView;''','''  assert(index == 0 || index == 1);
  return index==0 ? static_cast<View *>(&m_selectableTableView) : &m_dragImage;''')
    edit('apps/home/controller.cpp','void Controller::viewDidDisappear() {',
         'void Controller::viewDidDisappear() {\n  cancelHomeDrag();')
