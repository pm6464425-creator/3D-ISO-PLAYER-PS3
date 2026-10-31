#!/usr/bin/env python3
import argparse
import hashlib
import os
import struct
from pathlib import Path

MAGIC = 0x7F504B47
TYPE_DIR = 0x04
ITEM_SIZE = 0x20


def be16(b, o): return struct.unpack_from('>H', b, o)[0]
def be32(b, o): return struct.unpack_from('>I', b, o)[0]
def be64(b, o): return struct.unpack_from('>Q', b, o)[0]


def debug_keystream(qa_digest: bytes, block_index: int) -> bytes:
    buf = bytearray(64)
    buf[0:8] = qa_digest[0:8]
    buf[8:16] = qa_digest[0:8]
    buf[16:24] = qa_digest[8:16]
    buf[24:32] = qa_digest[8:16]
    buf[56:64] = struct.pack('>Q', block_index)
    return hashlib.sha1(buf).digest()[:16]


def decrypt_region(f, data_offset: int, qa_digest: bytes, pos: int, size: int) -> bytes:
    if size <= 0:
        return b''
    start = pos & ~0xF
    skip = pos - start
    need = skip + size
    blocks = (need + 15) // 16
    f.seek(data_offset + start)
    enc = f.read(blocks * 16)
    out = bytearray()
    first_block = start // 16
    for i in range(0, len(enc), 16):
        chunk = enc[i:i+16]
        key = debug_keystream(qa_digest, first_block + i // 16)
        out.extend(a ^ b for a, b in zip(chunk, key))
    return bytes(out[skip:skip + size])


def safe_dest(root: Path, name: str) -> Path:
    name = name.replace('\\', '/').lstrip('/')
    parts = [p for p in name.split('/') if p not in ('', '.')]
    if any(p == '..' for p in parts):
        raise ValueError(f'unsafe path: {name}')
    dest = root.joinpath(*parts)
    dest.resolve().relative_to(root.resolve())
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg')
    ap.add_argument('--out', required=True)
    ap.add_argument('--prefix', action='append', required=True)
    args = ap.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    prefixes = tuple(p.replace('\\', '/').strip('/') for p in args.prefix)

    with open(args.pkg, 'rb') as f:
        hdr = f.read(0x80)
        if len(hdr) < 0x80 or be32(hdr, 0) != MAGIC:
            raise SystemExit('invalid PS3 PKG')
        revision = be16(hdr, 4)
        pkg_type = be16(hdr, 6)
        item_count = be32(hdr, 0x14)
        data_offset = be64(hdr, 0x20)
        qa_digest = hdr[0x60:0x70]
        if revision != 0x0000 or pkg_type != 0x0001:
            raise SystemExit(f'expected PS3 debug PKG, revision=0x{revision:04X} type=0x{pkg_type:04X}')

        table = decrypt_region(f, data_offset, qa_digest, 0, item_count * ITEM_SIZE)
        if len(table) != item_count * ITEM_SIZE:
            raise SystemExit('truncated item table')

        extracted = 0
        matched_names = []
        for i in range(item_count):
            e = table[i*ITEM_SIZE:(i+1)*ITEM_SIZE]
            name_off = be32(e, 0x00)
            name_size = be32(e, 0x04)
            file_off = be64(e, 0x08)
            file_size = be64(e, 0x10)
            flags = be32(e, 0x18)
            raw_name = decrypt_region(f, data_offset, qa_digest, name_off, name_size)
            name = raw_name.rstrip(b'\0').decode('utf-8', 'replace').replace('\\', '/').strip('/')
            if not name or not any(name == p or name.startswith(p + '/') for p in prefixes):
                continue
            matched_names.append(name)
            dest = safe_dest(out_root, name)
            if (flags & 0xFF) == TYPE_DIR:
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            remaining = file_size
            pos = 0
            with open(dest, 'wb') as out:
                while remaining:
                    n = min(1024 * 1024, remaining)
                    data = decrypt_region(f, data_offset, qa_digest, file_off + pos, n)
                    if len(data) != n:
                        raise SystemExit(f'truncated data for {name}')
                    out.write(data)
                    pos += n
                    remaining -= n
            extracted += 1

    print(f'extracted files: {extracted}')
    for name in matched_names[:30]:
        print(name)
    if extracted == 0:
        raise SystemExit('no matching payload files found')


if __name__ == '__main__':
    main()
