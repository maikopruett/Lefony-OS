// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_MANAGEMENT_H
#define LEFONY_APP_MANAGEMENT_H
#include <stdint.h>
#include <stddef.h>
#include "lefony/files_wire.h"
#include "app_install_progress.h"
#include "lefony/data_wire.h"
namespace PrimeG2 {
namespace AppDeveloperKeys {struct Status;struct RecoveryInfo;}
namespace AppArchive {struct TransferStatus;struct ApprovalInfo;}
namespace AppManagement {
constexpr unsigned MaximumIcons=512;
struct Metadata { uint32_t abi; char id[49],name[81],version[24]; };
struct CatalogEntry { uint32_t bytes,generation; Metadata metadata; };
// Validation authenticates before parsing; no app code runs here.
void init(); // Mount/reserve once during OS startup, before app/USB management.
bool metadata(const uint8_t *package,size_t size,Metadata *out,bool requireSupported=false,bool inspect=false);
bool unwrap(const uint8_t *,size_t,const uint8_t **,size_t *,bool inspect=false);
AppDeveloperKeys::Status developerKeyStatus();
AppDeveloperKeys::RecoveryInfo developerKeyRecoveryInfo();
bool developerKeyNeedsPresentation();
bool developerKeyPresent();
void developerKeyRendered();
void developerKeyObserve(uint64_t physical);
bool developerKeyApprove();
void developerKeyDismiss();
void developerKeyDeny();
AppArchive::TransferStatus archiveStatus();
AppArchive::ApprovalInfo archiveApprovalInfo();
bool archiveNeedsPresentation();
bool archivePresent();
void archiveRendered();
void archiveObserve(uint64_t physical);
bool archiveApprove();
void archiveDismiss();
void archiveDeny();
bool request(uint8_t command,uint32_t argument,const uint8_t *data,size_t size);
// Bulk staging uses the same existing upload/session and explicit commit.
void setBulkActive(bool active);
uint8_t *bulkPackage(uint32_t length);
bool bulkPackageReceived(uint32_t length);
bool bulkFile(uint32_t sequence,const uint8_t *data,uint32_t length);
bool bulkFileExport(uint32_t sequence,uint8_t *data,uint32_t length);
void bulkFileProgress(uint32_t sequence);
const uint8_t *bulkPackageRead(uint32_t length);
bool response(uint8_t command,uint32_t argument,uint8_t *data,size_t capacity,size_t *size);
void acknowledge();
void abandonSetup();
void disconnect(); // Cancel uncommitted host file exchange, preserving package operations.
void poll();
AppInstallProgress::Status installationStatus(); // Read-only UI snapshot.
bool busy();
bool needsPolling(); // Runnable storage work, excluding host/app acknowledgement waits.
uint32_t revision();
const uint8_t *homeOrder(uint32_t *bytes);
bool saveHomeOrder(const uint8_t *,uint32_t bytes);
bool homeOrderSaveFailed(); // Consume one UI error; does not clear storage errors.
const uint8_t *icon(unsigned index); // Cached, authenticated LZ4 RGB565 menu image.
unsigned count(); // Current directory entries, no reserved app slots.
const CatalogEntry &entry(unsigned slot);
bool open(unsigned slot);
bool hasOpen();
void close();
int readData(uint32_t offset,void *data,uint32_t size);
int writeData(uint32_t offset,const void *data,uint32_t size);
int files(LefonyFileRequest &,const char *,const char *,const void *,void *);
int data(LefonyDataRequest &);
void endFiles(); // Queue cleanup after conventional exit without I/O in the SVC.
}}
#endif
