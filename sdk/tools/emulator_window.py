# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Qt desktop host for the private, shared emulator renderer."""
import argparse
from pathlib import Path
import sys
from urllib.parse import urlsplit


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
    from PySide6.QtCore import QUrl, Qt
    from PySide6.QtWidgets import QApplication, QMainWindow
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
    window.setMinimumSize(420, 500)
    available = app.primaryScreen().availableGeometry()
    window.resize(min(760, available.width()), min(1000, available.height() - 50))
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

    def loaded(ok):
        if ok:
            args.ready_file.write_text('ready\n', encoding='utf-8')
        else:
            print('The local emulator renderer could not load.', file=sys.stderr)
            app.exit(1)

    view.loadFinished.connect(loaded)
    window.show()
    view.load(url)
    result = app.exec()
    # Destroy the page before its off-the-record profile.
    import shiboken6
    shiboken6.delete(page)
    shiboken6.delete(profile)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
