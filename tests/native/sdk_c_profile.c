/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* Public foreground-newlib-1 conformance. No replacement allocator/syscalls. */
#define _POSIX_C_SOURCE 200809L
#include <lefony/files.h>
#include <lefony/foreground.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <float.h>
#include <limits.h>
#include <inttypes.h>
#include <locale.h>
#include <math.h>
#include <signal.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/times.h>
#include <unistd.h>

volatile unsigned profile_checks, profile_failure_line;
/* Only the boundary fixture waits here; its harness seeds synthetic OS state. */
volatile unsigned profile_gate;
volatile int profile_handles[8];
#define CHECK(c) do { ++profile_checks; if (!(c)) { profile_failure_line=__LINE__; lefony_program_exit(__LINE__); for (;;) {} } } while (0)
static unsigned char bytes[8193];
static unsigned char pattern(unsigned offset) { return (unsigned char)((offset*131u+(offset>>8))^0x5d); }
static void close_ok(FILE *file) { CHECK(file && fclose(file)==0); }

static void memory(void) {
  LefonyProgramRequest info; CHECK(lefony_program_info(&info)==0 && info.heapBytes==8380416);
  for (unsigned n=1;n<2048;n=n*2+1) {
    unsigned char *p=calloc(n,1); CHECK(p && (uintptr_t)p%_Alignof(max_align_t)==0);
    for (unsigned i=0;i<n;i++) CHECK(p[i]==0);
    memset(p,91,n); unsigned char *grown=realloc(p,n+4096); CHECK(grown);
    for (unsigned i=0;i<n;i++) CHECK(grown[i]==91);
    p=realloc(grown,n); CHECK(p && p[n-1]==91); free(p);
  }
  volatile size_t huge=SIZE_MAX; errno=0;
  CHECK(calloc(huge,2)==NULL && errno==ENOMEM);
  errno=0; CHECK(malloc(huge)==NULL && errno==ENOMEM);
  unsigned char *held=malloc(64); CHECK(held); memset(held,123,64);
  errno=0; CHECK(realloc(held,info.heapBytes+1)==NULL && errno==ENOMEM);
  for (unsigned i=0;i<64;i++) CHECK(held[i]==123);
  free(held); free(NULL);
  void *zero=malloc(0); free(zero); zero=calloc(0,37); free(zero);
  void *blocks[256]; unsigned count=0;
  while (count<256 && (blocks[count]=malloc(32768))) {
    memset(blocks[count],(int)count,32768); ++count;
  }
  CHECK(count>200 && count<256 && errno==ENOMEM);
  while (count) { --count; CHECK(((unsigned char *)blocks[count])[32767]==(unsigned char)count); free(blocks[count]); }
  held=malloc(6*1024*1024); CHECK(held); held[6*1024*1024-1]=42;
  CHECK(held[6*1024*1024-1]==42); free(held);
}

static void strings(void) {
  char a[64],b[64]; CHECK(memset(a,'x',sizeof(a))==a);
  CHECK(memcpy(b,a,sizeof(a))==b && memcmp(a,b,sizeof(a))==0);
  CHECK(memchr(a,'x',sizeof(a))==a && !memchr(a,'y',sizeof(a)));
  CHECK(strcpy(a,"abcdef")==a && strlen(a)==6);
  CHECK(memmove(a+2,a,5)==a+2 && memcmp(a,"ababcde",7)==0);
  CHECK(memmove(a,a+2,5)==a && memcmp(a,"abcde",5)==0);
  CHECK(strncpy(b,"xy",6)==b && memcmp(b,"xy\0\0\0\0",6)==0);
  CHECK(strcpy(a,"one")==a && strcat(a," two")==a && strncat(a," three",3)==a);
  CHECK(strcmp(a,"one two th")==0 && strncmp(a,"one!",3)==0 && strcmp("a","b")<0);
  CHECK(strchr(a,'t')==a+4 && strrchr(a,'t')==a+8 && strchr(a,0)==a+10);
  CHECK(strstr(a,"two")==a+4 && !strstr(a,"four"));
  const char *delimited="abc:def";
  CHECK(strspn("aabbc","ab")==4 && strcspn(delimited,":")==3 && strpbrk(delimited,":!")==strchr(delimited,':'));
  strcpy(a,"a,,b;c"); CHECK(!strcmp(strtok(a,",;"),"a")); CHECK(!strcmp(strtok(NULL,",;"),"b"));
  CHECK(!strcmp(strtok(NULL,",;"),"c") && strtok(NULL,",;")==NULL);
  CHECK(setlocale(LC_ALL,"C") && !strcmp(setlocale(LC_ALL,NULL),"C"));
  CHECK(!strcmp(localeconv()->decimal_point,"."));
  for (int c=0;c<128;c++) {
    int digit=c>='0'&&c<='9',upper=c>='A'&&c<='Z',lower=c>='a'&&c<='z';
    CHECK((!!isdigit(c))==digit && (!!isalpha(c))==(upper||lower) && (!!isalnum(c))==(digit||upper||lower));
    CHECK((!!isupper(c))==upper && (!!islower(c))==lower && (!!isxdigit(c))==(digit||(c>='a'&&c<='f')||(c>='A'&&c<='F')));
    CHECK((!!isspace(c))==(c==' '||(c>=9&&c<=13)) && (!!isblank(c))==(c==' '||c=='\t'));
    CHECK((!!iscntrl(c))==(c<32||c==127) && (!!isprint(c))==(c>=32&&c<127) && (!!isgraph(c))==(c>32&&c<127));
    CHECK((!!ispunct(c))==(c>32&&c<127&&!digit&&!upper&&!lower));
    CHECK(tolower(c)==(upper?c+32:c) && toupper(c)==(lower?c-32:c));
  }
  CHECK(!isalpha(EOF) && !isdigit(EOF) && tolower(EOF)==EOF && toupper(EOF)==EOF);
}

static int format(char *out,size_t size,const char *spec,...) {
  va_list ap;va_start(ap,spec);int result=vsnprintf(out,size,spec,ap);va_end(ap);return result;
}
static int scan(const char *in,const char *spec,...) {
  va_list ap;va_start(ap,spec);int result=vsscanf(in,spec,ap);va_end(ap);return result;
}
static int compare(const void *a,const void *b) { int x=*(const int *)a,y=*(const int *)b; return (x>y)-(x<y); }
static void numbers(void) {
  CHECK(sizeof(long)==4 && sizeof(long long)==8 && sizeof(double)==8 && CHAR_BIT==8);
  char out[96],*end; CHECK(snprintf(out,sizeof(out),"%d %08x %.3f %s",-27,42,1.25,"ARM")==22);
  CHECK(!strcmp(out,"-27 0000002a 1.250 ARM"));
  CHECK(format(out,4,"%s","abcdef")==6 && !strcmp(out,"abc"));
  CHECK(snprintf(NULL,0,"%llu",18446744073709551615ULL)==20);
  CHECK(snprintf(out,sizeof(out),"%lld %llu",LLONG_MIN,ULLONG_MAX)==41);
  CHECK(!strcmp(out,"-9223372036854775808 18446744073709551615"));
  CHECK(snprintf(out,sizeof(out),"%zu %td %jd",(size_t)123,(ptrdiff_t)-2,(intmax_t)-4294967297LL)>0);
  CHECK(!strcmp(out,"123 -2 -4294967297"));
  CHECK(snprintf(out,sizeof(out),"%a",1.5)>0 && strtod(out,&end)==1.5 && !*end);
  long long signed_value=0;unsigned long long unsigned_value=0;size_t size=0;
  CHECK(sscanf("-9223372036854775808 18446744073709551615 123","%lld %llu %zu",&signed_value,&unsigned_value,&size)==3);
  CHECK(signed_value==LLONG_MIN && unsigned_value==ULLONG_MAX && size==123);
  CHECK(strtol(" -123tail",&end,10)==-123 && !strcmp(end,"tail"));
  CHECK(strtoul("0xff!",&end,0)==255 && *end=='!');
  CHECK(strtoll("-9223372036854775808",&end,10)==LLONG_MIN && !*end);
  CHECK(strtoull("18446744073709551615",&end,10)==ULLONG_MAX && !*end);
  errno=0;CHECK(strtol("2147483648!",&end,10)==LONG_MAX && errno==ERANGE && *end=='!');
  errno=0;CHECK(strtoul("4294967296",&end,10)==ULONG_MAX && errno==ERANGE);
  errno=0;const char *invalid="not-a-number"; CHECK(strtol(invalid,&end,10)==0 && end==invalid && errno==0);
  CHECK(strtod("1.25e2!",&end)==125 && *end=='!' && strtof("0x1.8p2",&end)==6 && !*end);
  errno=0;CHECK(isinf(strtod("1e9999",&end)) && errno==ERANGE && !*end);
  errno=0;CHECK(strtod("1e-9999",&end)==0 && errno==ERANGE && !*end);
  CHECK(signbit(strtod("-0",&end)) && !*end);
  CHECK(atoi("-12")==-12 && atol("1234")==1234 && atoll("4294967297")==4294967297LL && atof("2.5")==2.5);
  int n=0;double d=0;char word[8]; CHECK(sscanf("42 2.5 hello","%d %lf %7s",&n,&d,word)==3 && n==42 && d==2.5 && !strcmp(word,"hello"));
  CHECK(scan("0xff 17","%i %lf",&n,&d)==2 && n==255 && d==17);
  n=91;CHECK(sscanf("wrong","%d",&n)==0 && n==91);
  int values[]={5,-2,19,0,5};qsort(values,5,sizeof(int),compare); CHECK(values[0]==-2 && values[4]==19);
  int key=0;CHECK(bsearch(&key,values,5,sizeof(int),compare)==values+1);key=77;CHECK(!bsearch(&key,values,5,sizeof(int),compare));
  CHECK(abs(-17)==17 && labs(-123L)==123 && llabs(-4294967297LL)==4294967297LL);
  div_t a=div(-17,5);ldiv_t b=ldiv(-17L,5L);lldiv_t c=lldiv(-17LL,5LL);
  CHECK(a.quot==-3 && a.rem==-2 && b.quot==-3 && b.rem==-2 && c.quot==-3 && c.rem==-2);
  srand(17);int first=rand(),second=rand();srand(17);CHECK(rand()==first && rand()==second && first>=0 && first<=RAND_MAX);
}

static void mathematics(void) {
  volatile double x=.5,two=2.0,negative=-1.0,zero=0.0;
  CHECK(fabs(sin(x)-0.479425538604203)<1e-14 && fabs(cos(x)-0.877582561890373)<1e-14);
  CHECK(fabs(tan(x)-0.546302489843791)<1e-14 && fabs(atan2(x,two)-0.244978663126864)<1e-14);
  CHECK(fabs(sqrt(two)-1.4142135623730951)<1e-14 && fabs(hypot(3.0,two*2)-5)<1e-14);
  CHECK(fabs(exp(x)-1.648721270700128)<1e-14 && fabs(log(two)-0.6931471805599453)<1e-14);
  CHECK(pow(two,10)==1024 && log10(100)==2);
  CHECK(floor(-x)==-1 && ceil(x)==1 && trunc(-x)==0 && round(-x)==-1 && fmod(7.5,two)==1.5);
  int exponent=0;double integer=0;CHECK(frexp(12.0,&exponent)==.75 && exponent==4 && ldexp(.75,4)==12);
  CHECK(modf(-2.75,&integer)==-.75 && integer==-2 && signbit(copysign(0.0,negative)));
  CHECK(isfinite(two) && !isfinite(INFINITY) && isnan(NAN) && isinf(INFINITY));
  CHECK(fpclassify(zero)==FP_ZERO && fpclassify(DBL_MIN)==FP_NORMAL);
  errno=0;double domain=sqrt(negative);CHECK(isnan(domain));
  if (math_errhandling&MATH_ERRNO) CHECK(errno==EDOM);
  errno=0;double pole=log(zero);CHECK(isinf(pole) && signbit(pole));
  if (math_errhandling&MATH_ERRNO) CHECK(errno==ERANGE);
}

static void verify_large(FILE *file) {
  unsigned offset=0;size_t got;
  while ((got=fread(bytes,1,sizeof(bytes),file))) {
    for (size_t i=0;i<got;i++) CHECK(bytes[i]==pattern(offset+(unsigned)i));
    offset+=(unsigned)got;
  }
  CHECK(offset==65549 && feof(file) && !ferror(file));
}
static void streams(void) {
  FILE *file=fopen("large","rb");if (file) { verify_large(file);close_ok(file); }
  else CHECK(errno==ENOENT);
  file=fopen("large","wb");CHECK(file);char buffer[3072];CHECK(setvbuf(file,buffer,_IOFBF,sizeof(buffer))==0);
  for (unsigned offset=0;offset<65549;) {
    size_t n=65549-offset;if (n>sizeof(bytes)) n=sizeof(bytes);
    for (size_t i=0;i<n;i++) bytes[i]=pattern(offset+(unsigned)i);
    CHECK(fwrite(bytes,1,n,file)==n);offset+=(unsigned)n;
  }
  CHECK(fflush(file)==0 && ftell(file)==65549 && fsync(fileno(file))==0);close_ok(file);
  file=fopen("large","rb");CHECK(file);verify_large(file);
  clearerr(file);CHECK(!feof(file) && !ferror(file));rewind(file);CHECK(ftell(file)==0);
  CHECK(fgetc(file)==pattern(0) && ungetc(77,file)==77 && getc(file)==77 && fgetc(file)==pattern(1));
  fpos_t pos;CHECK(fgetpos(file,&pos)==0);CHECK(fseek(file,-1,SEEK_END)==0 && ftell(file)==65548 && fgetc(file)==pattern(65548));
  CHECK(fsetpos(file,&pos)==0 && ftell(file)==2);close_ok(file);
  file=fopen("text","w+b");CHECK(file && setvbuf(file,NULL,_IONBF,0)==0);
  CHECK(fprintf(file,"%d %.2f\n",42,1.25)==8 && fputs("hello",file)>=0 && fputc('\n',file)=='\n' && putc('Z',file)=='Z');
  CHECK(fseek(file,0,SEEK_SET)==0);int n=0;double d=0;CHECK(fscanf(file,"%d %lf",&n,&d)==2 && n==42 && d==1.25);
  CHECK(fgetc(file)=='\n' && fgets((char *)bytes,16,file)==(char *)bytes && !strcmp((char *)bytes,"hello\n"));
  CHECK(fgetc(file)=='Z' && fgetc(file)==EOF && feof(file));close_ok(file);
  file=fopen("text","rb");CHECK(file);errno=0;CHECK(fputc('X',file)==EOF);
  CHECK(ferror(file));CHECK(errno==EBADF);
  clearerr(file);CHECK(!ferror(file));close_ok(file);
}

static void descriptors(void) {
  if (mkdir("dir",0700)!=0) CHECK(errno==EEXIST);
  int fd=open("./dir/file",O_CREAT|O_TRUNC|O_RDWR,0600);CHECK(fd>2);
  for (unsigned i=0;i<sizeof(bytes);i++) bytes[i]=pattern(i);
  CHECK(write(fd,bytes,sizeof(bytes))==2048 && lseek(fd,0,SEEK_CUR)==2048);
  CHECK(lseek(fd,0,SEEK_SET)==0 && read(fd,bytes,sizeof(bytes))==2048 && read(fd,bytes,1)==0);
  CHECK(lseek(fd,4096,SEEK_SET)==4096 && write(fd,"Z",1)==1 && fsync(fd)==0);
  struct stat info;CHECK(fstat(fd,&info)==0 && S_ISREG(info.st_mode) && info.st_size==4097);
  CHECK(close(fd)==0 && stat("dir/file",&info)==0 && info.st_size==4097);
  fd=open("dir/file",O_WRONLY|O_APPEND);CHECK(fd>2 && lseek(fd,0,SEEK_SET)==0 && write(fd,"A",1)==1 && close(fd)==0);
  CHECK(stat("dir/file",&info)==0 && info.st_size==4098);
  fd=open("dir/file",O_RDONLY);CHECK(fd>2);FILE *file=fdopen(fd,"rb");CHECK(file && fileno(file)==fd);
  CHECK(fseek(file,4096,SEEK_SET)==0 && fgetc(file)=='Z' && fgetc(file)=='A');close_ok(file);
  errno=0;CHECK(close(fd)==-1 && errno==EBADF);
  CHECK(rename("dir/file","descriptor-output")==0 && stat("dir",&info)==0 && S_ISDIR(info.st_mode));
  CHECK(unlink("dir")==0);
  file=fopen("descriptor-output","rb");CHECK(file);
  CHECK(fread(bytes,1,sizeof(bytes),file)==4098);
  for (unsigned i=0;i<2048;i++) CHECK(bytes[i]==pattern(i));
  for (unsigned i=2048;i<4096;i++) CHECK(bytes[i]==0);
  CHECK(bytes[4096]=='Z' && bytes[4097]=='A');close_ok(file);
}

/* Public byte offsets straddle both 2 KiB transfers and the current storage
 * chunks. The oracle is file contents, never private filesystem structures. */
enum { MultiBytes=262175, FirstPatch=130940, SecondPatch=261880, GapEnd=262151 };
static void write_pattern(FILE *file,unsigned length) {
  for (unsigned at=0;at<length;) {
    unsigned n=length-at;if (n>sizeof(bytes)) n=sizeof(bytes);
    for (unsigned i=0;i<n;i++) bytes[i]=pattern(at+i);
    CHECK(fwrite(bytes,1,n,file)==n);at+=n;
  }
}
static void read_pattern(FILE *file,unsigned length,int patched) {
  unsigned at=0;size_t got;
  while ((got=fread(bytes,1,sizeof(bytes),file))) {
    CHECK(got<=length-at);
    for (unsigned i=0;i<got;i++) {
      unsigned position=at+i;unsigned char expected=pattern(position);
      if (patched && position>=FirstPatch && position<FirstPatch+37) expected='A';
      if (patched && position>=SecondPatch && position<SecondPatch+17) expected='B';
      CHECK(bytes[i]==expected);
    }
    at+=(unsigned)got;
  }
  CHECK(at==length && feof(file) && !ferror(file));
}
static void stream_update(void) {
  FILE *file=fopen("multi-update","w+b");CHECK(file);char buffer[3073];
  CHECK(setvbuf(file,buffer,_IOFBF,sizeof(buffer))==0);
  write_pattern(file,MultiBytes);
  /* Positioning itself must flush output and allow a subsequent read. */
  CHECK(fseek(file,FirstPatch,SEEK_SET)==0 && ftell(file)==FirstPatch);
  fpos_t first;CHECK(fgetpos(file,&first)==0 && fgetc(file)==pattern(FirstPatch));
  CHECK(fsetpos(file,&first)==0);
  memset(bytes,'A',37);CHECK(fwrite(bytes,1,37,file)==37);
  CHECK(fseek(file,SecondPatch-MultiBytes,SEEK_END)==0 && ftell(file)==SecondPatch);
  memset(bytes,'B',17);CHECK(fwrite(bytes,1,17,file)==17);
  CHECK(fflush(file)==0 && fsync(fileno(file))==0 && ftell(file)==SecondPatch+17);
  CHECK(fsetpos(file,&first)==0 && fgetc(file)=='A');
  rewind(file);CHECK(!feof(file) && !ferror(file) && ftell(file)==0);
  read_pattern(file,MultiBytes,1);close_ok(file);
  file=fopen("multi-update","rb");CHECK(file);read_pattern(file,MultiBytes,1);close_ok(file);
}
static void stream_append(void) {
  FILE *file=fopen("append-existing","wb");CHECK(file && fputs("seed",file)>=0);close_ok(file);
  file=fopen("append-existing","a+b");CHECK(file);char buffer[7];
  CHECK(setvbuf(file,buffer,_IOFBF,sizeof(buffer))==0);
  CHECK(fseek(file,0,SEEK_SET)==0 && fread(bytes,1,4,file)==4 && !memcmp(bytes,"seed",4));
  CHECK(fseek(file,0,SEEK_SET)==0 && fwrite("first",1,5,file)==5);
  CHECK(fflush(file)==0 && fsync(fileno(file))==0 && ftell(file)==9);
  CHECK(fseek(file,-2,SEEK_END)==0 && fgetc(file)=='s' && fgetc(file)=='t' && fgetc(file)==EOF && feof(file));
  /* Input reaching EOF permits output on an update stream without a seek. */
  CHECK(fwrite("next",1,4,file)==4 && fflush(file)==0 && fsync(fileno(file))==0 && ftell(file)==13);
  CHECK(fseek(file,0,SEEK_SET)==0 && fwrite("last",1,4,file)==4);close_ok(file);
  file=fopen("append-existing","rb");CHECK(file);
  CHECK(fread(bytes,1,sizeof(bytes),file)==17 && !memcmp(bytes,"seedfirstnextlast",17));close_ok(file);
  /* A seek beyond EOF in append mode must not create a hole. */
  remove("append-new");file=fopen("append-new","a+b");CHECK(file);
  CHECK(fseek(file,GapEnd,SEEK_SET)==0 && fwrite("one",1,3,file)==3);
  CHECK(fflush(file)==0 && fsync(fileno(file))==0 && ftell(file)==3);
  CHECK(fseek(file,0,SEEK_SET)==0 && fread(bytes,1,sizeof(bytes),file)==3 && !memcmp(bytes,"one",3));close_ok(file);
}
static void stream_snapshots(void) {
  FILE *file=fopen("snapshot","wb");CHECK(file);write_pattern(file,MultiBytes);close_ok(file);
  FILE *old=fopen("snapshot","rb");CHECK(old);
  /* Leave prefetched bytes and an unread second storage chunk in this reader. */
  CHECK(fread(bytes,1,13,old)==13);
  file=fopen("snapshot","wb");CHECK(file && fputs("replacement",file)>=0);
  CHECK(fflush(file)==0 && fsync(fileno(file))==0);
  FILE *current=fopen("snapshot","rb");CHECK(current);close_ok(file);
  CHECK(rename("snapshot","snapshot-moved")==0);
  file=fopen("snapshot","wb");CHECK(file && fputs("temporary",file)>=0);close_ok(file);
  CHECK(unlink("snapshot")==0);
  rewind(old);read_pattern(old,MultiBytes,0);close_ok(old);
  CHECK(fread(bytes,1,sizeof(bytes),current)==11 && !memcmp(bytes,"replacement",11));close_ok(current);
  file=fopen("snapshot-moved","rb");CHECK(file);
  CHECK(fread(bytes,1,sizeof(bytes),file)==11 && !memcmp(bytes,"replacement",11));close_ok(file);
}
static void stream_position(void) {
  FILE *file=fopen("seek-gap","w+b");CHECK(file);
  CHECK(fwrite("head",1,4,file)==4 && fseek(file,GapEnd,SEEK_SET)==0 && fwrite("tail",1,4,file)==4);
  CHECK(fflush(file)==0 && fsync(fileno(file))==0 && ftell(file)==GapEnd+4);
  CHECK(fseek(file,0,SEEK_END)==0 && fgetc(file)==EOF && feof(file));
  CHECK(ungetc('Q',file)=='Q' && !feof(file) && ftell(file)==GapEnd+3);
  fpos_t pushed;CHECK(fgetpos(file,&pushed)==0);
  CHECK(fgetc(file)=='Q' && fgetc(file)==EOF && feof(file));
  CHECK(fsetpos(file,&pushed)==0 && !feof(file) && fgetc(file)=='l');
  CHECK(fseek(file,-4,SEEK_CUR)==0 && ftell(file)==GapEnd && fgetc(file)=='t');
  rewind(file);unsigned at=0;size_t got;
  while ((got=fread(bytes,1,sizeof(bytes),file))) {
    CHECK(got<=GapEnd+4-at);
    for (unsigned i=0;i<got;i++) {
      unsigned position=at+i;
      CHECK(bytes[i]==(position<4?"head"[position]:position>=GapEnd?"tail"[position-GapEnd]:0));
    }
    at+=(unsigned)got;
  }
  CHECK(at==GapEnd+4 && feof(file) && !ferror(file));close_ok(file);
}

static void file_errors(void) {
  errno=0;CHECK(open("missing",O_RDONLY)==-1 && errno==ENOENT);
  errno=0;CHECK(open("../escape",O_RDONLY)==-1 && errno==EINVAL);
  errno=0;CHECK(open("/absolute",O_RDONLY)==-1 && errno==EINVAL);
  errno=0;CHECK(open("bad",O_RDONLY|O_TRUNC)==-1 && errno==EINVAL);
  int fd=open("present",O_CREAT|O_TRUNC|O_WRONLY,0600);CHECK(fd>2);
  errno=0;CHECK(open("another",O_CREAT|O_WRONLY,0600)==-1 && errno==EBUSY);
  errno=0;CHECK(read(fd,bytes,1)==-1 && errno==EBADF);
  CHECK(write(fd,"safe",4)==4 && close(fd)==0);
  errno=0;CHECK(open("present",O_CREAT|O_EXCL|O_WRONLY,0600)==-1 && errno==EEXIST);
  int readers[4];for (unsigned i=0;i<4;i++) { readers[i]=open("present",O_RDONLY);CHECK(readers[i]>2); }
  errno=0;CHECK(open("present",O_RDONLY)==-1 && errno==EMFILE);
  errno=0;CHECK(write(readers[0],"no",2)==-1 && errno==EBADF);
  errno=0;CHECK(lseek(readers[0],-1,SEEK_SET)==-1 && errno==EINVAL);
  errno=0;CHECK(lseek(readers[0],0,999)==-1 && errno==EINVAL);
  for (unsigned i=0;i<4;i++) CHECK(close(readers[i])==0);
  CHECK(mkdir("folder",0700)==0);errno=0;CHECK(open("folder",O_RDONLY)==-1 && errno==EISDIR);
  FILE *file=fopen("folder/item","wb");CHECK(file && fputs("item",file)>=0);close_ok(file);
  errno=0;CHECK(remove("folder")==-1 && errno==ENOTEMPTY);
  CHECK(remove("folder/item")==0 && remove("folder")==0);
  errno=0;CHECK(read(0,bytes,1)==-1 && errno==EBADF);
  errno=0;CHECK(write(1,"no console",10)==-1 && errno==EBADF);
  errno=0;CHECK(close(2)==-1 && errno==EBADF);
}

static void high_handles(void) {
  while (!profile_gate) CHECK(lefony_program_yield()==0);
  for (unsigned i=0;i<4;i++) {
    FILE *file=fopen("high-handle","wb");CHECK(file);
    int writer=fileno(file);profile_handles[i*2]=writer;CHECK(writer>=32767);
    CHECK(fwrite("safe",1,4,file)==4 && fflush(file)==0 && fsync(writer)==0);close_ok(file);
    int reader=open("high-handle",O_RDONLY);profile_handles[i*2+1]=reader;CHECK(reader>writer);
    file=fdopen(reader,"rb");CHECK(file && fileno(file)==reader);
    CHECK(fread(bytes,1,4,file)==4 && memcmp(bytes,"safe",4)==0);close_ok(file);
    errno=0;CHECK(close(writer)==-1 && errno==EBADF);
    errno=0;CHECK(close(reader)==-1 && errno==EBADF);
  }
}

static void unsupported(void) {
  struct timeval wall={123,456};struct tms cpu={0};
  errno=0;CHECK(gettimeofday(&wall,NULL)==-1 && errno==ENOSYS && wall.tv_sec==123 && wall.tv_usec==456);
  errno=0;CHECK(times(&cpu)==(clock_t)-1 && errno==ENOSYS);
  errno=0;CHECK(getpid()==-1 && errno==ENOSYS);
  errno=0;CHECK(kill(1,0)==-1 && errno==ENOSYS);
  errno=0;CHECK(isatty(1)==0 && errno==ENOTTY);
  uint32_t before=lefony_millis();CHECK(lefony_program_sleep(20)==0);
  CHECK((uint32_t)(lefony_millis()-before)>=20 && lefony_program_yield()==0);
}

static void append_exit(char c) { FILE *file=fopen("exit-order","ab");CHECK(file && fputc(c,file)==c);close_ok(file); }
static void finish_a(void) { append_exit('A'); }
static void finish_b(void) { append_exit('B'); }
static char exit_buffer[1024];
int main(int argc,char **argv) {
  CHECK(argc==2 && argv[argc]==NULL && !strcmp(argv[0],"c-profile"));
  const char *mode=argv[1];
  if (!strcmp(mode,"memory")) memory();
  else if (!strcmp(mode,"strings")) strings();
  else if (!strcmp(mode,"numbers")) numbers();
  else if (!strcmp(mode,"math")) mathematics();
  else if (!strcmp(mode,"stdio")) streams();
  else if (!strcmp(mode,"descriptors")) descriptors();
  else if (!strcmp(mode,"stdio-update")) stream_update();
  else if (!strcmp(mode,"stdio-append")) stream_append();
  else if (!strcmp(mode,"stdio-snapshots")) stream_snapshots();
  else if (!strcmp(mode,"stdio-position")) stream_position();
  else if (!strcmp(mode,"file-errors")) file_errors();
  else if (!strcmp(mode,"high-handles")) high_handles();
  else if (!strcmp(mode,"unsupported")) unsupported();
  else if (!strcmp(mode,"implicit-exit") || !strcmp(mode,"implicit-error") ||
           !strcmp(mode,"immediate-unclosed") || !strcmp(mode,"flush-all")) {
    FILE *file=fopen("automatic","wb");CHECK(file && setvbuf(file,exit_buffer,_IOFBF,sizeof(exit_buffer))==0);
    if (!strcmp(mode,"flush-all")) {
      CHECK(fputs("one",file)>=0 && fflush(NULL)==0);
      CHECK(fputs("two",file)>=0 && fflush(NULL)==0 && fsync(fileno(file))==0);
      /* Check both flushes before exit, independently of automatic close. */
      FILE *snapshot=fopen("automatic","rb");CHECK(snapshot);
      CHECK(fread(bytes,1,sizeof(bytes),snapshot)==6 && !memcmp(bytes,"onetwo",6));
      close_ok(snapshot);
      CHECK(fputs("three",file)>=0);
    } else CHECK(fputs("after",file)>=0);
    if (!strcmp(mode,"immediate-unclosed")) _Exit(7);
    if (!strcmp(mode,"implicit-error")) exit(7);
    return 0; /* Standard exit owns this still-open stream's cleanup. */
  }
  else if (!strcmp(mode,"exit") || !strcmp(mode,"immediate-exit")) {
    FILE *file=fopen("exit-order","wb");CHECK(file && fputc('M',file)=='M');close_ok(file);
    CHECK(atexit(finish_a)==0 && atexit(finish_b)==0);
    if (!strcmp(mode,"immediate-exit")) _Exit(7);
    exit(7);
  } else CHECK(0);
  FILE *report=fopen("profile-result","wb");CHECK(report);
  CHECK(fprintf(report,"%s %u\n",mode,profile_checks)>0);close_ok(report);
  return 0;
}
