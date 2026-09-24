// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ARCHIVE_SESSION_H
#define LEFONY_APP_ARCHIVE_SESSION_H
#include "app_archive_export.h"
#include "app_archive_restore.h"
#include "app_storage.h"
#include "app_archive_wire.h"
namespace PrimeG2 { namespace AppArchive {
class Session {
public:
  struct Hooks {
    void *context;
    bool (*verify)(void *,const char *,const uint8_t *,uint32_t,bool inspect,bool supported,PackageInfo *);
    bool (*sameAuthority)(void *,const uint8_t *,const uint8_t *);
    uint32_t (*trustRevision)(void *);
    bool (*developerKey)(void *,const uint8_t *);
  };
  Session(AppStorage::Volume &,uint8_t *upload,uint8_t *inspection,uint32_t capacity,Hooks);
  static bool valid(const Request &);
  bool request(uint8_t,uint32_t,const uint8_t *,size_t);
  bool response(uint8_t,uint32_t,uint8_t *,size_t,size_t *) const;
  void acknowledge() { if(m_command) m_acknowledged=true; }
  void abandonSetup();
  void disconnect();
  void poll(uint32_t now);
  bool busy() const { return m_active; }
  bool needsPolling(uint32_t now) const;
  TransferStatus status() const;
  bool needsPresentation() const { return m_active && m_status.state==TransferState::AwaitUser && !m_presented; }
  bool present();
  void rendered();
  void observeKeyboard(uint64_t physical);
  bool approve(uint32_t now);
  void dismiss();
  void deny();
  ApprovalInfo approvalInfo() const { return m_approval; }

private:
  enum class Step { None,Initialize,Export,Write,Publish,Drain };
  static bool exportVerify(void *,const char *,const uint8_t *,uint32_t,PackageInfo *);
  static bool authenticate(void *,const Header &,const PairHeader &,unsigned,const uint8_t *);
  static bool privateVerified(void *,const PairHeader &,unsigned,const uint8_t *);
  static bool unchanged(void *);
  static bool admit(void *,uint32_t);
  void initialize(uint32_t);
  void stop(TransferError);
  void finish();
  void exportStep(uint32_t);
  void restoreStep(uint32_t);
  bool commitAcknowledged() const {return m_command==0x94 && m_acknowledged;}
  AppStorage::Volume &m_volume;
  Source m_source;
  SourceInfo m_before{};
  AppArchive::Export m_export;
  AppArchive::Restore m_restore;
  uint8_t *m_upload,*m_inspection;
  uint32_t m_capacity;
  Hooks m_hooks;
  Request m_request{};
  TransferStatus m_status{};
  Info m_info{};
  RepairInfo m_repairInfo{};
  ApprovalInfo m_approval{};
  uint8_t m_reply[512]{},m_input[488]{},m_currentSigner[32]{};
  uint32_t m_fill=0,m_inputBytes=0,m_inputUsed=0,m_ackOffset=0,m_lastProgress=0,m_trustRevision=0;
  uint8_t m_command=0;
  bool m_active=false,m_acknowledged=false,m_cancel=false,m_restoreStarted=false,m_commitRequested=false;
  bool m_consentRequired=false,m_presented=false,m_rendered=false,m_released=false;
  bool m_legacyPrefixProved=false;
  uint64_t m_physical=0;
  bool expired(uint32_t now) const;
  TransferError m_policyError=TransferError::None;
  Step m_step=Step::None;
};
}}
#endif
