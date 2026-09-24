/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/foreground.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int message(const char *text, int error) {
  lefony_fill((lefony_rect_t){0, 0, 320, 240, LEFONY_WHITE});
  lefony_text((lefony_text_t){12, 24, error ? 0xf800 : LEFONY_GREEN,
                            LEFONY_WHITE, text, strlen(text)});
  lefony_program_yield();
  return error;
}

int main(int argc, char **argv) {
  if (argc != 2) return message("Expected a data filename", 1);
  unsigned visits = 0;
  FILE *input = fopen(argv[1], "rb");
  if (input) {
    int valid = fscanf(input, "%u", &visits) == 1;
    if (fclose(input) != 0 || !valid) return message("Cannot read saved visits", 1);
  } else if (errno != ENOENT) return message("Cannot open saved visits", 1);
  FILE *output = fopen(argv[1], "wb");
  if (!output) return message("Cannot create visit file", 1);
  if (fprintf(output, "%u\n", ++visits) < 0) {
    /* Returning runs stream cleanup; check errors before promising a save. */
    fclose(output);
    return message("Write failed", 1);
  }
  if (fclose(output) != 0) return message("Save failed", 1);
  char text[64];
  snprintf(text, sizeof(text), "C main: %u saved visits", visits);
  message(text, 0);
  lefony_program_sleep(500);
  return 0;
}
