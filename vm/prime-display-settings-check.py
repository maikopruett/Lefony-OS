"""Display settings checks using the coordinate-touch test's live guest helpers."""
import time


def check(raw, press, touch, app, capture, q):
    def wait_guest_ms(milliseconds):
        # The VM target uses virtual GPT time, which can run slower than host
        # wall time under TCG. Qualify the actual firmware deadline.
        start = int(raw('TIME GET').split()[1])
        deadline = time.monotonic() + 45
        while int(raw('TIME GET').split()[1]) - start < milliseconds:
            assert time.monotonic() < deadline, 'guest timer stopped'
            time.sleep(.25)
    press('apps')
    for _ in range(4): press('down')
    for _ in range(2): press('right')
    press('ok')
    app(11)
    capture('settings-root')
    # The root's second row is Brightness Settings.
    for _ in range(15): press('up')
    press('down')
    press('ok')
    capture('brightness-settings')
    for _ in range(6): press('left')
    chosen = int(raw('PREF GET BRIGHTNESS').split()[1])
    assert chosen < 255, chosen
    time.sleep(1.5) # Several USB page timer firings must not undo the setting.
    assert raw('BRIGHTNESS GET') == f'VALUE {chosen}'
    pwm = q.readl(0x020f800c)
    assert pwm == 60000 * chosen // 255, (chosen, pwm)
    capture('brightness-reduced')
    print(f'PASS: settings brightness value {chosen} persists on USB; PWM sample {pwm}', flush=True)
    # Checking USB keep-awake must not depend on continually sending keys.
    assert raw('PREF SET BRIGHTNESS 170') == 'OK'
    time.sleep(.7)
    assert raw('BRIGHTNESS GET') == 'VALUE 170'
    assert q.readl(0x020f800c) == 40000
    for _ in range(4): press('down')
    press('ok')
    capture('refresh-default')
    assert raw('DISPLAY REFRESH') == 'VALUE 58892'
    touch('TAP 150 146') # Directly select the lower button, no prior highlight.
    assert raw('DISPLAY REFRESH') == 'VALUE 55212'
    assert raw('DISPLAY TRIAL') == 'VALUE 1'
    time.sleep(.25) # The mode-switch handler temporarily hides the backlight.
    pixels = capture('refresh-trial').split(b'\n', 3)[-1]
    assert len(set(pixels)) > 2, 'trial left the modeled panel blank'
    assert (q.readl(0x020c4038) >> 12) & 7 == 7
    assert (q.readl(0x020c4018) >> 23) & 7 == 3
    assert q.readl(0x021c8080) == 264 # unchanged porches/totals
    assert q.readl(0x020f800c) == 40000 # no shared PWM clock/duty change
    # Do not confirm: independent platform polling restores the baseline.
    wait_guest_ms(15100)
    assert raw('DISPLAY REFRESH') == 'VALUE 58892'
    assert raw('DISPLAY TRIAL') == 'VALUE 0'
    # The platform can report the restored registers before the next UI timer
    # redraws the dialog. Wait for that redraw before injecting the next key.
    wait_guest_ms(1000)
    capture('refresh-auto-reverted')
    print('PASS: physical LCD divider change and unattended 15-second rollback', flush=True)
    press('down'); press('ok')
    assert raw('DISPLAY REFRESH') == 'VALUE 55212', ('second trial did not start', raw('DISPLAY TRIAL'))
    capture('refresh-second-trial')
    wait_guest_ms(1100)
    touch('TAP 150 104') # Confirm by touch after the accidental-repeat guard.
    assert raw('DISPLAY TRIAL') == 'VALUE 0'
    assert raw('DISPLAY REFRESH') == 'VALUE 55212', 'touch confirmation did not retain rate'
    capture('refresh-confirmed')
    press('back')
    time.sleep(.5)
    assert raw('DISPLAY REFRESH') == 'VALUE 55212'
    press('ok') # reopen from the same row; no duplicate timer registration
    press('ok') # default restores immediately
    assert raw('DISPLAY REFRESH') == 'VALUE 58892'
    press('down'); press('ok'); press('back') # unconfirmed trial cancels on exit
    assert raw('DISPLAY REFRESH') == 'VALUE 58892'
    assert raw('DISPLAY GUARDS') == 'OK'
    print('PASS: refresh confirmation, repeated page visits, cancel-on-exit', flush=True)
