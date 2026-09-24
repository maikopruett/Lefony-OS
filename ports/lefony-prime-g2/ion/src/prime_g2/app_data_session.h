// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_DATA_SESSION_H
#define LEFONY_APP_DATA_SESSION_H
#include "app_file_session.h"
#include "lefony/data_wire.h"
namespace PrimeG2 { namespace AppData {
// Owns staged and submitted private bytes for one authenticated app. The
// committed buffer is separate OS-owned app-management scratch, stable until
// this controller and the file session have both drained. No filesystem work
// runs in request(), read(), write(), finish() or reset().
class Session {
public:
  Session(AppStorage::Volume &volume,AppFiles::Session &files):m_volume(volume),m_files(files) {}
  bool attach(const char *id,const uint32_t version[3],uint32_t appSchema,uint32_t savedSchema,
              uint8_t *committed,uint32_t bytes);
  int read(uint32_t offset,void *out,uint32_t bytes) const;
  int write(uint32_t offset,const void *input,uint32_t bytes);
  int request(LefonyDataRequest &);
  void poll();
  void finish(bool save); // Freeze app writes; faults cancel only before commit.
  bool reset(); // After pending work drains; preserves buffers used by Close.
  bool active() const { return m_id[0]; }
  bool needsPolling() const { return m_phase!=Phase::Idle; }
  bool dirty() const { return m_dirty && !m_poisoned; }
  bool migrating() const { return m_migrating; }
  uint32_t savedSchema() const { return m_savedSchema; }
  uint32_t bytes() const { return m_bytes; }
  const uint8_t *data() const { return m_data; }
private:
  enum class Phase { Idle,Start,Writing };
  bool inspect();
  void complete(uint32_t error=0,uint32_t flags=0);
  void reply(LefonyDataRequest &) const;
  AppStorage::Volume &m_volume;AppFiles::Session &m_files;
  char m_id[49]{};uint32_t m_version[3]{},m_appSchema=0,m_savedSchema=0,m_generation=0;
  uint8_t m_data[AppStorage::MaximumData]{},m_snapshot[AppStorage::MaximumData]{};
  uint8_t *m_committed=nullptr;
  uint32_t m_bytes=0,m_committedBytes=0,m_editRevision=1,m_snapshotRevision=0,m_serial=0,m_token=0;
  LefonyDataRequest m_request{};
  Phase m_phase=Phase::Idle;
  uint32_t m_error=0,m_flags=0;
  bool m_dirty=false,m_pendingUpgrade=false,m_migrating=false,m_done=false,m_cancel=false;
  bool m_cancelSent=false,m_frozen=false,m_poisoned=false;
};
}}
#endif
