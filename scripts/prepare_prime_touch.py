"""Idempotent coordinate-touch integration into a prepared Upsilon checkout.

Only exact, checked substitutions are allowed; no checkout/reset operations.
"""
import argparse
from pathlib import Path
import shutil
import prepare_prime_functions_touch

ROOT = Path(__file__).resolve().parents[1]


def prepare(source):
    port = ROOT / "ports/lefony-prime-g2"
    shutil.copy2(port / "ion/include/ion/touch.h", source / "ion/include/ion/touch.h")
    shutil.copy2(port / "apps/prime_touch_table_impl.h", source / "apps/prime_touch_table_impl.h")
    shutil.copy2(port / "apps/prime_calculation_touch_impl.h", source / "apps/prime_calculation_touch_impl.h")

    def edit(name, old, new):
        path = source / name
        text = path.read_text()
        if new in text:
            return
        if text.count(old) != 1:
            raise ValueError(f"Unexpected touch integration context: {name}: {old[:70]}")
        path.write_text(text.replace(old, new))

    edit("apps/calculation/edit_expression_controller.h", "  void restoreInput();", '''#if defined(PLATFORM_PRIME_G2)
  bool handleTouch(const Ion::Touch::Event & touch) override {
    return m_contentView.mainView()->handleTouch(touch);
  }
#endif
  void restoreInput();''')
    edit("apps/calculation/selectable_table_view.h", "  void scrollToBottom();", '''#if defined(PLATFORM_PRIME_G2)
  bool handleTouch(const Ion::Touch::Event & touch) override;
private:
  int historyTouchTarget(int x, int y, int * row);
  bool m_historyTouchTracking = false;
  int m_historyTouchRow = -1, m_historyTouchTarget = 0;
  KDPoint m_historyTouchOffset = KDPoint(0, 0);
public:
#endif
  void scrollToBottom();''')
    edit("apps/calculation/selectable_table_view.cpp", '#include "selectable_table_view.h"',
         '#include "selectable_table_view.h"\n#if defined(PLATFORM_PRIME_G2)\n#include "history_controller.h"\n#endif')
    edit("apps/calculation/selectable_table_view.cpp", "namespace Calculation {",
         'namespace Calculation {\n#if defined(PLATFORM_PRIME_G2)\n#include <apps/prime_calculation_touch_impl.h>\n#endif')
    edit("apps/shared/scrollable_multiple_expressions_view.h", "  bool displayCenter() const { return constContentCell()->displayCenter(); }", '''#if defined(PLATFORM_PRIME_G2)
  bool touchTargetsApproximate(int screenX) {
    auto right = contentCell()->rightExpressionView();
    return !displayCenter() || screenX >= right->touchOrigin().x();
  }
#endif
  bool displayCenter() const { return constContentCell()->displayCenter(); }''')
    edit("apps/calculation/history_controller.h", "  void reload();", '''#if defined(PLATFORM_PRIME_G2)
  void recallByTouch(int row, bool input, bool approximate);
#endif
  void reload();''')
    edit("apps/calculation/history_controller.cpp", "void HistoryController::reload() {", '''#if defined(PLATFORM_PRIME_G2)
void HistoryController::recallByTouch(int row, bool input, bool approximate) {
  if (row < 0 || row >= numberOfRows()) return;
  // Copy before deselection/focus changes can rebuild layouts and move storage.
  char text[Constant::MaxSerializedExpressionSize];
  auto calculation = calculationAtIndex(row);
  const char * source = input ? calculation->inputText() :
    (approximate && !calculation->shouldOnlyDisplayExactOutput() ?
      calculation->approximateOutputText(Calculation::NumberOfSignificantDigits::Maximal) :
      calculation->exactOutputText());
  strlcpy(text, source, sizeof(text));
  m_selectableTableView.deselectTable();
  static_cast<EditExpressionController *>(parentResponder())->insertTextBody(text);
}
#endif

void HistoryController::reload() {''')

    edit("ion/include/ion/events.h", "constexpr Event ExternalText = Event::Special(6);",
         "constexpr Event ExternalText = Event::Special(6);\n#if defined(PLATFORM_PRIME_G2)\nconstexpr Event Touch = Event::Special(7);\n#endif")
    edit("ion/src/shared/events.cpp", "bool Event::isDefined() const  {",
         "bool Event::isDefined() const  {\n#if defined(PLATFORM_PRIME_G2)\n  if (*this == Touch) return true;\n#endif")
    edit("escher/include/escher/responder.h", "#include <ion/events.h>",
         "#include <ion/events.h>\n#if defined(PLATFORM_PRIME_G2)\n#include <ion/touch.h>\n#endif")
    edit("escher/include/escher/responder.h", "  virtual void didBecomeFirstResponder() {}",
         "#if defined(PLATFORM_PRIME_G2)\n  virtual bool handleTouch(const Ion::Touch::Event &) { return false; }\n  virtual bool acceptsMultitouch() const { return false; }\n#endif\n  virtual void didBecomeFirstResponder() {}")
    edit("escher/include/escher/view.h", "  KDRect bounds() const;",
         "  KDRect bounds() const;\n#if defined(PLATFORM_PRIME_G2)\n  KDPoint touchOrigin() const { return absoluteOrigin(); }\n#endif")
    edit("escher/include/escher/app.h", "  Responder * m_firstResponder;",
         "#if defined(PLATFORM_PRIME_G2)\n  Responder * m_touchResponder = nullptr;\n  void cancelTouch();\n#endif\n  Responder * m_firstResponder;")
    edit("escher/src/app.cpp", "bool App::processEvent(Ion::Events::Event event) {", '''#if defined(PLATFORM_PRIME_G2)
void App::cancelTouch() {
  Responder * target = m_touchResponder;
  m_touchResponder = nullptr;
  if (target) {
    Ion::Touch::Event cancelled;
    target->handleTouch(cancelled);
  }
}
#endif

bool App::processEvent(Ion::Events::Event event) {
#if defined(PLATFORM_PRIME_G2)
  if (event == Ion::Events::Touch) {
    const auto touch = Ion::Touch::currentEvent();
    if (touch.phase == Ion::Touch::Phase::Down) {
      cancelTouch();
      Responder * hit = m_modalViewController.view()->touchResponderAt(touch.x, touch.y);
      if (hit) {
        if (touch.contacts > 1 && !hit->acceptsMultitouch()) return true;
        m_touchResponder = hit;
        if (hit->handleTouch(touch)) return true;
        m_touchResponder = nullptr;
      }
      for (Responder * r = m_firstResponder; r; r = r->parentResponder()) {
        if (touch.contacts > 1 && !r->acceptsMultitouch()) continue;
        m_touchResponder = r;
        if (r->handleTouch(touch)) return true;
        m_touchResponder = nullptr;
      }
    } else if (m_touchResponder) {
      if (touch.contacts > 1 && !m_touchResponder->acceptsMultitouch()) {
        cancelTouch();
        return true;
      }
      Responder * target = m_touchResponder;
      if (touch.phase == Ion::Touch::Phase::Up || touch.phase == Ion::Touch::Phase::Cancel)
        m_touchResponder = nullptr; // Activation may destroy this App.
      target->handleTouch(touch);
    }
    return true; // Never reinterpret an unhandled touch as Enter/arrows.
  }
  if (event.isKeyboardEvent()) cancelTouch();
#endif''')
    edit("escher/src/app.cpp", "  if (m_modalViewController.isDisplayingModal()) {\n    m_modalViewController.dismissModalViewController();",
         "#if defined(PLATFORM_PRIME_G2)\n  cancelTouch();\n#endif\n  if (m_modalViewController.isDisplayingModal()) {\n    m_modalViewController.dismissModalViewController();")
    edit("escher/src/app.cpp", "void App::dismissModalViewController(bool willExitApp) {",
         "void App::dismissModalViewController(bool willExitApp) {\n#if defined(PLATFORM_PRIME_G2)\n  cancelTouch();\n#endif")
    edit("escher/src/app.cpp", "void App::willBecomeInactive() {",
         "void App::willBecomeInactive() {\n#if defined(PLATFORM_PRIME_G2)\n  cancelTouch();\n#endif")
    edit("escher/include/escher/selectable_table_view.h", "  bool handleEvent(Ion::Events::Event event) override;", '''  bool handleEvent(Ion::Events::Event event) override;
#if defined(PLATFORM_PRIME_G2)
  bool handleTouch(const Ion::Touch::Event & touch) override;
private:
  bool touchCellAt(int x, int y, int * column, int * row);
  bool m_touchTracking = false;
  int m_touchColumn = -1, m_touchRow = -1;
  KDPoint m_touchOffset = KDPoint(0, 0);
public:
#endif''')
    edit("escher/include/escher/selectable_table_view_delegate.h", "public:",
         "public:\n#if defined(PLATFORM_PRIME_G2)\n  virtual bool canSelectCellByTouch(SelectableTableView *, int, int) { return true; }\n#endif")
    edit("escher/src/selectable_table_view.cpp", "#include <assert.h>",
         "#include <assert.h>\n#if defined(PLATFORM_PRIME_G2)\n#include <algorithm>\n#include <apps/prime_touch_table_impl.h>\n#endif")
    edit("apps/home/controller.h", "  bool handleEvent(Ion::Events::Event event) override;",
         "  bool handleEvent(Ion::Events::Event event) override;\n#if defined(PLATFORM_PRIME_G2)\n  bool canSelectCellByTouch(SelectableTableView *, int column, int row) override {\n    return row * k_numberOfColumns + column < numberOfIcons();\n  }\n#endif")
    edit("apps/apps_container.cpp", "  if (event.isKeyboardEvent()) {\n    m_backlightDimmingTimer.reset();",
         "  if (event.isKeyboardEvent()\n#if defined(PLATFORM_PRIME_G2)\n      || event == Ion::Events::Touch\n#endif\n  ) {\n    m_backlightDimmingTimer.reset();")

    prepare_prime_functions_touch.prepare(source, port, edit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source.resolve())
