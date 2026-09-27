// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef POINCARE_DERIVATIVE_LAYOUT_H
#define POINCARE_DERIVATIVE_LAYOUT_H

#include <poincare/layout.h>
#include <poincare/layout_cursor.h>

namespace Poincare {

/* Keep the operator semantic: a displayed fraction of letters would parse as
 * division/multiplication. Symbolic layouts have one editable variable, reused
 * as diff's evaluation argument only when serializing. */
class DerivativeLayoutNode final : public LayoutNode {
public:
  DerivativeLayoutNode(bool evaluated) : m_evaluated(evaluated) {}
  Type type() const override { return Type::DerivativeLayout; }
  size_t size() const override { return sizeof(DerivativeLayoutNode); }
  int numberOfChildren() const override { return m_evaluated ? 3 : 2; }
  void moveCursorLeft(LayoutCursor *, bool *, bool) override;
  void moveCursorRight(LayoutCursor *, bool *, bool) override;
  void moveCursorUp(LayoutCursor *, bool *, bool = false, bool = false) override;
  void moveCursorDown(LayoutCursor *, bool *, bool = false, bool = false) override;
  void deleteBeforeCursor(LayoutCursor *) override;
  int serialize(char *, int, Preferences::PrintFloatMode, int) const override;
  CodePoint XNTCodePoint(int childIndex = -1) const override;
#if POINCARE_TREE_LOG
  void logNodeName(std::ostream & stream) const override { stream << "DerivativeLayout"; }
#endif
protected:
  KDSize computeSize() override;
  KDCoordinate computeBaseline() override;
  KDPoint positionOfChild(LayoutNode *) override;
private:
  LayoutNode * function() const { return childAtIndex(0); }
  LayoutNode * variable() const { return childAtIndex(1); }
  LayoutNode * point() const { return childAtIndex(2); }
  KDCoordinate operatorWidth();
  KDCoordinate operatorBaseline();
  KDCoordinate operatorHeight();
  KDCoordinate suffixX();
  KDCoordinate suffixBaseline();
  void render(KDContext *, KDPoint, KDColor, KDColor, Layout *, Layout *, KDColor) override;
  bool m_evaluated;
};

class DerivativeLayout final : public Layout {
public:
  static DerivativeLayout Builder(Layout function, Layout variable, Layout point = Layout());
};

}
#endif
