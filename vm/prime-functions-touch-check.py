"""Functions controls and pan/pinch through modeled Goodix contacts."""
import math
import struct
import time


def check(raw, press, touch, app, capture):
    def tab(expected):
        assert raw("GRAPH TAB") == f"VALUE {expected}"

    def bounds():
        return [struct.unpack("<f", bytes.fromhex(raw(f"GRAPH RANGE {i}").removeprefix("DATA ")))[0]
                for i in range(4)]

    def same(a, b):
        assert all(math.isclose(x, y, rel_tol=2e-5, abs_tol=2e-5) for x, y in zip(a, b)), (a, b)

    def frame(*contacts):
        fields = [str(len(contacts))] + [str(v) for c in contacts for v in c]
        assert raw("TOUCH FRAME " + " ".join(fields)) == "OK"
        time.sleep(.15)

    def text(value):
        assert raw("TEXT " + value.encode().hex()) == "OK"
        time.sleep(.2)

    press("apps")
    touch("TAP 160 75")
    app(2)
    capture("functions-empty")
    # A visible add row edits the function, even with no prior keyboard selection.
    touch("TAP 160 80")
    text("x^2")
    press("ok")
    capture("functions-defined")
    touch("TAP 80 220") # Plot graph footer
    tab(1)
    initial = bounds()
    capture("functions-graph")
    touch("SWIPE 110 110 142 134")
    panned = bounds()
    same([panned[1] - panned[0], panned[3] - panned[2]],
         [initial[1] - initial[0], initial[3] - initial[2]])
    same([panned[0] - initial[0], panned[2] - initial[2]],
         [-32 * (initial[1] - initial[0]) / 319, 24 * (initial[3] - initial[2]) / 173])
    capture("functions-panned")
    # Second finger joins, then records reorder. Neither changes the range.
    frame((5, 100, 130))
    frame((5, 100, 130), (2, 180, 130))
    same(bounds(), panned)
    frame((2, 180, 130), (5, 100, 130))
    same(bounds(), panned)
    # Spread by 2x and translate centroid by (+10,+10). Verify anchoring.
    anchor = [panned[0] + 140 * (panned[1] - panned[0]) / 319,
              panned[3] - (130 - 66) * (panned[3] - panned[2]) / 173]
    frame((5, 70, 140), (2, 230, 140))
    zoomed = bounds()
    same([zoomed[1] - zoomed[0], zoomed[3] - zoomed[2]],
         [(panned[1] - panned[0]) / 2, (panned[3] - panned[2]) / 2])
    same(anchor, [zoomed[0] + 150 * (zoomed[1] - zoomed[0]) / 319,
                  zoomed[3] - (140 - 66) * (zoomed[3] - zoomed[2]) / 173])
    capture("functions-pinched-in")
    frame((2, 190, 140), (5, 110, 140))
    zoomed_out = bounds()
    same([zoomed_out[1] - zoomed_out[0], zoomed_out[3] - zoomed_out[2]],
         [panned[1] - panned[0], panned[3] - panned[2]])
    # The first sorted contact lifts. The survivor rebases before panning.
    frame((5, 110, 140))
    same(bounds(), zoomed_out)
    frame((5, 120, 140))
    continued = bounds()
    same([continued[0] - zoomed_out[0]], [-10 * (zoomed_out[1] - zoomed_out[0]) / 319])
    frame()
    same(bounds(), continued)
    # Direct two-finger down, third-finger cancellation, and release quarantine.
    frame((0, 100, 120), (1, 180, 120))
    same(bounds(), continued)
    frame((0, 100, 120), (1, 180, 120), (2, 150, 150))
    frame((0, 140, 120))
    same(bounds(), continued)
    frame()
    # A pinch crossing onto controls cancels; no accidental tab/button click.
    frame((0, 110, 120))
    frame((0, 110, 120), (1, 160, 30))
    frame((0, 140, 120))
    frame()
    tab(1)
    same(bounds(), continued)
    # Toolbar buttons use their own target, independent of graph keyboard focus.
    touch("TAP 20 54") # Auto restores initial bounds
    same(bounds(), initial)
    touch("TAP 95 54") # Equal axes
    normalized = bounds()
    assert all(math.isfinite(v) for v in normalized)
    capture("functions-normalized")
    touch("TAP 235 54") # Axes menu
    capture("functions-axes")
    touch("TAP 110 105") # An editable range row
    capture("functions-axis-cell")
    press("back")
    press("back")
    touch("TAP 175 30") # Graph tab after leaving a menu
    tab(1)
    touch("TAP 176 54") # Navigate
    capture("functions-navigate")
    before = bounds()
    touch("SWIPE 100 105 120 115")
    assert bounds() != before
    press("back")
    touch("TAP 160 230") # Bottom banner opens curve options
    capture("functions-curve-options")
    press("back")
    touch("TAP 270 30")
    tab(2)
    capture("functions-values")
    touch("TAP 110 54") # Set interval
    capture("functions-interval")
    touch("TAP 160 207") # Confirm button in the interval table
    touch("TAP 50 30")
    tab(0)
    touch("TAP 225 220") # Display values footer
    tab(2)
    touch("TAP 50 30")
    tab(0)
    touch("TAP 30 80") # Function options cell
    capture("functions-options")
    press("back")
    # A two-finger touch on a tab may never activate it on release.
    frame((0, 170, 30))
    frame((0, 170, 30), (1, 200, 30))
    frame((0, 170, 30))
    frame()
    tab(0)
    # Keyboard input cancels an in-flight graph gesture.
    touch("TAP 170 30")
    frame((0, 100, 120))
    press("back")
    before = bounds()
    frame((0, 140, 150))
    frame()
    same(bounds(), before)
    # Touch returns keyboard focus from tabs to the graph.
    touch("TAP 140 120")
    before = bounds()
    press("plus")
    after = bounds()
    assert after[1] - after[0] < before[1] - before[0]
    assert raw("DISPLAY GUARDS") == "OK"
    assert raw("DISPLAY TIMEOUTS") == "VALUE 0"
    print("PASS: Functions tabs, add/edit/options, footer/toolbar, values/interval, pan, anchored pinch, transitions, cancellation", flush=True)
