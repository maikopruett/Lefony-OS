// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#pragma once
#include <escher.h>
namespace NativeApps {
int builtInCount();
int menuCount();
int slotAt(int index);
int menuIndex(int position); // Visual position to default one-based app index.
const Image *menuIcon(int position);
bool moveMenuIcon(int from,int to); // Preview only; one save on release.
bool saveMenuOrder();
bool menuOrderSaveFailed();
void reloadMenuOrder();
const char *installedName(unsigned slot);
const Image *installedIcon(unsigned slot);
uint32_t catalogRevision();
bool launchInstalled(int slot);
}
