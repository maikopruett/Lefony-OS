// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui.h>
#include <lefony/runtime.h>
#include <lefony/extensions.h>
#include <lefony/numeric.h>
namespace {
constexpr uint32_t Ink=0x1947,Muted=0x6b6d,Paper=0xf7be;
struct Record { uint32_t magic,schema,count;uint32_t samples[24]; };
Record record{0x4c504c46,1,0,{}};
Lefony::Arena<512> arena;
Lefony::NumberField<4> field;
Lefony::Button add({16,183,140,36,Lefony::Green},"Add / OK");
Lefony::Button clear({164,183,140,36,Muted},"Clear / Del");
bool batched=false,installed=false,dirty=false,hadSavedData=false,dataWritable=true;
const char *message="Enter 0-999, then OK";
void draw() {
  Lefony::fill({0,0,320,240,Paper});
  Lefony::fill({0,0,320,39,Lefony::Green});
  Lefony::label(16,11,"POCKET LAB",Lefony::White,Lefony::Green);
  Lefony::label(16,48,"Sample",Ink,Paper);field.draw(95,43);
  Lefony::label(16,84,"Count",Muted,Paper);
  char count[11];Lefony::number(count,record.count);Lefony::label(65,84,count,Ink,Paper);
  Lefony::Numeric::Statistics stats;
  for(unsigned i=0;i<record.count;i++) stats.add(record.samples[i]);
  double mean=0;stats.mean(mean);
  Lefony::label(115,84,"Mean",Muted,Paper);
  char average[11];Lefony::number(average,static_cast<uint32_t>(mean));Lefony::label(158,84,average,Ink,Paper);
  Lefony::label(211,84,"rounded down",Muted,Paper);
  Lefony::fill({16,111,288,45,Lefony::White});
  arena.reset();
  auto *bars=static_cast<Lefony::Rect *>(arena.allocate(24*sizeof(Lefony::Rect),alignof(Lefony::Rect)));
  if(bars && record.count) {
    for(unsigned i=0;i<record.count;i++) {
      int height=1+record.samples[i]*43/999;
      bars[i]={18+static_cast<int>(i)*12,155-height,9,height,Lefony::Green};
    }
    if(!batched || Lefony::batch(bars,record.count)<0)
      for(unsigned i=0;i<record.count;i++) Lefony::fill(bars[i]);
  }
  Lefony::label(16,164,message,Ink,Paper);add.draw();clear.draw();
  const char *status=!installed?"Preview: use --workspace to save":
    !dataWritable?"Read-only: saved data preserved":dirty?"Staged: Back saves; power loss loses":
    hadSavedData?"Loaded saved samples":"Installed: no saved samples yet";
  Lefony::label(16,225,status,Muted,Paper);
}
bool stage() {
  dirty=true;
  if(installed && Lefony::writeData(0,&record,sizeof(record))!=static_cast<int>(sizeof(record)))
    { message="Could not stage changes";return false; }
  return true;
}
void append() {
  if(!dataWritable) { message="Saved data has unsupported schema";draw();return; }
  const char *text=field.value();
  if(!*text) { message="Enter a sample first";draw();return; }
  if(record.count==24) { message="24 samples full - clear to restart";draw();return; }
  unsigned value=0;for(unsigned i=0;text[i];i++) value=value*10+text[i]-'0';
  record.samples[record.count++]=value;
  if(stage()) message="Sample added";
  field=Lefony::NumberField<4>();draw();
}
}
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t second) {
  Lefony::Input input{event,first,second};
  if(event==Lefony::Event::Start) {
    Record saved{};
    installed=Lefony::readData(0,&saved,0)==0;
    uint8_t probe=0;
    hadSavedData=Lefony::readData(0,&probe,1)==1;
    bool valid=Lefony::readData(0,&saved,sizeof(saved))==static_cast<int>(sizeof(saved)) && saved.magic==record.magic && saved.schema==1 && saved.count<=24;
    if(valid) for(unsigned i=0;i<saved.count;i++) valid=valid && saved.samples[i]<=999;
    if(valid) record=saved;
    else if(hadSavedData) { dataWritable=false;message="Saved data has unsupported schema"; }
    Lefony::Capabilities features;
    batched=Lefony::discover(features)==0 && (features.features&Lefony::RectangleBatch);
    draw();return;
  }
  if(add.handle(input) || (event==Lefony::Event::Key && first==static_cast<unsigned>(Lefony::Key::Confirm))) append();
  if(clear.handle(input) || (event==Lefony::Event::Key && first==static_cast<unsigned>(Lefony::Key::Delete) && !*field.value())) {
    if(!dataWritable) { message="Saved data has unsupported schema";draw();return; }
    record.count=0;message="Samples cleared";stage();draw();return;
  }
  if(field.handle(input)) { message="Enter 0-999, then OK";draw(); }
}
