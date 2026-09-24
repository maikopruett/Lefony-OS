// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_FILE_WRITER_H
#define LEFONY_FILE_WRITER_H
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
// Also declared by files.h. Keep this app-linked adapter independent of the
// raw ARM service inline functions so pure document models remain host-usable.
extern "C" int lefony_file_abort(int descriptor);
namespace Lefony {
// A single OS-staged replacement. commit() is the only publishing operation;
// write failure, cancellation and destruction request discard. A failed commit
// may already be durable: reopen and inspect before retrying. Requires API 12 and
// declared capabilities NamedFiles|FileAbort. No stdio buffering or allocation.
class FileWriter {
public:
  FileWriter()=default;
  FileWriter(const FileWriter &)=delete;
  FileWriter &operator=(const FileWriter &)=delete;
  ~FileWriter() { cancel(); }
  bool active() const {return m_descriptor>=0;}
  int error() const {return m_error;}
  bool begin(const char *name) {
    if(active()) {m_error=EBUSY;return false;}
    m_error=0;
    // Probe authorization with a nonexistent handle before opening a writer.
    // This cannot convert storage or publish data. Unsupported/undeclared
    // abort must never degrade into a close that could publish partial bytes.
    if(lefony_file_abort(0)!=-1 || errno!=EBADF) {m_error=errno?errno:EIO;return false;}
    m_descriptor=open(name,O_WRONLY|O_CREAT|O_TRUNC,0600);
    if(m_descriptor<0) {m_error=errno;return false;}
    return true;
  }
  bool write(const void *bytes,unsigned size) {
    if(!active() || m_error) return false;
    if(size && !bytes) return failed(EINVAL);
    const auto *input=static_cast<const unsigned char *>(bytes);
    for(unsigned at=0;at<size;) {
      ssize_t count=::write(m_descriptor,input+at,size-at);
      if(count<=0) return failed(count<0?errno:EIO);
      at+=static_cast<unsigned>(count);
    }
    return true;
  }
  bool commit() {
    if(!active() || m_error) {cancel();return false;}
    int descriptor=m_descriptor;m_descriptor=-1;
    if(close(descriptor)<0) {m_error=errno;return false;}
    return true;
  }
  bool cancel() {
    if(!active()) return true;
    int result=lefony_file_abort(m_descriptor),error=errno;
    if(result==0 || error==EBADF) m_descriptor=-1;
    if(result<0) {if(!m_error) m_error=error;return false;}
    return true;
  }
private:
  bool failed(int error) {m_error=error;cancel();return false;}
  int m_descriptor=-1,m_error=0;
};
}
#endif
