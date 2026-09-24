// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_FILE_SESSION_H
#define LEFONY_APP_FILE_SESSION_H
#include "app_storage.h"
#include "lefony/files_wire.h"
namespace PrimeG2 { namespace AppFiles {
// One authenticated foreground namespace. Only OS-owned paths/data are retained
// across polls. Token counters survive detach and cannot wrap into stale handles.
class Session {
public:
  explicit Session(AppStorage::Volume &volume):m_volume(volume) {}
  bool attach(const char *id,const uint32_t version[3],uint32_t schema,
              uint32_t savedSchema,const uint8_t *committed,uint32_t bytes);
  void detach(); // Abort unclosed staging; drain operations past the commit point.
  void poll();
  bool active() const { return m_id[0]; }
  bool busy() const { return m_phase!=Phase::Idle || m_token; }
  // An undelivered completion is busy, but cannot advance without the app.
  bool needsPolling() const { return m_phase!=Phase::Idle; }
  bool quiescent() const {
    if(!active() || busy()) return false;
    for(const auto &handle:m_handles) if(handle.token) return false;
    return true;
  }
  // Trusted app-management coordination only. Public file requests cannot
  // grant migration access or replace the committed private-data snapshot.
  bool dataContext(uint32_t savedSchema,const uint8_t *committed,uint32_t bytes,bool migrating);
  int exchange(LefonyFileRequest &,const char *path,const char *destination,
               const void *input,void *output);
private:
  enum class Phase { Idle, Start, Convert, Open, Read, Write, Close, Sync, Reopen, Abort, Mutation, Drain };
  struct Handle { uint32_t token,snapshot,flags; };
  void complete(int result,uint32_t error=0);
  void start();
  void dispatch();
  void inspect();
  int slot(uint32_t token) const;
  uint32_t allocate(unsigned slot,uint32_t flags,uint32_t snapshot=0);
  bool release(unsigned slot);
  bool terminal() const;
  static uint32_t error(int);
  AppStorage::Volume &m_volume;
  Handle m_handles[5]{}; // Four snapshots and one growing writer.
  char m_id[49]{},m_path[96]{},m_destination[96]{},m_writerPath[96]{};
  uint32_t m_syncPosition=0;
  uint32_t m_version[3]{},m_schema=0,m_savedSchema=0,m_committedBytes=0;
  const uint8_t *m_committed=nullptr; // Stable OS snapshot, never app memory.
  LefonyFileRequest m_request{};
  uint8_t m_buffer[LEFONY_FILE_TRANSFER_BYTES]{};
  uint32_t m_token=0,m_requestSerial=0,m_handleSerial=2,m_outputBytes=0;
  int m_result=0;
  uint32_t m_error=0;
  Phase m_phase=Phase::Idle;
  bool m_done=false,m_detaching=false,m_writerFailed=false,m_cancelled=false,m_migrating=false;
};
}}
#endif
