# SPDX-License-Identifier: GPL-3.0-or-later
"""Local interactive display, using the VM's normal KPP and Goodix inputs."""
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import time
import webbrowser

from PIL import Image
from emulator_ui_page import page


def validate_input(value, keys):
    if not isinstance(value, dict) or set(value) != {'keys', 'touch'}:
        raise ValueError('expected keys and touch')
    names, contacts = value['keys'], value['touch']
    if (not isinstance(names, list) or len(names) > len(keys) or
            not all(isinstance(key, str) and key in keys for key in names) or
            len(set(names)) != len(names)):
        raise ValueError('invalid Prime keys')
    if not isinstance(contacts, list) or len(contacts) > 2:
        raise ValueError('expected at most two touch contacts')
    ids = set()
    for contact in contacts:
        if (not isinstance(contact, list) or len(contact) != 3 or
                not all(type(v) is int for v in contact) or
                not 0 <= contact[0] < 16 or not 0 <= contact[1] < 320 or
                not 0 <= contact[2] < 240 or contact[0] in ids):
            raise ValueError('invalid display coordinates')
        ids.add(contact[0])
    return names, contacts


class Panel:
    """All guest access is serialized by the single HTTP request loop."""
    lease_seconds = 1.5
    minimum_press = .08
    minimum_release = .05

    def __init__(self, controls, folder, keys):
        self.controls, self.folder, self.keys = controls, folder, keys
        self.pressed_at = {}
        self.released_at = {}
        self.touch = []
        self.touch_at = 0
        self.last_input = time.monotonic()
        self.stopped = False
        self.failure = None
        self.frame_at = 0
        self.frame_data = b''

    def input(self, value):
        names, contacts = validate_input(value, self.keys)
        now = time.monotonic()
        # Very short browser clicks still need to cross guest key debouncing.
        released = set(self.pressed_at) - set(names)
        starts = [self.pressed_at[name] for name in released]
        if self.touch and not contacts:
            starts.append(self.touch_at)
        delay = max(0, self.minimum_press - (now - max(starts))) if starts else 0
        for name in set(names) - set(self.pressed_at):
            delay = max(delay, self.minimum_release - (now - self.released_at.get(name, 0)))
        if delay > 0:
            time.sleep(delay)
        self.controls.keys(names)
        for name in released:
            self.released_at[name] = time.monotonic()
        self.pressed_at = {name: self.pressed_at.get(name, time.monotonic()) for name in names}
        if contacts != self.touch:
            command = 'TOUCH FRAME ' + str(len(contacts))
            for contact in contacts:
                command += ' ' + ' '.join(str(v) for v in contact)
            if self.controls.channel.command(command) != 'OK':
                raise RuntimeError('emulator touch input failed')
            if contacts and not self.touch:
                self.touch_at = time.monotonic()
            self.touch = contacts
        self.last_input = time.monotonic()

    def release(self):
        self.input({'keys': [], 'touch': []})

    def expire(self):
        if (self.pressed_at or self.touch) and time.monotonic() - self.last_input > self.lease_seconds:
            self.release()

    def frame(self):
        if time.monotonic() - self.frame_at >= .1:
            path = self.folder / 'interactive.ppm'
            self.controls.execute('screendump', {'filename': str(path)})
            with Image.open(path) as frame:
                if frame.size != (320, 240):
                    raise RuntimeError('unexpected Prime display size')
                buffer = io.BytesIO()
                frame.save(buffer, format='PNG')
            self.frame_data = buffer.getvalue()
            self.frame_at = time.monotonic()
        return self.frame_data


class Server(HTTPServer):
    allow_reuse_address = False
    request_queue_size = 8

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(.5)
        return sock, address


def make_server(panel, title):
    token = secrets.token_urlsafe(32)
    root = '/' + token + '/'
    document = page(title).encode('utf-8')

    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.0 closes connections, so idle keepalives cannot own the loop.
        def log_message(self, *args):
            pass  # Session URL and calculator content stay out of access logs.

        def respond(self, status, data=b'', mime='text/plain; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            return (self.headers.get('Host') == self.server.authority and
                    self.path.startswith(root) and
                    self.headers.get('Sec-Fetch-Site') not in ('cross-site',))

        def do_GET(self):
            if not self.allowed():
                self.respond(403)
                return
            try:
                if self.path == root:
                    self.respond(200, document, 'text/html; charset=utf-8')
                elif self.path == root + 'frame':
                    self.respond(200, panel.frame(), 'image/png')
                else:
                    self.respond(404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:
                panel.failure = error
                panel.stopped = True
                self.respond(503, b'Emulator connection ended')

        def do_POST(self):
            if not self.allowed() or self.headers.get('Origin') != 'http://' + self.server.authority:
                self.respond(403)
                return
            try:
                size = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= size <= 4096 or self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                    raise ValueError('invalid request size or type')
                value = json.loads(self.rfile.read(size))
                if self.path == root + 'input':
                    panel.input(value)
                elif self.path == root + 'stop' and value == {}:
                    panel.release()
                    panel.stopped = True
                else:
                    self.respond(404)
                    return
            except (ValueError, UnicodeError):
                self.respond(400)
                return
            except Exception as error:
                panel.failure = error
                panel.stopped = True
                self.respond(503, b'Emulator connection ended')
                return
            try:
                self.respond(204)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = Server(('127.0.0.1', 0), Handler)
    server.authority = '127.0.0.1:' + str(server.server_port)
    server.url = 'http://' + server.authority + root
    server.timeout = .1
    return server


def run_panel(channel, folder, process, title):
    # Lazy import: replay also imports runner.
    from replay import Controls, KEYS, control_session
    timeout = channel.socket.gettimeout()
    try:
        channel.socket.settimeout(2)
        with control_session(Controls(channel, folder)) as controls:
            controls.qmp.socket.settimeout(2)
            controls.qtest.socket.settimeout(2)
            panel = Panel(controls, folder, KEYS)
            with make_server(panel, title) as server:
                print('Lefony Emulator: ' + server.url + '\nUse Stop emulator or Ctrl-C to finish.', flush=True)
                try:
                    webbrowser.open(server.url)
                except webbrowser.Error:
                    print('Open the local URL above in your browser.', flush=True)
                try:
                    while not panel.stopped and process.poll() is None:
                        server.handle_request()
                        panel.expire()
                except KeyboardInterrupt:
                    pass
                if panel.failure:
                    raise RuntimeError('interactive emulator connection failed') from panel.failure
    finally:
        channel.socket.settimeout(timeout)
