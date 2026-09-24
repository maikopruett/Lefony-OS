#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the pinned existing minigzip program as an ordinary external SDK app."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def adapt(text):
    """Checked changes to the utility only; compression library stays intact."""
    changes = [
        ('static char *prog;', '''/* Lefony adaptation: direct OS-staged replacement with explicit commit/abort.
 * Finish and verify the stream before commit; failed processing discards output.
 * Compression/decompression algorithms and their library sources are unchanged.
 */
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <lefony/files.h>
static char *prog;
static int output_descriptor = -1;
static void error(const char *msg);
static void abort_output(void) {
    if (output_descriptor >= 0) {
        /* Do not let exit's stdio cleanup publish after a failed abort. */
        if (lefony_file_abort(output_descriptor) < 0 && errno != EBADF)
            _exit(1);
        output_descriptor = -1;
    }
}
static int begin_output(const char *destination) {
    if (output_descriptor >= 0) { errno = EBUSY; return -1; }
    /* Confirm discard authorization before any writer can be created. */
    if (lefony_file_abort(0) != -1 || errno != EBADF) return -1;
    output_descriptor = open(destination, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    return output_descriptor;
}
static gzFile gzip_output(const char *destination, const char *mode) {
    int fd = begin_output(destination);
    return fd < 0 ? NULL : gzdopen(fd, mode);
}
static FILE *plain_output(const char *destination) {
    int fd = begin_output(destination);
    return fd < 0 ? NULL : fdopen(fd, "wb");
}
static void commit_output(void) {
    /* The complete stream has reached staging. close commits and invalidates
     * its descriptor before libc/zlib frees stream buffers. No writer reopen
     * is needed. A failed commit is ambiguous, so retain the input. */
    if (close(output_descriptor)) error("save unconfirmed; input retained");
    output_descriptor = -1;
}'''),
        ('    prog = argv[0];', '''    prog = argv[0];
    if (atexit(abort_output)) error("cannot register output cleanup");'''),
        ('        len = gzread(in, buf, sizeof(buf));\n        if (len < 0) error (gzerror(in, &err));',
         '''        len = gzread(in, buf, sizeof(buf));
        if (len < 0) error (gzerror(in, &err));
        /* gzread can return bytes with a deferred trailer/input error.
         * Check it before another call clears the recoverable status. */
        (void)gzerror(in, &err);
        if (err != Z_OK) error(gzerror(in, &err));'''),
        ('out = gzopen(outfile, mode);', 'out = gzip_output(outfile, mode);'),
        ('    unlink(file);', '    if (unlink(file)) error("output saved; failed input removal");'),
        ('out = fopen(outfile, "wb");', 'out = plain_output(outfile);'),
        ('    unlink(infile);', '    if (unlink(infile)) error("output saved; failed input removal");'),
        ('''    fclose(in);
    if (gzclose(out) != Z_OK) error("failed gzclose");
}''', '''    if (fclose(in)) error("failed input close");
    if (gzflush(out, Z_FINISH) != Z_OK) error("failed gzip finalization");
    commit_output();
    /* Descriptor was explicitly closed after stream validation. gzclose releases codec
     * buffers; its attempted write/close must fail and cannot publish again. */
    if (gzclose(out) != Z_ERRNO) error("unexpected gzip cleanup result");
}'''),
        ('''    if (fclose(out)) error("failed fclose");

    if (gzclose(in) != Z_OK) error("failed gzclose");''', '''    if (gzclose(in) != Z_OK) error("failed input gzip close");
    if (fflush(out)) error("failed output flush");
    commit_output();
    /* Release the now-detached FILE buffer, without another commit. */
    if (fclose(out) != EOF || errno != EBADF) error("unexpected stdio cleanup result");'''),
        ('    if (argc == 0) {', '''    if (argc == 0 || copyout) error("only named-file mode is supported");
    if (argc == 0) {'''),
    ]
    for before, after in changes:
        if text.count(before) != 1:
            raise ValueError('unexpected minigzip source context: ' + before)
        text = text.replace(before, after)
    return text


def prepare(destination, archive, arguments):
    spec = json.loads((ROOT / 'sdk/ports/minigzip/source.json').read_text())
    if sha(archive.read_bytes()) != spec['archive_sha256']:
        raise ValueError('zlib source archive hash mismatch')
    if destination.exists():
        raise ValueError('Project already exists; existing source was preserved')
    contents = {}
    with tarfile.open(archive) as bundle:
        for name, expected in spec['files'].items():
            item = bundle.getmember(spec['directory'] + '/' + name)
            if not item.isfile() or item.size > 256 * 1024:
                raise ValueError('Unexpected upstream source entry: ' + name)
            data = bundle.extractfile(item).read()
            if sha(data) != expected:
                raise ValueError('Upstream source hash mismatch: ' + name)
            contents[name] = data
    contents['test/minigzip.c'] = adapt(contents['test/minigzip.c'].decode()).encode()
    destination.mkdir(parents=True)
    for name, data in contents.items():
        target = destination / ('notices/zlib.txt' if name == 'LICENSE' else 'src/zlib/' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    metadata = json.loads((ROOT / 'sdk/examples/c-main/app.json').read_text())
    metadata.update(id='minigzip', name='Minigzip', version='0.2.0', minimum_api=12,
                    required_capabilities=8216, license='CC-BY-NC-SA-4.0 AND Zlib')
    config = {'schema': 2, 'runtime': 'foreground-newlib-1',
              'sources': sorted('src/zlib/' + name for name in contents if name.endswith('.c')),
              'include_dirs': ['src/zlib'], 'defines': spec['defines'], 'arguments': arguments}
    for name, data in [('app.json', metadata), ('project.json', config)]:
        (destination / name).write_text(json.dumps(data, indent=2) + '\n')
    for name in ('AGENTS.md', 'README.md'):
        shutil.copyfile(ROOT / 'sdk/ports/minigzip' / name, destination / name)
    shutil.copyfile(ROOT / 'sdk/templates/basic/CMakeLists.txt', destination / 'CMakeLists.txt')
    notice = ('Minigzip/zlib ' + spec['version'] + '\nSource archive SHA-256: ' + spec['archive_sha256'] +
              '\nUpstream test/minigzip.c has marked commit/abort output and deferred-read-error adaptations.\n'
              'DYNAMIC_CRC_TABLE builds tables in app memory; unused crc32.h is omitted.\n'
              'SDK startup/adapters retain CC-BY-NC-SA-4.0; zlib sources retain Zlib terms.\n')
    (destination / 'notices/port.txt').write_text(notice)
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('arguments', nargs='*', default=['input.dat'])
    args = parser.parse_args()
    spec = json.loads((ROOT / 'sdk/ports/minigzip/source.json').read_text())
    archive = args.archive or ROOT / ('build/sdk-1.0-upstream/zlib-' + spec['version'] + '.tar.gz')
    if not archive.exists():
        if args.offline:
            raise ValueError('Pinned zlib archive unavailable offline')
        with urllib.request.urlopen(spec['url'], timeout=30) as response:
            data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024 or sha(data) != spec['archive_sha256']:
            raise ValueError('zlib download size or hash mismatch')
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open('xb') as stream:
            stream.write(data)
    prepare(args.project.resolve(), archive, args.arguments)
    print('Prepared pinned minigzip external project:', args.project)


if __name__ == '__main__':
    main()
