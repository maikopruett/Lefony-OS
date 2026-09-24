// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_FILE_EXCHANGE_H
#define LEFONY_APP_FILE_EXCHANGE_H
#include "app_file_session.h"
namespace PrimeG2 { namespace AppFileExchange {
// Host-only file exchange. These records contain no native pointers or device
// identifiers. USB copies/queues frames; only poll performs filesystem work.
struct Request {
  uint32_t size,schema,operation,flags,generation,dataSchema,length,cursor;
  char id[64],path[96];uint8_t digest[32];
};
struct Status {
  uint32_t magic,size,schema,state,operation,error,sequence,offset,length,available;
  uint32_t generation,dataSchema,chunkBytes,flags,reserved[2];uint8_t digest[32];
};
struct Info {
  uint32_t size,schema,version[3],dataSchema,appSchema,pendingUpgrade;
  LefonyFileSpace space;LefonyFileQuota quota;
};
// Additive host data/recovery operations require app hello capability 128.
struct DataInfo {
  uint32_t size,schema,generation,flags,version[3],appSchema,dataSchema,privateBytes;
  uint32_t previousVersion[3],previousSchema,previousPrivateBytes,highVersion[3],previousPackage,reserved;
  uint8_t packageHash[32],previousPackageHash[32],privateHash[32];
};
enum : uint32_t { Inspect=1,Export=2,Import=3,List=4,InspectData=5,ExportData=6,ImportData=7,Rollback=8,Replace=1 };
enum : uint32_t { PendingUpgrade=1,RecoveryTrusted=2 };
enum : uint32_t { Idle=0,Working=1,Readable=2,Writable=3,Complete=4,Failed=5,Cancelled=6 };
enum : uint32_t { DigestMismatch=17,CancelledError=18,Timeout=19 };
enum : uint32_t { Committed=1,CommitUncertain=2 };
struct Identity {
  char id[49];uint32_t version[3],appSchema,dataSchema,generation,privateBytes;
  const uint8_t *privateData;bool pendingUpgrade;
  DataInfo dataInfo{}; // Populated by authenticated app management, never USB.
};
class Session {
public:
  explicit Session(AppStorage::Volume &v):m_volume(v),m_files(v) {}
  static bool valid(const Request &);
  bool begin(const Request &,const Identity &,uint32_t now);
  void reject(const Request &,uint32_t error);
  bool request(uint8_t command,uint32_t arg,const uint8_t *,size_t);
  bool response(uint8_t command,uint32_t arg,uint8_t *,size_t,size_t *) const;
  bool stage(uint32_t sequence,const uint8_t *data,uint32_t length);
  bool stageExport(uint32_t sequence,uint8_t *data,uint32_t length);
  void stageProgress(uint32_t sequence,uint32_t now);
  void acknowledge() { if(m_command) m_acknowledged=true; }
  void abandonSetup() { if(!m_acknowledged) m_command=0; }
  void disconnect(); // Queue cancellation; never performs filesystem work.
  void poll(uint32_t now);
  bool busy() const { return m_active; }
  const Status &status() const { return m_status; }
  bool canBegin() const { return !m_active && m_status.sequence!=0xffffffffu; }
  bool needsPolling() const { return m_staged || m_export || m_step!=Step::None || m_cancel || (m_command && m_acknowledged); }
private:
  enum class Step { None,InfoSpace,InfoQuota,OpenExport,ExportStat,Read,OpenImport,Write,Close,Drain,DataCommit,ImportConvert,ImportPrepare,ImportWrite,ImportCommit };
  void submit(uint32_t operation,Step,uint32_t flags=0,uint32_t length=0);
  void stop(uint32_t error);
  void finish();
  void beginImport();
  void pollImport(uint32_t now);
  void ready(uint32_t state,uint32_t now);
  bool direct() const { return m_request.operation>=InspectData; }
  bool commitAcknowledged() const { return m_command==0x74 && m_acknowledged; }
  AppStorage::Volume &m_volume;
  AppFiles::Session m_files;
  Request m_request{};Status m_status{0x5841464c,96,1,Idle,0,0,0,0,0,0,0,0,512,0,{0,0},{0}};
  Info m_info{};NativeAppHash::SHA256 m_hash{};
  DataInfo m_dataInfo{};
  uint8_t m_private[AppStorage::MaximumData]{};
  const uint8_t *m_saved=nullptr;
  uint8_t m_reply[2048]{},m_upload[2048]{};
  const uint8_t *m_staged=nullptr;
  uint8_t *m_export=nullptr;
  uint32_t m_handle=0,m_token=0,m_uploadBytes=0,m_uploadUsed=0,m_lastProgress=0,m_ackOffset=0;
  uint8_t m_command=0;Step m_step=Step::None;
  bool m_active=false,m_acknowledged=false,m_cancel=false,m_commitStarted=false,m_importOwned=false;
};
}}
#endif
