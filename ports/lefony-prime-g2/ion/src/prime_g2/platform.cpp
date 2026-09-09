#include <ion.h>

namespace Ion {
extern uint32_t staticStorageArea[];

const char * softwareVersion() {
  return "15.5.0";
}

const char * upsilonVersion() {
  /* The API name is retained for compatibility with the upstream About
   * controller; the user-visible product is Lefony OS. */
  return "Lefony OS 1.0.0";
}

const char * omegaVersion() {
  return "2.0.2";
}

const volatile char * username() {
  return "Lefony OS";
}

const char * patchLevel() {
  return "Lefony Prime G2";
}

const void * storageAddress() {
  return staticStorageArea;
}

void updateSlotInfo() {
}

const uint32_t * externalAppsFlashStart() {
  return nullptr;
}

}
