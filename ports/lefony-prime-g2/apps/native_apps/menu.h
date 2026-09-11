// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#pragma once
#include <escher.h>
namespace NativeApps {
int builtInCount();
int menuCount();
int slotAt(int index);
const char *installedName(unsigned slot);
const Image *installedIcon();
uint32_t catalogRevision();
bool launchInstalled(int slot);
}
