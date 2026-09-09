#!/usr/bin/env python3
"""Compile the prepared firmware's actual event table/decoder on the host."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    test = r'''
#include <ion/events.h>
#include <cassert>
#include <cstring>
namespace Ion { namespace Events {
const char *Event::text() const { return defaultText(); }
}}
using namespace Ion;
static void text(Keyboard::Key key, const char *expected) {
  Events::Event event(key, true, false, false);
  assert(event.isDefined() && event.hasText());
  assert(strcmp(event.text(), expected) == 0);
}
static void semantic(Keyboard::Key key, Events::Event expected) {
  Events::Event event(key, true, false, false);
  assert(event == expected && event.isDefined() && !event.hasText());
}
int main() {
  using K = Keyboard::Key;
  text(K::Ln, "ℯ^(\x11)"); text(K::Log, "10^(\x11)");
  text(K::Sine, "asin(\x11)"); text(K::Cosine, "acos(\x11)");
  text(K::Tangent, "atan(\x11)"); text(K::Square, "√(\x11)");
  text(K::Power, "root(\x11,\x11)"); text(K::LeftParenthesis, "!");
  text(K::PrimeAlphaM, "abs(\x11)"); text(K::Division, "^(-1)");
  text(K::Multiplication, "arg(\x11)"); text(K::Two, "𝐢");
  text(K::Three, "π"); text(K::Plus, "ans"); text(K::Dot, "=");
  text(K::EE, "→"); text(K::PrimeAlphaSpace, "_");
  text(K::Eight, "{\x11}"); text(K::Five, "[");
  text(K::Nine, "[[\x11,\x11]]");
  semantic(K::PrimeAlphaC, Events::PrimeUnits);
  semantic(K::Six, Events::PrimeCalculus);
  semantic(K::Seven, Events::PrimeList); semantic(K::Four, Events::PrimeMatrix);
  semantic(K::PrimeView, Events::Copy); semantic(K::PrimeMenu, Events::Paste);
  semantic(K::Back, Events::Clear); semantic(K::Backspace, Events::PrimeDelete);
  semantic(K::OK, Events::ShiftOK);
  auto square = Events::Event(K::Square, false, false, false);
  assert(square == Events::Square && strcmp(square.text(), "^2") == 0);
  // No printed Shift legend on a digit or navigation key may accidentally
  // fall through to the NumWorks base-key meaning.
  assert(Events::Event(K::PrimeAlphaC, false, false, false) == Events::PrimeMathTemplates);
  assert(strcmp(Events::Event(K::PrimeAlphaSpace, false, true, false).text(), " ") == 0);
  assert(strcmp(Events::Event(K::Two, false, true, false).text(), "z") == 0);
  assert(strcmp(Events::Event(K::Two, true, true, false).text(), "Z") == 0);
}
'''
    with tempfile.TemporaryDirectory(prefix="lf-shift-") as directory:
        binary = Path(directory) / "events"
        subprocess.run(["c++", "-std=c++11", "-DPLATFORM_PRIME_G2=1",
                        "-I", str(root / "ion/include"),
                        "-I", str(root / "ion/include/ion/keyboard/layout_B2"),
                        "-I", str(root / "ion/include/ion/keyboard"),
                        "-I", str(root / "ion/src/shared"),
                        str(root / "ion/src/shared/events.cpp"),
                        str(root / "ion/src/shared/keyboard/layout_B2/layout_events.cpp"),
                        "-x", "c++", "-", "-o", str(binary)],
                       input=test, text=True, check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS: 20 Shift text mappings, 9 semantic shortcuts, plain math/x² and Alpha preservation")


if __name__ == "__main__":
    main()
