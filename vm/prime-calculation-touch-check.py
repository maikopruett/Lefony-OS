"""Calculation history gestures through Goodix and the real calculator UI."""
import time


def check(raw, press, touch, app, capture):
    def text(value):
        assert raw("TEXT " + value.encode().hex()) == "OK"
        time.sleep(.2)

    def oldest():
        for _ in range(6):
            touch("SWIPE 160 65 160 195")

    def result(value):
        actual = raw("RESULT EXACT")
        assert actual == f"TEXT {value}", (raw("RESULT INPUT"), actual)

    press("home")
    app(1)
    touch("SWIPE 160 65 160 195") # Empty history is safe to drag.
    touch("TAP 290 38")
    for number in range(100, 115):
        text(f"{number}+1")
        press("ok")
        assert raw("RESULT EXACT") == f"TEXT {number + 1}"
        if number == 100:
            # One bottom-aligned row uses a top margin, unlike full history.
            touch("TAP 290 181")
            press("ok")
            result(101)
            assert raw("RESULT INPUT") == "TEXT 101"
    capture("history-latest")
    oldest()
    capture("history-oldest")
    assert raw("RESULT EXACT") == "TEXT 115" # Scrolling never submits.
    touch("TAP 270 43")
    capture("history-recalled")
    press("plus")
    press("two")
    press("ok")
    capture("history-edited")
    result(103)
    assert raw("RESULT INPUT") == "TEXT 101+2"
    # The left side recalls the submitted expression, not just its answer.
    oldest()
    touch("TAP 25 38")
    press("plus")
    press("three")
    press("ok")
    result(104)
    assert raw("RESULT INPUT") == "TEXT 100+1+3"
    # Browsing must preserve a partially typed expression; recall inserts at
    # its cursor using the same path as keyboard history selection.
    text("7+")
    oldest()
    touch("TAP 290 38")
    press("ok")
    result(108)
    assert raw("RESULT INPUT") == "TEXT 7+101"
    # Works when keyboard navigation already owns history focus, too.
    press("up")
    oldest()
    touch("TAP 290 38")
    press("ok")
    result(101)
    # Scrolling back down and clamping at either end never recalls a row.
    oldest()
    for _ in range(8):
        touch("SWIPE 160 195 160 65")
    press("nine")
    press("ok")
    result(9)
    # Keyboard cancellation of a pending tap prevents delayed insertion.
    oldest()
    assert raw("HOLD 290 38 700") == "OK"
    time.sleep(.12)
    press("left") # Cancel capture without Esc leaving the empty editor.
    time.sleep(.8)
    press("eight")
    press("ok")
    result(8)
    text("√(2)")
    press("ok")
    capture("history-exact-approximate")
    text("7+")
    touch("TAP 290 181")
    press("ok")
    assert raw("RESULT INPUT").startswith("TEXT 7+1.414"), raw("RESULT INPUT")
    text("√(2)")
    press("ok")
    text("9+")
    touch("TAP 190 181")
    press("square")
    press("ok")
    result(11)
    capture("history-exact-recalled-and-squared")
    assert raw("DISPLAY GUARDS") == "OK"
    assert raw("DISPLAY TIMEOUTS") == "VALUE 0"
    print("PASS: older output/input recall, exact/approximate selection, editing, draft preservation, keyboard focus, bounded scrolling and cancellation", flush=True)
