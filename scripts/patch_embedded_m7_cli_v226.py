#!/usr/bin/env python3
"""Patch M7 PS3 native startup to parse the movie URL from argv.

The official M7 PS3 main calls ps3_early_init but not parse_opts,
so the app ignores the URI passed by FLOW. This patch creates an
executable trampoline in the unused space after the RX load segment,
and branches from main's first startup call to:
  save argc/argv in a private aligned frame,
  ps3_early_init(argc,argv),
  parse_opts(argc,argv),
  restore stack and branch back to main.
The existing Movian nav_create() uses gconf.initial_url after navigation starts.

Usage:
  patch_embedded_m7_cli_v226.py <original movian.self> <decrypted ELF> <patched ELF>
"""
from pathlib import Path
from zipfile import ZipFile
import sys,struct,hashlib,json
if len(sys.argv)!=4:raise SystemExit(__doc__)
SELF,BASE,OUT=map(Path,sys.argv[1:])
assert hashlib.sha256(SELF.read_bytes()).hexdigest()=="25d12712ec5241f6a4aa4d2c8f79638e566989aeb2cc4d95384d53bd908dd8cb"
assert hashlib.sha256(BASE.read_bytes()).hexdigest()=="2e695803b732aa8aaa7ac2340548af83982d32743c6dd7afbffc0b3ee5c1bc00"
with ZipFile(SELF) as z:
    assert z.testzip() is None
    syms={}
    for line in z.read("movian.syms").decode("ascii","ignore").splitlines():
        p=line.strip().split()
        if len(p)>=2 and p[1].startswith("."):syms[p[1][1:]]=int(p[0],16)
main,early,parse=[syms[n] for n in ("main","ps3_early_init","parse_opts")]
d=bytearray(BASE.read_bytes())
assert d[:6]==bytes.fromhex("7f454c460202")
phoff=struct.unpack_from(">Q",d,32)[0]
entsize=struct.unpack_from(">H",d,54)[0]
count=struct.unpack_from(">H",d,56)[0]
segs=[]
for i in range(count):
    o=phoff+i*entsize
    t,flags,off,vaddr,paddr,fs,ms,align=struct.unpack_from(">IIQQQQQQ",d,o)
    if t==1:segs.append((i,o,off,vaddr,fs,ms,flags))
rx=[x for x in segs if x[-1]&1]
assert len(rx)==1
_,entry,offset,vaddr,filesz,memsz,_=rx[0]
assert filesz==memsz
stub=(vaddr+filesz+15)&~15
stuboff=offset+stub-vaddr
gap=min(x[2] for x in segs if x[2]>offset)
assert stuboff+64<gap and d[stuboff:stuboff+64]==bytes(64)
def loc(addr):
    for _,_,off,vaddr,sz,_,_ in segs:
        if vaddr<=addr<vaddr+sz:return off+addr-vaddr
    raise RuntimeError(hex(addr))
def branch(src,dst,link=False):
    delta=dst-src
    assert delta%4==0 and -(1<<25)<=delta<(1<<25),(hex(src),hex(dst))
    return 0x48000000|(delta&0x03fffffc)|int(link)
assert struct.unpack_from(">I",d,loc(main+24))[0]==branch(main+24,early,True)
words=[
    0xF821FF51,                 # stdu r1, -0xB0(r1): own stack frame
    0xF8610090,                 # std r3, 0x90(r1): argc
    0xF8810098,                 # std r4, 0x98(r1): argv
    branch(stub+12,early,True),# bl ps3_early_init
    0xE8610090,                 # ld r3, 0x90(r1)
    0xE8810098,                 # ld r4, 0x98(r1)
    branch(stub+24,parse,True),# bl parse_opts
    0x382100B0,                 # addi r1,r1,0xB0: restore stack
    branch(stub+32,main+28)    # b main+28
]
struct.pack_into(">I",d,loc(main+24),branch(main+24,stub))
for i,w in enumerate(words):struct.pack_into(">I",d,stuboff+i*4,w)
newsize=stub+len(words)*4-vaddr
struct.pack_into(">Q",d,entry+32,newsize)
struct.pack_into(">Q",d,entry+40,newsize)
assert struct.unpack_from(">I",d,stuboff+6*4)[0]==branch(stub+24,parse,True)
assert struct.unpack_from(">I",d,stuboff+8*4)[0]==branch(stub+32,main+28)
assert len(d)==BASE.stat().st_size
OUT.write_bytes(d)
print(json.dumps({"original_sha":hashlib.sha256(BASE.read_bytes()).hexdigest(),
 "patched_sha":hashlib.sha256(d).hexdigest(),"main":hex(main),
 "parse_opts":hex(parse),"new_trampoline":hex(stub),"size":len(d)},indent=2))
