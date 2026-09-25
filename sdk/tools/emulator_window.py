# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Qt desktop host for the private, shared emulator renderer."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


def device_size(width, height, scale, available_width, available_height):
    """Keep the whole calculator visible, including on small desktop screens."""
    fit = min(available_width / width, available_height / height)
    factor = fit if scale is None else min(scale, fit)
    return max(1, int(width * factor)), max(1, int(height * factor))


def validate_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or
            parsed.username or parsed.password or not parsed.port or
            not parsed.path.startswith('/') or parsed.path == '/' or
            parsed.query or parsed.fragment):
        raise ValueError('Expected the private local emulator session URL')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', type=validate_url)
    parser.add_argument('--title', default='Lefony OS')
    parser.add_argument('--ready-file', type=Path, required=True)
    args = parser.parse_args(argv)
    # Lazy imports keep headless operation independent of a desktop toolkit.
    from PySide6.QtCore import QUrl, Qt, QTimer
    from PySide6.QtGui import QAction, QActionGroup, QKeySequence
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
    from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile,
                                       QWebEngineSettings, QWebEngineUrlRequestInterceptor)
    from PySide6.QtWebEngineWidgets import QWebEngineView

    url = QUrl(args.url)
    app = QApplication([sys.argv[0]])
    app.setApplicationName('Lefony Emulator')
    app.setOrganizationName('Lefony')

    def local(target):
        return (target.scheme() == url.scheme() and target.host() == url.host()
                and target.port() == url.port() and target.path().startswith(url.path()))

    class Requests(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, request):
            # The renderer only needs its own session and in-memory frame blobs.
            if request.requestUrl().scheme() != 'blob' and not local(request.requestUrl()):
                request.block(True)

    class Page(QWebEnginePage):
        def acceptNavigationRequest(self, target, kind, main_frame):
            return main_frame and target == url

        def createWindow(self, kind):
            return None

    window = QMainWindow()
    window.setWindowTitle(f'Lefony Emulator · {args.title}')
    window.setMinimumSize(180, 180)
    window.resize(381, 797)
    view = QWebEngineView(window)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    # No persistent profile, browsing history, cookies, extensions or disk cache.
    profile = QWebEngineProfile(view)
    requests = Requests(profile)
    profile.setUrlRequestInterceptor(requests)
    profile.downloadRequested.connect(lambda download: download.cancel())
    page = Page(profile, view)
    view.setPage(page)
    page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    page.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
    window.setCentralWidget(view)

    def release():
        page.runJavaScript('window.lefonyDesktop?.release()')

    menus = window.menuBar()
    menus.setNativeMenuBar(True)
    file_menu = menus.addMenu('&File')
    stop = file_menu.addAction('&Stop Emulator')
    # Keep Stop under File instead of macOS's automatic Quit action relocation.
    stop.setMenuRole(QAction.MenuRole.NoRole)
    stop.setShortcut(QKeySequence('Ctrl+W'))
    stop.triggered.connect(window.close)
    quit_action = file_menu.addAction('&Quit Lefony Emulator')
    quit_action.setMenuRole(QAction.MenuRole.QuitRole)
    quit_action.setShortcut(QKeySequence.StandardKey.Quit)
    quit_action.triggered.connect(window.close)
    view_menu = menus.addMenu('&View')
    layout_menu = view_menu.addMenu('&Layout')
    scale_menu = view_menu.addMenu('&Scale')
    layout_group = QActionGroup(window)
    scale_group = QActionGroup(window)
    selected = {'skin': None, 'scale': 1.0}

    def resize_device():
        skin = selected['skin']
        if skin is None:
            return
        available = window.screen().availableGeometry()
        # Account for local Linux/Windows menus and the native window frame.
        chrome_width = window.frameGeometry().width() - window.width()
        chrome_height = window.frameGeometry().height() - window.height()
        menu_height = 0 if menus.isNativeMenuBar() else menus.sizeHint().height()
        width, height = device_size(skin['width'], skin['height'], selected['scale'],
                                    max(1, available.width() - chrome_width - 24),
                                    max(1, available.height() - chrome_height - menu_height - 24))
        window.resize(width, height + menu_height)

    def choose_scale(scale):
        release()
        selected['scale'] = scale
        resize_device()
        view.setFocus()

    for scale in (.75, 1.0, 1.25, 1.5, 2.0, None):
        label = 'Fit to Screen' if scale is None else f'{scale:g}×'
        action = scale_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(scale == 1.0)
        scale_group.addAction(action)
        if scale is None:
            action.setShortcut(QKeySequence('Ctrl+0'))
        action.triggered.connect(lambda checked=False, scale=scale: choose_scale(scale))

    help_menu = menus.addMenu('&Help')
    shortcuts = help_menu.addAction('&Keyboard Shortcuts and Saving')
    shortcuts.triggered.connect(lambda: QMessageBox.information(window, 'Keyboard Shortcuts and Saving',
        'Click the Prime keys or touch its display.\n\n'
        'Enter = Enter; Escape = Esc; Backspace = Delete\n'
        'Arrow keys = directions; Home = Home\n'
        'F1–F6 = Symb, Plot, Num, Help, View, Menu\n'
        'Shift = Shift; Alt = Alpha; use Alpha for letters.\n'
        'Command or Control shortcuts remain available.\n\n'
        'Save inside the app, then choose File → Stop Emulator or close the window. '
        'A named SDK workspace keeps saved calculator data between runs.'))
    connection_action = help_menu.addAction('&Connection Status')
    connection_action.triggered.connect(lambda: page.runJavaScript(
        'window.lefonyDesktop?.connection()', lambda value: QMessageBox.information(
            window, 'Emulator Connection', str(value or 'Connecting…'))))
    for menu in (file_menu, view_menu, layout_menu, scale_menu, help_menu):
        menu.aboutToShow.connect(release)

    def configure(value):
        try:
            configuration = json.loads(value)
            skins = configuration['skins']
            selected['skin'] = next(skin for skin in skins if skin['id'] == configuration['activeSkin'])
        except (TypeError, ValueError, KeyError, StopIteration):
            print('The emulator device skin could not load.', file=sys.stderr)
            app.exit(1)
            return
        for skin in skins:
            action = layout_menu.addAction(skin['title'])
            action.setCheckable(True)
            action.setChecked(skin['id'] == selected['skin']['id'])
            layout_group.addAction(action)

            def choose(checked=False, skin=skin):
                release()
                selected['skin'] = skin
                page.runJavaScript('window.lefonyDesktop.chooseSkin(' + json.dumps(skin['id']) + ')')
                resize_device()
                view.setFocus()

            action.triggered.connect(choose)
        resize_device()
        view.setFocus()
        args.ready_file.write_text('ready\n', encoding='utf-8')

    # Connection errors belong to native UI too; no banners cover the device.
    reported_failure = False

    def connection_changed(value):
        nonlocal reported_failure
        if isinstance(value, str) and value.startswith('Disconnected') and not reported_failure:
            reported_failure = True
            QMessageBox.warning(window, 'Emulator Disconnected', value)

    timer = QTimer(window)
    timer.setInterval(1000)
    timer.timeout.connect(lambda: page.runJavaScript('window.lefonyDesktop?.connection()', connection_changed))

    def loaded(ok):
        if ok:
            page.runJavaScript('JSON.stringify(window.lefonyDesktop?.configuration())', configure)
            timer.start()
        else:
            print('The local emulator renderer could not load.', file=sys.stderr)
            app.exit(1)

    view.loadFinished.connect(loaded)
    window.show()
    view.load(url)
    result = app.exec()
    timer.stop()
    # Destroy the page before its off-the-record profile.
    import shiboken6
    shiboken6.delete(page)
    shiboken6.delete(profile)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
