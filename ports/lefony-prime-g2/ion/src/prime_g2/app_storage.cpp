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
Volume::Volume(Backend backend)
    : m_backend(backend), m_legacy(backend), m_fs{}, m_config{}, m_file{}, m_fileConfig{},
      m_readCache{}, m_writeCache{}, m_fileCache{}, m_lookahead{}, m_scratch{}, m_protected{},
      m_used{}, m_identity{}, m_header{}, m_path{}, m_package(nullptr), m_data(nullptr),
      m_packageBytes(0), m_dataBytes(0), m_cursor(0), m_hash{}, m_state(State::Unprovisioned),
      m_icon(false), m_mounted(false), m_open(false), m_legacyValid(false), m_finishedMigration(false) {
  m_config.context = this;
  m_config.read = readBlock;
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
}
Volume::~Volume() {
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
int Volume::programBlock(const lfs_config *c, lfs_block_t block, lfs_off_t offset, const void *data,
                         lfs_size_t size) {
  auto &v = *static_cast<Volume *>(c->context);
  if (block >= FSBlocks || offset % PageBytes || size % PageBytes || offset > BlockBytes ||
      size > BlockBytes - offset)
    return LFS_ERR_INVAL;
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
    lfs_unmount(&m_fs);
    m_mounted = false;
  }
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
    return true;
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
  if (!out || !path(id, file, icon) || !readHeader(file, header))
    return false;
  *out = {get(header + 12), get(header + 16), get(header + 20)};
  return true;
}
bool Volume::read(const char *id, uint8_t *package, size_t capacity, uint8_t *data,
                  size_t dataCapacity, bool icon) {
  char file[64];
  uint8_t header[64];
  if (!path(id, file, icon) || !readHeader(file, header) || !package || capacity < get(header + 16) ||
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
bool Volume::list(Visitor visitor, void *context) {
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
    Entry e;
    if (!entry(info.name, &e) || !visitor(context, info.name, e)) {
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
  if (!m_mounted || (m_state != State::Ready && m_state != State::Complete) || !path(id, m_path, icon) ||
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
  Entry old = {};
  entry(id, &old, icon);
  if (old.generation == 0xffffffffu || (!packageBytes && !old.packageBytes))
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
void Volume::step() {
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
    if (ok)
      m_state = State::Complete;
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
  if (m_state == State::Writing || m_state == State::Verifying) {
    if (closeFile())
      m_state = State::Ready;
    else
      fail();
  }
}
} // namespace AppStorage
} // namespace PrimeG2
