// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Cursor/tree operations follow Upsilon's integral and nth-root layouts.
#include <poincare/derivative_layout.h>
#include <poincare/code_point_layout.h>
#include <poincare/left_parenthesis_layout.h>
#include <poincare/right_parenthesis_layout.h>
#include <poincare/serialization_helper.h>
#include <algorithm>
#include <string.h>

namespace Poincare {

static constexpr const KDFont * k_font = KDFont::LargeFont;
static constexpr KDCoordinate k_gap = 2;

void DerivativeLayoutNode::moveCursorLeft(LayoutCursor * cursor, bool * recompute, bool selection) {
  if (cursor->layoutNode() == this) {
    if (cursor->position() == LayoutCursor::Position::Right) {
      cursor->setLayoutNode(m_evaluated ? point() : function());
    } else if (parent()) {
      parent()->moveCursorLeft(cursor, recompute, selection);
    }
    return;
  }
  assert(cursor->position() == LayoutCursor::Position::Left);
  LayoutNode * target = cursor->layoutNode() == function() ? variable() :
    cursor->layoutNode() == variable() ? this : function();
  cursor->setLayoutNode(target);
  cursor->setPosition(target == this ? LayoutCursor::Position::Left : LayoutCursor::Position::Right);
}

void DerivativeLayoutNode::moveCursorRight(LayoutCursor * cursor, bool * recompute, bool selection) {
  if (cursor->layoutNode() == this) {
    if (cursor->position() == LayoutCursor::Position::Left) {
      cursor->setLayoutNode(variable());
    } else if (parent()) {
      parent()->moveCursorRight(cursor, recompute, selection);
    }
    return;
  }
  assert(cursor->position() == LayoutCursor::Position::Right);
  LayoutNode * target = cursor->layoutNode() == variable() ? function() :
    cursor->layoutNode() == function() && m_evaluated ? point() : this;
  cursor->setLayoutNode(target);
  cursor->setPosition(target == this ? LayoutCursor::Position::Right : LayoutCursor::Position::Left);
}

void DerivativeLayoutNode::moveCursorUp(LayoutCursor * cursor, bool * recompute, bool visited, bool selection) {
  if (cursor->layoutNode()->hasAncestor(variable(), true) ||
      (m_evaluated && cursor->layoutNode()->hasAncestor(point(), true))) {
    function()->moveCursorUpInDescendants(cursor, recompute, selection);
    return;
  }
  LayoutNode::moveCursorUp(cursor, recompute, visited, selection);
}

void DerivativeLayoutNode::moveCursorDown(LayoutCursor * cursor, bool * recompute, bool visited, bool selection) {
  if (cursor->layoutNode()->hasAncestor(function(), true)) {
    variable()->moveCursorDownInDescendants(cursor, recompute, selection);
    return;
  }
  LayoutNode::moveCursorDown(cursor, recompute, visited, selection);
}

void DerivativeLayoutNode::deleteBeforeCursor(LayoutCursor * cursor) {
  if (cursor->isEquivalentTo(LayoutCursor(function(), LayoutCursor::Position::Left))) {
    Layout self(this), child(function());
    self.replaceChildWithGhostInPlace(child);
    cursor->setLayout(self.childAtIndex(0));
    cursor->setPosition(LayoutCursor::Position::Left);
    self.replaceWith(child, cursor);
    return;
  }
  LayoutNode::deleteBeforeCursor(cursor);
}

int DerivativeLayoutNode::serialize(char * buffer, int size, Preferences::PrintFloatMode mode, int digits) const {
  if (size == 0) return -1;
  buffer[size - 1] = 0;
  int length = strlcpy(buffer, "diff", size);
  if (length >= size - 1) return size - 1;
  auto append = [&](CodePoint c) {
    if (length < size - 1) length += SerializationHelper::CodePoint(buffer + length, size - length, c);
  };
  append(UCodePointLeftSystemParenthesis);
  for (int i = 0; i < 3; i++) {
    if (i) append(',');
    append(UCodePointLeftSystemParenthesis);
    if (length < size - 1) {
      LayoutNode * child = childAtIndex(i == 2 && !m_evaluated ? 1 : i);
      length += child->serialize(buffer + length, size - length, mode, digits);
    }
    append(UCodePointRightSystemParenthesis);
  }
  append(UCodePointRightSystemParenthesis);
  return length;
}

CodePoint DerivativeLayoutNode::XNTCodePoint(int childIndex) const {
  LayoutNode * v = variable();
  if (v->type() == Type::HorizontalLayout && v->numberOfChildren() == 1) v = v->childAtIndex(0);
  return v->type() == Type::CodePointLayout ? static_cast<CodePointLayoutNode *>(v)->codePoint() : CodePoint('x');
}

KDCoordinate DerivativeLayoutNode::operatorWidth() {
  return k_font->glyphSize().width() + variable()->layoutSize().width() + 2*k_gap;
}

KDCoordinate DerivativeLayoutNode::operatorBaseline() {
  return k_font->glyphSize().height() + k_gap + 1;
}

KDCoordinate DerivativeLayoutNode::operatorHeight() {
  KDCoordinate fontHeight = k_font->glyphSize().height();
  return operatorBaseline() + k_gap + std::max<KDCoordinate>(fontHeight/2, variable()->baseline()) +
    std::max<KDCoordinate>(fontHeight-fontHeight/2, variable()->layoutSize().height()-variable()->baseline());
}

KDCoordinate DerivativeLayoutNode::computeBaseline() {
  return std::max<KDCoordinate>(operatorBaseline(), function()->baseline() + k_gap);
}

KDCoordinate DerivativeLayoutNode::suffixX() {
  return operatorWidth() + k_gap + 2*ParenthesisLayoutNode::ParenthesisWidth() + function()->layoutSize().width();
}

KDCoordinate DerivativeLayoutNode::suffixBaseline() {
  return baseline() + std::max<KDCoordinate>(k_font->glyphSize().height()/2,
    std::max(variable()->baseline(), point()->baseline()));
}

KDSize DerivativeLayoutNode::computeSize() {
  KDCoordinate height = baseline() + std::max<KDCoordinate>(operatorHeight()-operatorBaseline(),
    function()->layoutSize().height()-function()->baseline()+k_gap);
  KDCoordinate width = suffixX();
  if (m_evaluated) {
    width += 2*k_gap + 1 + variable()->layoutSize().width() + k_font->glyphSize().width() + point()->layoutSize().width();
    height = std::max<KDCoordinate>(height, suffixBaseline() + std::max<KDCoordinate>(k_font->glyphSize().height()/2,
      std::max(variable()->layoutSize().height()-variable()->baseline(), point()->layoutSize().height()-point()->baseline())));
  }
  return KDSize(width, height);
}

KDPoint DerivativeLayoutNode::positionOfChild(LayoutNode * child) {
  if (child == function()) return KDPoint(operatorWidth()+k_gap+ParenthesisLayoutNode::ParenthesisWidth(), baseline()-child->baseline());
  if (child == variable()) return KDPoint(k_gap+k_font->glyphSize().width(), baseline()+k_gap+
    std::max<KDCoordinate>(k_font->glyphSize().height()/2, child->baseline())-child->baseline());
  assert(m_evaluated && child == point());
  return KDPoint(suffixX()+2*k_gap+1+variable()->layoutSize().width()+k_font->glyphSize().width(), suffixBaseline()-child->baseline());
}

void DerivativeLayoutNode::render(KDContext * ctx, KDPoint p, KDColor fg, KDColor bg, Layout * start, Layout * end, KDColor selected) {
  KDCoordinate fontWidth = k_font->glyphSize().width(), fontHeight = k_font->glyphSize().height();
  ctx->drawString("d", p.translatedBy(KDPoint((operatorWidth()-fontWidth)/2, baseline()-operatorBaseline())), k_font, fg, bg);
  ctx->fillRect(KDRect(p.x(), p.y()+baseline()-1, operatorWidth(), 1), fg);
  ctx->drawString("d", p.translatedBy(KDPoint(k_gap, baseline()+k_gap+
    std::max<KDCoordinate>(fontHeight/2, variable()->baseline())-fontHeight/2)), k_font, fg, bg);
  KDPoint left = p.translatedBy(KDPoint(operatorWidth()+k_gap, baseline()-function()->baseline()-k_gap));
  LeftParenthesisLayoutNode::RenderWithChildHeight(function()->layoutSize().height(), ctx, left, fg, bg);
  RightParenthesisLayoutNode::RenderWithChildHeight(function()->layoutSize().height(), ctx,
    left.translatedBy(KDPoint(ParenthesisLayoutNode::ParenthesisWidth()+function()->layoutSize().width(), 0)), fg, bg);
  if (m_evaluated) {
    ctx->fillRect(KDRect(p.x()+suffixX()+k_gap, left.y(), 1, function()->layoutSize().height()+2*k_gap), fg);
    KDPoint v = p.translatedBy(KDPoint(suffixX()+2*k_gap+1, suffixBaseline()-variable()->baseline()));
    // Repeat the variable in the annotation; its sole editable owner remains
    // the denominator, so changing it cannot desynchronize the two labels.
    variable()->draw(ctx, KDPoint(v.x()-variable()->absoluteOrigin().x(), v.y()-variable()->absoluteOrigin().y()), fg, bg);
    ctx->drawString("=", p.translatedBy(KDPoint(suffixX()+2*k_gap+1+variable()->layoutSize().width(), suffixBaseline()-fontHeight/2)), k_font, fg, bg);
  }
}

DerivativeLayout DerivativeLayout::Builder(Layout function, Layout variable, Layout point) {
  bool evaluated = !point.isUninitialized();
  void * buffer = TreePool::sharedPool()->alloc(sizeof(DerivativeLayoutNode));
  auto node = new (buffer) DerivativeLayoutNode(evaluated);
  TreeHandle h = TreeHandle::BuildWithGhostChildren(node);
  h.replaceChildAtIndexInPlace(0, function);
  h.replaceChildAtIndexInPlace(1, variable);
  if (evaluated) h.replaceChildAtIndexInPlace(2, point);
  return static_cast<DerivativeLayout &>(h);
}

}
