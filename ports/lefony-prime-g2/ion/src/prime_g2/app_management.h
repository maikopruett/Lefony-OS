// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_MANAGEMENT_H
#define LEFONY_APP_MANAGEMENT_H
#include <stdint.h>
#include <stddef.h>
namespace PrimeG2 { namespace AppManagement {
struct Metadata { uint32_t abi; char id[49],name[81],version[24]; };
struct CatalogEntry { uint32_t bytes,generation; Metadata metadata; };
// Validation authenticates before parsing; no app code runs here.
void init(); // Mount/reserve once during OS startup, before app/USB management.
bool metadata(const uint8_t *package,size_t size,Metadata *out);
bool request(uint8_t command,uint32_t argument,const uint8_t *data,size_t size);
bool response(uint8_t command,uint32_t argument,uint8_t *data,size_t capacity,size_t *size);
void acknowledge();
void abandonSetup();
void poll();
bool busy();
uint32_t revision();
const CatalogEntry &entry(unsigned slot);
bool open(unsigned slot);
void close();
int readData(uint32_t offset,void *data,uint32_t size);
int writeData(uint32_t offset,const void *data,uint32_t size);
}}
#endif
