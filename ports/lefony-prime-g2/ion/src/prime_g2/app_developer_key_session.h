// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_DEVELOPER_KEY_SESSION_H
#define LEFONY_APP_DEVELOPER_KEY_SESSION_H
#include "app_developer_keys.h"
#include "app_developer_key_snapshot.h"
#include "app_storage.h"
#include "app_developer_key_wire.h"
namespace PrimeG2 { namespace AppDeveloperKeys {
static_assert(MaximumKeys==8,"developer key discovery bound");
struct RecoveryHooks {
  Error (*prepare)(const Request &,const Table &,RecoveryInfo *);
  Error (*begin)(const Request &,const Table &,const RecoveryInfo &);
  State (*step)(Error *);
  bool (*cancel)();
  void (*finish)(State);
  Error (*removable)(const uint8_t id[32],const Table &);
  RecoveryHooks(decltype(prepare) p=nullptr,decltype(begin) b=nullptr,decltype(step) s=nullptr,
                decltype(cancel) c=nullptr,decltype(finish) f=nullptr,decltype(removable) r=nullptr):
    prepare(p),begin(b),step(s),cancel(c),finish(f),removable(r) {}
};
class Controller {
public:
  explicit Controller(AppStorage::Volume &,RecoveryHooks={});
  void initialize();
  bool request(const Request &,uint64_t now);
  bool cancel(const Control &);
  void acknowledge();
  void abandonSetup();
  void disconnect();
  void poll(uint64_t now);
  bool busy() const;
  bool needsPolling() const;
  bool needsPresentation() const { return m_status.state==State::AwaitUser && !m_presented; }
  bool present();
  void rendered();
  void observeKeyboard(uint64_t physical);
  bool approve(uint64_t now); // Requires rendered UI, all-up scan, then physical OK.
  void dismiss();
  void deny();
  Status status() const { return m_status; }
  RecoveryInfo recoveryInfo() const { return m_recovery; }
  bool keyInfo(unsigned index,KeyInfo *) const;
  bool damageInfo(DamageInfo *);
  int damagedBytes(uint32_t offset,void *,uint32_t bytes);
  bool unreadableInfo(UnreadableInfo *) const;
  int unreadableBytes(uint32_t offset,void *,uint32_t bytes);
  const Table *table() const { return m_store.current(); }
  static bool compiledKey(const uint8_t id[32]);
  static bool valid(const Request &);
private:
  void syncStatus(Result);
  void finish(State,Error=Error::None);
  void cancelPending(State);
  static Error error(Result);
  AppStorage::Volume &m_volume;
  Store m_store;
  Snapshot m_snapshot;
  enum class SnapshotUse { None, Backup, BeforeApproval, AfterApproval };
  SnapshotUse m_snapshotUse=SnapshotUse::None;
  Request m_request{};
  Status m_status{};
  RecoveryHooks m_hooks;
  RecoveryInfo m_recovery{};
  uint64_t m_since=0,m_physical=0;
  bool m_presented=false,m_rendered=false,m_released=false;
};
}}
#endif
