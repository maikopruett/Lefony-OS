// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#define _POSIX_C_SOURCE 200809L
#include <lefony/https.h>
#include <lefony/foreground.h>
#include <lefony/ui_system.h>
#include <lefony/file_writer.h>
#include <unistd.h>
#include "cache.h"
namespace {
using namespace Lefony;using namespace Lefony::UI;
constexpr Box Download{12,196,144,28},Secondary{164,196,144,28},Picture{16,48,288,128};
class Gallery {
  enum Phase {Idle,Pairing,Begin,URL,Preparing,Receiving,Cancelling,Saving} phase=Idle;
  Palette palette;Focus<> focus;char endpoint[129]={},message[80]="Offline: no saved image";
  uint32_t session=0,id=0,offset=0,received=0,headers=0,headerReceived=0,lastDraw=0,transferAt=0;
  uint16_t *pixels=nullptr;FileWriter part;GalleryCache::Candidate candidate;
  bool dirty=true,requestSent=false,cancelSent=false,response=false;
  bool busy() const {return phase!=Idle;}
  bool cancellable() const {return phase==Pairing || phase==Begin || phase==URL || phase==Receiving;}
  bool secondaryEnabled() const {return cancellable() || (phase==Idle && session);}
  void notify(const char *text) {if(text!=message) snprintf(message,sizeof(message),"%s",text);dirty=true;}
  void layout() {
    unsigned selected=focus.focused();focus.clear();focus.add(1,Download,!busy() && endpoint[0]);focus.add(2,Secondary,secondaryEnabled());
    if(selected) focus.select(selected);
    navigationDepth(busy()?1:0);dirty=true;
  }
  void discard() {part.cancel();candidate.reset();}
  void ended(const char *text) {discard();phase=Idle;notify(text);layout();}
  void disconnected(const char *text) {session=0;id=0;ended(text);}
  void cancel(const char *reason="Cancelling; saved image kept") {
    if(phase==Cancelling) return;
    notify(reason);
    if(!requestSent) {if(session) lefony_channel_close(session);session=0;id=0;phase=Idle;layout();return;}
    phase=Cancelling;cancelSent=false;discard();layout();
  }
  void download() {
    discard();received=headers=headerReceived=offset=0;response=requestSent=cancelSent=false;transferAt=lefony_millis();
    if(!session) {
      int status=lefony_channel_open(&session);
      if(status<0) {notify("Connection unavailable; restart the app");return;}
      phase=Pairing;notify("Open the companion on your computer");
    } else {phase=Begin;notify("Requesting image...");}
    layout();
  }
  void complete() {
    if(phase==Cancelling) {ended(!strcmp(message,"Cancelling; saved image kept")?"Cancelled; saved image kept":message);return;}
    if(!part.active() || received!=GalleryCache::Bytes || !candidate.complete()) {ended("Invalid image or no memory; cache kept");return;}
    phase=Saving;notify("Saving verified image...");layout();draw();
    if(!part.commit()) {ended("Save unconfirmed; reopen to inspect cache");return;}
    free(pixels);pixels=candidate.take();phase=Idle;notify("Saved for offline viewing");layout();
  }
  void packet(uint32_t kind,uint32_t *data,unsigned size) {
    if(kind==LEFONY_HTTPS_RESPONSE) {
      if(size!=32 || response || data[0]!=1 || data[1]!=id || data[3]>8192 || data[6] || data[7]) {cancel("Invalid server response; cache kept");return;}
      response=true;headers=data[3];headerReceived=0;
      if(phase==Cancelling) return;
      if(data[2]!=200) {char text[64];snprintf(text,sizeof(text),"Server returned HTTP %u; cache kept",static_cast<unsigned>(data[2]));cancel(text);return;}
      if(data[5]!=LEFONY_HTTPS_UNKNOWN && data[5]!=GalleryCache::Bytes) {cancel("Unexpected image size; cache kept");return;}
      phase=Preparing;notify("Preparing image storage...");layout();draw();
      if(!part.begin("image.cache")) {cancel("Cannot create cache; free some space");return;}
      phase=Receiving;layout();notify("Downloading image...");return;
    }
    if(size<4 || data[0]!=id) {cancel("Unexpected response identity; cache kept");return;}
    if(kind==LEFONY_HTTPS_HEADER) {
      if(size<=8 || !response || data[1]!=headerReceived || headerReceived+size-8>headers) {cancel("Invalid response headers; cache kept");return;}
      headerReceived+=size-8;
    } else if(kind==LEFONY_HTTPS_DATA) {
      if(phase==Cancelling) return;
      if(!response || !part.active() || size<=8 || data[1]!=received || headerReceived!=headers || received+size-8>GalleryCache::Bytes) {cancel("Invalid image stream; cache kept");return;}
      if(!candidate.append(data+2,size-8)) {cancel("Invalid image or no memory; cache kept");return;}
      if(!part.write(data+2,size-8)) {cancel("Storage full or write failed; cache kept");return;}
      received+=size-8;dirty=true;
    } else if(kind==LEFONY_HTTPS_DONE) {
      if(size!=16 || data[1] || data[3] || (phase!=Cancelling && data[2]!=received)) {cancel("Incomplete download; cache kept");return;}
      complete();
    } else if(kind==LEFONY_HTTPS_ERROR) {
      if(size!=24 || data[5]) {disconnected("Invalid companion error; reconnect");return;}
      static const char *errors[]={"Connection failed; cache kept","Host did not grant this URL","Protocol error; cache kept","TLS verification failed; cache kept",
        "Network unavailable; cache kept","Request timed out; cache kept","Cancelled; saved image kept"};
      ended(phase==Cancelling?(!strcmp(message,"Cancelling; saved image kept")?"Cancelled; saved image kept":message):errors[data[1]<=6?data[1]:0]);
    } else if(kind!=LEFONY_HTTPS_PROGRESS || size!=16) cancel("Unexpected companion message; cache kept");
  }
public:
  void start(int argc,char **argv) {
    LefonySystemInfo info;if(lefony_system_info(&info)==0) palette=systemPalette(info);
    if(argc==2 && strlen(argv[1])<sizeof(endpoint)) snprintf(endpoint,sizeof(endpoint),"%s",argv[1]);
    pixels=GalleryCache::read("image.cache");if(pixels) notify("Saved image available offline");
    if(!endpoint[0]) notify("Set the server URL in project.json");
    unlink("download.part");layout();draw();
  }
  void tick() {
    if(!session) {if(dirty) draw();return;}
    if(busy() && uint32_t(lefony_millis()-transferAt)>=125000) {
      lefony_channel_close(session);disconnected("Request timed out; saved image kept");return;
    }
    LefonyChannelInfo info;
    int status=lefony_channel_info(&info);
    if(status<0 || info.state==LEFONY_CHANNEL_ENDED || info.state==LEFONY_CHANNEL_CLOSED) {
      disconnected(status==0 && info.error==LEFONY_CHANNEL_DENIED?"Connection declined; saved image kept":"Disconnected; saved image kept");return;
    }
    if(phase==Pairing && info.state==LEFONY_CHANNEL_CONNECTED) {phase=Begin;notify("Requesting image...");}
    if(phase==Begin) {
      if(id==UINT32_MAX) {lefony_channel_close(session);disconnected("Start a new connection");return;}
      LefonyHTTPSBegin request{1,id+1,LEFONY_HTTPS_GET,0,GalleryCache::Bytes,120000,static_cast<uint32_t>(strlen(endpoint)),0};
      status=lefony_https_begin(session,&request);
      if(status==0) {id++;requestSent=true;phase=URL;offset=0;}
      else if(status!=-6) disconnected("Could not begin request; reconnect");
    } else if(phase==URL) {
      unsigned bytes=strlen(endpoint)-offset;if(bytes>440) bytes=440;
      status=lefony_https_metadata(session,LEFONY_HTTPS_URL,id,offset,endpoint+offset,bytes);
      if(status==0) {offset+=bytes;if(offset==strlen(endpoint)) phase=Receiving;}
      else if(status!=-6) disconnected("Could not send request; reconnect");
    } else if(phase==Cancelling && !cancelSent) {
      status=lefony_https_cancel(session,id);if(status==0) cancelSent=true;else if(status!=-6) disconnected("Disconnected; saved image kept");
    }
    if(phase==Receiving || phase==Cancelling) {
      uint32_t buffer[112];LefonyChannelRequest result{};status=lefony_channel_receive(session,buffer,sizeof(buffer),&result);
      if(status==0) packet(result.kind,buffer,result.length);
      else if(status!=-6) disconnected("Disconnected; saved image kept");
    }
    if(dirty && uint32_t(lefony_millis()-lastDraw)>=200) draw();
  }
  void draw() {
    lastDraw=lefony_millis();dirty=false;Widgets ui(palette);inspectionBegin();ui.canvas().fill({0,0,320,240},palette.paper);
    ui.label(10,{12,10,296,24},"Link Gallery",LEFONY_FONT_LARGE,LEFONY_UI_HERE);ui.canvas().fill({12,38,296,2},palette.accent);
    inspectNode(11,Custom,Picture,Picture,Enabled,"Saved image",LEFONY_UI_HERE);
    if(!pixels) {
      ui.canvas().fill(Picture,palette.surface);ui.canvas().outline(Picture,palette.disabled);
      ui.label(12,{40,93,240,18},"Your image will appear here",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      ui.label(13,{44,118,232,18},"Saved images work offline",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
    }
    ui.progress(14,{12,184,296,4},received,GalleryCache::Bytes,LEFONY_UI_HERE);
    auto state=[&](unsigned key,bool enabled=true) {return (enabled?Enabled:NoState)|(focus.focused()==key?Focused:NoState)|(focus.pressed()==key?Pressed:NoState);};
    ui.button(1,Download,pixels?"Refresh":"Download",state(1,!busy() && endpoint[0]),LEFONY_UI_HERE);
    const char *secondary=phase==Preparing?"Preparing":phase==Saving?"Saving":phase==Cancelling?"Cancelling":busy()?"Cancel":session?"Disconnect":"Offline";
    ui.button(2,Secondary,secondary,state(2,secondaryEnabled()),LEFONY_UI_HERE);
    ui.label(15,{12,226,296,14},message,LEFONY_FONT_SMALL,LEFONY_UI_HERE);inspectionEnd();
    if(pixels) lefony_present(pixels,16,48,GalleryCache::Width,GalleryCache::Height,GalleryCache::Width);
  }
  void input(const InputSnapshot &input) {
    unsigned action=0;
    if(input.event==1) {
      focus.cancel();
      if(input.key==InputKey::Back && cancellable()) cancel();
      else if(input.key==InputKey::Left || input.key==InputKey::Up) focus.move(-1);
      else if(input.key==InputKey::Right || input.key==InputKey::Down) focus.move(1);
      else if(input.key==InputKey::Confirm) action=focus.confirm();
    } else if(input.event==3) action=focus.touch(input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,input.flags&ContactsChanged);
    else return;
    if(action==1 && !busy() && endpoint[0]) download();
    else if(action==2) {
      if(busy()) cancel();
      else if(session) {lefony_channel_close(session);disconnected("Disconnected; saved image kept");}
    }
    draw();
  }
};
}
int main(int argc,char **argv) {
  Gallery app;app.start(argc,argv);uint32_t sequence=0;
  for(;;) {
    InputSnapshot input;if(readInput(input)==0 && input.sequence!=sequence) {sequence=input.sequence;app.input(input);}
    app.tick();lefony_program_sleep(5);
  }
}
