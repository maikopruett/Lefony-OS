# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded local emulator diagnostics, separate from app data and test evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading

LIMIT = 65536


def file_identity(path):
    try:
        if not Path(path).is_file():return None
        with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    except OSError:return None


def tail(path):
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0,2);total=stream.tell();stream.seek(max(0,total-LIMIT))
            return stream.read(LIMIT),total
    except OSError:return b'',0


class Capture:
    def __init__(self, process):
        self.process=process;self.buffer=bytearray();self.total=0;self.lock=threading.Lock()
        self.read_error=None;self.finished=None
        self.thread=threading.Thread(target=self._read,daemon=True,name='lefony-qemu-stderr')
        self.thread.start()

    def _read(self):
        try:
            while chunk:=self.process.stderr.read1(8192):
                with self.lock:
                    self.total+=len(chunk);self.buffer.extend(chunk)
                    if len(self.buffer)>LIMIT:del self.buffer[:-LIMIT]
        except (OSError,ValueError) as error:self.read_error=type(error).__name__
        finally:self.process.stderr.close()

    def finish(self):
        if self.finished is not None:return self.finished
        before=self.process.poll();action='already-exited'
        if before is None:
            action='terminated-for-cleanup'
            try:self.process.terminate()
            except ProcessLookupError:pass
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            action='killed-after-cleanup-timeout';self.process.kill();self.process.wait(timeout=5)
        self.thread.join(timeout=1)
        with self.lock:stderr=bytes(self.buffer);total=self.total
        self.finished=({'exit_before_cleanup':before,'exit_after_cleanup':self.process.returncode,
                        'cleanup_action':action,'stderr_bytes':total,'stderr_retained_bytes':len(stderr),
                        'stderr_truncated':total>len(stderr),'stderr_complete':not self.thread.is_alive(),
                        'stderr_read_error':self.read_error},stderr)
        return self.finished


def record(error, outcome, stderr, uart, *, identities, command, phase, directory=None, cleanup_errors=()):
    uart_data,uart_total=tail(uart)
    report={'schema':1,'kind':'emulator-run-failure','phase':phase,'command':command,
            'exception':type(error).__name__,'identities':identities,'process':outcome,
            'uart_bytes':uart_total,'uart_retained_bytes':len(uart_data),'uart_truncated':uart_total>len(uart_data),
            'cleanup_errors':list(cleanup_errors),'physical':'not_tested'}
    if directory is not None:
        try:
            directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
            output=Path(tempfile.mkdtemp(prefix='failure-',dir=directory))
            for name,data in (('stderr.log',stderr),('uart.log',uart_data)):(output/name).write_bytes(data)
            report['logs']={name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
                            for name,data in (('stderr.log',stderr),('uart.log',uart_data))}
            # Keep raw host paths/output out of the structured report. The caller
            # can locate this private diagnostic directory within its own build.
            report['directory']=output.name
            (output/'failure.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        except OSError as failure:
            report['save_error']={'type':type(failure).__name__,'errno':failure.errno}
    error.emulator_failure=report
    return report,stderr,uart_data
