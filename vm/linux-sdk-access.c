// SPDX-License-Identifier: GPL-3.0-or-later
// Dependency-isolation launcher for trusted SDK qualification, not an untrusted-code service.
// Uses the Linux userspace Landlock API: https://docs.kernel.org/userspace-api/landlock.html
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <unistd.h>

#define MAX_PROBES 32
#define READ_ACCESS (LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_READ_DIR)
#define EXEC_ACCESS (READ_ACCESS | LANDLOCK_ACCESS_FS_EXECUTE)
#define ALL_ACCESS (EXEC_ACCESS | LANDLOCK_ACCESS_FS_WRITE_FILE | \
    LANDLOCK_ACCESS_FS_REMOVE_DIR | LANDLOCK_ACCESS_FS_REMOVE_FILE | \
    LANDLOCK_ACCESS_FS_MAKE_CHAR | LANDLOCK_ACCESS_FS_MAKE_DIR | \
    LANDLOCK_ACCESS_FS_MAKE_REG | LANDLOCK_ACCESS_FS_MAKE_SOCK | \
    LANDLOCK_ACCESS_FS_MAKE_FIFO | LANDLOCK_ACCESS_FS_MAKE_BLOCK | \
    LANDLOCK_ACCESS_FS_MAKE_SYM | LANDLOCK_ACCESS_FS_REFER | LANDLOCK_ACCESS_FS_TRUNCATE)

static void fail(const char *operation) {
    perror(operation);
    exit(125);
}

static void usage(void) {
    fputs("usage: linux-sdk-access --probe | [--read PATH | --exec PATH | --work PATH | --expect-denied FILE]... -- COMMAND [ARG...]\n", stderr);
    exit(125);
}

static void allow_path(int ruleset, const char *path, uint64_t access) {
    struct stat info;
    int fd = open(path, O_PATH | O_CLOEXEC);
    if (fd < 0 || fstat(fd, &info)) fail("Open allowed path");
    if (!S_ISDIR(info.st_mode)) access &= LANDLOCK_ACCESS_FS_READ_FILE |
        LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_TRUNCATE;
    struct landlock_path_beneath_attr rule = {.allowed_access = access, .parent_fd = fd};
    if (syscall(SYS_landlock_add_rule, ruleset, LANDLOCK_RULE_PATH_BENEATH, &rule, 0))
        fail("Add Landlock rule");
    close(fd);
}

int main(int argc, char **argv) {
    int abi = syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
    if (abi < 0) fail("Landlock unavailable");
    if (abi < 3) {
        fputs("SDK isolation requires Landlock ABI 3 or newer; refusing unrestricted execution\n", stderr);
        return 125;
    }
    if (argc == 2 && !strcmp(argv[1], "--probe")) {
        struct utsname machine;
        if (uname(&machine)) fail("uname");
        printf("{\"landlock_abi\":%d,\"machine\":\"%s\",\"kernel\":\"%s\"}\n",
               abi, machine.machine, machine.release);
        return 0;
    }
    struct landlock_ruleset_attr attributes = {.handled_access_fs = ALL_ACCESS};
    int ruleset = syscall(SYS_landlock_create_ruleset, &attributes, sizeof(attributes), 0);
    if (ruleset < 0) fail("Create Landlock ruleset");
    const char *probes[MAX_PROBES];
    int count = 0, command = 0;
    for (int index = 1; index < argc; index++) {
        const char *option = argv[index];
        if (!strcmp(option, "--")) {command = index + 1; break;}
        if (++index >= argc || argv[index][0] != '/') usage();
        const char *path = argv[index];
        if (!strcmp(option, "--expect-denied")) {
            if (count == MAX_PROBES) usage();
            // A missing or already unreadable file is not evidence of isolation.
            int fd = open(path, O_RDONLY | O_CLOEXEC);
            if (fd < 0) fail("Read negative control before isolation");
            close(fd);
            probes[count++] = path;
        } else if (!strcmp(option, "--read")) allow_path(ruleset, path, READ_ACCESS);
        else if (!strcmp(option, "--exec")) allow_path(ruleset, path, EXEC_ACCESS);
        else if (!strcmp(option, "--work")) allow_path(ruleset, path, ALL_ACCESS);
        else usage();
    }
    if (!command || command >= argc) usage();
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) fail("Set no_new_privs");
    if (syscall(SYS_landlock_restrict_self, ruleset, 0)) fail("Enforce Landlock ruleset");
    close(ruleset);
    for (int index = 0; index < count; index++) {
        int fd = open(probes[index], O_RDONLY | O_CLOEXEC);
        if (fd >= 0) {
            close(fd);
            fputs("SDK isolation negative control remained readable; refusing execution\n", stderr);
            return 125;
        }
        if (errno != EACCES) fail("Unexpected negative-control error");
    }
    fprintf(stderr, "SDK isolation: Landlock ABI %d; %d denied reads verified\n", abi, count);
    execv(argv[command], &argv[command]);
    fail("Execute isolated SDK command");
}
