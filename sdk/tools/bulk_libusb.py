# SPDX-License-Identifier: GPL-3.0-or-later
"""libusb adapter for bounded LFB1 staging; target policy is explicit."""
import ctypes
from bulk_transfer import available, upload, download


def transfer(device,target,data,allowed,**kwargs):
    if target not in allowed:
        raise ValueError('Bulk target is outside this transport capability')
    lib=device.lib;handle=device.handle
    def read(request,value=0,index=0,length=64,standard=False):
        buf=(ctypes.c_ubyte*length)()
        n=lib.libusb_control_transfer(handle,0x80 if standard else 0xc0,request,value,index,buf,length,3000)
        if n<0:raise RuntimeError(f'Bulk control read failed ({n})')
        return bytes(buf[:n])
    descriptor=read(6,value=0x200,length=32,standard=True)
    if not available(descriptor):return None if target>=4 else False
    def write(request,data=b'',value=0,index=0):
        buf=(ctypes.c_ubyte*max(1,len(data)))()
        if data:buf[:len(data)]=data
        n=lib.libusb_control_transfer(handle,0x40,request,value,index,buf,len(data),3000)
        if n!=len(data):raise RuntimeError(f'Bulk control write failed ({n}); no retry')
    lib.libusb_claim_interface.argtypes=[ctypes.c_void_p,ctypes.c_int]
    lib.libusb_release_interface.argtypes=[ctypes.c_void_p,ctypes.c_int]
    lib.libusb_bulk_transfer.argtypes=[ctypes.c_void_p,ctypes.c_ubyte,ctypes.POINTER(ctypes.c_ubyte),ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.c_uint]
    if lib.libusb_claim_interface(handle,0)<0:raise RuntimeError('Cannot claim USB bulk interface; close other calculator tools')
    def send(block):
        buf=(ctypes.c_ubyte*len(block)).from_buffer_copy(block);done=ctypes.c_int()
        result=lib.libusb_bulk_transfer(handle,1,buf,len(block),ctypes.byref(done),10000)
        if result or done.value!=len(block):raise RuntimeError(f'Bulk transfer incomplete ({result}, {done.value}/{len(block)}); no retry')
    def receive(size):
        buf=(ctypes.c_ubyte*size)();done=ctypes.c_int()
        result=lib.libusb_bulk_transfer(handle,0x81,buf,size,ctypes.byref(done),10000)
        if result or done.value!=size:raise RuntimeError(f'Bulk read incomplete ({result}, {done.value}/{size})')
        return bytes(buf)
    try:
        return download(read,write,receive,target,data,**kwargs) if target>=4 else upload(read,write,send,target,data,**kwargs)
    finally:lib.libusb_release_interface(handle,0)
