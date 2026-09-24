// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui_controls.h>
#include <lefony/expression.h>
#include <lefony/expression_input.h>
namespace {
using namespace Lefony;
using namespace Lefony::UI;
struct Row { char expression[64];int32_t milli; };
struct Record { uint32_t magic,schema,count;Row rows[6]; };
Record record{0x54464c46,1,0,{}};
Focus<> focus;
Navigation<> navigation;
TextBuffer<64> expression;
Expression::Context math;
bool keep=true,installed=false,writable=true,staged=false;
unsigned selectedRow=0;
char message[64]="Edit the expression, then press OK";
constexpr Box Field{12,59,296,32},Keep{12,102,296,30},Evaluate{12,144,142,32},Table{166,144,142,32};
constexpr Box Return{12,208,142,28},Clear{166,208,142,28},Remove{26,140,128,32},Cancel{166,140,128,32};
void copy(char *destination,const char *source,unsigned capacity) {
  unsigned i=0;for(;i+1<capacity && source[i];i++) destination[i]=source[i];destination[i]=0;
}
void notify(const char *text) { copy(message,text,sizeof(message)); }
void fixed(char out[24],int32_t milli) {
  unsigned cursor=0;uint32_t positive=milli<0?static_cast<uint32_t>(-int64_t(milli)):static_cast<uint32_t>(milli);
  if(milli<0) out[cursor++]='-';
  char whole[11];Lefony::number(whole,positive/1000);
  for(unsigned i=0;whole[i];i++) out[cursor++]=whole[i];
  out[cursor++]='.';out[cursor++]=static_cast<char>('0'+positive/100%10);
  out[cursor++]=static_cast<char>('0'+positive/10%10);out[cursor++]=static_cast<char>('0'+positive%10);out[cursor]=0;
}
void rebuild(uint32_t restore=0) {
  focus.clear();
  if(navigation.screen()==1) {
    focus.add(1,Field);focus.add(2,Keep);focus.add(3,Evaluate,!keep || (writable && record.count<6));focus.add(4,Table);
  } else if(navigation.screen()==2) {
    for(unsigned i=0;i<record.count;i++) focus.add(100+i,{12,60+static_cast<int>(i)*24,296,22});
    focus.add(10,Return);focus.add(11,Clear,writable && record.count>0);
  } else if(navigation.screen()==3) {
    focus.add(20,Remove,writable);focus.add(21,Cancel);
  } else {
    focus.add(30,Remove,writable);focus.add(31,Cancel);
  }
  if(restore) focus.select(restore);
}
void text(Canvas &canvas,int x,int y,const char *value,uint16_t color=Theme::Ink,uint16_t background=Theme::Paper,unsigned width=296) {
  canvas.text({x,y,static_cast<int>(width),14},value,Lefony::length(value),color,background);
}
void draw() {
  Canvas canvas;canvas.fill({0,0,320,240},Theme::Paper);canvas.fill({0,0,320,34},Theme::Accent);
  text(canvas,12,10,navigation.screen()==1?"FORMS + TABLES":navigation.screen()==2?"RESULTS":"CONFIRM",White,Theme::Accent);
  if(navigation.screen()==1) {
    text(canvas,12,41,"Expression");field(canvas,Field,expression,focus.focused()==1);
    toggle(canvas,Keep,"Keep result in table",keep,focus.focused()==2);
    button(canvas,Evaluate,"Evaluate",focus.focused()==3,focus.pressed()==3,!keep || (writable && record.count<6));
    button(canvas,Table,"Table",focus.focused()==4,focus.pressed()==4);
    text(canvas,12,185,message);
    text(canvas,12,205,!writable?"Read-only: saved schema preserved":staged?"Staged changes save on app exit":installed?"Private storage available":"Preview: changes are temporary",Theme::Muted);
    text(canvas,12,225,"Up/Down: focus   OK: activate",Theme::Muted);
  } else if(navigation.screen()==2) {
    text(canvas,12,40,"Expression",Theme::Muted);text(canvas,210,40,"Result",Theme::Muted,Theme::Paper,92);
    if(!record.count) text(canvas,12,76,"No results yet. Evaluate an expression.");
    for(unsigned i=0;i<record.count;i++) {
      Box row{12,60+static_cast<int>(i)*24,296,22};bool chosen=focus.focused()==100+i;
      uint16_t background=chosen?Theme::Selected:White;canvas.fill(row,background);
      if(chosen) canvas.outline(row,Theme::Accent,2);
      char preview[26];copy(preview,record.rows[i].expression,sizeof(preview));
      if(Lefony::length(record.rows[i].expression,64)>25) copy(preview+22,"...",4);
      text(canvas,18,row.y+4,preview,Theme::Ink,background,180);
      char result[24];fixed(result,record.rows[i].milli);
      text(canvas,210,row.y+4,result,Theme::Ink,background,92);
    }
    button(canvas,Return,"Back",focus.focused()==10,focus.pressed()==10);
    button(canvas,Clear,"Clear table",focus.focused()==11,focus.pressed()==11,writable && record.count);
  } else {
    canvas.fill({12,50,296,142},White);canvas.outline({12,50,296,142},Theme::Accent,2);
    if(navigation.screen()==3 && selectedRow<record.count) {
      text(canvas,26,65,"Remove this result?",Theme::Ink,White,268);
      const char *source=record.rows[selectedRow].expression;
      text(canvas,26,86,source,Theme::Muted,White,268);
      if(Lefony::length(source,64)>38) text(canvas,26,103,source+38,Theme::Muted,White,268);
      char result[24];fixed(result,record.rows[selectedRow].milli);text(canvas,26,122,result,Theme::Ink,White,268);
    } else text(canvas,26,74,"Clear all saved results?",Theme::Ink,White,268);
    uint32_t yes=navigation.screen()==3?20:30,no=navigation.screen()==3?21:31;
    button(canvas,Remove,navigation.screen()==3?"Remove":"Clear",focus.focused()==yes,focus.pressed()==yes,writable);
    button(canvas,Cancel,"Cancel",focus.focused()==no,focus.pressed()==no);
    text(canvas,12,216,navigation.hardwareBack()?"Back cancels; focus will be restored":"Choose Cancel to return",Theme::Muted);
  }
  if(canvas.error()<0) notify("A drawing operation failed");
}
bool stage(const Record &next) {
  if(!writable) { notify("Saved schema is read-only");return false; }
  if(installed && Lefony::writeData(0,&next,sizeof(next))!=static_cast<int32_t>(sizeof(next))) {
    notify("Could not stage changes");return false;
  }
  record=next;staged=installed;return true;
}
void evaluate() {
  auto parsed=math.parse(expression.text(),expression.size());
  if(parsed.status!=Expression::Status::Ok) { notify("Check expression syntax and limits");return; }
  auto value=math.evaluate(parsed.expression);
  if(value.status!=Expression::Status::Ok) { notify("Undefined name, domain or operation");return; }
  if(value.value < -1000000 || value.value > 1000000) { notify("Result exceeds +/-1,000,000");return; }
  int32_t milli=static_cast<int32_t>(value.value*1000+(value.value<0?-.5:.5));
  if(keep) {
    if(record.count==6) { notify("Table full: remove a result first");return; }
    Record next=record;Row &row=next.rows[next.count++];copy(row.expression,expression.text(),sizeof(row.expression));row.milli=milli;
    if(!stage(next)) return;
  }
  char number[24];fixed(number,milli);copy(message,"Result: ",sizeof(message));copy(message+8,number,sizeof(message)-8);
  uint32_t old=focus.focused();rebuild(old);
}
void back() {
  auto restored=navigation.pop();if(restored.ok) rebuild(restored.focus);
}
void activate(uint32_t id) {
  if(navigation.screen()==1) {
    if(id==1 || id==3) evaluate();
    if(id==2) { keep=!keep;rebuild(2); }
    if(id==4 && navigation.push(2,focus.focused())) rebuild();
  } else if(navigation.screen()==2) {
    if(id>=100 && id<100+record.count) { selectedRow=id-100;if(navigation.push(3,id)) rebuild(); }
    if(id==10) back();
    if(id==11 && navigation.push(4,id)) rebuild();
  } else {
    if(id==21 || id==31) back();
    if(id==20 && selectedRow<record.count) {
      Record next=record;
      for(unsigned i=selectedRow+1;i<next.count;i++) next.rows[i-1]=next.rows[i];
      next.rows[--next.count]={};if(stage(next)) back();
    }
    if(id==30) { Record next=record;next.count=0;for(auto &row:next.rows) row={};if(stage(next)) back(); }
  }
}
void start() {
  expression.insert("2+3*4",5);
  Record saved{};installed=Lefony::readData(0,&saved,0)==0;
  uint8_t probe=0;bool existing=Lefony::readData(0,&probe,1)==1;
  bool valid=Lefony::readData(0,&saved,sizeof(saved))==static_cast<int32_t>(sizeof(saved)) &&
    saved.magic==record.magic && saved.schema==1 && saved.count<=6;
  if(valid) for(unsigned i=0;i<saved.count;i++) {
    unsigned length=Lefony::length(saved.rows[i].expression,64);
    valid=valid && length<64 && saved.rows[i].milli>=-1000000000 && saved.rows[i].milli<=1000000000;
    for(unsigned j=0;j<length;j++) valid=valid && saved.rows[i].expression[j]>=32 && saved.rows[i].expression[j]<=126;
  }
  if(valid) record=saved;
  else if(existing) { writable=false;notify("Saved data has an unsupported schema"); }
  rebuild();draw();
}
bool compose(const InputSnapshot &input) {
  return Expression::edit(expression,input);
}
}
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t second) {
  if(event==Lefony::Event::Start) { start();return; }
  if(event==Lefony::Event::Close) { focus.cancel();return; }
  if(event!=Lefony::Event::Key && event!=Lefony::Event::Touch) return;
  Lefony::InputSnapshot input;
  if(!Lefony::UI::read({event,first,second},input)) { notify("Could not read input");draw();return; }
  uint32_t action=0;
  if(event==Lefony::Event::Key) {
    focus.cancel();
    if(input.key==Lefony::InputKey::Back) { back();draw();return; }
    if(input.key==Lefony::InputKey::Up || input.key==Lefony::InputKey::Down) focus.move(input.key==Lefony::InputKey::Up?-1:1);
    else if(input.key==Lefony::InputKey::Confirm) action=focus.confirm();
    else if(navigation.screen()==1 && focus.focused()==1) {
      if(!compose(input) && input.textBytes) notify("Text is full or unsupported");
    } else if(input.key==Lefony::InputKey::Left || input.key==Lefony::InputKey::Right) focus.move(input.key==Lefony::InputKey::Left?-1:1);
  } else {
    action=focus.touch(input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,(input.flags&Lefony::ContactsChanged)!=0);
  }
  if(action) activate(action);
  draw();
}
