#include "apps_container.h"
#include "regression/app.h"
#include "statistics/app.h"

#include <ion.h>
#include <ion/storage.h>
#include <ion/timing.h>
#include <string.h>

namespace {
constexpr uint32_t Magic = 0x31544144; // "DAT1"
constexpr uint16_t Version = 1;
constexpr char StatisticsRecord[] = "mahalo.statistics";
constexpr char RegressionRecord[] = "mahalo.regression";

enum class Kind : uint8_t { Statistics = 0, Regression = 1 };

struct Payload {
  uint32_t magic;
  uint16_t version;
  uint16_t size;
  uint8_t kind;
  uint8_t counts[Shared::DoublePairStore::k_numberOfSeries];
  uint8_t regressionTypes[Shared::DoublePairStore::k_numberOfSeries];
  uint8_t reserved;
  double values[Shared::DoublePairStore::k_numberOfSeries]
               [Shared::DoublePairStore::k_numberOfColumnsPerSeries]
               [Shared::DoublePairStore::k_maxNumberOfPairs];
  double auxiliary[2];
  uint32_t crc;
};

bool sInitialized = false;
uint64_t sNextSync = 0;

Statistics::Store *statisticsStore() {
  auto *snapshot = static_cast<Statistics::App::Snapshot *>(
    AppsContainer::sharedAppsContainer()->appSnapshotAtIndex(5));
  return snapshot->store();
}

Regression::Store *regressionStore() {
  auto *snapshot = static_cast<Regression::App::Snapshot *>(
    AppsContainer::sharedAppsContainer()->appSnapshotAtIndex(10));
  return snapshot->store();
}

Shared::DoublePairStore *store(Kind kind) {
  return kind == Kind::Statistics ?
    static_cast<Shared::DoublePairStore *>(statisticsStore()) :
    static_cast<Shared::DoublePairStore *>(regressionStore());
}

uint32_t checksum(const Payload &source) {
  Payload copy = source;
  copy.crc = 0;
  return Ion::crc32Byte(reinterpret_cast<const uint8_t *>(&copy), sizeof(copy));
}

Payload currentPayload(Kind kind) {
  Payload result = {};
  result.magic = Magic;
  result.version = Version;
  result.size = sizeof(Payload);
  result.kind = static_cast<uint8_t>(kind);
  Shared::DoublePairStore *source = store(kind);
  for (int series = 0; series < Shared::DoublePairStore::k_numberOfSeries; series++) {
    int count = source->numberOfPairsOfSeries(series);
    result.counts[series] = count;
    for (int column = 0; column < Shared::DoublePairStore::k_numberOfColumnsPerSeries; column++) {
      for (int row = 0; row < count; row++) {
        result.values[series][column][row] = source->get(series, column, row);
      }
    }
  }
  if (kind == Kind::Statistics) {
    result.auxiliary[0] = statisticsStore()->barWidth();
    result.auxiliary[1] = statisticsStore()->firstDrawnBarAbscissa();
  } else {
    for (int series = 0; series < Shared::DoublePairStore::k_numberOfSeries; series++) {
      result.regressionTypes[series] = static_cast<uint8_t>(
        regressionStore()->seriesRegressionType(series));
    }
  }
  result.crc = checksum(result);
  return result;
}

bool valid(const Payload &value, Kind kind) {
  if (value.magic != Magic || value.version != Version ||
      value.size != sizeof(Payload) || value.kind != static_cast<uint8_t>(kind) ||
      value.crc != checksum(value)) {
    return false;
  }
  for (int series = 0; series < Shared::DoublePairStore::k_numberOfSeries; series++) {
    if (value.counts[series] > Shared::DoublePairStore::k_maxNumberOfPairs) {
      return false;
    }
    if (kind == Kind::Regression &&
        value.regressionTypes[series] >= Regression::Model::k_numberOfModels) {
      return false;
    }
  }
  return true;
}

void apply(const Payload &value, Kind kind) {
  Shared::DoublePairStore *destination = store(kind);
  destination->deleteAllPairs();
  for (int series = 0; series < Shared::DoublePairStore::k_numberOfSeries; series++) {
    for (int row = 0; row < value.counts[series]; row++) {
      for (int column = 0; column < Shared::DoublePairStore::k_numberOfColumnsPerSeries; column++) {
        destination->set(value.values[series][column][row], series, column, row);
      }
    }
  }
  if (kind == Kind::Statistics) {
    statisticsStore()->setBarWidth(value.auxiliary[0]);
    statisticsStore()->setFirstDrawnBarAbscissa(value.auxiliary[1]);
  } else {
    for (int series = 0; series < Shared::DoublePairStore::k_numberOfSeries; series++) {
      regressionStore()->setSeriesRegressionType(series,
        static_cast<Regression::Model::Type>(value.regressionTypes[series]));
    }
  }
}

void save(Kind kind) {
  const char *name = kind == Kind::Statistics ? StatisticsRecord : RegressionRecord;
  Payload value = currentPayload(kind);
  Ion::Storage *storage = Ion::Storage::sharedStorage();
  Ion::Storage::Record record = storage->recordNamed(name);
  if (record.isNull()) {
    storage->createRecordWithFullName(name, &value, sizeof(value));
    return;
  }
  Ion::Storage::Record::Data data = record.value();
  if (data.size != sizeof(value) || memcmp(data.buffer, &value, sizeof(value)) != 0) {
    record.setValue({&value, sizeof(value)});
  }
}

void loadOrCreate(Kind kind) {
  const char *name = kind == Kind::Statistics ? StatisticsRecord : RegressionRecord;
  Ion::Storage::Record record = Ion::Storage::sharedStorage()->recordNamed(name);
  if (!record.isNull()) {
    Ion::Storage::Record::Data data = record.value();
    if (data.size == sizeof(Payload)) {
      Payload value;
      memcpy(&value, data.buffer, sizeof(value));
      if (valid(value, kind)) {
        apply(value, kind);
        return;
      }
    }
  }
  save(kind);
}
}

extern "C" void prime_g2_datasets_sync() {
  if (!sInitialized) {
    sInitialized = true;
    loadOrCreate(Kind::Statistics);
    loadOrCreate(Kind::Regression);
    sNextSync = Ion::Timing::millis() + 500;
    return;
  }
  uint64_t now = Ion::Timing::millis();
  if (now >= sNextSync) {
    save(Kind::Statistics);
    save(Kind::Regression);
    sNextSync = now + 500;
  }
}

extern "C" void prime_g2_datasets_factory_reset() {
  statisticsStore()->deleteAllPairs();
  regressionStore()->reset();
  sInitialized = true;
  save(Kind::Statistics);
  save(Kind::Regression);
  sNextSync = Ion::Timing::millis() + 500;
}

extern "C" bool prime_g2_test_dataset_set(unsigned kind, unsigned series,
                                             unsigned column, unsigned row,
                                             int value) {
  if (kind > 1 || series >= Shared::DoublePairStore::k_numberOfSeries ||
      column >= Shared::DoublePairStore::k_numberOfColumnsPerSeries ||
      row >= Shared::DoublePairStore::k_maxNumberOfPairs) {
    return false;
  }
  store(static_cast<Kind>(kind))->set(value, series, column, row);
  save(static_cast<Kind>(kind));
  return true;
}

extern "C" bool prime_g2_test_dataset_get(unsigned kind, unsigned series,
                                             unsigned column, unsigned row,
                                             int *value) {
  if (value == nullptr || kind > 1 ||
      series >= Shared::DoublePairStore::k_numberOfSeries ||
      column >= Shared::DoublePairStore::k_numberOfColumnsPerSeries ||
      row >= static_cast<unsigned>(
        store(static_cast<Kind>(kind))->numberOfPairsOfSeries(series))) {
    return false;
  }
  *value = static_cast<int>(store(static_cast<Kind>(kind))->get(series, column, row));
  return true;
}
