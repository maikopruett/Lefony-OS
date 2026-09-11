// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app.h"
#include "../apps_container.h"
#include "../apps_window.h"
#include "../../ion/src/prime_g2/native_app.h"
#include "../../ion/src/prime_g2/app_management.h"
#include <ion/timing.h>
#include <string.h>
#include <apps/settings/settings_icon.h>
#include <apps/i18n.h>
namespace NativeApps {
I18n::Message App::Descriptor::name() { return I18n::Message::NativeApps; }
I18n::Message App::Descriptor::upperName() { return I18n::Message::NativeAppsCapital; }
const Image *App::Descriptor::icon() { return ImageStore::SettingsIcon; }
App *App::Snapshot::unpack(Container *container) { return new(container->currentAppBuffer()) App(this); }
App::Descriptor *App::Snapshot::descriptor() { static Descriptor d; return &d; }
App::App(Snapshot *snapshot) : ::App(snapshot,&m_controller), Timer(1) {}
void App::didBecomeActive(Window *window) {
  ::App::didBecomeActive(window);
  static_cast<AppsWindow *>(window)->hideTitleBarView(true);
  setFirstResponder(&m_controller);
  if (PrimeG2::NativeApp::lastResult()==0) PrimeG2::NativeApp::invoke(0);
  AppsContainer::sharedAppsContainer()->addTimer(this);
  if(!PrimeG2::NativeApp::pixels() && PrimeG2::AppManagement::request(0x60,0,nullptr,0)) PrimeG2::AppManagement::acknowledge();
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
    context->drawString("Native apps",KDPoint(8,4),KDFont::SmallFont);
    bool any=false;
    for(unsigned i=0;i<8;i++) {
      const auto &entry=PrimeG2::AppManagement::entry(i);
      if(!entry.bytes) continue;
      any=true;
      KDColor background=i==selected?KDColor::RGB16(0xcffa):Palette::BackgroundHard;
      context->fillRect(KDRect(0,27+i*25,320,25),background);
      char name[37];strlcpy(name,entry.metadata.name,sizeof(name));
      context->drawString(name,KDPoint(8,30+i*25),KDFont::SmallFont,KDColorBlack,background);
    }
    if(!any) context->drawString(PrimeG2::AppManagement::busy()?"Reading app storage...":"Install apps from lefony.com/apps",KDPoint(8,40),KDFont::SmallFont);
    return;
  }
  // Per-row copies preserve the normal view's clip/origin and driver ownership.
  KDColor working[320];
  for(int y=rect.y();y<=rect.bottom() && y<240;y++) {
    if(y<0) continue;
    context->fillRectWithPixels(KDRect(0,y,320,1),pixels+y*320,working);
  }
}
bool App::Controller::activate(unsigned slot) {
  if(!PrimeG2::AppManagement::open(slot)) return false;
  installed=true;PrimeG2::NativeApp::invoke(0);m_view.invalidate();return true;
}
void App::Controller::closeInstalled() {
  if(!installed) return;
  PrimeG2::NativeApp::invoke(4);PrimeG2::AppManagement::close();PrimeG2::NativeApp::unload();installed=false;m_view.invalidate();
}
bool App::Controller::handleEvent(Ion::Events::Event event) {
  if(event==Ion::Events::Back && installed) { closeInstalled();return true; }
  if(!PrimeG2::NativeApp::pixels()) {
    if(installed) closeInstalled();
    if(event==Ion::Events::Up || event==Ion::Events::Down) {
      int direction=event==Ion::Events::Up?-1:1;
      for(unsigned count=0;count<8;count++) { m_view.selected=(m_view.selected+direction+8)%8;if(PrimeG2::AppManagement::entry(m_view.selected).bytes) break; }
      m_view.invalidate();return true;
    }
    if(event==Ion::Events::OK || event==Ion::Events::EXE) { activate(m_view.selected);return true; }
    return false;
  }
  if(event==Ion::Events::Back || event==Ion::Events::Home || event==Ion::Events::OnOff) return false;
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
  if(!PrimeG2::NativeApp::pixels()) {
    int slot=event.y>=27 && event.y<227?(event.y-27)/25:-1;
    unsigned phase=static_cast<unsigned>(event.phase);
    if(phase==0) m_touchSlot=slot;
    if(phase==2) { if(slot>=0 && slot==m_touchSlot) { m_view.selected=slot;activate(slot); } m_touchSlot=-1; }
    if(phase==3) m_touchSlot=-1;
    return true;
  }
  uint32_t coordinates=(static_cast<uint32_t>(event.x)&65535) | (static_cast<uint32_t>(event.y)<<16);
  PrimeG2::NativeApp::invoke(3,coordinates,static_cast<uint32_t>(event.phase)|(event.contacts<<8));
  m_view.invalidate();
  return true;
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
