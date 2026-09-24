// SPDX-License-Identifier: GPL-3.0-or-later
#define _POSIX_C_SOURCE 200809L
#include <lefony/files.h>
#include <lefony/file_writer.h>
#include <lefony/foreground.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#define check(yes) do {if(!(yes)) __asm__ volatile("udf %0" :: "I"(__LINE__));} while(0)
static void value(const char *expected) {
  char bytes[64]{};int fd=open("value",O_RDONLY);check(fd>=0);
  check(read(fd,bytes,sizeof(bytes))==static_cast<int>(strlen(expected)) && !strcmp(bytes,expected));check(close(fd)==0);
}
int main(int argc,char **argv) {
  check(argc==2);
  if(strcmp(argv[1],"normal")) {
    int expected=!strcmp(argv[1],"denied")?EACCES:ENOSYS;
    check(lefony_file_abort(0)==-1 && errno==expected);
    Lefony::FileWriter writer;check(!writer.begin("must-not-exist") && writer.error()==expected && !writer.active());
    struct stat info;check(stat("must-not-exist",&info)==-1 && errno==ENOENT);return 0;
  }
  struct stat marker;if(stat("complete",&marker)==0) {value("final");return 0;}
  Lefony::FileWriter writer;check(writer.begin("value") && writer.write("original",8) && writer.commit());
  int reader=open("value",O_RDONLY);check(reader>=0);
  check(writer.begin("value") && writer.write("invalid",7));check(writer.cancel() && !writer.active());value("original");
  check(lefony_file_abort(reader)==-1 && errno==EBADF);char bytes[16]{};
  check(read(reader,bytes,sizeof(bytes))==8 && !strcmp(bytes,"original"));check(close(reader)==0);
  {Lefony::FileWriter discarded;check(discarded.begin("value") && discarded.write("destructor",10));}value("original");
  check(writer.begin("value") && !writer.write(nullptr,4) && writer.error()==EINVAL && !writer.active());value("original");
  int fd=open("value",O_WRONLY|O_TRUNC);check(fd>=0 && write(fd,"synced",6)==6 && fsync(fd)==0);
  check(write(fd,"-discarded",10)==10 && lefony_file_abort(fd)==0);value("synced");
  check(close(fd)==-1 && errno==EBADF);int stale=fd;
  fd=open("value",O_WRONLY|O_TRUNC);check(fd>=0 && fd!=stale && write(fd,"accepted",8)==8);
  check(lefony_file_abort(stale)==-1 && errno==EBADF && close(fd)==0);value("accepted");
  // Stdio cleanup after abort cannot flush buffered bytes into a new file.
  FILE *stream=fopen("value","wb");check(stream && fwrite("buffered",1,8,stream)==8);
  check(lefony_file_abort(fileno(stream))==0);check(fclose(stream)==EOF);value("accepted");
  stream=fopen("value","wb");check(stream && fwrite("flushed",1,7,stream)==7 && fflush(stream)==0);
  check(lefony_file_abort(fileno(stream))==0);check(fclose(stream)==EOF);value("accepted");
  // Large writes exercise the adapter's short-transfer loop over public calls.
  char block[8193];for(unsigned i=0;i<sizeof(block);i++) block[i]=static_cast<char>(i*17u);
  check(writer.begin("large") && writer.write(block,sizeof(block)) && writer.commit());
  stream=fopen("large","rb");check(stream);char copied[8193];check(fread(copied,1,sizeof(copied),stream)==sizeof(copied));
  check(fclose(stream)==0 && !memcmp(block,copied,sizeof(block)));
  check(writer.begin("not-published") && writer.write(block,sizeof(block)) && writer.cancel());
  struct stat info;check(stat("not-published",&info)==-1 && errno==ENOENT);
  check(writer.begin("value") && writer.write("final",5) && writer.commit());value("final");
  check(writer.begin("complete") && writer.write("done",4) && writer.commit());return 0;
}
