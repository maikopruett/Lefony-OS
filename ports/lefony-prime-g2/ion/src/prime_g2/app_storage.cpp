// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_storage.h"
#include <string.h>
namespace PrimeG2 {
namespace AppStorage {
namespace {
constexpr uint32_t FSFirst = FirstBlock + 2, FSBlocks = BlockCount - 2;
const char *Pending = "apps/.pending";
uint32_t get(const uint8_t *p) {
  return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}
void put(uint8_t *p, uint32_t v) {
  for (unsigned i = 0; i < 4; i++)
    p[i] = v >> (8 * i);
}
void seal(uint8_t *p) { NativeAppHash::sha256(p, PageBytes - 32, p + PageBytes - 32); }
bool sealed(const uint8_t *p) {
  uint8_t h[32];
  NativeAppHash::sha256(p, PageBytes - 32, h);
  return !memcmp(h, p + PageBytes - 32, 32);
}
bool headerValid(const uint8_t *p) {
  return !memcmp(p, "LFAFILE2", 8) && get(p + 8) == 2 && get(p + 12) && get(p + 16) >= 468 &&
         get(p + 16) <= MaximumPackage && get(p + 20) <= MaximumData && !get(p + 56) &&
         !get(p + 60);
}
uint32_t fileBlocks(uint32_t bytes) {
  return (bytes + 64 + (BlockBytes - 128) - 1) / (BlockBytes - 128);
}
} // namespace
Volume::Volume(Backend backend,AppFileStore::ReadCache *cache)
    : m_backend(backend), m_legacy(backend), m_fs{}, m_documents(&m_fs), m_files(&m_fs,&m_documents), m_config{}, m_file{}, m_fileConfig{},
      m_readCache{}, m_writeCache{}, m_fileCache{}, m_lookahead{}, m_scratch{}, m_protected{},
      m_used{}, m_identity{}, m_header{}, m_path{}, m_package(nullptr), m_data(nullptr),
      m_packageBytes(0), m_dataBytes(0), m_cursor(0), m_hash{}, m_state(State::Unprovisioned),
      m_icon(false), m_mounted(false), m_open(false), m_legacyValid(false), m_finishedMigration(false) {
  m_config.context = this;
  m_config.read = readBlock;
  m_config.read_metadata = readMetadata;
  m_config.prog = programBlock;
  m_config.erase = eraseBlock;
  m_config.sync = syncBlock;
  m_config.read_size = PageBytes;
  m_config.prog_size = PageBytes;
  m_config.block_size = BlockBytes;
  m_config.block_count = FSBlocks;
  m_config.block_cycles = 100;
  m_config.cache_size = PageBytes;
  m_config.lookahead_size = sizeof(m_lookahead);
  m_config.read_buffer = m_readCache;
  m_config.prog_buffer = m_writeCache;
  m_config.lookahead_buffer = m_lookahead;
  m_config.name_max = 53;
  m_config.file_max = MaximumPackage + MaximumData + 64;
  m_config.metadata_max = 8192;
  m_config.inline_max = 256;
  m_fileConfig.buffer = m_fileCache;
  m_documents.setChunkRetainer(retainChunk,this);
  m_files.setChunkAdmission(admitChunk,this);
  for(auto &reader:m_readers) reader.setCache(cache);
}
Volume::~Volume() {
  closeSnapshots();
  if (m_mounted)
    lfs_unmount(&m_fs);
}
int Volume::readBlock(const lfs_config *c, lfs_block_t block, lfs_off_t offset, void *data,
                      lfs_size_t size) {
  auto &v = *static_cast<Volume *>(c->context);
  if (block >= FSBlocks || offset % PageBytes || size % PageBytes || offset > BlockBytes ||
      size > BlockBytes - offset)
    return LFS_ERR_INVAL;
  for (uint32_t i = 0; i < size; i += PageBytes)
    if (!v.m_backend.read(v.m_backend.context,
                          (FSFirst + block) * PagesPerBlock + (offset + i) / PageBytes,
                          static_cast<uint8_t *>(data) + i))
      return LFS_ERR_CORRUPT;
  return 0;
}
int Volume::readMetadata(const lfs_config *c,lfs_block_t block,lfs_off_t offset,void *data,lfs_size_t size) {
  auto &v=*static_cast<Volume *>(c->context);
  if(block>=FSBlocks || offset%PageBytes || size%PageBytes || offset>BlockBytes || size>BlockBytes-offset) return LFS_ERR_INVAL;
  for(uint32_t i=0;i<size;i+=PageBytes) {
    uint32_t tag=block*PagesPerBlock+(offset+i)/PageBytes+1;
    MetadataPage *cached=nullptr;
    for(auto &page:v.m_metadata) if(page.tag==tag) {cached=&page;break;}
    if(!cached) {
      auto &page=v.m_metadata[v.m_metadataNext];page.tag=0;
      int rc=readBlock(c,block,offset+i,page.data,PageBytes);
      if(rc) return rc; // Failed/partial reads never become cache entries.
      page.tag=tag;cached=&page;v.m_metadataNext=(v.m_metadataNext+1)%MetadataPages;
    }
    memcpy(static_cast<uint8_t *>(data)+i,cached->data,PageBytes);
  }
  return 0;
}
void Volume::invalidateMetadata(uint32_t block) {
  // Also invalidate before commands that fail or are interrupted: their media
  // effects can be uncertain. Never serve pre-write bytes during readback.
  for(auto &page:m_metadata) if(page.tag && (page.tag-1)/PagesPerBlock==block) page.tag=0;
}
void Volume::refreshMetadata() {
  // Revalidation across a consent/commit boundary must observe the medium,
  // including changes outside this Volume's program/erase callbacks.
  for(auto &page:m_metadata) page.tag=0;
  m_metadataNext=0;
  m_fs.rcache.block=static_cast<lfs_block_t>(-1);
}
int Volume::programBlock(const lfs_config *c, lfs_block_t block, lfs_off_t offset, const void *data,
                         lfs_size_t size) {
  auto &v = *static_cast<Volume *>(c->context);
  if (block >= FSBlocks || offset % PageBytes || size % PageBytes || offset > BlockBytes ||
      size > BlockBytes - offset)
    return LFS_ERR_INVAL;
  v.invalidateMetadata(block);
  if (v.m_protected[block + 2] || !v.m_backend.usable(v.m_backend.context, FSFirst + block))
    return LFS_ERR_CORRUPT;
  for (uint32_t i = 0; i < size; i += PageBytes)
    if (!v.m_backend.program(v.m_backend.context,
                             (FSFirst + block) * PagesPerBlock + (offset + i) / PageBytes,
                             static_cast<const uint8_t *>(data) + i))
      return LFS_ERR_CORRUPT;
  return 0;
}
int Volume::eraseBlock(const lfs_config *c, lfs_block_t block) {
  auto &v = *static_cast<Volume *>(c->context);
  if (block >= FSBlocks)
    return LFS_ERR_INVAL;
  v.invalidateMetadata(block);
  if (v.m_protected[block + 2] || !v.m_backend.usable(v.m_backend.context, FSFirst + block))
    return LFS_ERR_CORRUPT;
  return v.m_backend.erase(v.m_backend.context, FSFirst + block) ? 0 : LFS_ERR_CORRUPT;
}
int Volume::syncBlock(const lfs_config *) {
  return 0;
} // Backend completes physical writes synchronously.
void Volume::fail() { m_state = State::Failed; }
bool Volume::validName(const char *id) const {
  if (!id || id[0] < 'a' || id[0] > 'z')
    return false;
  unsigned i = 0;
  for (; id[i] && i < 49; i++)
    if (!((id[i] >= 'a' && id[i] <= 'z') ||
          (i && ((id[i] >= '0' && id[i] <= '9') || id[i] == '-'))))
      return false;
  return i > 0 && i <= 48;
}
bool Volume::path(const char *id, char out[64], bool icon) const {
  if (!validName(id))
    return false;
  size_t n = strlen(id);
  const char *prefix = icon ? "icons/" : "apps/";
  size_t start = strlen(prefix);
  memcpy(out, prefix, start);
  memcpy(out + start, id, n);
  memcpy(out + start + n, ".app", 5);
  return true;
}
bool Volume::openFile(const char *name, int flags) {
  if (m_open || lfs_file_opencfg(&m_fs, &m_file, name, flags, &m_fileConfig) < 0)
    return false;
  m_open = true;
  return true;
}
bool Volume::closeFile() {
  if (!m_open)
    return true;
  int result = lfs_file_close(&m_fs, &m_file);
  m_open = false;
  return result == 0;
}
bool Volume::readSmall(const char *name, uint8_t *data, size_t size) {
  if (!openFile(name, LFS_O_RDONLY))
    return false;
  bool ok = lfs_file_size(&m_fs, &m_file) == static_cast<lfs_soff_t>(size) &&
            lfs_file_read(&m_fs, &m_file, data, size) == static_cast<lfs_ssize_t>(size);
  return closeFile() && ok;
}
bool Volume::writeSmall(const char *name, const uint8_t *data, size_t size) {
  if (!openFile(".setup", LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC))
    return false;
  bool ok = lfs_file_write(&m_fs, &m_file, data, size) == static_cast<lfs_ssize_t>(size);
  if (!closeFile() || !ok)
    return false;
  return lfs_rename(&m_fs, ".setup", name) == 0;
}
bool Volume::marker(const uint8_t *p) const {
  return !memcmp(p, "LFAVFS2\0", 8) && get(p + 8) == 2 && get(p + 12) == FirstBlock &&
         get(p + 16) == BlockCount && sealed(p);
}
bool Volume::mount() {
  if (m_open ||
      (m_state != State::Ready && m_state != State::Complete && m_state != State::Failed &&
       m_state != State::Unprovisioned && m_state != State::Migrating))
    return false;
  if (m_mounted) {
    if(!closeSnapshots()) { fail();return false; }
    lfs_unmount(&m_fs);
    m_mounted = false;
  }
  for(auto &page:m_metadata) page.tag=0;
  m_metadataNext=0;
  memset(m_protected, 0, sizeof(m_protected));
  m_finishedMigration = false;
  m_legacyValid = false;
  m_state = State::Unprovisioned;
  unsigned anchors = 0;
  for (unsigned i = 0; i < 2; i++)
    if (m_backend.usable(m_backend.context, FirstBlock + i) &&
        m_backend.read(m_backend.context, (FirstBlock + i) * PagesPerBlock, m_scratch) &&
        marker(m_scratch)) {
      if (anchors && memcmp(m_identity, m_scratch + 32, 32)) {
        fail();
        return false;
      }
      memcpy(m_identity, m_scratch + 32, 32);
      anchors++;
    }
  if (!anchors) {
    m_legacyValid = m_legacy.mount();
    if (!m_legacyValid) {
      if (m_legacy.state() != LegacyAppStorage::State::Unprovisioned)
        fail();
      return false;
    }
    memcpy(m_identity, m_legacy.identity(), 32);
    if (!m_legacy.protect(m_protected)) {
      fail();
      return false;
    }
  }
  if (lfs_mount(&m_fs, &m_config) < 0) {
    if (anchors)
      fail();
    else
      m_state = State::Migrating;
    return false;
  }
  m_mounted = true;
  uint8_t identity[32];
  if (!readSmall("volume", identity, 32) || memcmp(identity, m_identity, 32)) {
    if (anchors)
      fail();
    else
      m_state = State::Migrating;
    return false;
  }
  m_finishedMigration = readSmall("migrated", identity, 32) && !memcmp(identity, m_identity, 32);
  if (anchors && !m_finishedMigration) {
    fail();
    return false;
  }
  if (!m_finishedMigration || anchors != 2) {
    m_state = State::Migrating;
    return false;
  }
  memset(m_protected, 0, sizeof(m_protected));
  m_state = State::Ready;
  return true;
}
bool Volume::provision(const uint8_t backup[32]) {
  return m_state == State::Unprovisioned && m_legacy.provision(backup);
}
bool Volume::initialize(uint8_t *package, size_t capacity, uint8_t *data, size_t dataCapacity,
                        NameReader nameReader) {
  if (!package || capacity < MaximumPackage || !data || dataCapacity < MaximumData || !nameReader)
    return false;
  if (mount()) {
    int rc = lfs_remove(&m_fs, Pending);
    if (rc != 0 && rc != LFS_ERR_NOENT) {
      fail();
      return false;
    }
    return pruneOrphans();
  }
  if (m_state == State::Unprovisioned) {
    if (!m_legacy.reserve()) {
      fail();
      return false;
    }
    mount();
  }
  if (m_state != State::Migrating)
    return false;
  if (!m_mounted) {
    if (!m_legacyValid || lfs_format(&m_fs, &m_config) < 0 || lfs_mount(&m_fs, &m_config) < 0) {
      fail();
      return false;
    }
    m_mounted = true;
  }
  // Legacy live extents stay protected until every file and this migration
  // marker are durable. Power loss can resume from the original v1 records.
  if (!m_finishedMigration) {
    uint8_t identity[32];
    if (!readSmall("volume", identity, 32)) {
      if (!writeSmall("volume", m_identity, 32)) {
        fail();
        return false;
      }
    } else if (memcmp(identity, m_identity, 32)) {
      fail();
      return false;
    }
    int rc = lfs_mkdir(&m_fs, "apps");
    if (rc != 0 && rc != LFS_ERR_EXIST) {
      fail();
      return false;
    }
    if (!m_legacyValid) {
      fail();
      return false;
    }
    char names[LegacyAppStorage::Slots][49] = {};
    for (unsigned i = 0; i < LegacyAppStorage::Slots; i++) {
      const auto old = m_legacy.entry(i);
      if (!old.packageBytes)
        continue;
      if (!m_legacy.read(i, package, capacity, data, dataCapacity) ||
          !nameReader(package, old.packageBytes, names[i]) || !validName(names[i])) {
        fail();
        return false;
      }
      for (unsigned j = 0; j < i; j++)
        if (!strcmp(names[i], names[j])) {
          fail();
          return false;
        }
      char file[64];
      path(names[i], file);
      uint8_t header[64], hash[32];
      NativeAppHash::SHA256 digest;
      NativeAppHash::shaInit(&digest);
      NativeAppHash::shaUpdate(&digest, package, old.packageBytes);
      NativeAppHash::shaUpdate(&digest, data, old.dataBytes);
      NativeAppHash::shaFinal(&digest, hash);
      if (readHeader(file, header)) {
        if (get(header + 16) != old.packageBytes || get(header + 20) != old.dataBytes ||
            memcmp(hash, header + 24, 32) ||
            !read(names[i], package, capacity, data, dataCapacity)) {
          fail();
          return false;
        }
      } else {
        m_state = State::Ready;
        if (!begin(names[i], package, old.packageBytes, data, old.dataBytes)) {
          fail();
          return false;
        }
        put(m_header + 12, old.generation);
        if (!finish()) {
          fail();
          return false;
        }
      }
    }
    if (!writeSmall("migrated", m_identity, 32)) {
      fail();
      return false;
    }
  }
  // Retire the v1 anchors only after the filesystem contains all apps/data.
  // Old firmware then fails closed instead of treating pooled blocks as banks.
  memset(m_scratch, 255, PageBytes);
  memcpy(m_scratch, "LFAVFS2\0", 8);
  put(m_scratch + 8, 2);
  put(m_scratch + 12, FirstBlock);
  put(m_scratch + 16, BlockCount);
  memcpy(m_scratch + 32, m_identity, 32);
  seal(m_scratch);
  uint8_t verify[PageBytes];
  for (unsigned i = 0; i < 2; i++) {
    uint32_t b = FirstBlock + i;
    if (!m_backend.usable(m_backend.context, b)) {
      fail();
      return false;
    }
    if (m_backend.read(m_backend.context, b * PagesPerBlock, verify) &&
        !memcmp(verify, m_scratch, PageBytes))
      continue;
    if (!m_backend.erase(m_backend.context, b) ||
        !m_backend.program(m_backend.context, b * PagesPerBlock, m_scratch) ||
        !m_backend.read(m_backend.context, b * PagesPerBlock, verify) ||
        memcmp(verify, m_scratch, PageBytes)) {
      fail();
      return false;
    }
  }
  m_state = State::Ready;
  return mount();
}
bool Volume::readHeader(const char *file, uint8_t header[64]) {
  if (!m_mounted || !openFile(file, LFS_O_RDONLY))
    return false;
  bool ok = lfs_file_read(&m_fs, &m_file, header, 64) == 64 && headerValid(header) &&
            lfs_file_size(&m_fs, &m_file) ==
                static_cast<lfs_soff_t>(64 + get(header + 16) + get(header + 20));
  return closeFile() && ok;
}
bool Volume::entry(const char *id, Entry *out, bool icon) {
  char file[64];
  uint8_t header[64];
  if (!out || !path(id, file, icon)) return false;
  if (!readHeader(file, header)) {
    AppDocumentRoot::Root root;
    if(icon || !documentRoot(id,&root)) return false;
    uint32_t bytes;if(!m_documents.privateBytes(id,root.current,&bytes)) return false;
    *out={root.serial,root.current.packageBytes,bytes};return true;
  }
  *out = {get(header + 12), get(header + 16), get(header + 20)};
  return true;
}
bool Volume::read(const char *id, uint8_t *package, size_t capacity, uint8_t *data,
                  size_t dataCapacity, bool icon) {
  char file[64];
  uint8_t header[64];
  if(!path(id,file,icon)) return false;
  if(!readHeader(file,header)) return !icon && m_mounted && m_documents.read(id,package,capacity,data,dataCapacity);
  if (!package || capacity < get(header + 16) ||
      (get(header + 20) && (!data || dataCapacity < get(header + 20))) ||
      !openFile(file, LFS_O_RDONLY))
    return false;
  bool ok = lfs_file_seek(&m_fs, &m_file, 64, LFS_SEEK_SET) == 64 &&
            lfs_file_read(&m_fs, &m_file, package, get(header + 16)) ==
                static_cast<lfs_ssize_t>(get(header + 16)) &&
            lfs_file_read(&m_fs, &m_file, data, get(header + 20)) ==
                static_cast<lfs_ssize_t>(get(header + 20));
  if (!closeFile() || !ok)
    return false;
  NativeAppHash::SHA256 hash;
  uint8_t digest[32];
  NativeAppHash::shaInit(&hash);
  NativeAppHash::shaUpdate(&hash, package, get(header + 16));
  if (get(header + 20))
    NativeAppHash::shaUpdate(&hash, data, get(header + 20));
  NativeAppHash::shaFinal(&hash, digest);
  return !memcmp(digest, header + 24, 32);
}
int Volume::namespaceState(const char *id) {
  char file[64];if(!m_mounted || m_open || !path(id,file)) return LFS_ERR_INVAL;
  lfs_info info;int result=lfs_stat(&m_fs,file,&info);
  return !result?1:result==LFS_ERR_NOENT?0:result;
}
bool Volume::list(Visitor visitor, void *context,bool includeUnreadable) {
  if (!m_mounted || m_open || !visitor)
    return false;
  lfs_dir_t dir;
  if (lfs_dir_open(&m_fs, &dir, "apps") < 0)
    return false;
  lfs_info info;
  int rc;
  bool ok = true;
  while ((rc = lfs_dir_read(&m_fs, &dir, &info)) > 0) {
    if (info.type == LFS_TYPE_DIR || !strcmp(info.name, ".pending"))
      continue;
    size_t length = strlen(info.name);
    if (length < 5 || length > 52 || strcmp(info.name + length - 4, ".app")) {
      ok = false;
      break;
    }
    info.name[length - 4] = 0;
    Entry e{};
    if ((!entry(info.name, &e) && !includeUnreadable) || !visitor(context, info.name, e)) {
      ok = false;
      break;
    }
  }
  return lfs_dir_close(&m_fs, &dir) == 0 && rc >= 0 && ok;
}
int Volume::usedBlock(void *context, lfs_block_t block) {
  if (block >= FSBlocks)
    return LFS_ERR_CORRUPT;
  static_cast<Volume *>(context)->m_used[block + 2] = true;
  return 0;
}
bool Volume::space(Space *out) {
  if (!m_mounted || !out)
    return false;
  memset(m_used, 0, sizeof(m_used));
  if (lfs_fs_traverse(&m_fs, usedBlock, this) < 0)
    return false;
  uint32_t usable = 0, used = 0;
  for (uint32_t i = 2; i < BlockCount; i++) {
    bool good = m_backend.usable(m_backend.context, FirstBlock + i);
    usable += good ? 1 : 0;
    used += (m_used[i] || m_protected[i]) ? 1 : 0;
  }
  uint32_t capacity = usable > ReserveBlocks ? (usable - ReserveBlocks) * BlockBytes : 0,
           allocated = used * BlockBytes;
  *out = {capacity, 0, capacity > allocated ? capacity - allocated : 0, allocated,
          BlockCount * BlockBytes - capacity};
  return true;
}
bool Volume::begin(const char *id, const uint8_t *package, uint32_t packageBytes,
                   const uint8_t *data, uint32_t dataBytes, bool icon) {
  // Readers keep immutable chunks alive, but uninstall must not remove their
  // namespace. The application lifecycle closes its handles before uninstall.
  if(!icon && !packageBytes && hasSnapshots(id)) return false;
  if (!m_mounted || m_fileOperation || (m_state != State::Ready && m_state != State::Complete) || !path(id, m_path, icon) ||
      packageBytes > MaximumPackage || dataBytes > MaximumData ||
      (packageBytes && (!package || packageBytes < 468)) || (dataBytes && !data) ||
      (!packageBytes && dataBytes))
    return false;
  if (icon) {
    if (dataBytes || packageBytes != 6576) return false;
    int rc = lfs_mkdir(&m_fs, "icons");
    if (rc != 0 && rc != LFS_ERR_EXIST) return false;
  }
  m_icon = icon;
  AppDocumentRoot::Root documents;
  // An old writer must never replace a FILE3 root with a combined FILE2 file.
  // Version-aware update/checkpoint methods own all subsequent mutations.
  if(!icon && packageBytes && documentRoot(id,&documents)) return false;
  m_documentOperation=false;
  Entry old = {};
  bool readableEntry=entry(id,&old,icon);
  lfs_info existing;int stat=lfs_stat(&m_fs,m_path,&existing);
  if((stat && stat!=LFS_ERR_NOENT) || (!stat && !readableEntry)) return false;
  if ((packageBytes && old.generation == 0xffffffffu) || (!packageBytes && !old.packageBytes))
    return false;
  Space usage;
  if (!space(&usage))
    return false;
  if (packageBytes) {
    uint32_t needed = fileBlocks(packageBytes + dataBytes),
             previous = old.packageBytes ? fileBlocks(old.packageBytes + old.dataBytes) : 0;
    if (needed > usage.available / BlockBytes + previous)
      return false;
  }
  m_package = package;
  m_data = data;
  m_packageBytes = packageBytes;
  m_dataBytes = dataBytes;
  m_cursor = 0;
  memset(m_header, 0, 64);
  memcpy(m_header, "LFAFILE2", 8);
  put(m_header + 8, 2);
  put(m_header + 12, old.generation + 1);
  put(m_header + 16, packageBytes);
  put(m_header + 20, dataBytes);
  NativeAppHash::SHA256 hash;
  NativeAppHash::shaInit(&hash);
  if (packageBytes)
    NativeAppHash::shaUpdate(&hash, package, packageBytes);
  if (dataBytes)
    NativeAppHash::shaUpdate(&hash, data, dataBytes);
  NativeAppHash::shaFinal(&hash, m_header + 24);
  m_state = packageBytes ? State::Writing : State::Committing;
  return true;
}
int Volume::readHomeOrder(uint8_t *out,uint32_t capacity) {
  if(!out || !documentReady()) return -1;
  lfs_info info;int rc=lfs_stat(&m_fs,"home-order",&info);
  if(rc==LFS_ERR_NOENT) return 0;
  if(rc || info.type!=LFS_TYPE_REG || info.size<72 || info.size>64+MaximumHomeOrder) return -1;
  uint32_t bytes=info.size-64;if(bytes>capacity) return -1;
  uint8_t header[64],digest[32];
  bool ok=openFile("home-order",LFS_O_RDONLY) && lfs_file_read(&m_fs,&m_file,header,64)==64 &&
    !memcmp(header,"LFHOME1\0",8) && get(header+16)==bytes;
  if(ok) ok=lfs_file_read(&m_fs,&m_file,out,bytes)==static_cast<lfs_ssize_t>(bytes);
  ok=closeFile() && ok;
  if(ok) {NativeAppHash::sha256(out,bytes,digest);ok=!memcmp(digest,header+24,32);}
  return ok?static_cast<int>(bytes):-1;
}
bool Volume::beginHomeOrder(const uint8_t *data,uint32_t bytes) {
  if(!documentReady() || !data || bytes<8 || bytes>MaximumHomeOrder || !documentSpace(0,bytes,false)) return false;
  // Reuse the existing write -> close -> full readback -> atomic rename path.
  // The dedicated root file is outside every app's namespace and catalog.
  m_documentOperation=false;m_icon=true;
  memcpy(m_path,"home-order",11);m_package=data;m_packageBytes=bytes;
  m_data=nullptr;m_dataBytes=0;m_cursor=0;memset(m_header,0,sizeof(m_header));
  memcpy(m_header,"LFHOME1\0",8);put(m_header+16,bytes);
  NativeAppHash::sha256(data,bytes,m_header+24);m_state=State::Writing;return true;
}
void Volume::step() {
  if(m_fileOperation) {
    m_files.step();using F=AppFileStore::Store::State;
    if(m_fileAdmission && m_files.prepared()) {
      m_fileAdmission=false;
      if(!documentSpace(m_fileBudgetPackage,m_fileBudgetData,false)) { m_files.cancel();fail();return; }
    }
    switch(m_files.state()) {
    case F::Complete:m_state=State::Complete;m_fileOperation=false;break;
    case F::Failed:fail();break;
    case F::Committing:m_state=State::Committing;break;
    case F::Reading:m_state=State::Ready;break;
    default:m_state=State::Writing;break;
    }
    return;
  }
  if(m_documentOperation) {
    m_documents.step();
    using S=AppDocumentStore::Store::State;
    switch(m_documents.state()) {
    case S::Complete:m_state=State::Complete;break;
    case S::Failed:fail();break;
    case S::Committing:m_state=State::Committing;break;
    default:m_state=State::Writing;break;
    }
    return;
  }
  bool ok = true;
  if (m_state == State::Writing) {
    if (!m_open)
      ok = openFile(Pending, LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC) &&
           lfs_file_write(&m_fs, &m_file, m_header, 64) == 64;
    else if (m_cursor < m_packageBytes + m_dataBytes) {
      uint32_t bytes = m_packageBytes + m_dataBytes - m_cursor;
      if (bytes > PageBytes)
        bytes = PageBytes;
      uint32_t app = m_cursor < m_packageBytes ? m_packageBytes - m_cursor : 0;
      if (app > bytes)
        app = bytes;
      if (app)
        memcpy(m_scratch, m_package + m_cursor, app);
      if (bytes > app)
        memcpy(m_scratch + app, m_data + m_cursor + app - m_packageBytes, bytes - app);
      ok = lfs_file_write(&m_fs, &m_file, m_scratch, bytes) == static_cast<lfs_ssize_t>(bytes);
      m_cursor += bytes;
    } else {
      ok = closeFile();
      m_cursor = 0;
      NativeAppHash::shaInit(&m_hash);
      m_state = State::Verifying;
    }
  } else if (m_state == State::Verifying) {
    if (!m_open)
      ok = openFile(Pending, LFS_O_RDONLY) && lfs_file_read(&m_fs, &m_file, m_scratch, 64) == 64 &&
           !memcmp(m_scratch, m_header, 64);
    else if (m_cursor < m_packageBytes + m_dataBytes) {
      uint32_t bytes = m_packageBytes + m_dataBytes - m_cursor;
      if (bytes > PageBytes)
        bytes = PageBytes;
      ok = lfs_file_read(&m_fs, &m_file, m_scratch, bytes) == static_cast<lfs_ssize_t>(bytes);
      if (ok)
        NativeAppHash::shaUpdate(&m_hash, m_scratch, bytes);
      m_cursor += bytes;
    } else {
      uint8_t digest[32];
      NativeAppHash::shaFinal(&m_hash, digest);
      ok = closeFile() && !memcmp(digest, m_header + 24, 32);
      m_state = State::Committing;
    }
  } else if (m_state == State::Committing) {
    // The optional icon has no executable state. Removing it first is safe
    // across power loss: the still-installed app falls back to the default icon.
    if (!m_packageBytes && !m_icon) {
      char iconPath[64];
      memcpy(iconPath, "icons/", 6);
      memcpy(iconPath + 6, m_path + 5, strlen(m_path + 5) + 1);
      int rc = lfs_remove(&m_fs, iconPath);
      if (rc != 0 && rc != LFS_ERR_NOENT) { fail(); return; }
    }
    ok = m_packageBytes ? lfs_rename(&m_fs, Pending, m_path) == 0 : lfs_remove(&m_fs, m_path) == 0;
    if (ok) {
      m_state = State::Complete;
      if(!m_packageBytes && !m_icon) {
        char id[49];size_t n=strlen(m_path+5)-4;memcpy(id,m_path+5,n);id[n]=0;
        if(!m_documents.prune(id)) fail();
        else if(m_documents.state()!=AppDocumentStore::Store::State::Complete) {
          m_documentOperation=true;m_state=State::Committing;
        }
      }
    }
  }
  if (!ok) {
    closeFile();
    fail();
  }
}
bool Volume::finish() {
  for (unsigned i = 0; i < 10000 && m_state != State::Complete && m_state != State::Failed; i++)
    step();
  return m_state == State::Complete;
}
void Volume::cancel() {
  if(m_fileOperation) {
    m_files.cancel();
    if(m_files.state()==AppFileStore::Store::State::Idle) { m_fileOperation=false;m_state=State::Ready; }
    else if(m_files.state()==AppFileStore::Store::State::Failed) fail();
    return;
  }
  if(m_documentOperation) {
    m_documents.cancel();
    if(m_documents.state()==AppDocumentStore::Store::State::Idle) m_state=State::Ready;
    else if(m_documents.state()==AppDocumentStore::Store::State::Failed) fail();
    return;
  }
  if (m_state == State::Writing || m_state == State::Verifying) {
    if (closeFile())
      m_state = State::Ready;
    else
      fail();
  }
}
bool Volume::documentReady() const {
  return m_mounted && !m_open && !m_fileOperation && (m_state==State::Ready || m_state==State::Complete);
}
bool Volume::documentRoot(const char *id,AppDocumentRoot::Root *out) {
  return m_mounted && !m_open && m_documents.root(id,out);
}
bool Volume::documentSpace(uint32_t packageBytes,uint32_t dataBytes,bool conversion) {
  Space usage;if(!space(&usage) || !usage.capacity) return false;
  // Include one FILE5 payload block, two metadata blocks for commit/recovery and four for the
  // first objects/app directory pairs. Account for retained generations by
  // using actual allocation; they cannot be credited as reclaimable space.
  uint32_t needed=3+(conversion?4:0)+(packageBytes?fileBlocks(packageBytes):0)+
    (dataBytes>256?fileBlocks(dataBytes):0);
  uint32_t total=usage.capacity+ReserveBlocks*BlockBytes;
  return usage.allocated<=total && needed<=(total-usage.allocated)/BlockBytes;
}
bool Volume::beginCheckpoint(const char *id,const uint8_t *data,uint32_t bytes,
                             const uint32_t version[3],uint32_t schema,bool acceptUpgrade) {
  if(!documentReady() || bytes>MaximumData || (bytes && !data) || !path(id,m_path)) return false;
  AppDocumentRoot::Root before,after;bool converted=documentRoot(id,&before);
  if(converted) {
    if(before.serial==0xffffffffu) return false;
    after=before;after.serial++;
    if(!(before.flags&AppDocumentRoot::PendingUpgrade)) after.previous=before.current;
  } else {
    uint8_t header[64];
    if(!version || !readHeader(m_path,header) || get(header+12)==0xffffffffu || acceptUpgrade) return false;
    for(unsigned i=0;i<3;i++) { if(version[i]>999999) return false;after.highVersion[i]=version[i]; }
    after.serial=get(header+12)+1;after.current.package=after.serial;after.current.packageBytes=get(header+16);
  }
  if(acceptUpgrade) {
    if(!(before.flags&AppDocumentRoot::PendingUpgrade)) return false;
    after.flags=0;after.previous={};
  }
  if(converted && before.current.dataKind==AppDocumentRoot::FileIndex) {
    after.current.dataSchema=schema;
    if(!m_files.begin(id,nullptr,bytes,before,after,false,0,data,true)) return false;
    m_fileAdmission=true;m_fileBudgetPackage=bytes;m_fileBudgetData=AppFileIndex::MaximumBytes;
    m_documentOperation=false;m_fileOperation=true;m_state=State::Writing;return true;
  }
  after.current.data=after.serial;after.current.dataBytes=bytes;after.current.dataSchema=schema;
  if(!documentSpace(converted?0:after.current.packageBytes,bytes,!converted)) return false;
  if(!m_documents.begin(id,before,after,nullptr,data,true,!converted)) return false;
  m_documentOperation=true;m_state=State::Writing;return true;
}
bool Volume::beginUpgrade(const char *id,const uint8_t *package,uint32_t bytes,const uint32_t version[3]) {
  if(!documentReady() || !package || bytes<468 || bytes>MaximumPackage || !version) return false;
  AppDocumentRoot::Root before;
  if(!documentRoot(id,&before) || before.serial==0xffffffffu || before.flags&AppDocumentRoot::PendingUpgrade) return false;
  int order=0;
  for(unsigned i=0;i<3;i++) {
    if(version[i]>999999) return false;
    if(!order && version[i]!=before.highVersion[i]) order=version[i]>before.highVersion[i]?1:-1;
  }
  if(order<=0) return false;
  auto after=before;after.serial++;after.previous=before.current;after.flags=AppDocumentRoot::PendingUpgrade;
  memcpy(after.highVersion,version,sizeof(after.highVersion));after.current.package=after.serial;after.current.packageBytes=bytes;
  if(!documentSpace(bytes,0,false)) return false;
  if(!m_documents.begin(id,before,after,package,nullptr,false,false)) return false;
  m_documentOperation=true;m_state=State::Writing;return true;
}
bool Volume::beginAccept(const char *id,uint32_t expectedSchema) {
  if(!documentReady()) return false;
  AppDocumentRoot::Root before;
  if(!documentRoot(id,&before) || before.serial==0xffffffffu || !(before.flags&AppDocumentRoot::PendingUpgrade) ||
     before.current.dataSchema!=expectedSchema) return false;
  auto after=before;after.serial++;after.flags=0;after.previous={};
  if(!documentSpace(0,0,false)) return false;
  if(!m_documents.begin(id,before,after,nullptr,nullptr,false,false)) return false;
  m_documentOperation=true;m_state=State::Writing;return true;
}
bool Volume::beginRollback(const char *id) {
  if(!documentReady()) return false;
  AppDocumentRoot::Root before;
  if(!documentRoot(id,&before) || before.serial==0xffffffffu || !(before.flags&AppDocumentRoot::PendingUpgrade)) return false;
  auto after=before;after.serial++;after.current=before.previous;after.previous={};after.flags=0;
  if(!documentSpace(0,0,false)) return false;
  if(!m_documents.begin(id,before,after,nullptr,nullptr,false,false)) return false;
  m_documentOperation=true;m_state=State::Writing;return true;
}
bool Volume::recoveryPackage(const char *id,uint8_t *package,size_t capacity,Entry *out) {
  AppDocumentRoot::Root root;uint32_t bytes;
  if(!out || !documentReady() || !documentRoot(id,&root) || !(root.flags&AppDocumentRoot::PendingUpgrade) ||
     !m_documents.privateBytes(id,root.previous,&bytes) || !m_documents.readRecoveryPackage(id,package,capacity)) return false;
  *out={root.previous.package,root.previous.packageBytes,bytes};return true;
}
bool Volume::pruneOrphans() {
  lfs_dir_t dir;int rc=lfs_dir_open(&m_fs,&dir,"objects");
  if(rc==LFS_ERR_NOENT) return true;
  if(rc) { fail();return false; }
  lfs_info info;bool ok=true;unsigned entries=0;
  while((rc=lfs_dir_read(&m_fs,&dir,&info))>0) {
    if(!strcmp(info.name,".") || !strcmp(info.name,"..")) continue;
    char file[64];
    if(++entries>MaximumEntries || info.type!=LFS_TYPE_DIR || !path(info.name,file)) { ok=false;break; }
    lfs_info app;int exists=lfs_stat(&m_fs,file,&app);
    if(exists==LFS_ERR_NOENT) {
      if(!m_documents.prune(info.name)) { ok=false;break; }
      m_documentOperation=true;m_state=State::Writing;
      if(!finish()) { ok=false;break; }
    } else if(exists) { ok=false;break; }
  }
  ok=(lfs_dir_close(&m_fs,&dir)==0)&&rc>=0&&ok;
  if(!ok) fail();else { m_state=State::Ready;m_documentOperation=false; }
  return ok;
}
bool Volume::nextFileRoot(const char *id,AppDocumentRoot::Root *before,AppDocumentRoot::Root *after) {
  if(!documentReady() || !documentRoot(id,before) || before->serial==0xffffffffu) return false;
  *after=*before;after->serial++;
  if(!(before->flags&AppDocumentRoot::PendingUpgrade)) after->previous=before->current;
  return true;
}
bool Volume::beginFile(const char *id,const char *name,uint32_t bytes,bool patch,uint32_t offset) {
  AppDocumentRoot::Root before,after;
  if(!name || bytes>64*1024*1024 || !nextFileRoot(id,&before,&after)) return false;
  uint32_t extra=patch?((bytes+AppFileIndex::ChunkBytes-1)/AppFileIndex::ChunkBytes+2)*BlockBytes:bytes;
  if(!m_files.begin(id,name,bytes,before,after,patch,offset)) return false;
  m_fileAdmission=true;m_fileBudgetPackage=extra;m_fileBudgetData=AppFileIndex::MaximumBytes;
  m_documentOperation=false;m_fileOperation=true;m_state=State::Writing;return true;
}
bool Volume::admitChunk(void *context,uint32_t bytes) {
  auto &volume=*static_cast<Volume *>(context);Space usage;
  if(!volume.space(&usage)) return false;
  // Growing user output must not consume the volume's reserved maintenance
  // blocks. Package updates/recovery retain access to those blocks through
  // documentSpace; staging leaves two metadata blocks plus the FILE5 payload
  // and file index for its own commit, including an empty streamed output.
  uint32_t needed=3+(bytes?fileBlocks(bytes):0)+fileBlocks(AppFileIndex::MaximumBytes);
  return usage.allocated<=usage.capacity && needed<=(usage.capacity-usage.allocated)/BlockBytes;
}
bool Volume::beginStream(const char *id,const char *name,AppFileStore::Store::StreamMode mode) {
  AppDocumentRoot::Root before,after;
  if(!nextFileRoot(id,&before,&after) || !m_files.beginStream(id,name,mode,before,after)) return false;
  // The final size is unknown. Admission reserves index/commit headroom before
  // each chunk flush and again before publishing even an empty file.
  m_fileAdmission=false;m_documentOperation=false;m_fileOperation=true;m_state=State::Writing;return true;
}
bool Volume::changeFile(const char *id,const char *name,const char *destination,bool directory) {
  AppDocumentRoot::Root before,after;
  if(!nextFileRoot(id,&before,&after) ||
     !m_files.mutate(id,name,destination,directory,before,after)) return false;
  m_fileAdmission=true;m_fileBudgetPackage=0;m_fileBudgetData=AppFileIndex::MaximumBytes;
  m_documentOperation=false;m_fileOperation=true;m_state=State::Writing;return true;
}
int Volume::fileInfo(const char *id,const char *name,uint32_t *kind,uint32_t *bytes) {
  if(!m_mounted || m_open || !kind || !bytes || !path(id,m_path)) return LFS_ERR_IO;
  AppDocumentRoot::Root root;
  if(documentRoot(id,&root)) return m_documents.fileInfo(id,root.current,name,kind,bytes);
  // A verified FILE2 header has no named files. Corrupt/unknown roots fail;
  // they must never be treated as an empty namespace or reformatted.
  uint8_t header[64];return readHeader(m_path,header)?0:LFS_ERR_IO;
}
bool Volume::openFile(const char *id,const char *name) {
  AppDocumentRoot::Root root;
  if(!documentReady() || !documentRoot(id,&root) || !m_files.openRead(id,name,root)) return false;
  m_documentOperation=false;m_fileOperation=true;m_fileAdmission=false;return true;
}
int Volume::listFiles(const char *id,const char *directory,uint32_t offset,uint32_t *generation,
                       AppFileIndex::Entry *out,uint32_t capacity,uint32_t *next) {
  if(!directory || (*directory && !AppFileIndex::path(directory)) || !generation ||
     !out || !capacity || !next || (offset && !*generation)) return LFS_ERR_INVAL;
  if(!m_mounted || m_open || m_state==State::Failed || !path(id,m_path)) return LFS_ERR_IO;
  AppDocumentRoot::Root root;
  if(documentRoot(id,&root)) {
    if(*generation && *generation!=root.serial) return CatalogChanged;
    int count=m_documents.listFiles(id,root.current,directory,offset,out,capacity,next);
    if(count>=0) *generation=root.serial;
    return count;
  }
  // A verified legacy header has an empty named namespace. Inspection must
  // not convert it, create a root, or treat malformed media as an empty app.
  uint8_t header[64];if(!readHeader(m_path,header)) return LFS_ERR_IO;
  uint32_t serial=AppFileIndex::get(header+12);
  if(*generation && *generation!=serial) return CatalogChanged;
  if(*directory) return LFS_ERR_NOENT;
  if(offset) return LFS_ERR_INVAL;
  *generation=serial;*next=0;return 0;
}
bool Volume::fileUsage(const char *id,FileUsage *out) {
  if(!m_mounted || m_open || m_state==State::Failed || !out || !path(id,m_path)) return false;
  FileUsage usage{};AppDocumentRoot::Root root;
  if(documentRoot(id,&root)) {
    usage.generation=root.serial;usage.packageBytes=root.current.packageBytes;
    if(!m_documents.fileUsage(id,root.current,&usage.data)) return false;
  } else {
    uint8_t header[64];if(!readHeader(m_path,header)) return false;
    usage.generation=AppFileIndex::get(header+12);
    usage.packageBytes=AppFileIndex::get(header+16);
    usage.data.privateBytes=AppFileIndex::get(header+20);
  }
  *out=usage;return true;
}
bool Volume::closeReader() {
  if(!m_fileOperation || !m_files.closeRead()) return false;
  m_fileOperation=false;m_state=State::Ready;return true;
}
bool Volume::retainChunk(void *context,const char *id,uint32_t generation,uint32_t part) {
  const auto &v=*static_cast<Volume *>(context);
  for(const auto &reader:v.m_readers) if(reader.retains(id,generation,part)) return true;
  return false;
}
bool Volume::hasSnapshots(const char *id) const {
  for(const auto &reader:m_readers) if(reader.belongsTo(id)) return true;
  return false;
}
int Volume::snapshotSlot(const char *id,uint32_t token) const {
  if(!token) return -1;
  unsigned slot=token%MaximumReaders;
  return m_readerTokens[slot]==token && m_readers[slot].belongsTo(id)?static_cast<int>(slot):-1;
}
uint32_t Volume::openSnapshot(const char *id,const char *name) {
  if(!m_mounted || m_open || m_state==State::Failed ||
     (!documentReady() && !m_fileOperation) || m_readerSerial==0x3fffffffu) return 0;
  unsigned slot=0;while(slot<MaximumReaders && m_readerTokens[slot]) slot++;
  if(slot==MaximumReaders) return 0;
  AppDocumentRoot::Root root;
  // root/snapshot reject while the shared document engine is working. Already
  // open snapshots have independent lfs files and can advance during that work.
  if(!documentRoot(id,&root) || !m_readers[slot].open(&m_fs,&m_documents,id,name,root)) return 0;
  uint32_t token=(++m_readerSerial)*MaximumReaders+slot;m_readerTokens[slot]=token;return token;
}
int Volume::readSnapshot(const char *id,uint32_t token,void *out,uint32_t bytes) {
  int slot=snapshotSlot(id,token);return slot<0?-1:m_readers[slot].read(out,bytes);
}
int Volume::readCachedSnapshot(const char *id,uint32_t token,void *out,uint32_t bytes) {
  int slot=snapshotSlot(id,token);return slot<0?-1:m_readers[slot].readCached(out,bytes);
}
bool Volume::stepSnapshot(const char *id,uint32_t token) {
  int slot=snapshotSlot(id,token);if(slot<0) return false;
  m_readers[slot].step();return true;
}
bool Volume::seekSnapshot(const char *id,uint32_t token,uint32_t offset) {
  int slot=snapshotSlot(id,token);return slot>=0 && m_readers[slot].seek(offset);
}
bool Volume::snapshotInfo(const char *id,uint32_t token,SnapshotInfo *out) const {
  int slot=snapshotSlot(id,token);if(slot<0 || !out) return false;
  const auto &reader=m_readers[slot];
  *out={reader.size(),reader.position(),reader.verifiedBytes(),reader.state()};return true;
}
bool Volume::closeSnapshot(const char *id,uint32_t token) {
  int slot=snapshotSlot(id,token);if(slot<0) return false;
  bool ok=m_readers[slot].close();m_readerTokens[slot]=0;return ok;
}
bool Volume::closeSnapshots(const char *id) {
  bool ok=true;
  for(unsigned i=0;i<MaximumReaders;i++) if(m_readerTokens[i] && (!id || m_readers[i].belongsTo(id))) {
    ok=m_readers[i].close()&&ok;m_readerTokens[i]=0;
  }
  return ok;
}
} // namespace AppStorage
} // namespace PrimeG2
