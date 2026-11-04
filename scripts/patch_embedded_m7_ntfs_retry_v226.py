#!/usr/bin/env python3
"""Movian M7 embedded NTFS file probe retry. ELF patch; PS3 test still needed."""
from pathlib import Path
import struct,hashlib,sys,json

if len(sys.argv)!=3: raise SystemExit('usage: patch_embedded_m7_ntfs_retry_v226.py CLI_PATCHED.elf RETRY_PATCHED.elf')
src=Path(sys.argv[1]).read_bytes()
expected='2dfd5555b7aacea2b74597399f1d5cb5e36365160a9d3475116bceab013d4eff'
assert hashlib.sha256(src).hexdigest()==expected
b=bytearray(src)
assert b[:6]==bytes.fromhex('7f454c460202')
phoff=struct.unpack_from('>Q',b,32)[0]
count=struct.unpack_from('>H',b,56)[0]
entsz=struct.unpack_from('>H',b,54)[0]
segments=[]
for i in range(count):
  e=phoff+i*entsz
  t,flags,off,va,pa,fs,ms,al=struct.unpack_from('>IIQQQQQQ',b,e)
  if t==1:segments.append((e,off,va,fs,flags))
exes=[s for s in segments if s[-1]&1]
assert len(exes)==1
ent,off,va,fs,flags=exes[0]
start=(va+fs+15)&~15
assert start==0xbf0780,hex(start)
def pos(addr):return off+addr-va
def branch(a,d,link=1):
 delta=d-a
 assert delta%4==0 and -(1<<25)<=delta<(1<<25),(hex(a),hex(d))
 return 0x48000000|(delta&0x3fffffc)|link
assert struct.unpack_from('>I',b,pos(0x23935c))[0]==branch(0x23935c,0xc9bd8)
stub=bytearray.fromhex('7c0802a6f821ff61f8010010f8610070f88100783940000091410080e8610070e8810078600000002c23000041820064814100802c0a000940800018394a00019141008038600001600000004bffffd0e86100703880000038a00000600000002c0300004180002490610088e8810078600000009061008c80610088600000008061008c480000103860ffff4800000838600000e8010010382100a07c0803a64e800020')
assert len(stub)==164
assert b[pos(start):pos(start)+len(stub)]==bytes(len(stub))
for relative,target in [(0x24,0xc9bd8),(0x48,0x3fb6f8),(0x5c,0xc93f8),(0x70,0xc9b28),(0x7c,0xc96f8)]:
 assert struct.unpack_from('>I',stub,relative)[0]==0x60000000
 struct.pack_into('>I',stub,relative,branch(start+relative,target))
struct.pack_into('>I',b,pos(0x23935c),branch(0x23935c,start))
b[pos(start):pos(start)+len(stub)]=stub
new_fs=start+len(stub)-va
assert new_fs<fs+512
struct.pack_into('>Q',b,ent+32,new_fs)
struct.pack_into('>Q',b,ent+40,new_fs)
assert len(b)==len(src)
out=Path(sys.argv[2]);out.write_bytes(b)
sha=hashlib.sha256(b).hexdigest()
assert sha=='db20a26b31e1c571f86c2be580c257a1296c7b8ef880004f48d4642771159c56'
print(json.dumps({'sha':sha,'retry_seconds':9,'fallback':'ps3ntfs_open+ps3ntfs_fstat','probe_hook':hex(0x23935c),'trampoline':hex(start),'size':len(b)},indent=2))
