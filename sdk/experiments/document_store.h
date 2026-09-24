// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Architecture experiment only. Not linked into firmware or a public SDK API.
// Runs on the same littlefs implementation and geometry as profile 2, but uses
// a separate synthetic filesystem. This is not an on-device migration writer.
#ifndef LEFONY_DOCUMENT_STORE_EXPERIMENT_H
#define LEFONY_DOCUMENT_STORE_EXPERIMENT_H
#include "littlefs/lfs.h"
#include "native_app_digest.h"
#include "legacy_app_storage.h"
#include <stdint.h>
#include <string.h>

namespace DocumentStoreExperiment {
namespace NativeAppHash = PrimeG2::NativeAppHash;
enum class Result { Ok, Missing, Invalid, Corrupt, IO, Limit };
struct Pair {
  uint32_t package, data, packageBytes, dataBytes;
  uint8_t packageHash[32], dataHash[32];
};
struct Root { uint32_t serial; Pair current, previous; };
class Store {
public:
  static constexpr uint32_t MaximumPackage = PrimeG2::LegacyAppStorage::MaximumPackage;
  static constexpr uint32_t MaximumData = PrimeG2::LegacyAppStorage::MaximumData;
  static constexpr unsigned RootBytes = 208;
  explicit Store(lfs_t *fs) : m_fs(fs), m_cache{}, m_scratch{}, m_packageWrites(0), m_dataWrites(0) {}
  uint32_t packageWrites() const { return m_packageWrites; }
  uint32_t dataWrites() const { return m_dataWrites; }
  Result read(Root &root) {
    lfs_info info;
    int status = lfs_stat(m_fs, "x/active", &info);
    if (status == LFS_ERR_NOENT) return Result::Missing;
    if (status < 0) return Result::IO;
    uint8_t wire[RootBytes], digest[32];
    if (info.size != RootBytes || !readFile("x/active", wire, RootBytes)) return Result::Corrupt;
    NativeAppHash::sha256(wire, RootBytes - 32, digest);
    if (memcmp(wire, "LFDOCX1\0", 8) || get(wire + 8) != 1 ||
        memcmp(digest, wire + RootBytes - 32, 32)) return Result::Corrupt;
    root.serial = get(wire + 12);
    decode(wire + 16, root.current); decode(wire + 96, root.previous);
    if (!root.serial || !valid(root.current, root.serial) ||
        (root.previous.package && !valid(root.previous, root.serial)) ||
        (!root.previous.package && !empty(root.previous))) return Result::Corrupt;
    if (!verify(root.current) || (root.previous.package && !verify(root.previous))) return Result::Corrupt;
    return Result::Ok;
  }
  // A null package means checkpoint the current package with replacement data.
  // A package starts a tentative upgrade: retain the old complete pair until
  // an explicit acceptance or rollback. Checkpoints do not discard that pair.
  Result commit(const uint8_t *package, uint32_t packageBytes, const uint8_t *data, uint32_t dataBytes) {
    if ((package && (!packageBytes || packageBytes > MaximumPackage)) ||
        (!package && packageBytes) || dataBytes > MaximumData || (dataBytes && !data)) return Result::Invalid;
    Root root{};
    Result status = read(root);
    if (status != Result::Ok && status != Result::Missing) return status;
    if (status == Result::Missing && !package) return Result::Missing;
    // A second upgrade cannot silently evict the last known-good pair.
    if (root.serial == UINT32_MAX || (package && root.previous.package)) return Result::Limit;
    int rc = lfs_mkdir(m_fs, "x");
    if (rc && rc != LFS_ERR_EXIST) return Result::IO;
    if (!collect(root)) return Result::IO;
    root.serial++;
    Pair next = root.current;
    if (package) {
      root.previous = root.current;
      next.package = root.serial; next.packageBytes = packageBytes;
      NativeAppHash::sha256(package, packageBytes, next.packageHash);
      if (!writeBlob('p', next.package, package, packageBytes)) return Result::IO;
    }
    next.data = root.serial; next.dataBytes = dataBytes;
    NativeAppHash::sha256(data, dataBytes, next.dataHash);
    if (!writeBlob('d', next.data, data, dataBytes)) return Result::IO;
    root.current = next;
    if (!verify(next)) return Result::Corrupt;
    return commitRoot(root) ? Result::Ok : Result::IO;
  }
  Result accept() { return select(false); }
  Result rollback() { return select(true); }
  Result data(uint8_t *out, uint32_t capacity, uint32_t &size) {
    Root root{}; Result status = read(root);
    if (status != Result::Ok) return status;
    if (capacity < root.current.dataBytes || (root.current.dataBytes && !out)) return Result::Invalid;
    char name[12]; path('d', root.current.data, name);
    if (!readFile(name, out, root.current.dataBytes)) return Result::IO;
    size = root.current.dataBytes; return Result::Ok;
  }
private:
  static uint32_t get(const uint8_t *p) { return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24; }
  static void put(uint8_t *p, uint32_t n) { for (unsigned i=0; i<4; i++) p[i] = n >> (8*i); }
  static void path(char kind, uint32_t generation, char out[12]) {
    memcpy(out, "x/p00000000", 12); out[2] = kind;
    for (unsigned i=0; i<8; i++) out[10-i] = "0123456789abcdef"[(generation >> (4*i)) & 15];
  }
  static void encode(uint8_t *p, const Pair &pair) {
    put(p, pair.package); put(p+4, pair.data); put(p+8, pair.packageBytes); put(p+12, pair.dataBytes);
    memcpy(p+16, pair.packageHash, 32); memcpy(p+48, pair.dataHash, 32);
  }
  static void decode(const uint8_t *p, Pair &pair) {
    pair.package=get(p); pair.data=get(p+4); pair.packageBytes=get(p+8); pair.dataBytes=get(p+12);
    memcpy(pair.packageHash, p+16, 32); memcpy(pair.dataHash, p+48, 32);
  }
  static bool empty(const Pair &pair) { uint8_t wire[80]{}, actual[80]; encode(actual,pair); return !memcmp(wire,actual,80); }
  static bool valid(const Pair &pair, uint32_t serial) {
    return pair.package && pair.data && pair.package <= serial && pair.data <= serial &&
      pair.packageBytes && pair.packageBytes <= MaximumPackage && pair.dataBytes <= MaximumData;
  }
  bool readFile(const char *name, uint8_t *out, uint32_t size) {
    lfs_file_t file{}; lfs_file_config config{}; config.buffer=m_cache;
    if (lfs_file_opencfg(m_fs,&file,name,LFS_O_RDONLY,&config)<0) return false;
    bool ok=lfs_file_size(m_fs,&file)==static_cast<lfs_soff_t>(size) &&
      (!size || lfs_file_read(m_fs,&file,out,size)==static_cast<lfs_ssize_t>(size));
    return lfs_file_close(m_fs,&file)==0 && ok;
  }
  bool writeFile(const char *name, const uint8_t *data, uint32_t size, uint32_t *counter=nullptr) {
    lfs_file_t file{}; lfs_file_config config{}; config.buffer=m_cache;
    if (lfs_file_opencfg(m_fs,&file,name,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_TRUNC,&config)<0) return false;
    bool ok=true;
    for (uint32_t offset=0;offset<size;) {
      uint32_t n=size-offset; if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      if (lfs_file_write(m_fs,&file,data+offset,n)!=static_cast<lfs_ssize_t>(n)) { ok=false;break; }
      if(counter) *counter+=n;
      offset+=n;
    }
    return lfs_file_close(m_fs,&file)==0 && ok;
  }
  bool writeBlob(char kind,uint32_t generation,const uint8_t *data,uint32_t size) {
    char name[12];path(kind,generation,name);
    return writeFile(name,data,size,kind=='p'?&m_packageWrites:&m_dataWrites);
  }
  bool hashFile(char kind,uint32_t generation,uint32_t size,const uint8_t *expected) {
    char name[12];path(kind,generation,name);
    lfs_file_t file{};lfs_file_config config{};config.buffer=m_cache;
    if(lfs_file_opencfg(m_fs,&file,name,LFS_O_RDONLY,&config)<0) return false;
    bool ok=lfs_file_size(m_fs,&file)==static_cast<lfs_soff_t>(size);
    NativeAppHash::SHA256 hash;NativeAppHash::shaInit(&hash);
    for(uint32_t offset=0;ok && offset<size;) {
      uint32_t n=size-offset;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      ok=lfs_file_read(m_fs,&file,m_scratch,n)==static_cast<lfs_ssize_t>(n);
      if(ok) NativeAppHash::shaUpdate(&hash,m_scratch,n);
      offset+=n;
    }
    uint8_t digest[32];NativeAppHash::shaFinal(&hash,digest);
    return lfs_file_close(m_fs,&file)==0 && ok && !memcmp(digest,expected,32);
  }
  bool verify(const Pair &pair) { return hashFile('p',pair.package,pair.packageBytes,pair.packageHash) && hashFile('d',pair.data,pair.dataBytes,pair.dataHash); }
  bool commitRoot(const Root &root) {
    uint8_t wire[RootBytes]{};memcpy(wire,"LFDOCX1\0",8);put(wire+8,1);put(wire+12,root.serial);
    encode(wire+16,root.current);encode(wire+96,root.previous);
    NativeAppHash::sha256(wire,RootBytes-32,wire+RootBytes-32);
    if(!writeFile("x/pending",wire,RootBytes)) return false;
    uint8_t check[RootBytes];
    return readFile("x/pending",check,RootBytes) && !memcmp(wire,check,RootBytes) && lfs_rename(m_fs,"x/pending","x/active")==0;
  }
  Result select(bool previous) {
    Root root{};Result status=read(root);if(status!=Result::Ok) return status;
    if(!root.previous.package) return Result::Missing;
    if(root.serial==UINT32_MAX) return Result::Limit;
    if(previous) root.current=root.previous;
    root.previous={};root.serial++;
    return commitRoot(root)?Result::Ok:Result::IO;
  }
  bool collect(const Root &root) {
    // Each attempt can leave at most two blobs. Do not delete the directory
    // cursor's current entry: restart after each deletion, with a hard cap.
    char keep[4][12];path('p',root.current.package,keep[0]);path('d',root.current.data,keep[1]);
    path('p',root.previous.package,keep[2]);path('d',root.previous.data,keep[3]);
    for(unsigned removed=0;removed<16;removed++) {
      lfs_dir_t dir{};if(lfs_dir_open(m_fs,&dir,"x")<0) return false;
      lfs_info info{};int rc;char obsolete[12]{};
      while((rc=lfs_dir_read(m_fs,&dir,&info))>0) {
        if(info.type!=LFS_TYPE_REG || strlen(info.name)!=9 || (info.name[0]!='p' && info.name[0]!='d')) continue;
        char name[12];memcpy(name,"x/",2);memcpy(name+2,info.name,10);
        bool retained=false;for(const auto &k:keep) retained|=!strcmp(name,k);
        if(!retained) { memcpy(obsolete,name,12);break; }
      }
      if(lfs_dir_close(m_fs,&dir)<0 || rc<0) return false;
      if(!obsolete[0]) return true;
      if(lfs_remove(m_fs,obsolete)<0) return false;
    }
    return false;
  }
  lfs_t *m_fs;
  uint8_t m_cache[2048],m_scratch[2048];
  uint32_t m_packageWrites,m_dataWrites;
};
}
#endif
