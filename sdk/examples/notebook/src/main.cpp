// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui_widgets.h>
#include <lefony/ui_system.h>
#include <lefony/number_format.h>
#include <lefony/foreground.h>
#include <lefony/expression_input.h>
#include <lefony/expression.h>
#include <lefony/graphics_screen.h>
#include "document.h"
#include "package_data.h"
namespace {
using namespace Lefony;
using namespace Lefony::UI;
constexpr Box FieldBox{12,65,296,32},PlotBox{12,132,296,46};
constexpr Box ListBox{12,60,296,116};
constexpr Box First{12,190,92,32},Second{114,190,92,32},Third{216,190,92,32};
constexpr Box Options{224,8,84,24},Digits{12,154,296,28};
class Notebook {
  Document document;
  unsigned optionAngle=1,optionFormat=0,osAngle=1,osFormat=0,osDigits=9;
  SliderModel optionDigits{1,14,9};
  Palette osPalette;
  TextBuffer<Document::ExpressionBytes> expression;
  TextFieldModel field;
  Focus<> focus;ListModel list;Navigation<> navigation;
  Expression::Context math;
  unsigned editing=0;bool writable=true,valid=false,resultError=false,dirty=false;
  char message[96]="Up/Down selects; OK opens",result[64]="";
  Palette palette() const {
    if(!document.dark) return osPalette;
    return {0x10c4,0x2126,0xef7d,0xadb6,0x4df2,0x10c4,0x328b,0x528a,0xfaaa};
  }
  uint32_t state(unsigned id,bool enabled=true) const {
    return (enabled?Enabled:NoState)|(focus.focused()==id?Focused:NoState)|(focus.pressed()==id?Pressed:NoState);
  }
  void notify(const char *text) {snprintf(message,sizeof(message),"%s",text);}
  void rebuild(unsigned restore=0) {
    field.cancel(expression);
    focus.clear();list.count(document.count);
    if(navigation.screen()==1) {
      for(unsigned row=0;row<list.visible();row++) {
        unsigned index=list.first()+row;focus.add(100+index,intersect(list.row(index),ListBox));
      }
      focus.add(1,First,writable && document.count<Document::Capacity);focus.add(2,Second);focus.add(3,Third,document.count>0);
      focus.add(4,Options,writable);
    } else if(navigation.screen()==2) {
      focus.add(10,FieldBox,writable);focus.add(11,First,writable);focus.add(12,Second,writable && editing<document.count);focus.add(13,Third);
      focus.add(14,Options,writable);
    } else if(navigation.screen()==5) {
      for(unsigned i=0;i<3;i++) focus.add(30+i,{12+static_cast<int>(i)*102,58,92,28});
      for(unsigned i=0;i<3;i++) focus.add(33+i,{12+static_cast<int>(i)*102,106,92,28});
      focus.add(36,Digits);focus.add(37,First);focus.add(38,Second);focus.add(39,Third);
    } else {DialogLayout{}.open(focus,20,21,writable);}
    if(restore) focus.select(restore);
  }
  void configureMath() {math.angle(document.angle==0?Math::Angle::Degrees:document.angle==2?Math::Angle::Gradians:Math::Angle::Radians);}
  const char *angleName() const {return document.angle==0?"DEG":document.angle==2?"GRAD":"RAD";}
  const char *formatName() const {return document.format==0?"AUTO":document.format==1?"SCI":"ENG";}
  static const char *errorName(Expression::Status status) {
    switch(status) {
      case Expression::Status::Invalid:return "Invalid expression";
      case Expression::Status::Limit:return "Expression limit reached";
      case Expression::Status::Unbound:return "Unknown variable";
      case Expression::Status::Domain:return "Undefined result";
      case Expression::Status::Unsupported:return "Unsupported function";
      case Expression::Status::Cancelled:return "Cancelled";
      default:return "Expression unavailable";
    }
  }
  bool answerText(const char *text,char *output,unsigned capacity) {
    math.set("x",1);auto parsed=math.parse(text,strlen(text));
    if(parsed.status!=Expression::Status::Ok) {snprintf(output,capacity,"%s at %u",errorName(parsed.status),parsed.position+1);return false;}
    auto answer=math.evaluate(parsed.expression);
    if(answer.status!=Expression::Status::Ok) {snprintf(output,capacity,"%s at %u",errorName(answer.status),answer.position+1);return false;}
    if(lefony_format_number(output,capacity,answer.value,document.digits,document.format)<0) {snprintf(output,capacity,"Number cannot be formatted");return false;}
    return true;
  }
  void evaluate() {
    math.set("x",1);auto parsed=math.parse(expression.text(),expression.size());
    valid=parsed.status==Expression::Status::Ok;
    char text[48];resultError=!answerText(expression.text(),text,sizeof(text));
    snprintf(result,sizeof(result),resultError?"%s":"x = 1: %s",text);
  }
  void plot(Widgets &ui) {
    auto &p=ui.palette();ui.canvas().fill(PlotBox,p.surface);
    inspectNode(40,Custom,PlotBox,PlotBox,Enabled,"Expression plot",LEFONY_UI_HERE);
    auto parsed=math.parse(expression.text(),expression.size());if(parsed.status!=Expression::Status::Ok) return;
    Graphics::Screen screen;auto sink=[&](int x,int y,int width,uint16_t color){return screen.span(x,y,width,color);};
    Graphics::line(PlotBox,{12,155},{307,155},p.disabled,sink);
    Graphics::line(PlotBox,{160,132},{160,177},p.disabled,sink);
    bool previous=false;Graphics::Point last{};
    for(unsigned i=0;i<75;i++) {
      math.set("x",-5.0+i*10.0/74);auto answer=math.evaluate(parsed.expression);
      bool usable=answer.status==Expression::Status::Ok && answer.value>=-10 && answer.value<=10;
      Graphics::Point point{12+i*295.0/74,155-answer.value*2.2};
      if(usable && previous && Numeric::abs(point.y-last.y)<23) Graphics::line(PlotBox,last,point,p.accent,sink);
      previous=usable;last=point;
    }
    screen.flush();
  }
  void open(unsigned row) {
    list.cancel();
    if(!navigation.push(2,focus.focused())) return;
    editing=row;expression.set(row<document.count?document.expressions[row]:"2+3*4",row<document.count?strlen(document.expressions[row]):5);
    dirty=false;evaluate();rebuild(10);notify("Edit with keypad; x ranges -5 to 5");
  }
  void back() {list.cancel();optionDigits.cancel();auto previous=navigation.pop();if(previous.ok) {rebuild(previous.focus);notify(writable?"Up/Down selects; OK opens":"Cannot read file; export it for recovery");}}
  bool save(Document next) {
    if(!writable) return false;
    status("Saving document...");
    if(!next.save()) {notify("Save unconfirmed; draft kept. Reopen.");return false;}
    next.migrated=false;document=next;configureMath();notify("Saved to notebook.txt");return true;
  }
  void exportText() {
    char bytes[2048];unsigned used=snprintf(bytes,sizeof(bytes),"# Notebook %s %s %u / x=1\n",angleName(),formatName(),document.digits);
    for(unsigned i=0;i<document.count;i++) {
      char result[64];answerText(document.expressions[i],result,sizeof(result));
      int count=snprintf(bytes+used,sizeof(bytes)-used,"%s = %s\n",document.expressions[i],result);
      if(count<0 || static_cast<unsigned>(count)>=sizeof(bytes)-used) {notify("Export exceeds size limit");return;}used+=count;
    }
    status("Exporting text...");
    notify(Document::publish("export.txt",bytes,used)?"Export ready: use SDK files export":"Export unconfirmed; inspect with SDK");
  }
  void activate(unsigned id) {
    list.cancel();
    if(navigation.screen()==1) {
      if(id>=100) {list.select(id-100);open(id-100);}
      else if(id==1) open(document.count);
      else if(id==2) {Document next=document;next.dark=!next.dark;if(writable) save(next);else document.dark=next.dark;rebuild(2);}
      else if(id==3) exportText();
      else if(id==4 && navigation.push(5,focus.focused())) {
        optionAngle=document.angle;optionFormat=document.format;optionDigits.set(document.digits);rebuild(30+optionAngle);
        notify("Applies to all document expressions");
      }
    } else if(navigation.screen()==2) {
      if(id==10 || id==11) {
        evaluate();if(!valid) {notify("Fix the expression before saving");return;}
        Document next=document;if(editing==next.count) next.count++;
        snprintf(next.expressions[editing],sizeof(next.expressions[editing]),"%s",expression.text());
        if(save(next)) {dirty=false;back();notify("Saved to notebook.txt");}
      } else if(id==12) {if(navigation.push(4,focus.focused())) rebuild(21);}
      else if(id==13) leave();
      else if(id==14) {expression.selectAll();focus.select(10);notify("Selection ready to copy, cut or replace");}
    } else if(navigation.screen()==5) {
      if(id>=30 && id<=32) optionAngle=id-30;
      else if(id>=33 && id<=35) optionFormat=id-33;
      else if(id==37) {
        Document next=document;next.angle=optionAngle;next.format=optionFormat;next.digits=optionDigits.value();
        if(save(next)) {back();notify("Document settings saved");}
      } else if(id==38) {optionAngle=osAngle;optionFormat=osFormat;optionDigits.set(osDigits);notify("OS defaults selected; Apply to save");}
      else if(id==39) back();
    } else if(id==21) back();
    else if(id==20) {
      if(navigation.screen()==4) {
        Document next=document;for(unsigned i=editing+1;i<next.count;i++) memcpy(next.expressions[i-1],next.expressions[i],Document::ExpressionBytes);
        memset(next.expressions[--next.count],0,Document::ExpressionBytes);
        if(!save(next)) return;
      }
      dirty=false;back();back();
    }
  }
  void leave() {if(dirty) {if(navigation.push(3,focus.focused())) rebuild(21);}else back();}
  void clipboard(const InputSnapshot &input) {
    if(input.key==InputKey::Paste) {
      char bytes[LEFONY_CLIPBOARD_MAXIMUM+1];int size=lefony_clipboard_read(input.sequence,bytes,sizeof(bytes));
      if(size<0) {notify("Clipboard unavailable or unsupported");return;}
      if(!size) {notify("Clipboard is empty");return;}
      auto status=Expression::insertText(expression,bytes,static_cast<unsigned>(size));
      if(status!=Expression::TextStatus::Ok) {notify(status==Expression::TextStatus::Full?"Paste exceeds the 95-byte field":"Paste one supported expression");return;}
      dirty=true;evaluate();notify("Pasted expression");return;
    }
    unsigned first=expression.selectionStart(),last=expression.selectionEnd();bool selection=last>first;
    if(!selection) {first=0;last=expression.size();}
    if(lefony_clipboard_write(input.sequence,expression.text()+first,last-first)<0) {notify("Clipboard unavailable; text unchanged");return;}
    if(input.key==InputKey::Cut) {
      if(!selection) expression.selectAll();
      expression.insert(nullptr,0);dirty=true;evaluate();notify("Cut to clipboard");
    } else notify(selection?"Copied selection":"Copied expression");
  }
public:
  void status(const char *text) {
    Widgets ui(palette());inspectionBegin();ui.canvas().fill({0,0,320,240},ui.palette().paper);
    ui.label(90,{12,86,296,20},"Notebook",LEFONY_FONT_LARGE,LEFONY_UI_HERE);
    ui.label(91,{12,118,296,20},text,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
    ui.progress(92,{12,150,296,4},1,3,LEFONY_UI_HERE);inspectionEnd(false);lefony_program_yield();
  }
  void start() {
    LefonySystemInfo system;
    if(lefony_system_info(&system)==0) {
      osPalette=systemPalette(system);osAngle=system.angleUnit;osFormat=system.displayMode;osDigits=system.significantDigits;
      document.angle=osAngle;document.format=osFormat;document.digits=osDigits;
    }
    status("Opening document...");
    LefonyDataRequest package;
    bool supported=NotebookPackage::inspect(&package);
    writable=supported && document.load();
    // Claim package/data compatibility only after the complete document has
    // been read and parsed. Unknown schemas and malformed files retain the
    // previous pair for the explicit host rollback/recovery commands.
    if(writable && !NotebookPackage::accept(package)) {writable=false;notify("Upgrade unconfirmed; reopen to inspect");}
    else if(!supported) notify("Unsupported app data; restore a compatible backup");
    else if(!writable) notify("Cannot read file; export it for recovery");
    else if(document.migrated) notify("Older document; next save upgrades it");
    // Remove the older app's disposable staging file only after the document
    // and package/data pair are accepted. Read-only recovery never changes it.
    if(writable) unlink("notebook.tmp");
    configureMath();list.layout(ListBox,40,4);list.count(document.count);rebuild();
    draw();
  }
  void draw() {
    Widgets ui(palette());auto &p=ui.palette();inspectionBegin();ui.canvas().fill({0,0,320,240},p.paper);
    ui.label(50,{12,10,202,22},navigation.screen()==1?"Notebook":navigation.screen()==2?"Edit expression":navigation.screen()==5?"Document options":"Confirm",LEFONY_FONT_LARGE,LEFONY_UI_HERE);
    ui.canvas().fill({12,36,296,2},p.accent);
    if(navigation.screen()==1) {
      ui.button(4,Options,"Options",state(4,writable),LEFONY_UI_HERE);
      char count[48];snprintf(count,sizeof(count),"%u / %u expressions / %s",document.count,Document::Capacity,angleName());
      ui.label(51,{12,42,296,14},count,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      if(!document.count) {
        ui.label(52,{24,85,272,18},writable?"A place for your calculations":"Document unavailable",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
        ui.paragraph(53,{24,112,272,60},writable?
          "Choose New to add an expression. Your calculations are saved in notebook.txt.":
          "The original file is unchanged. Export notebook.txt with the SDK before restoring a compatible backup.",
          LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      }
      Widgets rows(p,ListBox);
      for(unsigned row=0;row<list.visible();row++) {
        unsigned index=list.first()+row;char detail[48];answerText(document.expressions[index],detail,sizeof(detail));
        rows.row(100+index,list.row(index),document.expressions[index],detail,
          state(100+index)|(list.selected()==index?Selected:NoState)|(list.pressed()==index+1?Pressed:NoState),LEFONY_UI_HERE);
      }
      ui.scrollbar(63,{312,60,4,116},list,LEFONY_UI_HERE);
      ui.button(1,First,"New",state(1,writable && document.count<Document::Capacity),LEFONY_UI_HERE);
      ui.button(2,Second,document.dark?"Light":"Dark",state(2),LEFONY_UI_HERE);
      ui.button(3,Third,"Export",state(3,document.count>0),LEFONY_UI_HERE);
    } else if(navigation.screen()==2) {
      ui.button(14,Options,"Select all",state(14,writable),LEFONY_UI_HERE);
      char label[40];snprintf(label,sizeof(label),"Expression / %s / %s",angleName(),formatName());
      ui.label(54,{12,45,296,14},label,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      ui.field(10,FieldBox,expression,state(10,writable)|(valid?NoState:Invalid),LEFONY_UI_HERE,&field);
      ui.label(55,{12,108,296,14},result,LEFONY_FONT_SMALL,LEFONY_UI_HERE,Enabled|(resultError?Invalid:NoState));plot(ui);
      ui.button(11,First,"Save",state(11,writable),LEFONY_UI_HERE);
      ui.button(12,Second,"Delete",state(12,writable && editing<document.count),LEFONY_UI_HERE);
      ui.button(13,Third,"Back",state(13),LEFONY_UI_HERE);
    } else if(navigation.screen()==5) {
      ui.label(70,{12,41,296,14},"Angle unit",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      const char *angles[]={"Deg","Rad","Grad"},*formats[]={"Auto","Sci","Eng"};
      for(unsigned i=0;i<3;i++) ui.choice(30+i,{12+static_cast<int>(i)*102,58,92,28},angles[i],optionAngle==i,state(30+i),LEFONY_UI_HERE);
      ui.label(71,{12,89,296,14},"Number format",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      for(unsigned i=0;i<3;i++) ui.choice(33+i,{12+static_cast<int>(i)*102,106,92,28},formats[i],optionFormat==i,state(33+i),LEFONY_UI_HERE);
      char label[40];snprintf(label,sizeof(label),"Significant digits: %u",optionDigits.value());
      ui.label(72,{12,137,296,14},label,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      ui.slider(36,Digits,optionDigits.value()-1,13,state(36)|(optionDigits.dragging()?Pressed:NoState),LEFONY_UI_HERE);
      ui.button(37,First,"Apply",state(37),LEFONY_UI_HERE);ui.button(38,Second,"OS defaults",state(38),LEFONY_UI_HERE);
      ui.button(39,Third,"Cancel",state(39),LEFONY_UI_HERE);
    } else {
      ui.dialog(60,DialogLayout{},navigation.screen()==4?"Delete this expression?":"Discard unsaved changes?",
        20,navigation.screen()==4?"Delete":"Discard",state(20,writable),21,"Cancel",state(21),LEFONY_UI_HERE);
    }
    ui.label(62,{12,226,296,14},message,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
    inspectionEnd();
  }
  void input(const InputSnapshot &input) {
    unsigned action=0;
    if(input.event==1) {
      field.cancel(expression);
      focus.cancel();optionDigits.cancel();list.cancel();
      if(input.key==InputKey::Back) {if(navigation.screen()==2) leave();else back();}
      else if(navigation.screen()==5 && focus.focused()==36 && (input.key==InputKey::Left || input.key==InputKey::Right))
        optionDigits.move(input.key==InputKey::Left?-1:1);
      else if(input.key==InputKey::Up || input.key==InputKey::Down) {
        int direction=input.key==InputKey::Up?-1:1;
        if(navigation.screen()==1 && focus.focused()>=100 && list.select(focus.focused()-100) && list.move(direction)) rebuild(100+list.selected());
        else focus.move(direction);
      } else if(input.key==InputKey::Confirm) action=focus.confirm();
      else if(navigation.screen()==2 && focus.focused()==10 && writable &&
        (input.key==InputKey::Copy || input.key==InputKey::Cut || input.key==InputKey::Paste)) clipboard(input);
      else if(navigation.screen()==2 && focus.focused()==10) {
        char before[Document::ExpressionBytes];memcpy(before,expression.text(),expression.size()+1);
        if(Expression::edit(expression,input)) {dirty=dirty || strcmp(before,expression.text());evaluate();}
        else if(input.textBytes) notify("Text full or unsupported");
      } else if(input.key==InputKey::Left || input.key==InputKey::Right) focus.move(input.key==InputKey::Left?-1:1);
    } else if(input.event==3) {
      if(navigation.screen()==2 && writable && (field.captured() || (input.touchPhase==0 && field.contains(input.contacts[0].x,input.contacts[0].y)))) {
        focus.select(10);field.touch(expression,input);draw();return;
      }
      if(navigation.screen()==1 && (list.captured() || (input.touchPhase==0 && ListBox.contains(input.contacts[0].x,input.contacts[0].y)))) {
        focus.cancel();unsigned selected=list.touch(input);rebuild(100+list.selected());
        if(selected) activate(99+selected);
        draw();return;
      }
      bool slider=navigation.screen()==5 && (optionDigits.dragging() || (input.touchPhase==0 && Digits.contains(input.contacts[0].x,input.contacts[0].y)));
      if(slider) {
        focus.select(36);optionDigits.touch(Digits,input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,input.flags&ContactsChanged);
      } else action=focus.touch(input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,input.flags&ContactsChanged);
    }
    else return;
    if(action) activate(action);
    draw();
  }
};
}
int main() {
  Notebook app;app.start();uint32_t sequence=0;
  for(;;) {
    InputSnapshot input;
    if(readInput(input)==0 && input.sequence!=sequence) {sequence=input.sequence;app.input(input);}
    lefony_program_yield();
  }
}
