// SPDX-License-Identifier: GPL-3.0-or-later
// Native macOS host for the same local interface used by the SDK browser.
import Cocoa
import WebKit

final class EmulatorWindow: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    let url: URL
    init(url: URL) { self.url = url }
    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Quit Lefony Emulator", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        menu.addItem(appItem)
        NSApp.mainMenu = menu
        let height = min(1040, (NSScreen.main?.visibleFrame.height ?? 1000) - 50)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: height),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Lefony OS · HP Prime G2"
        window.minSize = NSSize(width: 420, height: 500)
        web = WKWebView(frame: window.contentView!.bounds)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        window.contentView = web
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        web.load(URLRequest(url: url))
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        let target = action.request.url
        decisionHandler(target?.scheme == url.scheme && target?.host == url.host && target?.port == url.port ? .allow : .cancel)
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

guard CommandLine.arguments.count == 2, let url = URL(string: CommandLine.arguments[1]),
      url.scheme == "http", url.host == "127.0.0.1" else { exit(2) }
let application = NSApplication.shared
let delegate = EmulatorWindow(url: url)
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
