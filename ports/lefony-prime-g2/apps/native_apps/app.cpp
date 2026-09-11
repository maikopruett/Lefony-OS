// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app.h"
#include "menu.h"
#include "../global_preferences.h"
#include "../apps_container.h"
#include "../apps_window.h"
#include "../../ion/src/prime_g2/native_app.h"
#include "../../ion/src/prime_g2/app_management.h"
#include <ion/timing.h>
#include <string.h>
#include <apps/i18n.h>
namespace NativeApps {
namespace { bool sInstalledLaunch=false; }
I18n::Message App::Descriptor::name() { return I18n::Message::NativeApps; }
I18n::Message App::Descriptor::upperName() { return I18n::Message::NativeAppsCapital; }
App *App::Snapshot::unpack(Container *container) { return new(container->currentAppBuffer()) App(this); }
App::Descriptor *App::Snapshot::descriptor() { static Descriptor d; return &d; }
App::App(Snapshot *snapshot) : ::App(snapshot,&m_controller), Timer(1) {}
void App::didBecomeActive(Window *window) {
  ::App::didBecomeActive(window);
  static_cast<AppsWindow *>(window)->hideTitleBarView(true);
  setFirstResponder(&m_controller);
  m_controller.installed=sInstalledLaunch;sInstalledLaunch=false;
  if (PrimeG2::NativeApp::lastResult()==0) PrimeG2::NativeApp::invoke(0);
  AppsContainer::sharedAppsContainer()->addTimer(this);
  m_controller.refresh();
}
void App::willBecomeInactive() {
  AppsContainer::sharedAppsContainer()->removeTimer(this); setNext(nullptr);
  if(m_controller.installed) m_controller.closeInstalled();
  else if(PrimeG2::NativeApp::pixels()) PrimeG2::NativeApp::invoke(4);
  ::App::willBecomeInactive();
}
bool App::fire() {
  if(PrimeG2::NativeApp::pixels()) PrimeG2::NativeApp::invoke(2,static_cast<uint32_t>(Ion::Timing::millis()),0);
  m_controller.refresh();return true;
}
void App::SurfaceView::drawRect(KDContext *context,KDRect rect) const {
  auto *pixels=static_cast<const KDColor *>(PrimeG2::NativeApp::pixels());
  if (!pixels) {
    context->fillRect(rect,Palette::BackgroundHard);
    context->drawString("This app could not start.",KDPoint(8,40),KDFont::SmallFont);
    context->drawString("Press Back to return to the menu.",KDPoint(8,65),KDFont::SmallFont);
    return;
  }
  // Per-row copies preserve the normal view's clip/origin and driver ownership.
  KDColor working[320];
  for(int y=rect.y();y<=rect.bottom() && y<240;y++) {
    if(y<0) continue;
    context->fillRectWithPixels(KDRect(0,y,320,1),pixels+y*320,working);
  }
}
void App::Controller::closeInstalled() {
  if(!installed) return;
  PrimeG2::NativeApp::invoke(4);PrimeG2::AppManagement::close();PrimeG2::NativeApp::unload();installed=false;m_view.invalidate();
}
bool App::Controller::handleEvent(Ion::Events::Event event) {
  if(event==Ion::Events::Back || event==Ion::Events::Home || event==Ion::Events::Apps || event==Ion::Events::OnOff) return false;
  if(!PrimeG2::NativeApp::pixels()) return false;
  unsigned key=0;
  using namespace Ion::Events;
  if(event==Left) key=1; else if(event==Right) key=2; else if(event==Up) key=3; else if(event==Down) key=4;
  else if(event==OK || event==EXE) key=5; else if(event==Backspace) key=6; else if(event==Dot) key=26; else if(event==Minus) key=27;
  else {
    const Event digits[]={Zero,One,Two,Three,Four,Five,Six,Seven,Eight,Nine};
    for(unsigned i=0;i<10;i++) if(event==digits[i]) key=16+i;
  }
  PrimeG2::NativeApp::invoke(1,key,0);
  m_view.invalidate();
  return true;
}
bool App::Controller::handleTouch(const Ion::Touch::Event &event) {
  if(!PrimeG2::NativeApp::pixels()) return false;
  uint32_t coordinates=(static_cast<uint32_t>(event.x)&65535) | (static_cast<uint32_t>(event.y)<<16);
  PrimeG2::NativeApp::invoke(3,coordinates,static_cast<uint32_t>(event.phase)|(event.contacts<<8));
  m_view.invalidate();
  return true;
}
bool launchInstalled(int slot) {
  if(slot<0 || slot>=8 || GlobalPreferences::sharedGlobalPreferences()->isInExamMode() || !PrimeG2::AppManagement::open(slot)) return false;
  sInstalledLaunch=true;
  auto *container=AppsContainer::sharedAppsContainer();
  bool switched=container->switchTo(container->appSnapshotAtIndex(container->numberOfApps()-1));
  if(!switched) { sInstalledLaunch=false;PrimeG2::AppManagement::close();PrimeG2::NativeApp::unload(); }
  return switched;
}

}
extern "C" bool prime_g2_launch_native_app() {
  auto *container=AppsContainer::sharedAppsContainer();
  for(int i=0;i<container->numberOfApps();i++) {
    auto *snapshot=container->appSnapshotAtIndex(i);
    if(snapshot->descriptor()->name()==I18n::Message::NativeApps) return container->switchTo(snapshot);
  }
  return false;
}
