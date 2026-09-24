// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app.h"
#include "menu.h"
#include "../global_preferences.h"
#include "../apps_container.h"
#include "../apps_window.h"
#include "../../ion/src/prime_g2/native_app.h"
#include "../../ion/src/prime_g2/app_management.h"
#include "../../ion/src/prime_g2/app_system.h"
#include "../../ion/src/prime_g2/app_channel.h"
#include "../../ion/src/prime_g2/app_developer_key_wire.h"
#include "../../ion/src/prime_g2/app_archive_wire.h"
#include <escher/clipboard.h>
#include <ion/backlight.h>
#include <ion/timing.h>
#include <string.h>
#include <apps/i18n.h>
namespace NativeApps {
namespace { bool sInstalledLaunch=false,sDeveloperKeyLaunch=false,sDeveloperKeyView=false,sArchiveLaunch=false,sArchiveView=false; PrimeG2::AppArchive::ApprovalInfo sArchiveInfo; }
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
  m_controller.developerKeys=sDeveloperKeyLaunch;sDeveloperKeyLaunch=false;sDeveloperKeyView=m_controller.developerKeys;
  m_controller.archiveApproval=sArchiveLaunch;sArchiveLaunch=false;sArchiveView=m_controller.archiveApproval;
  if(!m_controller.developerKeys && !m_controller.archiveApproval) {
    PrimeG2::NativeApp::setForeground(true);
    if (PrimeG2::NativeApp::lastResult()==0) PrimeG2::NativeApp::invoke(0);
  }
  AppsContainer::sharedAppsContainer()->addTimer(this);
  m_controller.refresh();
}
void App::willBecomeInactive() {
  if(m_controller.archiveApproval) {PrimeG2::AppManagement::archiveDismiss();sArchiveView=false;}
  if(m_controller.developerKeys) {PrimeG2::AppManagement::developerKeyDismiss();sDeveloperKeyView=false;}
  PrimeG2::NativeApp::setForeground(false);
  AppsContainer::sharedAppsContainer()->removeTimer(this); setNext(nullptr);
  if(m_controller.installed) m_controller.closeInstalled();
  else if(PrimeG2::NativeApp::pixels()) PrimeG2::NativeApp::invoke(4);
  ::App::willBecomeInactive();
}
bool App::fire() {
  if(m_controller.developerKeys || m_controller.archiveApproval) {m_controller.refresh();return true;}
  PrimeG2::NativeApp::noteUITimer();
  bool pairing=PrimeG2::AppChannel::pairing();
  if(pairing || m_pairingVisible) {m_pairingVisible=pairing;m_controller.refresh();return true;}
  // Resumable programs have their own low-priority wake event. A UI timer
  // must not overwrite an input snapshot the running program has yet to read.
  if(PrimeG2::NativeApp::resumable()) return false;
  if(PrimeG2::NativeApp::pixels()) PrimeG2::NativeApp::invoke(2,static_cast<uint32_t>(Ion::Timing::millis()),0);
  m_controller.refresh();return true;
}
void App::SurfaceView::drawRect(KDContext *context,KDRect rect) const {
  if(sArchiveView) {
    using namespace PrimeG2;auto status=AppManagement::archiveStatus();const auto &info=sArchiveInfo;
    context->fillRect(rect,Palette::BackgroundHard);
    context->drawString("Restore recovery pair?",KDPoint(12,2),KDFont::LargeFont);
    char id[2][33]{};unsigned n=strlen(info.id);
    memcpy(id[0],info.id,n<32?n:32);if(n>32) memcpy(id[1],info.id+32,n-32);
    context->drawString(id[0],KDPoint(12,23),KDFont::SmallFont);
    context->drawString(id[1],KDPoint(12,35),KDFont::SmallFont);
    auto fingerprint=[&](const uint8_t *hash,int y) {
      static const char hex[]="0123456789abcdef";char lines[2][33]{};
      for(unsigned i=0;i<32;i++) {lines[i/16][(i%16)*2]=hex[hash[i]>>4];lines[i/16][(i%16)*2+1]=hex[hash[i]&15];}
      context->drawString(lines[0],KDPoint(12,y),KDFont::SmallFont);
      context->drawString(lines[1],KDPoint(12,y+12),KDFont::SmallFont);
    };
    auto version=[&](const char *name,const uint32_t *parts,int y) {
      char label[40]{};unsigned at=strlen(name);memcpy(label,name,at);
      for(unsigned part=0;part<3;part++) {
        if(part) label[at++]='.';
        bool started=false;
        for(uint32_t divisor=100000;divisor;divisor/=10) {
          unsigned digit=(parts[part]/divisor)%10;
          if(digit || started || divisor==1) {label[at++]=char('0'+digit);started=true;}
        }
      }
      context->drawString(label,KDPoint(12,y),KDFont::SmallFont);
    };
    version("Current ",info.version,50);fingerprint(info.currentSigner,64);
    version("Rollback ",info.previousVersion,94);fingerprint(info.previousSigner,108);
    context->drawString("Archive SHA-256",KDPoint(12,138),KDFont::SmallFont);fingerprint(info.digest,152);
    using S=AppArchive::TransferState;
    const char *message=status.sequence!=info.sequence?"Finished. Back to leave.":
      status.state==S::AwaitUser?"OK: allow pair    Back: cancel":
      status.state==S::Ready?"Approved. Waiting for host.":status.state==S::Complete?"Restored. Back to leave.":
      status.state==S::Working?"Finishing archive operation...":"Not restored. Back to leave.";
    context->drawString(message,KDPoint(12,189),KDFont::SmallFont);
    context->drawString("Rollback restores the old signer.",KDPoint(12,211),KDFont::SmallFont);
    AppManagement::archiveRendered();return;
  }
  if(sDeveloperKeyView) {
    using namespace PrimeG2;auto status=AppManagement::developerKeyStatus();
    context->fillRect(rect,Palette::BackgroundHard);
    if(status.operation==AppDeveloperKeys::Operation::RecoverInstall) {
      auto info=AppManagement::developerKeyRecoveryInfo();
      context->drawString("Recover private app",KDPoint(12,4),KDFont::LargeFont);
      char id[2][25]{};unsigned n=strlen(info.appId);
      memcpy(id[0],info.appId,n<24?n:24);if(n>24) memcpy(id[1],info.appId+24,n-24);
      context->drawString(id[0],KDPoint(12,26),KDFont::SmallFont);
      context->drawString(id[1],KDPoint(12,40),KDFont::SmallFont);
      context->drawString(info.version,KDPoint(12,54),KDFont::SmallFont);
      const uint8_t *values[3]={info.oldSigner,status.id,info.packageHash};
      const char *labels[3]={"Old key (revoked)","New signing key","Package SHA-256"};
      const char *digits="0123456789abcdef";
      for(unsigned row=0;row<3;row++) {
        context->drawString(labels[row],KDPoint(12,70+44*row),KDFont::SmallFont);
        char lines[2][33]{};
        for(unsigned i=0;i<32;i++) {lines[i/16][2*(i%16)]=digits[values[row][i]>>4];lines[i/16][2*(i%16)+1]=digits[values[row][i]&15];}
        context->drawString(lines[0],KDPoint(12,84+44*row),KDFont::SmallFont);
        context->drawString(lines[1],KDPoint(12,98+44*row),KDFont::SmallFont);
      }
      using S=AppDeveloperKeys::State;
      const char *message=status.state==S::AwaitUser?"OK: recover app    Back: cancel":
        status.state==S::Working?"Recovering app...":status.state==S::Complete?"App recovered. Back: menu":"Request ended. Check SDK status.";
      context->drawString(message,KDPoint(12,210),KDFont::SmallFont);
      AppManagement::developerKeyRendered();return;
    }
    if(status.operation==AppDeveloperKeys::Operation::Repair || status.operation==AppDeveloperKeys::Operation::RepairUnreadable) {
      bool unreadable=status.operation==AppDeveloperKeys::Operation::RepairUnreadable;
      context->drawString(unreadable?"Repair unreadable keys":"Repair developer keys",KDPoint(12,4),KDFont::LargeFont);
      context->drawString(status.label,KDPoint(12,28),KDFont::SmallFont);
      const uint8_t *values[2]={status.id,reinterpret_cast<const uint8_t *>(status.reserved)};
      const char *labels[2]={"Public key to trust",unreadable?"Partial backup SHA-256":"Damaged registry SHA-256"};
      const char *digits="0123456789abcdef";
      for(unsigned row=0;row<2;row++) {
        context->drawString(labels[row],KDPoint(12,48+52*row),KDFont::SmallFont);char lines[2][33]{};
        for(unsigned i=0;i<32;i++) {lines[i/16][2*(i%16)]=digits[values[row][i]>>4];lines[i/16][2*(i%16)+1]=digits[values[row][i]&15];}
        context->drawString(lines[0],KDPoint(12,64+52*row),KDFont::SmallFont);
        context->drawString(lines[1],KDPoint(12,78+52*row),KDFont::SmallFont);
      }
      using S=AppDeveloperKeys::State;
      const char *message=status.state==S::AwaitUser?"OK: rebuild trust    Back: cancel":
        status.state==S::Working?"Repairing registry...":status.state==S::Complete?"Registry repaired. Back: menu":"Request ended. Check SDK status.";
      context->drawString(message,KDPoint(12,162),KDFont::SmallFont);
      if(unreadable) context->drawString("Backup omits unreadable bytes.",KDPoint(12,180),KDFont::SmallFont);
      context->drawString("Other keys need re-enrollment.",KDPoint(12,194),KDFont::SmallFont);
      context->drawString("Installed apps/data are preserved.",KDPoint(12,212),KDFont::SmallFont);
      AppManagement::developerKeyRendered();return;
    }
    bool removing=status.operation==AppDeveloperKeys::Operation::Remove;
    context->drawString("Lefony developer key",KDPoint(12,10),KDFont::LargeFont);
    context->drawString(status.operation==AppDeveloperKeys::Operation::Enroll?"Allow privately signed apps?":
      removing?"Remove this unused revoked key?":"Revoke this developer key?",KDPoint(12,40),KDFont::SmallFont);
    context->drawString(status.label,KDPoint(12,62),KDFont::SmallFont);
    const char *digits="0123456789abcdef";char fingerprint[2][33]{};
    for(unsigned i=0;i<32;i++) {fingerprint[i/16][2*(i%16)]=digits[status.id[i]>>4];fingerprint[i/16][2*(i%16)+1]=digits[status.id[i]&15];}
    context->drawString("Compare this fingerprint on the host:",KDPoint(12,87),KDFont::SmallFont);
    context->drawString(fingerprint[0],KDPoint(12,108),KDFont::SmallFont);
    context->drawString(fingerprint[1],KDPoint(12,126),KDFont::SmallFont);
    const char *message="Request ended. Check SDK status.";
    using S=AppDeveloperKeys::State;
    if(status.state==S::AwaitUser) message="OK: approve     Back: cancel";
    else if(status.state==S::Working) message="Saving key change...";
    else if(status.state==S::Complete) message="Key change complete. Back: menu";
    else if(status.state==S::Cancelled || status.state==S::Denied) message="Cancelled. Back: menu";
    else if(status.state==S::Expired) message="Request expired. Back: menu";
    context->drawString(message,KDPoint(12,182),KDFont::SmallFont);
    context->drawString(status.operation==AppDeveloperKeys::Operation::Enroll?"Only approve a key you control.":
      removing?"Installed recovery pairs are protected.":"Saved data stays available for export.",KDPoint(12,212),KDFont::SmallFont);
    AppManagement::developerKeyRendered();return;
  }
  if(PrimeG2::AppChannel::pairing()) {
    auto info=PrimeG2::AppChannel::info();
    context->fillRect(rect,Palette::BackgroundHard);
    context->drawString("Lefony USB connection",KDPoint(12,18),KDFont::LargeFont);
    context->drawString("Allow this app to use the companion?",KDPoint(12,55),KDFont::SmallFont);
    context->drawString(info.appName,KDPoint(12,82),KDFont::SmallFont);
    context->drawString(info.hostLabel,KDPoint(12,108),KDFont::SmallFont);
    char code[7]={};uint32_t value=info.nonce[0]%1000000;
    for(int i=5;i>=0;i--) {code[i]='0'+value%10;value/=10;}
    context->drawString("Compare code on your computer:",KDPoint(12,135),KDFont::SmallFont);
    context->drawString(code,KDPoint(12,158),KDFont::LargeFont);
    context->drawString("OK: allow once     Back: deny",KDPoint(12,208),KDFont::SmallFont);
    return;
  }
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
  // The printed Setup/Info variants of the reserved Home/Apps keys stay with
  // the OS too. App input must not swallow them when Shift is latched.
  const bool systemNavigation=event==Ion::Events::Home || event==Ion::Events::ShiftHome ||
    event==Ion::Events::Apps || event==Ion::Events::PrimeInfo || event==Ion::Events::OnOff;
  if(archiveApproval) {
    if(systemNavigation || event==Ion::Events::Back) {
      PrimeG2::AppManagement::archiveDismiss();return false;
    }
    if(event==Ion::Events::OK) PrimeG2::AppManagement::archiveApprove();
    m_view.invalidate();return true;
  }
  if(developerKeys) {
    if(systemNavigation || event==Ion::Events::Back) {
      PrimeG2::AppManagement::developerKeyDismiss();return false;
    }
    if(event==Ion::Events::OK) PrimeG2::AppManagement::developerKeyApprove();
    m_view.invalidate();return true;
  }
  if(PrimeG2::AppChannel::pairing()) {
    if(systemNavigation) {
      PrimeG2::AppChannel::consent(false);return false;
    }
    if(event==Ion::Events::OK || event==Ion::Events::EXE) PrimeG2::AppChannel::consent(true);
    else if(event==Ion::Events::Back) PrimeG2::AppChannel::consent(false);
    m_view.invalidate();return true;
  }
  if(event==Ion::Events::NativeAppResume) {
    if(PrimeG2::NativeApp::resumeForeground()) m_view.invalidate();return true;
  }
  if(systemNavigation) return false;
  if(event==Ion::Events::Back && !PrimeG2::NativeApp::navigationDepth()) return false;
  if(!PrimeG2::NativeApp::pixels()) return false;
  unsigned key=0;
  using namespace Ion::Events;
  if(event==Left) key=1; else if(event==Right) key=2; else if(event==Up) key=3; else if(event==Down) key=4;
  else if(event==OK || event==EXE) key=5; else if(event==Backspace) key=6; else if(event==Dot) key=26; else if(event==Minus) key=27;
  else {
    const Event digits[]={Zero,One,Two,Three,Four,Five,Six,Seven,Eight,Nine};
    for(unsigned i=0;i<10;i++) if(event==digits[i]) key=16+i;
  }
  Lefony::InputSnapshot input;input.event=1;input.key=static_cast<Lefony::InputKey>(key);
  const Event extended[]={Plus,Multiplication,Division,Power,LeftParenthesis,RightParenthesis,Square,Sqrt,
    Ln,Log,Sine,Cosine,Tangent,EE,Shift,Alpha,XNT,Var,Ion::Events::Toolbox,Comma,Back,Arcsine,Arccosine,Arctangent,Pi,Exp};
  for(unsigned i=0;i<sizeof(extended)/sizeof(extended[0]);i++)
    if(event==extended[i]) input.key=static_cast<Lefony::InputKey>(28+i);
  if(event.isKeyboardEvent()) {
    unsigned page=event.id()/Event::PageSize,base=event.id()%Event::PageSize;
    input.modifiers=(page&1?uint32_t(Lefony::InputShift):0u)|(page&2?uint32_t(Lefony::InputAlpha):0u)|(isLockActive()?uint32_t(Lefony::InputAlphaLock):0u);
    // Modifier navigation keeps a logical arrow/Delete token for selection;
    // original ABI 1 first/second values above remain unchanged.
    const Ion::Keyboard::Key navigation[]={Ion::Keyboard::Key::Left,Ion::Keyboard::Key::Right,
      Ion::Keyboard::Key::Up,Ion::Keyboard::Key::Down,Ion::Keyboard::Key::OK,Ion::Keyboard::Key::Backspace};
    for(unsigned i=0;i<sizeof(navigation)/sizeof(navigation[0]);i++)
      if(base==static_cast<unsigned>(navigation[i])) input.key=static_cast<Lefony::InputKey>(1+i);
#define PRIME_G2_KEY(name, evdev, ion, row, col) \
    if(row<8 && col<8 && base==static_cast<unsigned>(Ion::Keyboard::Key::ion)) input.physicalKey=row*8+col;
#include "../../ion/src/prime_g2/keymap.inc"
#undef PRIME_G2_KEY
  }
  // Copy/Cut/Paste retain their logical gesture after modifier navigation.
  if(event==Copy) input.key=Lefony::InputKey::Copy;
  else if(event==Paste) input.key=Lefony::InputKey::Paste;
  else if(event==Cut) {
    input.key=Lefony::InputKey::Cut;
    // The API 10 dispatcher translated physical Shift+OK to the otherwise
    // unmapped EXE-based Cut event. Preserve the actual Prime key position.
    input.physicalKey=7*8;
  }
  int repeat=repetitionFactor();input.repeatFactor=repeat>0?(repeat<65536?repeat:65535):1;
  if(event.hasText()) {
    const char *text=event.text();unsigned length=0;
    if(text) while(length<33 && text[length]) length++;
    if(text && length<=sizeof(input.text) && Lefony::validInputText(text,length)) {
      input.textBytes=length;memcpy(input.text,text,length);
    } else input.flags|=Lefony::TextUnavailable;
  }
  PrimeG2::NativeApp::prepareInput(input);
  PrimeG2::NativeApp::invoke(1,key,0);
  m_view.invalidate();
  return true;
}
bool App::Controller::handleTouch(const Ion::Touch::Event &event) {
  if(developerKeys || archiveApproval) return true;
  if(PrimeG2::AppChannel::pairing()) return true;
  if(!PrimeG2::NativeApp::pixels()) return false;
  uint32_t coordinates=(static_cast<uint32_t>(event.x)&65535) | (static_cast<uint32_t>(event.y)<<16);
  Lefony::InputSnapshot input;input.event=3;input.touchPhase=static_cast<uint32_t>(event.phase);
  input.contactCount=(event.phase==Ion::Touch::Phase::Up || event.phase==Ion::Touch::Phase::Cancel)?0:event.contacts;
  input.contacts[0]={event.id,event.x,event.y};
  if(event.contacts==2) input.contacts[1]={event.id2,event.x2,event.y2};
  input.flags=event.contactsChanged?uint32_t(Lefony::ContactsChanged):0u;
  PrimeG2::NativeApp::prepareInput(input);
  PrimeG2::NativeApp::invoke(3,coordinates,static_cast<uint32_t>(event.phase)|(event.contacts<<8));
  m_view.invalidate();
  return true;
}
bool launchInstalled(int slot) {
  if(slot<0 || static_cast<unsigned>(slot)>=PrimeG2::AppManagement::count() || GlobalPreferences::sharedGlobalPreferences()->isInExamMode() || !PrimeG2::AppManagement::open(slot)) return false;
  sInstalledLaunch=true;
  auto *container=AppsContainer::sharedAppsContainer();
  bool switched=container->switchTo(container->appSnapshotAtIndex(container->numberOfApps()-1));
  if(!switched) { sInstalledLaunch=false;PrimeG2::AppManagement::close();PrimeG2::NativeApp::unload(); }
  return switched;
}

}
extern "C" bool prime_g2_present_developer_keys() {
  auto *container=AppsContainer::sharedAppsContainer();auto *active=container->activeApp();
  // Start from Home so a host cannot interrupt another application's edits.
  if(!active || container->appIndexFromSnapshot(active->snapshot())!=0 ||
     GlobalPreferences::sharedGlobalPreferences()->isInExamMode() || PrimeG2::AppManagement::hasOpen()) {
    PrimeG2::AppManagement::developerKeyDeny();return true;
  }
  if(!PrimeG2::AppManagement::developerKeyPresent()) return true;
  PrimeG2::NativeApp::unload();NativeApps::sDeveloperKeyLaunch=true;
  if(!container->switchTo(container->appSnapshotAtIndex(container->numberOfApps()-1))) {
    NativeApps::sDeveloperKeyLaunch=false;PrimeG2::AppManagement::developerKeyDismiss();
  }
  return true;
}
extern "C" bool prime_g2_present_archive_approval() {
  auto *container=AppsContainer::sharedAppsContainer();auto *active=container->activeApp();
  if(!active || container->appIndexFromSnapshot(active->snapshot())!=0 ||
     GlobalPreferences::sharedGlobalPreferences()->isInExamMode() || PrimeG2::AppManagement::hasOpen()) {
    PrimeG2::AppManagement::archiveDeny();return true;
  }
  if(!PrimeG2::AppManagement::archivePresent()) return true;
  PrimeG2::NativeApp::unload();NativeApps::sArchiveInfo=PrimeG2::AppManagement::archiveApprovalInfo();NativeApps::sArchiveLaunch=true;
  if(!container->switchTo(container->appSnapshotAtIndex(container->numberOfApps()-1))) {
    NativeApps::sArchiveLaunch=false;PrimeG2::AppManagement::archiveDismiss();
  }
  return true;
}
extern "C" void prime_app_system_preferences(LefonySystemInfo *info) {
  const KDColor colors[]={Palette::PrimaryText,Palette::SecondaryText,Palette::BackgroundHard,
    Palette::BackgroundApps,Palette::ControlEnabled,Palette::ControlDisabled,
    Palette::ListCellBackgroundSelected,Palette::BatteryLow};
  for(unsigned i=0;i<8;i++) info->colors[i]=static_cast<uint16_t>(colors[i]);
  auto *p=Poincare::Preferences::sharedPreferences();
  info->angleUnit=static_cast<uint32_t>(p->angleUnit());
  info->displayMode=static_cast<uint32_t>(p->displayMode());
  info->complexFormat=static_cast<uint32_t>(p->complexFormat());
  info->editionMode=static_cast<uint32_t>(p->editionMode());
  info->significantDigits=p->numberOfSignificantDigits();
  auto *g=GlobalPreferences::sharedGlobalPreferences();info->unitFormat=static_cast<uint32_t>(g->unitFormat());
  unsigned language=static_cast<unsigned>(g->language());
  if(language<I18n::NumberOfLanguages) {
    const char *code=I18n::LanguageISO6391Codes[language];
    info->language[0]=code[0];info->language[1]=code[1];
  }
}
extern "C" uint32_t prime_app_system_brightness() {
  return GlobalPreferences::sharedGlobalPreferences()->brightnessLevel();
}
extern "C" void prime_app_system_set_brightness(uint32_t value) {
  GlobalPreferences::sharedGlobalPreferences()->setBrightnessLevel(value);
  Ion::Backlight::setBrightness(value);
}
extern "C" int prime_app_system_clipboard_read(char *buffer,uint32_t capacity) {
  static_assert(Clipboard::k_bufferSize==LEFONY_CLIPBOARD_MAXIMUM+1,"clipboard bound changed");
  return Clipboard::sharedClipboard()->snapshotText(buffer,capacity);
}
extern "C" void prime_app_system_clipboard_write(const char *buffer,uint32_t length) {
  Clipboard::sharedClipboard()->store(buffer,length);
}
extern "C" bool prime_g2_launch_native_app() {
  auto *container=AppsContainer::sharedAppsContainer();
  for(int i=0;i<container->numberOfApps();i++) {
    auto *snapshot=container->appSnapshotAtIndex(i);
    if(snapshot->descriptor()->name()==I18n::Message::NativeApps) return container->switchTo(snapshot);
  }
  return false;
}
#if PRIME_G2_EMULATOR
extern "C" bool prime_g2_launch_installed_native_app(unsigned slot) {
  return NativeApps::launchInstalled(static_cast<int>(slot));
}
#endif
