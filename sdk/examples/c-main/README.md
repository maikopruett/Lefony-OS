# Conventional C startup example

This development candidate uses `main(argc, argv)`, newlib formatting and files,
and public foreground yield/sleep. The SDK supplies startup and descriptor
adapters. Each launch increments the `visits` file; a checked close completes
before the success message. Ordinary exit runs library cleanup.

Build with the pinned newlib sysroot and matching API 3 VM firmware. From the SDK:

```sh
lefony-sdk new /tmp/c-main --template c-main
lefony-sdk --project /tmp/c-main package
lefony-sdk --project /tmp/c-main source --format 2
```

`project.json` schema 2 selects `foreground-newlib-1`. Its `arguments` supply
`argv[1]`; `argv[0]` is the manifest app ID. See [the C runtime profile](../../C-RUNTIME.md)
for setup, limits, error behavior and qualification. No physical validation or
complete SDK 1.0 support is implied.
