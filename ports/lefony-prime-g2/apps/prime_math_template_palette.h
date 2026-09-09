#pragma once

#include "math_toolbox.h"

/* A Toolbox-compatible input accessory, with its own view and responder.
 * Do not enter the inherited nested-menu lifecycle: there is no list or
 * scrolling-text timer in this palette. The original input remains sender(). */
class PrimeMathTemplatePalette : public MathToolbox {
public:
  View * view() override { return &m_palette; }
  void initView() override {}
  void viewWillAppear() override { m_palette.select(0); m_touchIndex = -1; }
  void viewDidDisappear() override {}
  void didBecomeFirstResponder() override {}

  bool handleTouch(const Ion::Touch::Event & touch) override {
    using Ion::Touch::Phase;
    KDPoint origin = m_palette.touchOrigin();
    int x = touch.x - origin.x() - 1, y = touch.y - origin.y() - 1;
    int index = x >= 0 && x < 264 && y >= 0 && y < 144 ? (y / 36) * 4 + x / 66 : -1;
    if (touch.phase == Phase::Down) {
      m_touchIndex = index;
      if (index < 0) return false;
      m_palette.select(index);
      return true;
    }
    if (touch.phase == Phase::Cancel || touch.dragging) m_touchIndex = -1;
    if (touch.phase == Phase::Up) {
      bool activate = index >= 0 && index == m_touchIndex && !touch.dragging;
      m_touchIndex = -1;
      if (activate) return handleEvent(Ion::Events::OK);
    }
    return true;
  }

  bool handleEvent(Ion::Events::Event event) override {
    using namespace Ion::Events;
    int selected = m_palette.selected();
    if (event == Back || event == Ion::Events::Toolbox) {
      Container::activeApp()->dismissModalViewController();
      return true;
    }
    if (event == OK || event == EXE) {
      if (sender() != nullptr) sender()->handleEventWithText(entry(selected).text);
      Container::activeApp()->dismissModalViewController();
      return true;
    }
    if (event == Left && selected % 4 != 0) selected--;
    if (event == Right && selected % 4 != 3) selected++;
    if (event == Up && selected >= 4) selected -= 4;
    if (event == Down && selected < 12) selected += 4;
    if (event == Left || event == Right || event == Up || event == Down) {
      m_palette.select(selected);
      return true;
    }
    // Keep typing from reaching the covered editor; global Home/Apps still
    // pass through AppsContainer's normal navigation handling.
    return event.isKeyboardEvent();
  }

private:
  struct Entry { const char * label; const char * text; };
  static const Entry & entry(int index) {
    static const Entry entries[] = {
      {"Fraction", "/"}, {"Power", "^"},
      {"Square", "^2"}, {"Square root", "√(\x11)"},
      {"Nth root", "root(\x11,\x11)"}, {"Absolute value", "abs(\x11)"},
      {"Logarithm with base", "log(\x11,\x11)"}, {"Exponential", "ℯ^(\x11)"},
      {"Derivative", "diff(\x11,x,\x11)"}, {"Integral", "int(\x11,x,\x11,\x11)"},
      {"Sum", "sum(\x11,x,\x11,\x11)"}, {"Product", "product(\x11,x,\x11,\x11)"},
      {"Matrix", "["}, {"Row vector", "[[\x11,\x11]]"},
      {"Parentheses", "(\x11)"}, {"Reciprocal", "^(-1)"},
    };
    return entries[index];
  }

  class PaletteView : public View {
  public:
    int selected() const { return m_selected; }
    void select(int selected) {
      m_selected = selected;
      markRectAsDirty(bounds());
    }
    KDSize minimalSizeForOptimalDisplay() const override { return KDSize(266, 146); }
    void drawRect(KDContext * ctx, KDRect rect) const override {
      const KDColor green = KDColor::RGB24(0x416543);
      const KDColor border = KDColor::RGB24(0xCBD6CB);
      ctx->fillRect(bounds(), KDColorWhite);
      ctx->fillRect(bounds(), border);
      for (int i = 0; i < 16; i++) {
        int x = 1 + (i % 4) * 66;
        int y = 1 + (i / 4) * 36;
        KDColor bg = i == m_selected ? green : KDColorWhite;
        KDColor fg = i == m_selected ? KDColorWhite : green;
        ctx->fillRect(KDRect(x, y, 65, 35), bg);
        ctx->fillRect(KDRect(x, y + 35, 66, 1), border);
        ctx->fillRect(KDRect(x + 65, y, 1, 36), border);
        drawIcon(ctx, i, x + 32, y + 17, fg, bg);
      }
    }
  private:
    static void box(KDContext * ctx, int x, int y, KDColor color, int size = 7) {
      ctx->fillRect(KDRect(x, y, size, 1), color);
      ctx->fillRect(KDRect(x, y + size - 1, size, 1), color);
      ctx->fillRect(KDRect(x, y, 1, size), color);
      ctx->fillRect(KDRect(x + size - 1, y, 1, size), color);
    }
    static void drawIcon(KDContext * ctx, int i, int x, int y, KDColor fg, KDColor bg) {
      auto text = [&](const char * s, int dx, int dy) {
        ctx->drawString(s, KDPoint(x + dx, y + dy), KDFont::LargeFont, fg, bg);
      };
      switch (i) {
        case 0:
          box(ctx, x - 3, y - 12, fg);
          ctx->fillRect(KDRect(x - 8, y - 1, 17, 1), fg);
          box(ctx, x - 3, y + 4, fg); break;
        case 1: case 2: case 7: case 15:
          if (i == 7) text("e", -12, -5); else box(ctx, x - 12, y - 1, fg, 10);
          if (i == 1) box(ctx, x + 1, y - 12, fg);
          else ctx->drawString(i == 15 ? "-1" : i == 2 ? "2" : "", KDPoint(x + 1, y - 13), KDFont::SmallFont, fg, bg);
          if (i == 7) box(ctx, x + 1, y - 12, fg);
          break;
        case 3: case 4:
          text("√", -12, -9); box(ctx, x + 3, y - 2, fg, 9);
          if (i == 4) box(ctx, x - 17, y - 11, fg, 5);
          break;
        case 5: case 14:
          text(i == 5 ? "|" : "(", -17, -9);
          box(ctx, x - 4, y - 3, fg, 9);
          text(i == 5 ? "|" : ")", 9, -9); break;
        case 6:
          text("log", -24, -10); box(ctx, x + 12, y - 7, fg);
          box(ctx, x + 8, y + 6, fg, 5); break;
        case 8:
          ctx->drawString("d", KDPoint(x - 14, y - 15), KDFont::SmallFont, fg, bg);
          ctx->fillRect(KDRect(x - 18, y - 1, 19, 1), fg);
          ctx->drawString("dx", KDPoint(x - 16, y + 2), KDFont::SmallFont, fg, bg);
          box(ctx, x + 8, y - 3, fg, 9); break;
        case 9: case 10: case 11:
          text(i == 9 ? "∫" : i == 10 ? "Σ" : "Π", -13, -9);
          box(ctx, x - 9, y - 16, fg, 4); box(ctx, x - 9, y + 11, fg, 4);
          box(ctx, x + 9, y - 3, fg, 8); break;
        case 12: case 13:
          text("[", -23, -9); text("]", 17, -9);
          for (int r = 0; r < (i == 12 ? 2 : 1); r++) {
            int by = y + (i == 12 ? -10 + 12 * r : -3);
            box(ctx, x - 10, by, fg); box(ctx, x + 3, by, fg);
          }
          break;
      }
    }
    int m_selected = 0;
  };
  PaletteView m_palette;
  int m_touchIndex = -1;
};
