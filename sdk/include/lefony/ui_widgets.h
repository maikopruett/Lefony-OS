// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_WIDGETS_H
#define LEFONY_UI_WIDGETS_H
#include "ui_controls.h"
#include "typography.h"
#include "ui_inspection.h"
#include "ui_patterns.h"
#include "ui_text_field.h"
#include "ui_paragraph.h"
namespace Lefony { namespace UI {
struct Palette {
  uint16_t paper=0xf7be,surface=0xffff,ink=0x1947,muted=0x6b6d,accent=0x2528,
           onAccent=0xffff,selection=0xdedb,disabled=0xe71c,error=0xb904;
};
class Widgets {
public:
  explicit Widgets(Palette palette={},Box clip={0,0,320,240}) : m_palette(palette),m_clip(intersect(clip,{0,0,320,240})),m_canvas(m_clip),m_error(0) {}
  Canvas &canvas() { return m_canvas; }
  const Palette &palette() const { return m_palette; }
  int32_t error() const { return m_error?m_error:m_canvas.error(); }
  void label(uint32_t id,Box box,const char *text,uint32_t font=LEFONY_FONT_SMALL,Source source={},uint32_t state=Enabled) {
    inspectNode(id,Label,box,intersect(box,m_clip),state,text,source);
    write(box,text,!(state&Enabled)?m_palette.muted:(state&Invalid)?m_palette.error:m_palette.ink,m_palette.paper,font);
  }
  ParagraphMetrics paragraph(uint32_t id,Box box,const char *text,uint32_t font=LEFONY_FONT_SMALL,
                             Source source={},uint32_t state=Enabled,unsigned lineGap=2) {
    ParagraphMetrics result;
    auto fail=[&](int32_t error) {m_error=error;result.error=error;return result;};
    if(!text || box.x < -4096 || box.x>4096 || box.y < -4096 || box.y>4096 ||
       box.width<0 || box.width>32767 || box.height<0 || box.height>32767 || lineGap>32) return fail(-4);
    unsigned bytes=Lefony::length(text,ParagraphLayout::MaximumBytes+1);
    auto metrics=measure(nullptr,0,font);
    if(metrics.error) return fail(metrics.error);
    if(!metrics.glyphWidth || !metrics.glyphHeight) return fail(-4);
    unsigned columns=static_cast<unsigned>(box.width)/metrics.glyphWidth;
    ParagraphLayout layout(text,bytes,columns?columns:1);
    if(!layout.valid()) return fail(-4);
    // Validate all text, including clipped lines, before changing any pixels.
    // A base plus combining marks cannot be split across the 256-byte service.
    auto chunks=[&](ParagraphLine line,auto visit) {
      unsigned at=line.offset,end=line.offset+line.bytes;
      while(at<end) {
        unsigned next=at,cells=0;
        while(next<end) {
          unsigned cell=nextTextCell(text,end,next);
          if(cell-at>LEFONY_TEXT_MAXIMUM) break;
          next=cell;cells++;
        }
        if(next==at) return int32_t(-4);
        int32_t error=visit(at,next-at,cells);if(error<0) return error;
        at=next;
      }
      return int32_t(0);
    };
    ParagraphLine line;
    while(layout.next(line)) {
      int32_t error=chunks(line,[&](unsigned at,unsigned count,unsigned) {return measure(text+at,count,font).error;});
      if(error<0) return fail(error);
      result.lines++;
      if(line.cells*metrics.glyphWidth>static_cast<unsigned>(box.width)) result.clipped=true;
    }
    result.height=result.lines?result.lines*(metrics.glyphHeight+lineGap)-lineGap:0;
    Box area=intersect(box,m_clip);
    result.clipped=result.clipped || result.height>static_cast<unsigned>(box.height) ||
      area.x!=box.x || area.y!=box.y || area.width!=box.width || area.height!=box.height;
    inspectNode(id,Label,box,area,state,text,source);
    m_canvas.fill(box,m_palette.paper);
    layout=ParagraphLayout(text,bytes,columns?columns:1);
    int64_t y=box.y;uint16_t ink=!(state&Enabled)?m_palette.muted:(state&Invalid)?m_palette.error:m_palette.ink;
    while(layout.next(line)) {
      if(y< int64_t(area.y)+area.height && y+metrics.glyphHeight>area.y && area.width && area.height) {
        int64_t x=box.x;
        int32_t error=chunks(line,[&](unsigned at,unsigned count,unsigned cells) {
          int32_t error=0;unsigned width=cells*metrics.glyphWidth;
          if(x<int64_t(area.x)+area.width && x+width>area.x)
            error=drawText(area,static_cast<int>(x),static_cast<int>(y),text+at,count,ink,m_palette.paper,font);
          x+=width;return error;
        });
        if(error<0) return fail(error);
      }
      y+=metrics.glyphHeight+lineGap;
    }
    return result;
  }
  void button(uint32_t id,Box box,const char *text,uint32_t state=Enabled,Source source={}) {
    inspectNode(id,Button,box,intersect(box,m_clip),state,text,source);
    Box area=intersect(box,m_clip);if(box.width<12 || box.height<20 || !area.width || !area.height) return;
    uint16_t paper=!(state&Enabled)?m_palette.disabled:(state&Pressed)?m_palette.ink:m_palette.accent;
    m_canvas.fill(box,paper);m_canvas.outline(box,state&Focused?m_palette.ink:paper,2);
    if(!text) {m_error=-4;return;}
    auto size=measure(text,Lefony::length(text,257));if(size.error) {m_error=size.error;return;}
    int x=size.width<static_cast<unsigned>(box.width-12)?(box.width-static_cast<int>(size.width))/2:6;
    write({box.x+x,box.y+(box.height-static_cast<int>(size.height))/2,box.width-x-6,static_cast<int>(size.height)},
          text,state&Enabled?m_palette.onAccent:m_palette.muted,paper);
  }
  void row(uint32_t id,Box box,const char *title,const char *detail,uint32_t state=Enabled,Source source={}) {
    inspectNode(id,ListRow,box,intersect(box,m_clip),state,title,source);
    Box area=intersect(box,m_clip);if(box.width<16 || box.height<34 || area.width<=0 || area.height<=0) return;
    bool pressed=(state&(Enabled|Pressed))==(Enabled|Pressed);
    uint16_t paper=pressed?m_palette.accent:state&Selected?m_palette.selection:m_palette.surface;
    m_canvas.fill(box,paper);m_canvas.outline(box,state&Focused?m_palette.accent:paper,2);
    write({box.x+8,box.y+4,box.width-16,14},title,pressed?m_palette.onAccent:state&Enabled?m_palette.ink:m_palette.muted,paper);
    write({box.x+8,box.y+20,box.width-16,14},detail,pressed?m_palette.onAccent:m_palette.muted,paper);
  }
  void scrollbar(uint32_t id,Box box,const ListModel &list,Source source={}) {
    Box area=intersect(box,m_clip);
    if(!list.maximumOffset() || area.width<=0 || area.height<=0) return;
    inspectNode(id,Scrollbar,box,area,Enabled|(list.dragging()?Pressed:NoState),"Scroll position",source);
    m_canvas.fill(box,m_palette.disabled);
    int height=static_cast<int>(Detail::scale(box.height,list.viewportHeight(),list.extent()));
    if(height<8) height=box.height<8?box.height:8;
    int offset=static_cast<int>(Detail::scale(box.height-height,list.offset(),list.maximumOffset()));
    fillAt(box.x,int64_t(box.y)+offset,box.width,height,list.dragging()?m_palette.ink:m_palette.accent);
  }
  void choice(uint32_t id,Box box,const char *title,bool selected,uint32_t state=Enabled,Source source={}) {
    inspectNode(id,Choice,box,intersect(box,m_clip),state|(selected?Selected:NoState),title,source);
    Box area=intersect(box,m_clip);if(box.width<42 || box.height<24 || !area.width || !area.height) return;
    bool pressed=(state&(Enabled|Pressed))==(Enabled|Pressed);
    uint16_t paper=!(state&Enabled)?m_palette.disabled:pressed?m_palette.accent:m_palette.surface;
    uint16_t ink=!(state&Enabled)?m_palette.muted:pressed?m_palette.onAccent:m_palette.ink;
    m_canvas.fill(box,paper);m_canvas.outline(box,state&Focused?m_palette.accent:m_palette.muted,1);
    write({box.x+6,box.y+(box.height-14)/2,24,14},selected?"[x]":"[ ]",state&Enabled?pressed?m_palette.onAccent:m_palette.accent:m_palette.muted,paper);
    write({box.x+36,box.y+(box.height-14)/2,box.width-42,14},title,ink,paper);
  }
  void progress(uint32_t id,Box box,uint32_t done,uint32_t total,Source source={}) {
    inspectNode(id,Progress,box,intersect(box,m_clip),Enabled,"Progress",source);
    m_canvas.fill(box,m_palette.disabled);
    if(total && box.width>0) m_canvas.fill({box.x,box.y,static_cast<int>(uint64_t(box.width)*(done>total?total:done)/total),box.height},m_palette.accent);
  }
  void slider(uint32_t id,Box box,uint32_t value,uint32_t maximum,uint32_t state=Enabled,Source source={}) {
    inspectNode(id,Slider,box,intersect(box,m_clip),state,"Slider",source);
    Box area=intersect(box,m_clip);if(box.width<20 || box.height<20 || !area.width || !area.height) return;
    m_canvas.fill(box,m_palette.paper);m_canvas.outline(box,state&Focused?m_palette.accent:m_palette.paper);
    m_canvas.fill({box.x+6,box.y+box.height/2-2,box.width-12,4},m_palette.disabled);
    unsigned offset=maximum?uint64_t(box.width-20)*(value>maximum?maximum:value)/maximum:0;
    fillAt(int64_t(box.x)+6+offset,box.y+box.height/2-8,8,16,
           !(state&Enabled)?m_palette.muted:state&Pressed?m_palette.ink:m_palette.accent);
  }
  template<unsigned Capacity> void field(uint32_t id,Box box,const TextBuffer<Capacity> &value,uint32_t state=Enabled,Source source={},TextFieldModel *interaction=nullptr) {
    inspectNode(id,TextField,box,intersect(box,m_clip),state,value.text(),source);
    Box area=intersect(box,m_clip);if(box.width<20 || box.height<22 || !area.width || !area.height) {if(interaction) interaction->disable();return;}
    uint16_t paper=state&Enabled?m_palette.surface:m_palette.disabled;
    m_canvas.fill(box,paper);m_canvas.outline(box,state&Invalid?m_palette.error:state&Focused?m_palette.accent:m_palette.muted,2);
    // TextBuffer guarantees UTF-8. Validate fonts in whole-cell chunks, keeping
    // the API's 256-byte limit without limiting the field's total capacity.
    auto size=measure(nullptr,0);if(size.error || !size.glyphWidth) {m_error=size.error?size.error:-4;if(interaction) interaction->disable();return;}
    for(unsigned at=0;at<value.size();) {
      unsigned end=at;
      while(end<value.size()) {
        unsigned next=nextTextCell(value.text(),value.size(),end);
        if(next-at>256) break;
        end=next;
      }
      if(end==at) {m_error=-4;if(interaction) interaction->disable();return;}
      auto part=measure(value.text()+at,end-at);if(part.error) {m_error=part.error;if(interaction) interaction->disable();return;}
      at=end;
    }
    auto view=interaction?interaction->view(value,box,area,size.glyphWidth,state&Enabled):textFieldView(value,box.width,size.glyphWidth);
    unsigned caret=view.caret,visible=view.visible,scroll=view.scroll;
    int y=box.y+(box.height-static_cast<int>(size.glyphHeight))/2;
    unsigned column=0;
    for(unsigned at=0;at<value.size();column++) {
      unsigned next=nextTextCell(value.text(),value.size(),at);
      if(column>=scroll && column-scroll<visible) {
        uint16_t bg=(state&Focused) && at<value.selectionEnd() && next>value.selectionStart()?m_palette.selection:paper;
        int result=drawText(area,box.x+6+static_cast<int>((column-scroll)*size.glyphWidth),y,value.text()+at,next-at,
                           state&Enabled?m_palette.ink:m_palette.muted,bg);
        if(result<0) m_error=result;
      }
      at=next;
    }
    if((state&(Enabled|Focused))==(Enabled|Focused)) m_canvas.fill({box.x+6+static_cast<int>((caret-scroll)*size.glyphWidth),y,1,static_cast<int>(size.glyphHeight)},m_palette.ink);
  }
  void dialog(uint32_t id,const DialogLayout &layout,const char *title,
              uint32_t primaryId,const char *primary,uint32_t primaryState,
              uint32_t cancelId,const char *cancel,uint32_t cancelState,Source source={}) {
    if(!layout.valid()) {m_error=-4;return;}
    inspectNode(id,Dialog,layout.panel,intersect(layout.panel,m_clip),Enabled,title,source);
    m_canvas.fill(layout.panel,m_palette.paper);m_canvas.outline(layout.panel,m_palette.accent,2);
    write(layout.title,title,m_palette.ink,m_palette.paper);
    button(primaryId,layout.primary,primary,primaryState,source);
    button(cancelId,layout.secondary,cancel,cancelState,source);
  }
  template<unsigned Capacity> void menu(uint32_t id,const MenuModel<Capacity> &model,
                                       const char *empty="No actions",Source source={}) {
    Box bounds=model.list().bounds();Widgets rows(m_palette,intersect(bounds,m_clip));
    inspectNode(id,Menu,bounds,intersect(bounds,m_clip),Enabled,"Menu",source);
    m_canvas.fill(bounds,m_palette.surface);
    if(!model.count()) rows.write(bounds,empty,m_palette.muted,m_palette.surface);
    for(unsigned i=model.list().first();i<model.list().first()+model.list().visible();i++) {
      Box box=model.list().row(i);uint32_t action=model.id(i);
      uint32_t state=(model.enabled(i)?Enabled:NoState)|(model.focused()==action?Focused:NoState)|(model.pressed()==action?Pressed:NoState);
      uint16_t paper=!(state&Enabled)?m_palette.disabled:state&Pressed?m_palette.accent:m_palette.surface;
      inspectNode(action,MenuItem,box,intersect(box,rows.m_clip),state,model.title(i),source);
      rows.m_canvas.fill(box,paper);rows.m_canvas.outline(box,state&Focused?m_palette.accent:paper,1);
      if(box.width>12 && box.height>=14) rows.write({box.x+6,box.y+(box.height-14)/2,box.width-12,14},
        model.title(i),!(state&Enabled)?m_palette.muted:state&Pressed?m_palette.onAccent:m_palette.ink,paper);
    }
    if(rows.error()) m_error=rows.error();
  }
private:
  void fillAt(int64_t x,int64_t y,int32_t width,int32_t height,uint16_t color) {
    if(x<INT32_MIN || x>INT32_MAX || y<INT32_MIN || y>INT32_MAX) return;
    m_canvas.fill({static_cast<int32_t>(x),static_cast<int32_t>(y),width,height},color);
  }
  void write(Box box,const char *text,uint16_t ink,uint16_t paper,uint32_t font=LEFONY_FONT_SMALL) {
    if(!text) {m_error=-4;return;}
    int32_t result=drawText(intersect(box,m_clip),box.x,box.y,text,Lefony::length(text,257),ink,paper,font);
    if(result<0) m_error=result;
  }
  Palette m_palette;Box m_clip;Canvas m_canvas;int32_t m_error;
};

}}
#endif
