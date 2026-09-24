// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_NATIVE_APP_MANIFEST_H
#define LEFONY_NATIVE_APP_MANIFEST_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
namespace PrimeG2 { namespace NativeAppManifest {
constexpr uint32_t APIRevision=12,Features=16383,PackageSchemas=3;
struct Manifest {
  uint32_t abi=0,schema=0,required=0,optional=0,minimumAPI=0,dataSchema=0;
  char id[49]={},name[81]={},version[24]={};
};
namespace Detail {
inline bool match(const uint8_t *&p,const uint8_t *end,const char *text) {
  size_t n=strlen(text);if(size_t(end-p)<n || memcmp(p,text,n)) return false;p+=n;return true;
}
inline bool number(const uint8_t *&p,const uint8_t *end,uint32_t &out) {
  if(p==end || *p<'0' || *p>'9') return false;
  uint32_t value=0;bool zero=*p=='0';
  do { uint32_t digit=*p++-'0';if(value>(0xffffffffu-digit)/10) return false;value=value*10+digit;
    if(zero) break;
  } while(p<end && *p>='0' && *p<='9');
  out=value;return true;
}
inline bool string(const uint8_t *&p,const uint8_t *end,char *out,size_t capacity) {
  if(p==end || *p++!='"') return false;
  size_t count=0;bool nonspace=false;
  while(p<end && *p!='"') {
    uint8_t c=*p++;
    if(c=='\\') { if(p==end || (*p!='"' && *p!='\\')) return false;c=*p++; }
    if(c<32 || c>126 || count+1>=capacity) return false;
    out[count++]=c;nonspace|=c!=' ';
  }
  if(p==end || !count || !nonspace) return false;
  p++;out[count]=0;return true;
}
}
// Exact canonical JSON grammar. Bounded stack; no allocator or permissive JSON
// recovery. Callers authenticate the package before accepting this metadata.
inline bool parse(const uint8_t *bytes,size_t length,uint32_t schema,uint32_t abi,Manifest *out) {
  if(!bytes || !out || !length || length>4096 || schema>1 || abi>1 || (schema==1 && abi!=1)) return false;
  using namespace Detail;
  const uint8_t *p=bytes,*end=p+length;Manifest m;char license[81];m.schema=schema;
  if(!match(p,end,"{\"abi\":") || !number(p,end,m.abi) || m.abi!=abi) return false;
  if(schema && (!match(p,end,",\"data_schema\":") || !number(p,end,m.dataSchema))) return false;
  if(!match(p,end,",\"id\":") || !string(p,end,m.id,sizeof(m.id)) ||
     !match(p,end,",\"license\":") || !string(p,end,license,sizeof(license))) return false;
  if(schema && (!match(p,end,",\"minimum_api\":") || !number(p,end,m.minimumAPI) || !m.minimumAPI)) return false;
  if(!match(p,end,",\"name\":") || !string(p,end,m.name,sizeof(m.name))) return false;
  if(schema && (!match(p,end,",\"optional_capabilities\":") || !number(p,end,m.optional) ||
     !match(p,end,",\"required_capabilities\":") || !number(p,end,m.required) ||
     !match(p,end,",\"schema\":1") || (m.required&m.optional))) return false;
  if(!match(p,end,",\"version\":") || !string(p,end,m.version,sizeof(m.version)) || !match(p,end,"}") || p!=end) return false;
  for(unsigned i=0;m.id[i];i++) if(!((m.id[i]>='a' && m.id[i]<='z') ||
      (i && ((m.id[i]>='0' && m.id[i]<='9') || m.id[i]=='-')))) return false;
  unsigned groups=0,digits=0;
  for(unsigned i=0;;i++) { char c=m.version[i];
    if(c=='.' || !c) { if(!digits || digits>6) return false;groups++;digits=0;if(!c) break; }
    else if(c>='0' && c<='9') digits++;else return false;
  }
  if(groups!=3) return false;
  *out=m;return true;
}
inline bool supported(const Manifest &m,uint32_t api=APIRevision,uint32_t features=Features) {
  return m.minimumAPI<=api && !(m.required&~features);
}
}}
#endif
