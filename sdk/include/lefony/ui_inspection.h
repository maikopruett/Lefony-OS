// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_INSPECTION_H
#define LEFONY_UI_INSPECTION_H
#include "ui_model.h"
namespace Lefony { namespace UI {
struct Source { const char *file=nullptr;uint32_t line=0; };
enum WidgetState : uint32_t { NoState=0,Enabled=1,Focused=2,Pressed=4,Selected=8,Invalid=16 };
enum WidgetKind : uint32_t { Label=1,Button=2,ListRow=3,TextField=4,Progress=5,Custom=6,Choice=7,Slider=8,Dialog=9,Scrollbar=10,Menu=11,MenuItem=12 };
struct DebugNode {
  uint32_t id,kind;Box bounds,clip;uint32_t state,line;char name[32],file[96];
};
struct DebugFrame { uint32_t magic,schema,size,sequence,count,overflow;DebugNode nodes[64];uint32_t inputReady; };
static_assert(sizeof(DebugNode)==176 && sizeof(DebugFrame)==11292,"debug frame layout");
}}
#if defined(LEFONY_SDK_DEBUG) && LEFONY_SDK_DEBUG
extern "C" { inline Lefony::UI::DebugFrame lefony_ui_debug{}; }
#endif
namespace Lefony { namespace UI {
inline void inspectionBegin() {
#if defined(LEFONY_SDK_DEBUG) && LEFONY_SDK_DEBUG
  auto &f=lefony_ui_debug;f.magic=0x4955464c;f.schema=2;f.size=sizeof(f);
  f.sequence=(f.sequence+1)|1;f.count=f.overflow=f.inputReady=0;
#endif
}
inline void inspectNode(uint32_t id,WidgetKind kind,Box bounds,Box clip,uint32_t state,
                        const char *name,Source source={}) {
#if defined(LEFONY_SDK_DEBUG) && LEFONY_SDK_DEBUG
  auto &f=lefony_ui_debug;
  if(f.count==64) {f.overflow++;return;}
  auto &n=f.nodes[f.count++];n={};n.id=id;n.kind=kind;n.bounds=bounds;n.clip=clip;n.state=state;n.line=source.line;
  if(name) for(unsigned i=0;i+1<sizeof(n.name) && name[i];i++) n.name[i]=name[i];
  if(source.file) for(unsigned i=0;i+1<sizeof(n.file) && source.file[i];i++) n.file[i]=source.file[i];
#else
  (void)id;(void)kind;(void)bounds;(void)clip;(void)state;(void)name;(void)source;
#endif
}
inline void inspectionEnd(bool inputReady=true) {
#if defined(LEFONY_SDK_DEBUG) && LEFONY_SDK_DEBUG
  lefony_ui_debug.inputReady=inputReady?1:0;
  lefony_ui_debug.sequence=(lefony_ui_debug.sequence+1)&~1u;
#else
  (void)inputReady;
#endif
}
}}
#define LEFONY_UI_HERE ::Lefony::UI::Source{__FILE__,__LINE__}
#endif
