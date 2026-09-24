/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/foreground.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sys/time.h>
#include <unistd.h>
#define CHECK(c) do { if (!(c)) __asm__ volatile("udf %0" :: "i"(__LINE__)); } while (0)
static unsigned initialized;
static void append(char value) {
  FILE *f = fopen("order", "ab");
  CHECK(f && fwrite(&value, 1, 1, f) == 1 && fclose(f) == 0);
}
static struct Lifetime {
  unsigned char *memory;
  Lifetime() {
    CHECK(++initialized == 1);
    memory = static_cast<unsigned char *>(calloc(4096, 1));
    CHECK(memory && memory[4095] == 0);
    memory[4095] = 91;
    CHECK(lefony_program_sleep(10) == 0);
  }
  ~Lifetime() { CHECK(memory[4095] == 91); free(memory); append('D'); }
} lifetime;
static void finish() { append('A'); }

int main(int argc, char **argv) {
  CHECK(initialized == 1 && lifetime.memory[4095] == 91);
  CHECK(argc == 4 && !strcmp(argv[0], "main-proof") && !strcmp(argv[2], "quoted \"text\"") &&
        !strcmp(argv[3], "back\\slash") && argv[4] == nullptr);
  CHECK(!strcmp(argv[1], "clean") || !strcmp(argv[1], "failure"));
  int result = !strcmp(argv[1], "failure") ? 7 : 0;
  argv[2][0] = 'Q'; CHECK(argv[2][0] == 'Q');
  char text[64]; double number = 0; unsigned integer = 0;
  CHECK(snprintf(text, sizeof(text), "%u %.3f", 123u, 0.125) == 9);
  CHECK(sscanf(text, "%u %lf", &integer, &number) == 2 && integer == 123 && number == 0.125);
  volatile double angle = 0.5; CHECK(fabs(sin(angle) - 0.479425538604203) < 1e-14);
  auto *zone = static_cast<unsigned char *>(calloc(6*1024*1024, 1));
  CHECK(zone && !zone[0] && !zone[6*1024*1024-1]); zone[0] = 42;
  errno = 0; CHECK(!realloc(zone, 9*1024*1024) && errno == ENOMEM && zone[0] == 42);
  uint32_t before = lefony_millis(); CHECK(lefony_program_sleep(50) == 0);
  CHECK(static_cast<uint32_t>(lefony_millis() - before) >= 50 && zone[0] == 42);
  free(zone);
  struct timeval wall;
  errno = 0; CHECK(gettimeofday(&wall, nullptr) == -1 && errno == ENOSYS);
  errno = 0; CHECK(write(1, "no console", 10) == -1 && errno == EBADF);
  FILE *f = fopen("order", "wb");
  CHECK(f && fwrite("M", 1, 1, f) == 1 && fclose(f) == 0);
  CHECK(atexit(finish) == 0);
  return result;
}
