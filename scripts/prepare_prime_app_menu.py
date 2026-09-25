# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrate installed native apps into the pinned Upsilon home menu."""
from pathlib import Path
import sys
import prepare_prime_home_order
import prepare_prime_home_selection


def prepare(root: Path):
    # Home hides only the final runtime snapshot; built-in hardware shortcuts
    # depend on Settings immediately preceding it in the pinned app list.
    platform=(root/'build/platform.prime_g2.mak').read_text()
    apps=[line for line in platform.splitlines() if line.startswith('EPSILON_APPS =')]
    if len(apps)!=1 or not apps[0].endswith(' settings native_apps'):
        raise ValueError('Unexpected built-in/runtime app ordering')
    def edit(name, old, new):
        p=root/name;s=p.read_text()
        if new in s:return
        if s.count(old)!=1:raise ValueError(f'Unexpected app menu source: {name}: {old[:70]}')
        p.write_text(s.replace(old,new))
    edit('apps/home/controller.cpp','#include "../apps_container.h"','#include "../apps_container.h"\n#include "../native_apps/menu.h"')
    edit('apps/home/controller.cpp','    int index = selectionDataSource()->selectedRow()*k_numberOfColumns+selectionDataSource()->selectedColumn()+1;', '''    int index = selectionDataSource()->selectedRow()*k_numberOfColumns+selectionDataSource()->selectedColumn()+1;
    index = NativeApps::menuIndex(index-1);
    if (index <= 0) return true;
    if (index > NativeApps::builtInCount()) {
      if (GlobalPreferences::sharedGlobalPreferences()->isInExamMode()) {
        App::app()->displayWarning(I18n::Message::ForbiddenAppInExamMode1, I18n::Message::ForbiddenAppInExamMode2);
      } else if (!NativeApps::launchInstalled(NativeApps::slotAt(index-NativeApps::builtInCount()-1))) {
        App::app()->displayWarning(I18n::Message::NativeAppUnavailable);
      }
      return true;
    }''')
    edit('apps/home/controller.cpp','    ::App::Snapshot * selectedSnapshot = container->appSnapshotAtIndex(index);','    ::App::Snapshot * selectedSnapshot = container->appSnapshotAtIndex(PermutedAppSnapshotIndex(index));')
    edit('apps/home/controller.cpp','  int appIndex = (j * k_numberOfColumns + i) + 1;', '''  int appIndex = (j * k_numberOfColumns + i) + 1;
  if (appIndex > numberOfIcons() || (m_homeDragging && appIndex-1==m_homeDragPosition)) {
    appCell->setVisible(false);return;
  }
  appCell->setVisible(true);
  appIndex = NativeApps::menuIndex(appIndex-1);
  if (appIndex > NativeApps::builtInCount()) {
    int slot=NativeApps::slotAt(appIndex-NativeApps::builtInCount()-1);
    appCell->setVisible(slot>=0);
    if (slot>=0) appCell->setInstalledApp(NativeApps::installedName(slot),NativeApps::installedIcon(slot));
    return;
  }''')
    edit('apps/home/controller.cpp','  return container->numberOfApps() - 1;','  (void)container;return NativeApps::menuCount();')
    edit('apps/home/controller.h','  void viewDidDisappear() override;','  void viewDidDisappear() override;\n  bool refreshInstalledApps();')
    edit('apps/home/controller.h','  App * m_app;','  App * m_app;\n  uint32_t m_catalogRevision = 0xffffffffu;')
    edit('apps/home/controller.cpp','View * Controller::view() {', '''bool Controller::refreshInstalledApps() {
  bool dragChanged=refreshHomeDrag();
  if(NativeApps::menuOrderSaveFailed()) App::app()->displayWarning(I18n::Message::StorageMemoryFull1);
  uint32_t revision=NativeApps::catalogRevision();
  if(revision==m_catalogRevision) return dragChanged;
  m_catalogRevision=revision;
  auto *table=m_view.selectableTableView();
  int selected=table->selectedRow()*k_numberOfColumns+table->selectedColumn();
  if(selected<0) selected=0;
  if(selected>=numberOfIcons()) selected=numberOfIcons()-1;
  table->deselectTable();table->reloadData(false);
  table->selectCellAtLocation(selected%k_numberOfColumns,selected/k_numberOfColumns);
  return true;
}

View * Controller::view() {''')
    edit('apps/home/app.h','class App : public ::App {','class App : public ::App, public Timer {')
    edit('apps/home/app.h','  void redraw();','  void redraw();\n  void willBecomeInactive() override;\n  bool fire() override { return m_controller.refreshInstalledApps(); }')
    edit('apps/home/app.cpp','#include "app.h"','#include "app.h"\n#include "../apps_container.h"')
    edit('apps/home/app.cpp','  m_window = window;','  m_window = window;\n  m_controller.refreshInstalledApps();\n  AppsContainer::sharedAppsContainer()->addTimer(this);')
    edit('apps/home/app.cpp','void App::redraw() {', '''void App::willBecomeInactive() {
  AppsContainer::sharedAppsContainer()->removeTimer(this);setNext(nullptr);
  ::App::willBecomeInactive();
}

void App::redraw() {''')
    edit('apps/home/app.cpp','  ::App(snapshot, &m_controller, I18n::Message::Warning),','  ::App(snapshot, &m_controller, I18n::Message::Warning), Timer(1),')
    edit('apps/home/app_cell.h','  void setAppDescriptor(::App::Descriptor * appDescriptor);','  void setAppDescriptor(::App::Descriptor * appDescriptor);\n  void setInstalledApp(const char *name, const Image *icon);')
    edit('apps/home/app_cell.h','  bool m_external_app;','  bool m_external_app;\n  char m_installedName[14];')
    edit('apps/home/app_cell.cpp','#include <assert.h>','#include <assert.h>\n#include <string.h>')
    edit('apps/home/app_cell.cpp','void AppCell::setAppDescriptor(::App::Descriptor * descriptor) {', '''void AppCell::setInstalledApp(const char *name,const Image *icon) {
  strlcpy(m_installedName,name,sizeof(m_installedName));
  if(strlen(name)>=sizeof(m_installedName)) memcpy(m_installedName+10,"...",4);
  setExtAppDescriptor(m_installedName,icon);
  m_external_app=false;reloadCell();
  markRectAsDirty(bounds());
}

void AppCell::setAppDescriptor(::App::Descriptor * descriptor) {''')
    # The hidden runtime stays last in the compiled list. Preserve the existing
    # fixed built-in indices; the Settings shortcut must skip that runtime.
    edit('apps/apps_container.cpp','switchTo(appSnapshotAtIndex(numberOfApps() - 1));','switchTo(appSnapshotAtIndex(numberOfApps() - 2));')

    prepare_prime_home_order.prepare(root,apps[0],edit)
    prepare_prime_home_selection.prepare(edit)

if __name__=='__main__':prepare(Path(sys.argv[1]))
