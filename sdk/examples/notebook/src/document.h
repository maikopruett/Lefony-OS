// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef NOTEBOOK_DOCUMENT_H
#define NOTEBOOK_DOCUMENT_H
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <lefony/file_writer.h>
struct Document {
  static constexpr unsigned Capacity=12,ExpressionBytes=96,MaximumBytes=Capacity*ExpressionBytes+32;
  char expressions[Capacity][ExpressionBytes]{};
  unsigned count=0;bool dark=false,migrated=false;
  // Ordinals match system preferences: degrees/radians/gradians and auto/sci/eng.
  // Old files retain the original radians/auto/9-digit interpretation.
  unsigned angle=1,format=0,digits=9;
  // An older file is parsed into a separate value. Saving publishes format 3;
  // malformed/future files stay untouched and make the UI read-only.
  bool decode(const char *bytes,unsigned size) {
    if(!bytes || size<8 || size>MaximumBytes || (memcmp(bytes,"LFNOTE1\n",8) && memcmp(bytes,"LFNOTE2\n",8) && memcmp(bytes,"LFNOTE3\n",8))) return false;
    Document next;next.migrated=bytes[6]!='3';unsigned at=8;
    if(bytes[6]!='1') {
      if(size<10 || (bytes[8]!='L' && bytes[8]!='D') || bytes[9]!='\n') return false;
      next.dark=bytes[8]=='D';at=10;
    }
    if(bytes[6]=='3') {
      if(size<17 || bytes[10]<'0' || bytes[10]>'2' || bytes[11]!=' ' ||
         bytes[12]<'0' || bytes[12]>'2' || bytes[13]!=' ' || bytes[14]<'0' || bytes[14]>'1' ||
         bytes[15]<'0' || bytes[15]>'9' || bytes[16]!='\n') return false;
      next.angle=bytes[10]-'0';next.format=bytes[12]-'0';next.digits=(bytes[14]-'0')*10+bytes[15]-'0';
      if(!next.digits || next.digits>14) return false;
      at=17;
    }
    while(at<size) {
      if(next.count==Capacity) return false;
      unsigned start=at;
      while(at<size && bytes[at]!='\n') {
        if(bytes[at]<32 || bytes[at]>126 || at-start>=ExpressionBytes-1) return false;
        at++;
      }
      if(at==size || at==start) return false;
      memcpy(next.expressions[next.count++],bytes+start,at-start);at++;
    }
    *this=next;return true;
  }
  bool load() {
    FILE *file=fopen("notebook.txt","rb");if(!file) return errno==ENOENT;
    char bytes[MaximumBytes];unsigned length=fread(bytes,1,sizeof(bytes),file);
    bool valid=!ferror(file) && feof(file);if(fclose(file)) valid=false;
    return valid && decode(bytes,length);
  }
  unsigned encode(char *bytes,unsigned capacity=MaximumBytes) const {
    if(!bytes || count>Capacity || angle>2 || format>2 || !digits || digits>14) return 0;
    unsigned sizes[Capacity],required=17;
    for(unsigned i=0;i<count;i++) {
      unsigned size=0;while(size<ExpressionBytes && expressions[i][size]) {
        if(expressions[i][size]<32 || expressions[i][size]>126) return 0;
        size++;
      }
      if(!size || size==ExpressionBytes) return 0;
      sizes[i]=size;required+=size+1;
    }
    if(capacity<required) return 0;
    memcpy(bytes,dark?"LFNOTE3\nD\n":"LFNOTE3\nL\n",10);
    bytes[10]='0'+angle;bytes[11]=' ';bytes[12]='0'+format;bytes[13]=' ';
    bytes[14]='0'+digits/10;bytes[15]='0'+digits%10;bytes[16]='\n';unsigned length=17;
    for(unsigned i=0;i<count;i++) {
      unsigned size=sizes[i];memcpy(bytes+length,expressions[i],size);length+=size;bytes[length++]='\n';
    }
    return length;
  }
  static bool publish(const char *destination,const char *bytes,unsigned size) {
    Lefony::FileWriter file;
    return file.begin(destination) && file.write(bytes,size) && file.commit();
  }
  bool save() const {char bytes[MaximumBytes];unsigned size=encode(bytes);return size && publish("notebook.txt",bytes,size);}
};
#endif
