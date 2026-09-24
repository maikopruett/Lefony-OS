// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_INSTALL_PROGRESS_H
#define LEFONY_APP_INSTALL_PROGRESS_H
#include <stdint.h>
#include <string.h>
namespace PrimeG2 { namespace AppInstallProgress {
// Presentation only: no wire protocol, storage ownership or completion decision.
enum class Phase : uint8_t { Idle, Receiving, Package, Data, Icon, Complete, Failed };
struct Status {
  Phase phase=Phase::Idle;
  uint32_t sequence=0,percent=0;
  bool updating=false;
  char name[81]{};
  bool active() const { return phase>=Phase::Receiving && phase<=Phase::Icon; }
};
class Tracker {
public:
  const Status &status() const { return m_status; }
  void begin(Phase phase,uint32_t total) {
    uint32_t sequence=m_status.sequence+1;
    m_status={};m_status.sequence=sequence;m_status.phase=phase;m_total=total;
  }
  void identify(const char *name,bool updating) {
    // Names reach this boundary only after package authentication.
    size_t n=0;while(name[n] && n<sizeof(m_status.name)-1) n++;
    memcpy(m_status.name,name,n);m_status.name[n]=0;m_status.updating=updating;
  }
  void phase(Phase phase,uint32_t total) {
    m_status.phase=phase;m_status.percent=0;m_total=total;
  }
  void progress(uint32_t bytes) {
    if(!m_status.active()) return;
    uint64_t percent=m_total?uint64_t(bytes)*100/m_total:0;
    if(percent>99) percent=99;
    // Storage readback can restart its byte cursor. Never run the bar backward.
    if(percent>m_status.percent) m_status.percent=percent;
  }
  void finish(bool success) {
    if(!m_status.active()) return;
    m_status.phase=success?Phase::Complete:Phase::Failed;
    if(success) m_status.percent=100;
  }
  void cancel() {m_status.phase=Phase::Idle;m_status.percent=0;}
private:
  Status m_status{};uint32_t m_total=0;
};
// Keep completion visible briefly, including very fast transfers between timer
// ticks. A new package/data/icon transaction renews the same screen.
class Presentation {
public:
  bool update(const Status &status,uint32_t now) {
    if(status.phase==Phase::Idle) {m_visible=false;m_terminal=false;return false;}
    if(status.sequence!=m_sequence || status.active()) {
      m_sequence=status.sequence;m_visible=true;m_terminal=false;
    }
    if(m_visible && !status.active()) {
      if(!m_terminal) {m_terminal=true;m_finished=now;}
      uint32_t duration=status.phase==Phase::Failed?1800:900;
      if(uint32_t(now-m_finished)>=duration) m_visible=false;
    }
    return m_visible;
  }
private:
  uint32_t m_sequence=0,m_finished=0;
  bool m_visible=false,m_terminal=false;
};
}}
#endif
