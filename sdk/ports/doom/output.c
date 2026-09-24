/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Keep processing failures separate from the final atomic file commit. */
#include "output.h"
#include <lefony/files.h>
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>
static FILE *output;
static int descriptor=-1;

void DG_DiscardOutput(void) {
    if(descriptor>=0) {
        /* An uncertain discard must not be followed by exit's stream flush. */
        if(lefony_file_abort(descriptor)<0 && errno!=EBADF) _exit(-1);
        descriptor=-1;
    }
    if(output) {
        FILE *stream=output;output=NULL;
        /* The invalidated descriptor cannot publish any remaining buffer. */
        (void)fclose(stream);
    }
}

FILE *DG_OpenOutput(const char *path) {
    if(output || descriptor>=0) {errno=EBUSY;return NULL;}
    /* Negotiate discard before acquiring a writer, including on older OSes. */
    if(lefony_file_abort(0)!=-1 || errno!=EBADF) return NULL;
    output=fopen(path,"wb");
    if(output) descriptor=fileno(output);
    return output;
}

int DG_FinishOutput(FILE *stream,int complete) {
    if(!stream || stream!=output) {errno=EINVAL;return -1;}
    if(!complete || ferror(stream) || fflush(stream)) {
        DG_DiscardOutput();return -1;
    }
    /* fflush has staged every byte. fclose is the one commit; an error means
     * the caller must treat its outcome as unconfirmed and inspect/retry. */
    output=NULL;
    int result=fclose(stream);
    if(result) DG_DiscardOutput();
    descriptor=-1;
    return result;
}

FILE *DG_OpenConfigInput(const char *path) {
    FILE *stream=fopen(path,"rb");
    if(!stream) return NULL;
    struct stat info;
    int failed=fstat(fileno(stream),&info);
    if(failed || info.st_size>65536) {
        int error=failed?errno:EFBIG;
        (void)fclose(stream);errno=error;return NULL;
    }
    return stream;
}
