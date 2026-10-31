from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.13 STABILITY
# Fix long-run freezes without changing the V2.12 look/motion.

# 1) Never memset a C++ object that owns std::string.
old='''static bool load_app_bitmap(const char *path, CoverBitmap *out)\n{\n    memset(out,0,sizeof(CoverBitmap));\n    FILE *f=fopen(path,"rb");'''
new='''static bool load_app_bitmap(const char *path, CoverBitmap *out)\n{\n    /* V2.13: CoverBitmap contains std::string.  memset() on it is undefined\n       behavior and can corrupt the heap after the app has been running. */\n    if(out->rgba) { stbi_image_free(out->rgba); out->rgba=NULL; }\n    out->path.clear();\n    out->w=0; out->h=0; out->stamp=0;\n    FILE *f=fopen(path,"rb");'''
if old not in s:
    raise SystemExit('load_app_bitmap memset anchor not found')
s=s.replace(old,new,1)

# 2) The old loop probed all 8 USB/NTFS ports every 45 frames (~0.75 s at 60 Hz).
#    Poll much less often. TRIANGLE still performs an immediate forced refresh.
old='''        if(++poll_counter>=45) {\n            poll_counter=0;\n            refresh_usb_state(false);\n        }'''
new='''        /* V2.13: do not hammer the NTFS layer every ~0.75 s.\n           A 10-second health check is enough; TRIANGLE remains manual refresh. */\n        if(++poll_counter>=600) {\n            poll_counter=0;\n            refresh_usb_state(false);\n        }'''
if old not in s:
    raise SystemExit('USB poll anchor not found')
s=s.replace(old,new,1)

# 3) Protect the PS3 heap from pathological poster images.  The app displays
#    covers at <=320x480, so decoding 40-50 MB RGBA posters provides no benefit.
old='''       probe_w <= 0 || probe_h <= 0 || probe_w > 4096 || probe_h > 4096 ||\n       (uint64_t)probe_w * (uint64_t)probe_h > 12000000ULL) {'''
new='''       probe_w <= 0 || probe_h <= 0 || probe_w > 3072 || probe_h > 3072 ||\n       (uint64_t)probe_w * (uint64_t)probe_h > 6000000ULL) {'''
if old not in s:
    raise SystemExit('cover decode guard anchor not found')
s=s.replace(old,new,1)

# 4) Reduce cover-cache churn slightly. Five cards are visible; six cache slots
#    cover the current view plus the next incoming poster while using less heap.
s=s.replace('#define COVER_CACHE_SLOTS 8','#define COVER_CACHE_SLOTS 6',1)

p.write_text(s)
print('FLOW MOVIE V2.13: safe C++ bitmap init + 10s NTFS poll + cover memory guards')
