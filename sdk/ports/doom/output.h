/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Doom's checked use of the public SDK file transaction API. */
#ifndef LEFONY_DOOM_OUTPUT_H
#define LEFONY_DOOM_OUTPUT_H
#include <stdio.h>
FILE *DG_OpenOutput(const char *path);
int DG_FinishOutput(FILE *stream,int complete);
void DG_DiscardOutput(void);
FILE *DG_OpenConfigInput(const char *path);
#endif
