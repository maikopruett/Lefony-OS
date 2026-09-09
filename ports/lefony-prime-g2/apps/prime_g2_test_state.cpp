#include "apps_container.h"
#include "calculation/app.h"
#include "home/app.h"
#include "graph/app.h"

#include <escher/container.h>
#include <ion/events.h>
#include <stddef.h>

namespace Ion {
namespace Events {
extern Event sLastEvent;
extern int sEventRepetitionCount;
}
}

Ion::Events::Event prime_g2_last_event_for_test() {
  return Ion::Events::sLastEvent;
}

int prime_g2_repetition_count_for_test() {
  return Ion::Events::sEventRepetitionCount;
}

void prime_g2_reset_event_state_for_test() {
  Ion::Events::sLastEvent = Ion::Events::None;
  Ion::Events::sEventRepetitionCount = 0;
}

extern "C" int prime_g2_test_active_app() {
  AppsContainer *container = AppsContainer::sharedAppsContainer();
  return container->appIndexFromSnapshot(Container::activeApp()->snapshot());
}

extern "C" bool prime_g2_test_home_selection(int *row, int *column) {
  if (row == nullptr || column == nullptr) {
    return false;
  }
  AppsContainer *container = AppsContainer::sharedAppsContainer();
  auto *snapshot = static_cast<Home::App::Snapshot *>(
    container->appSnapshotAtIndex(0));
  *row = snapshot->selectedRow();
  *column = snapshot->selectedColumn();
  return true;
}

extern "C" const char *prime_g2_test_calculation_text(unsigned kind) {
  AppsContainer *container = AppsContainer::sharedAppsContainer();
  auto *snapshot = static_cast<Calculation::App::Snapshot *>(
    container->appSnapshotAtIndex(1));
  Calculation::CalculationStore *store = snapshot->calculationStore();
  if (store->numberOfCalculations() == 0) {
    return nullptr;
  }
  Shared::ExpiringPointer<Calculation::Calculation> calculation =
    store->calculationAtIndex(0);
  if (kind == 0) {
    return calculation->inputText();
  }
  if (kind == 1) {
    return calculation->exactOutputText();
  }
  if (kind == 2) {
    return calculation->approximateOutputText(
      Calculation::Calculation::NumberOfSignificantDigits::UserDefined);
  }
  return nullptr;
}

extern "C" int prime_g2_test_graph_tab() {
  return Graph::App::app()->snapshot()->activeTab();
}

extern "C" float prime_g2_test_graph_range(unsigned index) {
  auto range = Graph::App::app()->snapshot()->graphRange();
  return index == 0 ? range->xMin() : index == 1 ? range->xMax() :
         index == 2 ? range->yMin() : range->yMax();
}
