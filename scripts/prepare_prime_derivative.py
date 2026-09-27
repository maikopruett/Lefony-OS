"""Install the semantic derivative layout into the pinned Upsilon source.

Host code: GPL-3.0-or-later. Embedded Upsilon adaptations: CC-BY-NC-SA-4.0.
"""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def prepare(source):
    def edit(name, old, new):
        path = source / name
        text = path.read_text()
        if new in text:
            return
        if text.count(old) != 1:
            raise ValueError(f"Unexpected derivative integration context: {name}")
        path.write_text(text.replace(old, new))

    edit("poincare/include/poincare/layout_node.h", "    VerticalOffsetLayout\n",
         "    VerticalOffsetLayout,\n    DerivativeLayout\n")
    edit("poincare/include/poincare/layout_cursor.h", "  friend class IntegralLayoutNode;",
         "  friend class IntegralLayoutNode;\n  friend class DerivativeLayoutNode;")
    edit("poincare/src/layout_cursor.cpp",
         "  /* Change the visibility of the neighbouring empty layout: it might be either",
         """  // Keep the derivative's editable placeholder visible while it has focus.
  Layout emptyParent = adjacentEmptyLayout.parent();
  if (!emptyParent.isUninitialized() && emptyParent.type() == LayoutNode::Type::HorizontalLayout) {
    emptyParent = emptyParent.parent();
  }
  if (!emptyParent.isUninitialized() && emptyParent.type() == LayoutNode::Type::DerivativeLayout) {
    show = true;
  }
  /* Change the visibility of the neighbouring empty layout: it might be either""")
    edit("poincare/Makefile", "  integral_layout.cpp \\\n",
         "  integral_layout.cpp \\\n  derivative_layout.cpp \\\n")
    edit("poincare/src/derivative.cpp", "#include <poincare/derivative.h>",
         "#include <poincare/derivative.h>\n#include <poincare/derivative_layout.h>")
    edit("poincare/src/derivative.cpp",
         "  return LayoutHelper::Prefix(this, floatDisplayMode, numberOfSignificantDigits, Derivative::s_functionHelper.name());",
         """  Expression expression(this);
  Layout function = expression.childAtIndex(0).createLayout(floatDisplayMode, numberOfSignificantDigits);
  Layout variable = expression.childAtIndex(1).createLayout(floatDisplayMode, numberOfSignificantDigits);
  if (expression.childAtIndex(1).isIdenticalTo(expression.childAtIndex(2))) {
    return DerivativeLayout::Builder(function, variable);
  }
  return DerivativeLayout::Builder(function, variable,
    expression.childAtIndex(2).createLayout(floatDisplayMode, numberOfSignificantDigits));""")
    overlay = ROOT / "ports/lefony-prime-g2/poincare"
    for name in ("include/poincare/derivative_layout.h", "src/derivative_layout.cpp"):
        shutil.copy2(overlay / name, source / "poincare" / name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source.resolve())
