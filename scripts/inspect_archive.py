import ctypes as C
import ctypes.util
import collections
import json
from pathlib import Path

import os
ROOT = Path(os.environ.get('JUDICIAL_WORK_DIR', '.')).resolve()
ARCHIVE = Path(os.environ['JUDICIAL_ARCHIVE']).resolve()
lib = C.CDLL(ctypes.util.find_library('archive'))
def bind(name, restype, args):
    f = getattr(lib, name); f.restype = restype; f.argtypes = args; return f
new = bind('archive_read_new', C.c_void_p, [])
support_filter = bind('archive_read_support_filter_all', C.c_int, [C.c_void_p])
support_format = bind('archive_read_support_format_all', C.c_int, [C.c_void_p])
open_file = bind('archive_read_open_filename', C.c_int, [C.c_void_p, C.c_char_p, C.c_size_t])
next_header = bind('archive_read_next_header', C.c_int, [C.c_void_p, C.POINTER(C.c_void_p)])
pathname = bind('archive_entry_pathname', C.c_char_p, [C.c_void_p])
entry_size = bind('archive_entry_size', C.c_int64, [C.c_void_p])
read_data = bind('archive_read_data', C.c_ssize_t, [C.c_void_p, C.c_void_p, C.c_size_t])
skip_data = bind('archive_read_data_skip', C.c_int, [C.c_void_p])
free = bind('archive_read_free', C.c_int, [C.c_void_p])
error = bind('archive_error_string', C.c_char_p, [C.c_void_p])

def entries(content=False):
    a = new(); support_filter(a); support_format(a)
    if open_file(a, str(ARCHIVE).encode(), 10240) != 0:
        raise RuntimeError(error(a))
    try:
        e = C.c_void_p()
        while True:
            status = next_header(a, C.byref(e))
            if status == 1: break
            if status < 0: raise RuntimeError(error(a))
            name = pathname(e).decode('utf-8', 'replace')
            size = entry_size(e)
            chunks=[]
            if content and size > 0:
                buf = C.create_string_buffer(1024*1024)
                while True:
                    n=read_data(a,buf,len(buf))
                    if n < 0: raise RuntimeError((name,error(a)))
                    if n == 0: break
                    chunks.append(buf.raw[:n])
            else: skip_data(a)
            yield name,size,b''.join(chunks)
    finally: free(a)

if __name__=='__main__':
    count=0; total=0; ext=collections.Counter(); sample=[]
    for name,size,_ in entries():
        count+=1; total+=size; ext[Path(name).suffix]+=1
        if len(sample)<10: sample.append([name,size])
    print(json.dumps(dict(entries=count,uncompressed_bytes=total,extensions=ext,sample=sample),ensure_ascii=False))
