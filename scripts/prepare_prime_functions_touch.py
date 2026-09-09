"""Visible control hit-testing and graph gestures for native Prime builds."""
import shutil


def prepare(source, port, edit):
    for name in ("prime_graph_gesture.h", "prime_graph_touch_impl.h", "prime_touch_controls_impl.h"):
        shutil.copy2(port / "apps" / name, source / "apps" / name)

    edit("escher/include/escher/view.h", "\nclass Window;", "\nclass Responder;\nclass Window;")
    edit("escher/include/escher/view.h", "  View * subview(int index);", '''  View * subview(int index);
#if defined(PLATFORM_PRIME_G2)
  bool touchContains(int x, int y) const {
    return absoluteVisibleFrame().contains(KDPoint(x, y));
  }
  virtual Responder * responderForTouch() { return nullptr; }
  virtual Responder * touchResponderAt(int x, int y) {
    if (!touchContains(x, y)) return nullptr;
    // Tables own their cells, and graphs own their overlays.
    if (auto responder = responderForTouch()) return responder;
    for (int i = numberOfSubviews() - 1; i >= 0; i--) {
      if (auto child = subviewAtIndex(i)) {
        if (auto responder = child->touchResponderAt(x, y)) return responder;
      }
    }
    return nullptr;
  }
#endif''')
    # Keep the existing touch integration substitutions intact for reruns.
    edit("escher/include/escher/selectable_table_view.h", "  void didEnterResponderChain(Responder * previousFirstResponder) override;", '''#if defined(PLATFORM_PRIME_G2)
  Responder * responderForTouch() override { return this; }
#endif
  void didEnterResponderChain(Responder * previousFirstResponder) override;''')
    edit("escher/include/escher/modal_view_controller.h", "    ContentView();", '''    ContentView();
#if defined(PLATFORM_PRIME_G2)
    Responder * touchResponderAt(int x, int y) override {
      // A modal blocks the covered app, including outside its own frame.
      View * target = m_isDisplayingModal ? m_currentModalView : m_regularView;
      return touchContains(x, y) && target ? target->touchResponderAt(x, y) : nullptr;
    }
#endif''')
    edit("escher/include/escher/button.h", "  void setMessage(I18n::Message message);", '''#if defined(PLATFORM_PRIME_G2)
  Responder * responderForTouch() override { return this; }
  bool handleTouch(const Ion::Touch::Event & touch) override;
private:
  bool m_touchTracking = false, m_touchWasHighlighted = false;
public:
#endif
  void setMessage(I18n::Message message);''')
    edit("escher/src/button.cpp", "#include <escher/button.h>", '''#include <escher/button.h>
#if defined(PLATFORM_PRIME_G2)
#include <apps/prime_touch_controls_impl.h>
#endif''')
    edit("escher/include/escher/tab_view.h", "  TabView();", '''  TabView();
#if defined(PLATFORM_PRIME_G2)
  Responder * responderForTouch() override { return m_touchController; }
  void setTouchController(Responder * controller) { m_touchController = controller; }
  int tabAtTouch(int x, int y) {
    for (int i = 0; i < m_numberOfTabs; i++) if (m_cells[i].touchContains(x, y)) return i;
    return -1;
  }
private:
  Responder * m_touchController = nullptr;
public:
#endif''')
    edit("escher/include/escher/tab_view_controller.h", "  int activeTab() const;", '''#if defined(PLATFORM_PRIME_G2)
  bool handleTouch(const Ion::Touch::Event & touch) override;
private:
  int m_touchTab = -1;
public:
#endif
  int activeTab() const;''')
    edit("escher/src/tab_view_controller.cpp", "  assert(one != nullptr);", '''#if defined(PLATFORM_PRIME_G2)
  m_view.m_tabView.setTouchController(this);
#endif
  assert(one != nullptr);''')
    edit("escher/src/tab_view_controller.cpp", "int TabViewController::activeTab() const {", '''#if defined(PLATFORM_PRIME_G2)
bool TabViewController::handleTouch(const Ion::Touch::Event & touch) {
  using Ion::Touch::Phase;
  int tab = m_view.m_tabView.tabAtTouch(touch.x, touch.y);
  if (touch.phase == Phase::Down) { m_touchTab = tab; return tab >= 0; }
  if (m_touchTab < 0) return false;
  int pressed = m_touchTab;
  if (touch.dragging || touch.phase == Phase::Cancel || touch.phase == Phase::Up) m_touchTab = -1;
  if (touch.phase == Phase::Up && !touch.dragging && tab == pressed) setActiveTab(tab);
  return true;
}
#endif

int TabViewController::activeTab() const {''')
    edit("apps/shared/curve_view.h", "  virtual void reload();", '''#if defined(PLATFORM_PRIME_G2)
  Responder * responderForTouch() override { return m_touchController; }
  void setTouchController(Responder * controller) { m_touchController = controller; }
  bool touchOnOK(int x, int y) { return m_okView && m_okView->touchContains(x, y); }
  bool touchOnBanner(int x, int y) { return bannerIsVisible() && m_bannerView->touchContains(x, y); }
private:
  Responder * m_touchController = nullptr;
public:
#endif
  virtual void reload();''')
    edit("apps/shared/zoom_curve_view_controller.h", '#include "curve_view.h"', '''#include "curve_view.h"
#if defined(PLATFORM_PRIME_G2)
#include <apps/prime_graph_gesture.h>
#endif''')
    edit("apps/shared/zoom_curve_view_controller.h", "  bool handleEvent(Ion::Events::Event event) override;", '''  bool handleEvent(Ion::Events::Event event) override;
#if defined(PLATFORM_PRIME_G2)
  virtual void focusForTouch();
  bool acceptsMultitouch() const override { return true; }
  bool handleTouch(const Ion::Touch::Event & touch) override;
private:
  PrimeG2::GraphGesture m_touchGesture;
  bool m_touchTracking = false, m_touchOnOK = false, m_touchOnBanner = false;
public:
#endif''')
    edit("apps/shared/zoom_curve_view_controller.cpp", "namespace Shared {", '''namespace Shared {
#if defined(PLATFORM_PRIME_G2)
#include <apps/prime_graph_touch_impl.h>
#endif''')
    edit("apps/shared/interactive_curve_view_controller.cpp", "  SimpleInteractiveCurveViewController::viewWillAppear();", '''  SimpleInteractiveCurveViewController::viewWillAppear();
#if defined(PLATFORM_PRIME_G2)
  curveView()->setTouchController(this);
#endif''')
    edit("apps/shared/interactive_curve_view_controller.cpp", "void InteractiveCurveViewController::viewDidDisappear() {", '''void InteractiveCurveViewController::viewDidDisappear() {
#if defined(PLATFORM_PRIME_G2)
  if (curveView()->responderForTouch() == this) curveView()->setTouchController(nullptr);
#endif''')
    edit("apps/shared/function_zoom_and_pan_curve_view_controller.cpp", "  ViewController::viewWillAppear();", '''  ViewController::viewWillAppear();
#if defined(PLATFORM_PRIME_G2)
  curveView()->setTouchController(this);
#endif''')
    edit("apps/shared/function_zoom_and_pan_curve_view_controller.cpp", "  // Restore the curve range", '''#if defined(PLATFORM_PRIME_G2)
  if (curveView()->responderForTouch() == this) curveView()->setTouchController(nullptr);
#endif
  // Restore the curve range''')

    edit("apps/shared/interactive_curve_view_controller.h", "  RangeParameterController * rangeParameterController();", """#if defined(PLATFORM_PRIME_G2)
  void focusForTouch() override { setCurveViewAsMainView(); }
#endif
  RangeParameterController * rangeParameterController();""")
    edit("apps/graph/graph/graph_controller.cpp", "  FunctionGraphController::viewWillAppear();", """  FunctionGraphController::viewWillAppear();
#if defined(PLATFORM_PRIME_G2)
  m_view.setOkView(nullptr);
#endif""")
