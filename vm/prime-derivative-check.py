"""Derivative editing/history through the normal Goodix and KPP event paths."""
import time


def check(raw, press, touch, app, capture):
    def text(value):
        assert raw("TEXT " + value.encode().hex()) == "OK"
        # Synchronize to guest time, as with the KPP/Goodix helpers. Wall time
        # alone can let the following key overtake text dispatch during builds.
        start = int(raw("TIME GET").split()[1])
        deadline = time.monotonic() + 10
        while int(raw("TIME GET").split()[1]) - start < 300:
            assert time.monotonic() < deadline, "guest timer stopped after text input"
            time.sleep(.01)

    def result(expected, expression=None):
        actual = raw("RESULT EXACT")
        assert actual == "TEXT " + expected, (raw("RESULT INPUT"), actual)
        if expression:
            assert raw("RESULT INPUT") == "TEXT " + expression, raw("RESULT INPUT")

    def template():
        press("units")
        capture("derivative-palette")
        touch("TAP 60 123")

    press("home")
    app(1)
    template()
    capture("derivative-empty")
    # All polynomial entry uses physical keypad events, starting in the box.
    for key in ("xnt", "square", "plus", "three", "xnt"):
        press(key)
    capture("derivative-polynomial-input")
    press("ok")
    result("2×x+3", "diff(x^2+3×x,x,x)")
    capture("derivative-polynomial-history")

    # Tap the submitted input, then submit the reconstructed layout again.
    touch("TAP 55 143")
    capture("derivative-recalled")
    press("ok")
    result("2×x+3", "diff(x^2+3×x,x,x)")

    # Change the template's variable. XNT must follow it and serialization must
    # use the changed variable for both symbolic arguments.
    template()
    press("left")
    capture("derivative-variable-selected")
    press("backspace")
    capture("derivative-variable-empty")
    press("alpha")
    press("divide") # Prime's alpha legend is t.
    capture("derivative-variable-replaced")
    press("right")
    capture("derivative-variable-to-function")
    press("xnt")
    press("square")
    press("right")
    capture("derivative-variable-t")
    press("ok")
    result("2×t", "diff(t^2,t,t)")

    # Empty-template backspace unwraps the function and leaves a usable editor.
    template()
    press("backspace")
    press("seven")
    press("ok")
    result("7", "7")

    for expression, expected, name in (
        ("diff(x^2+3*x,x,2)", "7", "evaluated"),
        ("diff(t^3,t,t)", "3×t^2", "other-variable"),
        ("diff(diff(x^3,x,x),x,x)", "6×x", "nested"),
        ("2*diff(x^2,x,x)+1", "4×x+1", "composition"),
        ("diff(1/(x+1),x,1)", "-1/4", "fraction"),
        ("int(x,x,0,1)", "int(x,x,0,1)", "integral-regression"),
    ):
        text(expression)
        capture("derivative-" + name + "-input")
        press("ok")
        result(expected)
        if name == "integral-regression":
            assert raw("RESULT APPROX") == "TEXT 0.5", raw("RESULT APPROX")
        capture("derivative-" + name + "-history")

    assert raw("DISPLAY GUARDS") == "OK"
    assert raw("DISPLAY TIMEOUTS") == "VALUE 0"
    print("PASS: derivative template, keypad entry, variable editing, symbolic/numeric results, history recall, deletion, nesting and integral regression", flush=True)
