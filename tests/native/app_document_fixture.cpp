// SPDX-License-Identifier: GPL-3.0-or-later
// Synthetic emulator fixture producer/reader; never accesses a USB device.
#include "app_storage.h"
#include "app_root_record.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <map>
#include <set>
#include <vector>
using namespace PrimeG2::AppStorage;
using Page=std::array<uint8_t,PageBytes>;
#include "app_storage_fixture.h"
using Root=PrimeG2::AppDocumentRoot::Root;
#include "app_raw_fixture.h"
static void finish(Volume &v) {
  for(unsigned i=0;i<200000 && v.state()!=State::Complete && v.state()!=State::Failed;i++) v.step();
  assert(v.state()==State::Complete);
}
static uint32_t word(const uint8_t *p) { return uint32_t(p[0])|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24; }
static void load(Flash &flash,const char *path) {
  std::ifstream input(path,std::ios::binary);assert(input);char magic[8];input.read(magic,8);assert(!memcmp(magic,"PG2OVL1\n",8));
  uint8_t header[8];
  while(input.read(reinterpret_cast<char *>(header),8)) {
    assert(!header[1] && !header[2] && !header[3]);uint32_t index=word(header+4);
    if(header[0]==1) {
      Flash::range(index/PagesPerBlock);Page data;uint8_t spare[64];
      assert(input.read(reinterpret_cast<char *>(data.data()),PageBytes));assert(input.read(reinterpret_cast<char *>(spare),64));
      flash.pages[index]=data;
    } else {
      assert(header[0]==2);Flash::range(index);
      for(unsigned i=0;i<PagesPerBlock;i++) flash.pages.erase(index*PagesPerBlock+i);
    }
  }
  assert(input.eof() && input.gcount()==0);
}
static void save(const Flash &flash,const char *path) {
  std::ofstream output(path,std::ios::binary|std::ios::trunc);assert(output);output.write("PG2OVL1\n",8);
  uint8_t spare[64];memset(spare,255,sizeof(spare));
  for(const auto &p:flash.pages) {
    uint8_t header[8]={1,0,0,0};for(unsigned i=0;i<4;i++) header[4+i]=p.first>>(8*i);
    output.write(reinterpret_cast<const char *>(header),8);output.write(reinterpret_cast<const char *>(p.second.data()),PageBytes);
    output.write(reinterpret_cast<const char *>(spare),sizeof(spare));
  }
  output.flush();assert(output.good());
}
int main(int argc,char **argv) {
  assert(argc==3 || argc==4 || argc==6);Flash flash;std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
  if(!strcmp(argv[1],"fill-shared") || !strcmp(argv[1],"release-shared")) {
    // Occupy actual littlefs blocks in a disposable overlay, independently of
    // the app's logical quota. Never change counters or firmware limits.
    assert(argc==3);load(flash,argv[2]);
    {Raw raw(flash);
      if(!strcmp(argv[1],"fill-shared")) raw.fill();
      else for(const char *prefix:{"filler","smallfill"}) for(unsigned i=0;i<1024;i++) {
        char name[32];snprintf(name,sizeof(name),"%s%u",prefix,i);
        if(raw.exists(name)) raw.remove(name);
      }
    }
    Volume v(flash.backend());assert(v.mount());Space space;assert(v.space(&space));
    save(flash,argv[2]);
    printf("{\"allocated\":%u,\"available\":%u,\"capacity\":%u}\n",space.allocated,space.available,space.capacity);return 0;
  }
  if(!strcmp(argv[1],"file-media")) {
    // Locate one real chunk page for QEMU BCH fault injection. The public app
    // still performs every read; this read-only helper never changes the image.
    assert(argc==6);load(flash,argv[2]);Root root;
    {Volume v(flash.backend());assert(v.mount() && v.documentRoot(argv[3],&root));}
    Raw raw(flash);PrimeG2::AppDocumentStore::Store documents(&raw.fs);
    PrimeG2::AppFileIndex::Index index;
    assert(documents.index(argv[3],root.current,&index));
    int found=index.find(argv[4]);assert(found>0);
    const auto &entry=index.entry[found];unsigned offset=0;char extra;
    assert(sscanf(argv[5],"%u%c",&offset,&extra)==1 && offset<entry.bytes);
    const auto &extent=index.extent[entry.first+offset/PrimeG2::AppFileIndex::ChunkBytes];
    unsigned within=offset%PrimeG2::AppFileIndex::ChunkBytes;
    char leaf[32],path[96];PrimeG2::AppFileIndex::objectName(extent,leaf);
    snprintf(path,sizeof(path),"objects/%s/%s",argv[3],leaf);
    lfs_file_t file{};lfs_file_config config{};uint8_t cache[2048];config.buffer=cache;
    assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDONLY,&config));
    assert(!(file.flags&LFS_F_INLINE) && file.ctz.size==extent.bytes && extent.bytes<BlockBytes);
    uint32_t page=(FirstBlock+2+file.ctz.head)*PagesPerBlock+within/PageBytes;
    assert(!lfs_file_close(&raw.fs,&file));
    printf("{\"generation\":%u,\"file_bytes\":%u,\"chunk_bytes\":%u,\"page\":%u,\"page_offset\":%u}\n",
      root.serial,entry.bytes,extent.bytes,page,within%PageBytes);return 0;
  }
  if(!strcmp(argv[1],"canonical-media")) {
    // Locate a FILE2 canonical header for a transient modeled read failure.
    // Only inspect a disposable overlay; do not rewrite or repair its contents.
    assert(argc==4);load(flash,argv[2]);Raw raw(flash);char path[64];
    assert(strlen(argv[3])<=48);snprintf(path,sizeof(path),"apps/%s.app",argv[3]);
    lfs_file_t file{};lfs_file_config config{};uint8_t cache[2048],header[64];config.buffer=cache;
    assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDONLY,&config));
    assert(!(file.flags&LFS_F_INLINE) && file.ctz.size>=64 && file.ctz.size<BlockBytes);
    assert(lfs_file_read(&raw.fs,&file,header,sizeof(header))==sizeof(header));
    assert(!memcmp(header,"LFAFILE2",8) && word(header+8)==2 && word(header+12));
    uint32_t page=(FirstBlock+2+file.ctz.head)*PagesPerBlock;
    uint32_t bytes=file.ctz.size;assert(!lfs_file_close(&raw.fs,&file));
    printf("{\"generation\":%u,\"canonical_bytes\":%u,\"page\":%u,\"page_offset\":0}\n",
      word(header+12),bytes,page);return 0;
  }
  if(!strcmp(argv[1],"root-media")) {
    // Independent read-only FILE5 location and exact-byte oracle. Only accepts
    // disposable PG2OVL1 images, with no device or private NAND access.
    assert(argc==4);load(flash,argv[2]);Raw raw(flash);char path[64];
    assert(strlen(argv[3])<=48);snprintf(path,sizeof(path),"apps/%s.app",argv[3]);
    namespace R=PrimeG2::AppRootRecord;R::Info root;
    assert(R::read(&raw.fs,path,argv[3],raw.cache,&root)==R::Result::Ok && root.copies==R::Copies::Both);
    lfs_file_t file{};lfs_file_config cfg{};cfg.buffer=raw.cache;
    assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDONLY,&cfg));
    assert(!(file.flags&LFS_F_INLINE) && lfs_file_size(&raw.fs,&file)==R::Bytes);
    uint32_t page=(FirstBlock+2+file.ctz.head)*PagesPerBlock;uint8_t wire[R::Bytes],attribute[R::Bytes];
    assert(lfs_file_read(&raw.fs,&file,wire,sizeof(wire))==sizeof(wire) && !lfs_file_close(&raw.fs,&file));
    assert(lfs_getattr(&raw.fs,path,R::Attribute,attribute,sizeof(attribute))==sizeof(attribute) && !memcmp(wire,attribute,sizeof(wire)));
    printf("{\"generation\":%u,\"canonical_bytes\":%u,\"page\":%u,\"page_offset\":0,\"original_hex\":\"",root.root.serial,R::Bytes,page);
    for(uint8_t b:wire)printf("%02x",b);puts("\"}");return 0;
  }
  if(!strcmp(argv[1],"corrupt-keys")) {
    assert(argc==3);load(flash,argv[2]);{Raw raw(flash);raw.corrupt("developer-keys");}
    save(flash,argv[2]);puts("{\"synthetic_key_corruption\":true}");return 0;
  }
  if(!strcmp(argv[1],"key-media")) {
    // Read-only location and byte oracle for synthetic registry media faults.
    assert(argc==3);load(flash,argv[2]);Raw raw(flash);lfs_file_t file{};lfs_file_config cfg{};cfg.buffer=raw.cache;
    assert(!lfs_file_opencfg(&raw.fs,&file,"developer-keys",LFS_O_RDONLY,&cfg));
    assert(!(file.flags&LFS_F_INLINE) && file.ctz.size==2752);
    uint8_t bytes[2752];assert(lfs_file_read(&raw.fs,&file,bytes,sizeof(bytes))==sizeof(bytes));
    uint32_t page=(FirstBlock+2+file.ctz.head)*PagesPerBlock;
    assert(!lfs_file_close(&raw.fs,&file));
    printf("{\"page\":%u,\"page_offset\":0,\"bytes\":2752,\"original_hex\":\"",page);
    for(uint8_t b:bytes)printf("%02x",b);puts("\"}");return 0;
  }
  if(!strcmp(argv[1],"corrupt-code") || !strcmp(argv[1],"missing-code") ||
     !strcmp(argv[1],"truncate-code") || !strcmp(argv[1],"corrupt-envelope") ||
     !strcmp(argv[1],"truncate-legacy") || !strcmp(argv[1],"corrupt-root")) {
    assert(argc==4);load(flash,argv[2]);Root root;bool documents;
    {Volume v(flash.backend());assert(v.mount());documents=v.documentRoot(argv[3],&root);}
    {Raw raw(flash);char path[96];bool canonical=!documents || !strcmp(argv[1],"corrupt-root");
      if(canonical) snprintf(path,sizeof(path),"apps/%s.app",argv[3]);
      else snprintf(path,sizeof(path),"objects/%s/p%08x",argv[3],root.current.package);
      if(!strcmp(argv[1],"corrupt-root")) raw.corruptRoot(path);
      else if(!strcmp(argv[1],"missing-code")) {assert(documents);raw.remove(path);}
      else {
        lfs_file_t file{};lfs_file_config cfg{};uint8_t cache[2048];cfg.buffer=cache;
        assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDWR,&cfg));
        if(!strcmp(argv[1],"truncate-legacy")) {assert(!documents);assert(!lfs_file_truncate(&raw.fs,&file,64));}
        else if(!strcmp(argv[1],"truncate-code")) assert(!lfs_file_truncate(&raw.fs,&file,documents?17:64+352));
        else {
          unsigned offset=(documents?0:64)+(!strcmp(argv[1],"corrupt-envelope")?96:352);uint8_t byte;
          assert(lfs_file_seek(&raw.fs,&file,offset,LFS_SEEK_SET)==int(offset) && lfs_file_read(&raw.fs,&file,&byte,1)==1);
          byte^=128;assert(lfs_file_seek(&raw.fs,&file,offset,LFS_SEEK_SET)==int(offset) && lfs_file_write(&raw.fs,&file,&byte,1)==1);
        }
        assert(!lfs_file_close(&raw.fs,&file));
      }
    }
    save(flash,argv[2]);puts("{\"synthetic_code_corruption\":true}");return 0;
  }
  if(!strcmp(argv[1],"corrupt-index") || !strcmp(argv[1],"corrupt-private")) {
    assert(argc==4);load(flash,argv[2]);Root root;
    {Volume v(flash.backend());assert(v.mount() && v.documentRoot(argv[3],&root));}
    {
      Raw raw(flash);char leaf[32],path[96];
      if(!strcmp(argv[1],"corrupt-private")) {
        PrimeG2::AppDocumentStore::Store documents(&raw.fs);PrimeG2::AppFileIndex::Index index;
        assert(documents.index(argv[3],root.current,&index) && index.entry[0].bytes);
        PrimeG2::AppFileIndex::objectName(index.extent[0],leaf);
      } else snprintf(leaf,sizeof(leaf),"d%08x",root.current.data);
      snprintf(path,sizeof(path),"objects/%s/%s",argv[3],leaf);raw.corrupt(path);
    }
    save(flash,argv[2]);puts("{\"synthetic_corruption\":true}");return 0;
  }
  if(!strcmp(argv[1],"seed-pending")) {
    // Deliberately construct a hash-valid retained pair with caller-supplied
    // package bytes. ARM tests must authenticate the old package themselves.
    // This only writes a fresh synthetic overlay, never a connected device.
    assert(argc==6);std::ifstream oldInput(argv[2],std::ios::binary),newInput(argv[3],std::ios::binary);
    assert(oldInput && newInput);
    std::vector<uint8_t> oldApp((std::istreambuf_iterator<char>(oldInput)),std::istreambuf_iterator<char>());
    std::vector<uint8_t> newApp((std::istreambuf_iterator<char>(newInput)),std::istreambuf_iterator<char>());
    Volume v(flash.backend());assert(v.initialize(package.data(),package.size(),data.data(),data.size(),
      [](const uint8_t *,size_t,char id[49]) { strcpy(id,"data-recovery");return true; }));
    uint32_t value=111,version[3]={1,0,0};const char *id=argv[5];
    assert(v.begin(id,oldApp.data(),oldApp.size(),reinterpret_cast<uint8_t *>(&value),4));finish(v);
    assert(v.beginCheckpoint(id,reinterpret_cast<uint8_t *>(&value),4,version,0));finish(v);
    const char text[]="old document";assert(v.beginFile(id,"document.txt",sizeof(text)-1));
    for(unsigned i=0;i<200000 && !v.fileWritable();i++) v.step();
    assert(v.fileWritable() && v.writeFile(reinterpret_cast<const uint8_t *>(text),sizeof(text)-1)==sizeof(text)-1);
    for(unsigned i=0;i<200000 && !v.fileWritable();i++) v.step();
    assert(v.commitFile());finish(v);version[0]=2;
    assert(v.beginUpgrade(id,newApp.data(),newApp.size(),version));finish(v);
    save(flash,argv[4]);puts("{\"pending_upgrade\":true}");return 0;
  }
  if(!strcmp(argv[1],"inspect-app")) {
    // Read the committed root/package after an ambiguous guest operation.
    // Mount and inspection never write the overlay back to disk.
    assert(argc==4);load(flash,argv[2]);Volume v(flash.backend());assert(v.mount());
    Entry entry;assert(v.entry(argv[3],&entry));
    assert(v.read(argv[3],package.data(),package.size(),data.data(),data.size()));
    PrimeG2::AppDocumentRoot::Root root;bool documents=v.documentRoot(argv[3],&root);
    uint8_t digest[32];PrimeG2::NativeAppHash::SHA256 hash;
    PrimeG2::NativeAppHash::shaInit(&hash);
    PrimeG2::NativeAppHash::shaUpdate(&hash,package.data(),entry.packageBytes);
    PrimeG2::NativeAppHash::shaFinal(&hash,digest);
    char hex[65];for(unsigned i=0;i<32;i++) snprintf(hex+2*i,3,"%02x",digest[i]);
    printf("{\"id\":\"%s\",\"package_bytes\":%u,\"private_bytes\":%u,\"package_sha256\":\"%s\",\"documents\":%s",
      argv[3],entry.packageBytes,entry.dataBytes,hex,documents?"true":"false");
    PrimeG2::NativeAppHash::sha256(data.data(),entry.dataBytes,digest);
    for(unsigned i=0;i<32;i++) snprintf(hex+2*i,3,"%02x",digest[i]);
    printf(",\"private_data_sha256\":\"%s\"",hex);
    if(documents) printf(",\"format\":%u,\"serial\":%u,\"package_generation\":%u,\"data_generation\":%u,\"data_kind\":%u,\"schema\":%u,\"pending_upgrade\":%u,\"previous_package\":%u,\"previous_data\":%u,\"high_version\":[%u,%u,%u]",
      root.format,root.serial,root.current.package,root.current.data,root.current.dataKind,
      root.current.dataSchema,root.flags,root.previous.package,root.previous.data,
      root.highVersion[0],root.highVersion[1],root.highVersion[2]);
    puts("}");return 0;
  }
  if(!strcmp(argv[1],"put-file")) {
    // Offline synthetic-fixture preparation only. Guest consumers still open
    // and process this file through authenticated public file services.
    assert(argc==6);load(flash,argv[2]);Volume v(flash.backend());assert(v.mount());
    PrimeG2::AppDocumentRoot::Root root;
    if(!v.documentRoot(argv[3],&root)) {
      // The minigzip workload starts with an installed 0.1.0/schema-0 package.
      // Read-only missing-file probes need not convert its legacy empty data.
      Entry entry;assert(v.entry(argv[3],&entry));
      assert(v.read(argv[3],package.data(),package.size(),data.data(),data.size()));
      const uint32_t version[3]={0,1,0};
      assert(v.beginCheckpoint(argv[3],data.data(),entry.dataBytes,version,0));finish(v);
    }
    std::ifstream input(argv[5],std::ios::binary|std::ios::ate);assert(input);
    auto length=input.tellg();assert(length>=0 && length<=64*1024*1024);input.seekg(0);
    assert(v.beginFile(argv[3],argv[4],static_cast<uint32_t>(length)));
    uint8_t buffer[2048];uint32_t offset=0;
    while(offset<static_cast<uint32_t>(length)) {
      for(unsigned i=0;i<200000 && !v.fileWritable() && v.state()!=State::Failed;i++) v.step();
      assert(v.fileWritable());uint32_t n=static_cast<uint32_t>(length)-offset;if(n>sizeof(buffer)) n=sizeof(buffer);
      input.seekg(offset);assert(input.read(reinterpret_cast<char *>(buffer),n));
      int used=v.writeFile(buffer,n);assert(used>0 && used<=static_cast<int>(n));offset+=used;
    }
    for(unsigned i=0;i<200000 && !v.fileWritable() && v.state()!=State::Failed;i++) v.step();
    assert(v.commitFile());finish(v);save(flash,argv[2]);
    printf("{\"bytes\":%u}\n",offset);return 0;
  }
  if(!strcmp(argv[1],"export-file")) {
    assert(argc==6);load(flash,argv[2]);Volume v(flash.backend());assert(v.mount());
    uint32_t token=v.openSnapshot(argv[3],argv[4]);assert(token);
    std::ofstream output(argv[5],std::ios::binary|std::ios::trunc);assert(output);
    uint8_t buffer[2048];uint32_t total=0,steps=0;
    for(;;) {
      int n=v.readSnapshot(argv[3],token,buffer,sizeof(buffer));
      if(n==PrimeG2::AppFileStore::Reader::Pending) { assert(++steps<1000000);assert(v.stepSnapshot(argv[3],token));continue; }
      assert(n>=0);if(!n) break;
      output.write(reinterpret_cast<const char *>(buffer),n);total+=n;
    }
    assert(v.closeSnapshot(argv[3],token));output.flush();assert(output.good());
    printf("{\"bytes\":%u,\"verification_steps\":%u}\n",total,steps);return 0;
  }
  if(!strcmp(argv[1],"seed") || !strcmp(argv[1],"seed-files") || !strcmp(argv[1],"seed-legacy")) {
    assert(argc==4);std::ifstream input(argv[2],std::ios::binary);assert(input);
    std::vector<uint8_t> app((std::istreambuf_iterator<char>(input)),std::istreambuf_iterator<char>());
    Volume v(flash.backend());assert(v.initialize(package.data(),package.size(),data.data(),data.size(),
      [](const uint8_t *,size_t,char id[49]) { strcpy(id,"document-arm");return true; }));
    uint32_t value=14,version[3]={1,0,0};
    assert(v.begin("document-arm",app.data(),app.size(),reinterpret_cast<uint8_t *>(&value),4));finish(v);
    if(!strcmp(argv[1],"seed-legacy")) {save(flash,argv[3]);puts("{\"synthetic_legacy\":true}");return 0;}
    assert(v.beginCheckpoint("document-arm",reinterpret_cast<uint8_t *>(&value),4,version,0));finish(v);
    if(!strcmp(argv[1],"seed-files")) {
      assert(v.changeFile("document-arm","assets",nullptr,true));finish(v);
      constexpr uint32_t bytes=PrimeG2::AppFileIndex::ChunkBytes+17;
      assert(v.beginFile("document-arm","assets/data.bin",bytes));uint8_t buffer[2048];uint32_t offset=0;
      while(offset<bytes) {
        for(unsigned i=0;i<200000 && !v.fileWritable() && v.state()!=State::Failed;i++) v.step();
        assert(v.fileWritable());uint32_t n=bytes-offset;if(n>sizeof(buffer)) n=sizeof(buffer);
        for(unsigned i=0;i<n;i++) buffer[i]=static_cast<uint8_t>((offset+i)*131u);
        int used=v.writeFile(buffer,n);assert(used>0);offset+=used;
      }
      for(unsigned i=0;i<200000 && !v.fileWritable() && v.state()!=State::Failed;i++) v.step();
      assert(v.commitFile());finish(v);
    }
    save(flash,argv[3]);
  } else {
    assert(!strcmp(argv[1],"inspect") && argc==3);load(flash,argv[2]);
  }
  Volume v(flash.backend());assert(v.mount());PrimeG2::AppDocumentRoot::Root root;
  assert(v.documentRoot("document-arm",&root));
  assert(v.read("document-arm",package.data(),package.size(),data.data(),data.size()));
  Entry entry;assert(v.entry("document-arm",&entry) && entry.dataBytes==4);
  char fileHash[65]={};
  if(root.current.dataKind==PrimeG2::AppDocumentRoot::FileIndex) {
    assert(v.openFile("document-arm","assets/data.bin"));uint8_t buffer[2048];uint32_t total=0;
    PrimeG2::NativeAppHash::SHA256 hash;PrimeG2::NativeAppHash::shaInit(&hash);
    for(;;) {int n=v.readFile(buffer,sizeof(buffer));assert(n>=0);if(!n) break;PrimeG2::NativeAppHash::shaUpdate(&hash,buffer,n);total+=n;}
    assert(total==PrimeG2::AppFileIndex::ChunkBytes+17 && v.closeReader());uint8_t digest[32];PrimeG2::NativeAppHash::shaFinal(&hash,digest);
    for(unsigned i=0;i<32;i++) snprintf(fileHash+2*i,3,"%02x",digest[i]);
  }
  char hash[65];for(unsigned i=0;i<32;i++) snprintf(hash+i*2,3,"%02x",root.current.packageHash[i]);
  printf("{\"format\":%u,\"serial\":%u,\"package_generation\":%u,\"data_generation\":%u,\"schema\":%u,\"pending_upgrade\":%u,\"previous_package\":%u,\"high_version\":[%u,%u,%u],\"value\":%u,\"package_sha256\":\"%s\",\"file_sha256\":\"%s\"}\n",
    root.format,root.serial,root.current.package,root.current.data,root.current.dataSchema,root.flags,root.previous.package,
    root.highVersion[0],root.highVersion[1],root.highVersion[2],word(data.data()),hash,fileHash);
}
