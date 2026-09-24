// SPDX-License-Identifier: GPL-3.0-or-later
#include <lefony/system.h>
#include <lefony/foreground.h>
#include <lefony/input.h>
#include <string.h>
#define check(good) do {if(!(good)) lefony_program_exit(__LINE__);} while(0)
static LefonySystemInfo snapshot() {
  LefonySystemInfo value;memset(&value,0xa5,sizeof(value));check(lefony_system_info(&value)==0);
  check(value.size==160 && value.schema==1 && !value.reserved[0] && !value.reserved[1]);
  return value;
}
static void rejected(LefonySystemRequest &r,int expected) {
  static unsigned probe=0;probe++;
  auto before=r;int result=lefony_system(&r);
  if(result!=expected) lefony_program_exit(10000+probe*100-result);
  check(!memcmp(&r,&before,sizeof(r)));
}
static void mark(unsigned stage) {
  check(lefony_fill((lefony_rect_t){static_cast<int32_t>(stage*24),0,20,20,0x2508})==0);
}
int main(int argc,char **argv) {
  check(argc==2);const char *mode=argv[1];
  LefonySystemInfo info;memset(&info,0xa5,sizeof(info));auto unchanged=info;
  if(!strcmp(mode,"denied") || !strcmp(mode,"unsupported")) {
    int expected=!strcmp(mode,"denied")?-LEFONY_SYSTEM_DENIED:-LEFONY_SYSTEM_UNSUPPORTED;
    check(lefony_system_info(&info)==expected && !memcmp(&info,&unchanged,sizeof(info)));return 0;
  }
  info=snapshot();check(info.utcOffsetMinutes==LEFONY_UTC_OFFSET_UNKNOWN);
  check(info.clockFlags==LEFONY_CLOCK_READABLE && info.year>=1970 && info.month>=1 && info.month<=12);
  check(info.maximumBrightness==240 && info.brightness<=240 && info.actualBrightness<=255);
  check(info.clipboardMaximum==219 && !info.clipboardSequence && !info.clipboardAction);
  check(info.angleUnit<=2 && info.displayMode<=2 && info.complexFormat<=2 && info.editionMode<=1 && info.unitFormat<=1);
  check(info.significantDigits>=1 && info.significantDigits<=14 && info.language[0] && info.language[1] && !info.language[2]);
  for(auto color:info.colors) check(color<=65535);
  if(!(info.batteryFlags&LEFONY_BATTERY_ESTIMATE_FRESH)) check(info.batteryPercent==UINT32_MAX && info.batteryMillivolts==UINT32_MAX);
  char output[220];memset(output,'X',sizeof(output));
  check(lefony_clipboard_read(1,output,sizeof(output))==-LEFONY_SYSTEM_DENIED && output[0]=='X');
  check(lefony_clipboard_write(1,"private",7)==-LEFONY_SYSTEM_DENIED);
  auto request=lefony_system_request(LEFONY_SYSTEM_INFO);request.buffer=(uint32_t)(uintptr_t)&info;request.capacity=160;
  for(unsigned i=0;i<12;i++) {
    auto bad=request;reinterpret_cast<uint32_t *>(&bad)[i]=UINT32_MAX;
    rejected(bad,-LEFONY_SYSTEM_INVALID);
  }
  request.buffer=(uint32_t)(uintptr_t)&request;rejected(request,-LEFONY_SYSTEM_INVALID);
  request.buffer=0x82000000;rejected(request,-LEFONY_SYSTEM_INVALID);
  request.buffer=0x10000000;rejected(request,-LEFONY_SYSTEM_INVALID);
  check(lefony_system(nullptr)==-LEFONY_SYSTEM_INVALID);
  check(lefony_service(LEFONY_SYSTEM_SERVICE,(void *)0x82000000)==-LEFONY_SYSTEM_INVALID);
  check(lefony_brightness(241)==-LEFONY_SYSTEM_INVALID);
  if(!strcmp(mode,"basic")) return 0;
  check(lefony_fill((lefony_rect_t){0,0,320,240,0xffff})==0);mark(0);
  const bool maximum=!strcmp(mode,"maximum");
  const bool clipboard=!strcmp(mode,"clipboard") || !strcmp(mode,"expired") || maximum;
  const bool telemetry=!strcmp(mode,"telemetry");
  if(!clipboard && !telemetry) {check(lefony_brightness(112)==0);check(snapshot().brightness==112);}
  unsigned last=0,stage=0;uint64_t before=lefony_system_millis(&info);
  for(;;) {
    Lefony::InputSnapshot input;check(Lefony::readInput(input)==0);
    if(input.sequence!=last && input.event==1) {
      last=input.sequence;
      if(clipboard) {
        if(input.key==Lefony::InputKey::Copy || input.key==Lefony::InputKey::Cut) {
          check(input.physicalKey==(input.key==Lefony::InputKey::Copy?43u:56u));
          auto current=snapshot();check(current.clipboardSequence==input.sequence);
          check(current.clipboardAction==(input.key==Lefony::InputKey::Copy?LEFONY_CLIPBOARD_COPY:LEFONY_CLIPBOARD_CUT));
          if(!strcmp(mode,"expired")) {
            lefony_program_sleep(2100);
            check(!snapshot().clipboardSequence);
            check(lefony_clipboard_write(input.sequence,"late",4)==-LEFONY_SYSTEM_DENIED);return 0;
          }
          check(lefony_clipboard_read(input.sequence,output,sizeof(output))==-LEFONY_SYSTEM_DENIED);
          check(lefony_clipboard_write(input.sequence,"a\0b",3)==-LEFONY_SYSTEM_TEXT);
          check(lefony_clipboard_write(input.sequence,"\xc0\x80",2)==-LEFONY_SYSTEM_TEXT);
          char longest[219];memset(longest,'L',sizeof(longest));longest[217]=char(0xcf);longest[218]=char(0x80);
          const char *text=input.key==Lefony::InputKey::Copy?"2+3":"6*7";
          check(lefony_clipboard_write(input.sequence,maximum?longest:text,maximum?(input.key==Lefony::InputKey::Copy?219:0):3)==0);
          check(lefony_clipboard_write(input.sequence,"replay",6)==-LEFONY_SYSTEM_DENIED);
          check(!snapshot().clipboardSequence);stage++;mark(stage);
        } else if(input.key==Lefony::InputKey::Paste) {
          check(input.physicalKey==42);
          check(snapshot().clipboardAction==LEFONY_CLIPBOARD_PASTE);
          auto r=lefony_system_request(LEFONY_SYSTEM_CLIPBOARD_READ);
          r.sequence=input.sequence;r.buffer=(uint32_t)(uintptr_t)output;r.capacity=maximum?219:2;
          if(!maximum || stage==1) {rejected(r,-LEFONY_SYSTEM_TOO_SMALL);check(output[0]=='X');}
          check(lefony_clipboard_read(input.sequence,output,sizeof(output))==(maximum?(stage==1?219:0):3));
          if(maximum) {
            if(stage==1) {for(unsigned i=0;i<217;i++) check(output[i]=='L');check((uint8_t)output[217]==0xcf && (uint8_t)output[218]==0x80 && !output[219]);}
            else check(!output[0]);
          } else check(!strcmp(output,stage?"2+3":"6*7"));
          check(lefony_clipboard_read(input.sequence,output,sizeof(output))==-LEFONY_SYSTEM_DENIED);
          memset(output,'X',sizeof(output));stage++;mark(stage);
        } else if(input.key==Lefony::InputKey::Confirm) {check(maximum?stage==4:(stage==3 || stage==1));return 0;}
      } else if(telemetry) {
        if(input.key==static_cast<Lefony::InputKey>(17)) {
          auto current=snapshot();check(lefony_system_millis(&current)>=before);before=lefony_system_millis(&current);
          check(current.clockFlags==(LEFONY_CLOCK_READABLE|LEFONY_CLOCK_SET_THIS_BOOT));
          check(current.year==2030 && current.month==2 && current.day==3 && current.hour==4 && current.minute==5);
          check((current.batteryFlags&(LEFONY_BATTERY_STATE_FRESH|LEFONY_BATTERY_PRESENT|LEFONY_BATTERY_ESTIMATE_FRESH))==67);
          check(current.batteryPercent==100 && current.batteryMillivolts>=3900 && current.batteryMillivolts<=4100);stage++;mark(stage);
        } else if(input.key==static_cast<Lefony::InputKey>(18)) {
          auto current=snapshot();check(lefony_system_millis(&current)>=before);
          check(current.year==2020 && current.clockFlags==3);
          check((current.batteryFlags&LEFONY_BATTERY_STATE_FRESH) && !(current.batteryFlags&LEFONY_BATTERY_PRESENT));
          check(!(current.batteryFlags&LEFONY_BATTERY_ESTIMATE_FRESH) && current.batteryPercent==UINT32_MAX);stage++;mark(stage);
        } else if(input.key==Lefony::InputKey::Confirm) {check(stage==2);return 0;}
      } else {
        check(snapshot().brightness==112);
        if(input.key==static_cast<Lefony::InputKey>(17)) mark(1);
        if(input.key==Lefony::InputKey::Confirm) {
          if(!strcmp(mode,"fault")) asm volatile("udf #0");
          if(!strcmp(mode,"restore")) {check(lefony_restore_brightness()==0);check(snapshot().brightness==info.brightness);}
          return 0;
        }
      }
    }
    lefony_program_yield();
  }
}
