// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui_widgets.h>
#include <lefony/foreground.h>
#include <stdio.h>
#include <string.h>
using namespace Lefony;
using namespace Lefony::UI;
namespace {
constexpr Box Header{224,8,84,24},Field{12,62,296,32},Check{12,106,142,28},Reset{166,106,142,28};
constexpr Box SliderBox{12,148,296,28},MenuBox{12,50,296,150};
class Gallery {
  Focus<> focus;Navigation<> navigation;MenuModel<9> menu;SliderModel slider{0,100,50};
  TextBuffer<1024> text;bool enabled=true,dark=false,loading=false;
  TextFieldModel field;
  uint32_t readyAt=0;unsigned actions=0;char message[96]="Up/Down selects; OK activates";
  Palette palette() const {
    return dark?Palette{0x10c4,0x2126,0xef7d,0xadb6,0x4df2,0x10c4,0x328b,0x528a,0xfaaa}:Palette{};
  }
  uint32_t state(unsigned id,bool active=true) const {
    return (active?Enabled:NoState)|(focus.focused()==id?Focused:NoState)|(focus.pressed()==id?Pressed:NoState);
  }
  void notify(const char *value) {snprintf(message,sizeof(message),"%s",value);}
  void rebuild(unsigned restore=0) {
    field.cancel(text);
    focus.clear();
    if(navigation.screen()==1) {
      focus.add(10,Field,enabled);focus.add(11,Check);focus.add(12,Reset,enabled);focus.add(13,SliderBox,enabled);focus.add(1,Header);
    } else if(navigation.screen()==4) DialogLayout{}.open(focus,20,21);
    else focus.add(1,Header);
    if(restore) focus.select(restore);
  }
  void back() {
    menu.cancel();slider.cancel();auto prior=navigation.pop();
    if(prior.ok) {loading=false;rebuild(prior.focus);notify("Returned without changing the field");}
  }
  bool screen(unsigned id) {
    menu.cancel();slider.cancel();
    if(!navigation.push(id,focus.focused())) return false;
    rebuild();return true;
  }
  void openMenu() {
    if(!screen(2)) return;
    menu.clear();menu.layout(MenuBox);
    menu.add(100,"Change theme");menu.add(101,"Unavailable action",false);
    menu.add(102,"Long text (1023 bytes)");menu.add(103,"Clear text");menu.add(104,"Four OS fonts");
    menu.add(105,"Empty menu");menu.add(106,"Loading actions");menu.add(107,"Close actions");
    menu.add(108,"Wrapped text");
    notify("Drag or Up/Down; OK runs an action");
  }
  void activate(unsigned id) {
    if(navigation.screen()==1) {
      if(id==1) openMenu();
      else if(id==10) {text.selectAll();notify("Selection ready; type to replace");}
      else if(id==11) {enabled=!enabled;rebuild(11);notify(enabled?"Controls enabled":"Controls disabled");}
      else if(id==12) screen(4);
      return;
    }
    if(navigation.screen()==4) {
      if(id==20) {text.set("Ready",5);actions++;back();notify("Field reset");}
      else if(id==21) back();
      return;
    }
    if(id==1) {back();return;}
    if(id==300) {back();notify("Loaded action selected");return;}
    actions++;
    if(id==100) {dark=!dark;back();notify("Theme changed");}
    else if(id==102) {
      char value[1024];memset(value,'a',1023);memcpy(value+1020,"END",3);value[1023]=0;
      text.set(value,1023);back();rebuild(10);notify("1023 bytes; Left/Right moves caret");
    } else if(id==103) {text.clear();back();rebuild(10);notify("Empty field");}
    else if(id==104) {back();screen(3);notify("Supported accents and math glyphs");}
    else if(id==105 || id==106) {
      back();screen(5);menu.clear();menu.layout(MenuBox);loading=id==106;readyAt=Lefony::millis()+3000;
      notify(loading?"Local loading-state demonstration":"An empty menu cannot activate");
    } else if(id==107) back();
    else if(id==108) {back();screen(6);notify("Words wrap; blank lines are kept");}
  }
public:
  void start() {text.set("Cafe\xcc\x81 \xcf\x80",9);rebuild();draw();}
  void tick() {
    if(loading && static_cast<int32_t>(Lefony::millis()-readyAt)>=0) {
      loading=false;menu.add(300,"Loaded action");notify("Ready; OK selects the loaded action");draw();
    }
  }
  void draw() {
    Widgets ui(palette());auto p=ui.palette();inspectionBegin();ui.canvas().fill({0,0,320,240},p.paper);
    const char *title=navigation.screen()==1?"UI gallery":navigation.screen()==2?"Actions":navigation.screen()==3?"OS fonts":navigation.screen()==4?"Confirmation":navigation.screen()==6?"Wrapped text":"Menu states";
    ui.label(50,{12,8,204,22},title,LEFONY_FONT_LARGE,LEFONY_UI_HERE);
    if(navigation.screen()!=4) ui.button(1,Header,navigation.screen()==1?"Actions":"Back",
      navigation.screen()==2 || navigation.screen()==5?Enabled|(focus.pressed()==1?Pressed:NoState):state(1),LEFONY_UI_HERE);
    if(navigation.screen()==1) {
      ui.label(51,{12,42,296,14},"Text field",LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      ui.field(10,Field,text,state(10,enabled),LEFONY_UI_HERE,&field);
      ui.choice(11,Check,"Enabled",enabled,state(11),LEFONY_UI_HERE);
      ui.button(12,Reset,"Reset field",state(12,enabled),LEFONY_UI_HERE);
      ui.slider(13,SliderBox,slider.value(),100,state(13,enabled)|(slider.dragging()?Pressed:NoState),LEFONY_UI_HERE);
      ui.progress(14,{12,180,296,6},slider.value(),100,LEFONY_UI_HERE);
      char info[64];snprintf(info,sizeof(info),"Value: %u / actions: %u",slider.value(),actions);
      ui.label(52,{12,194,296,14},info,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
    } else if(navigation.screen()==2 || navigation.screen()==5) {
      ui.menu(60,menu,loading?"Loading actions...":"No actions",LEFONY_UI_HERE);
      ui.scrollbar(61,{312,50,4,150},menu.list(),LEFONY_UI_HERE);
      if(loading) ui.progress(62,{12,206,296,4},1,3,LEFONY_UI_HERE);
    } else if(navigation.screen()==3) {
      for(unsigned font=0;font<4;font++) ui.label(70+font,{12,52+static_cast<int>(font)*32,296,22},"Cafe\xcc\x81 \xcf\x80 = 3.14",font,LEFONY_UI_HERE);
      ui.label(74,{12,190,296,14},"Disabled label",LEFONY_FONT_SMALL,LEFONY_UI_HERE,NoState);
      ui.label(75,{12,208,296,14},"Invalid value",LEFONY_FONT_SMALL,LEFONY_UI_HERE,Enabled|Invalid);
    } else if(navigation.screen()==6) {
      auto wrapped=ui.paragraph(76,{12,50,296,64},"Cafe\xcc\x81 \xcf\x80 stays together while this longer sentence wraps.\nA second line starts here.",
        LEFONY_FONT_SMALL,LEFONY_UI_HERE);
      auto word=ui.paragraph(77,{12,128,140,76},"A_very_long_word_without_spaces.",LEFONY_FONT_LARGE,LEFONY_UI_HERE,NoState);
      auto warning=ui.paragraph(78,{168,128,140,76},"Check the value.\n\nTry again when the input is valid.",
        LEFONY_FONT_SMALL_ITALIC,LEFONY_UI_HERE,Enabled|Invalid);
      if(wrapped.clipped || word.clipped || warning.clipped) lefony_program_exit(1100);
    } else ui.dialog(80,DialogLayout{},"Reset the text field?",20,"Reset",state(20),21,"Cancel",state(21),LEFONY_UI_HERE);
    ui.label(90,{12,226,296,14},message,LEFONY_FONT_SMALL,LEFONY_UI_HERE);
    inspectionEnd();if(ui.error()) lefony_program_exit(1000-ui.error());
  }
  void input(const InputSnapshot &input) {
    unsigned action=0;bool menuScreen=navigation.screen()==2 || navigation.screen()==5;
    if(input.event==1) {
      field.cancel(text);
      focus.cancel();slider.cancel();
      if(input.key==InputKey::Back) back();
      else if(menuScreen) action=menu.input(input);
      else if(input.key==InputKey::Up || input.key==InputKey::Down) focus.move(input.key==InputKey::Up?-1:1);
      else if(input.key==InputKey::Confirm) action=focus.confirm();
      else if(navigation.screen()==1 && focus.focused()==10 && enabled) {
        if(edit(text,input)) notify("Field edited");else if(input.textBytes) notify("Text full or invalid");
      } else if(navigation.screen()==1 && focus.focused()==13 && enabled && (input.key==InputKey::Left || input.key==InputKey::Right))
        slider.move(input.key==InputKey::Left?-1:1);
      else if(input.key==InputKey::Left || input.key==InputKey::Right) focus.move(input.key==InputKey::Left?-1:1);
    } else if(input.event==3) {
      if(navigation.screen()==1 && enabled && (field.captured() || (input.touchPhase==0 && field.contains(input.contacts[0].x,input.contacts[0].y)))) {
        focus.select(10);field.touch(text,input);
      } else if(menuScreen && (menu.list().captured() || (input.touchPhase==0 && MenuBox.contains(input.contacts[0].x,input.contacts[0].y)))) {
        focus.cancel();action=menu.touch(input);
      } else if(navigation.screen()==1 && enabled && (slider.dragging() || (input.touchPhase==0 && SliderBox.contains(input.contacts[0].x,input.contacts[0].y)))) {
        focus.select(13);slider.touch(SliderBox,input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,input.flags&ContactsChanged);
      } else action=focus.touch(input.touchPhase,input.contactCount,input.contacts[0].x,input.contacts[0].y,input.flags&ContactsChanged);
    } else return;
    if(action) activate(action);
    draw();
  }
};
}
int main() {
  Gallery app;app.start();uint32_t sequence=0;
  for(;;) {
    InputSnapshot input;
    if(readInput(input)==0 && input.sequence!=sequence) {sequence=input.sequence;app.input(input);}
    app.tick();lefony_program_yield();
  }
}
