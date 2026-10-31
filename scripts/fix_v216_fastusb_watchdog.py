from pathlib import Path

main=Path('source/main.cpp')
rsx=Path('source/rsxutil.cpp')
s=main.read_text()
r=rsx.read_text()

# FLOW MOVIE V2.16
# - Fix startup USB delay caused by counting refresh calls instead of elapsed time.
# - Log cover-load stages on cache misses.
# - Prevent permanent RSX flip waits with a 500 ms watchdog.

# 1) USB: mount immediately when insertion is detected. If the first attempt
# fails because the NTFS device is still settling, the startup loop retries at
# ~1 second intervals for a short window.
old='''        if(inserted && !g_present[usb]) {\n            g_present[usb] = true;\n            g_insert_delay[usb] = 2;\n            changed = true;\n        } else if(!inserted && g_present[usb]) {'''
new='''        if(inserted && !g_present[usb]) {\n            g_present[usb] = true;\n            /* V2.16: do not count future refresh calls as a delay.  The old\n               value of 2 became 60-90 seconds once polling was slowed down. */\n            g_insert_delay[usb] = 0;\n            changed = true;\n        } else if(!inserted && g_present[usb]) {'''
if old not in s: raise SystemExit('insert-delay anchor not found')
s=s.replace(old,new,1)

old='''        if(g_present[usb] && g_mount_count[usb] <= 0) {\n            if(g_insert_delay[usb] > 0) {\n                g_insert_delay[usb]--;\n            } else if(mount_port(usb)) {\n                changed = true;\n            }\n        }'''
new='''        if(g_present[usb] && g_mount_count[usb] <= 0) {\n            if(mount_port(usb)) changed = true;\n        }'''
if old not in s: raise SystemExit('mount-delay block not found')
s=s.replace(old,new,1)

old='''    int repeat_left=0, repeat_right=0;\n    int poll_counter=0;'''
new='''    int repeat_left=0, repeat_right=0;\n    int poll_counter=0;\n    int fast_usb_attempts=0;'''
if old not in s: raise SystemExit('poll vars anchor not found')
s=s.replace(old,new,1)

old='''        /* V2.15: conservative 30-second automatic NTFS probe. */\n        if(++poll_counter>=1800) {\n            poll_counter=0;\n            flow_log("USB_REFRESH_BEGIN","auto");\n            refresh_usb_state(false);\n            flow_log("USB_REFRESH_END","auto");\n        }'''
new='''        /* V2.16: while startup still has no movies, retry NTFS at ~1 s for\n           at most 15 attempts. Once the disk is mounted/library is visible,\n           return to the conservative 30 s health probe. */\n        int poll_limit=(g_movies.empty() && fast_usb_attempts<15) ? 60 : 1800;\n        if(++poll_counter>=poll_limit) {\n            poll_counter=0;\n            const char *kind=(poll_limit==60)?"startup-fast":"auto";\n            flow_log("USB_REFRESH_BEGIN",kind);\n            refresh_usb_state(false);\n            flow_log("USB_REFRESH_END",kind);\n            if(poll_limit==60) fast_usb_attempts++;\n        }'''
if old not in s: raise SystemExit('V2.15 poll block not found')
s=s.replace(old,new,1)

# 2) Cover-load diagnostics. These are only written on cache misses, not every frame.
old='''    size_t sz = 0;\n    unsigned char *file = read_file_bytes(m, m.cover, &sz);'''
new='''    size_t sz = 0;\n    flow_log("COVER_LOAD_BEGIN",m.cover.c_str());\n    unsigned char *file = read_file_bytes(m, m.cover, &sz);'''
if old not in s: raise SystemExit('cover begin anchor not found')
s=s.replace(old,new,1)

old='''        return NULL;\n    }\n    int probe_w=0, probe_h=0, probe_comp=0;'''
new='''        return NULL;\n    }\n    flow_log("COVER_READ_END",m.cover.c_str());\n    int probe_w=0, probe_h=0, probe_comp=0;'''
# specifically replace first matching after read failure; unique in this context after prior patch
pos=s.find('flow_log("COVER_LOAD_BEGIN"')
sub=s[pos:]
if old not in sub: raise SystemExit('cover read end anchor not found')
sub=sub.replace(old,new,1)
s=s[:pos]+sub

old='''    int iw=0, ih=0, comp=0;\n    unsigned char *decoded = stbi_load_from_memory(file, (int)sz, &iw, &ih, &comp, 4);'''
new='''    int iw=0, ih=0, comp=0;\n    flow_log("COVER_DECODE_BEGIN",m.cover.c_str());\n    unsigned char *decoded = stbi_load_from_memory(file, (int)sz, &iw, &ih, &comp, 4);'''
if old not in s: raise SystemExit('decode anchor not found')
s=s.replace(old,new,1)

old='''    g_cover_cache[slot].path = m.cover;\n    g_cover_cache[slot].stamp = ++g_cover_stamp;\n    return &g_cover_cache[slot];'''
new='''    g_cover_cache[slot].path = m.cover;\n    g_cover_cache[slot].stamp = ++g_cover_stamp;\n    flow_log("COVER_LOAD_END",m.cover.c_str());\n    return &g_cover_cache[slot];'''
if old not in s: raise SystemExit('cover end anchor not found')
s=s.replace(old,new,1)

# 3) RSX flip watchdog: a stalled flip must not freeze the entire application forever.
if '#include <sys/time.h>' not in r:
    r=r.replace('#include <sysutil/video.h>\n','#include <sysutil/video.h>\n#include <sys/time.h>\n',1)

old='''void waitflip()\n{\n    while(gcmGetFlipStatus()!=0) usleep(100);\n    gcmResetFlipStatus();\n}'''
new=r'''static uint64_t rsx_now_us()
{
    struct timeval tv;
    gettimeofday(&tv,NULL);
    return (uint64_t)tv.tv_sec*1000000ULL+(uint64_t)tv.tv_usec;
}

static void rsx_log_timeout()
{
    FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");
    if(!f) return;
    fprintf(f,"[RSX] RSX_FLIP_TIMEOUT | forced recovery after 500 ms\\n");
    fflush(f);
    fclose(f);
}

void waitflip()
{
    uint64_t start=rsx_now_us();
    while(gcmGetFlipStatus()!=0) {
        usleep(100);
        if(rsx_now_us()-start>=500000ULL) {
            /* A half-second wait is already ~30 missed 60 Hz frames.  Do not
               allow a transient RSX flip-status failure to hard-lock the app. */
            rsx_log_timeout();
            gcmResetFlipStatus();
            return;
        }
    }
    gcmResetFlipStatus();
}'''
if old not in r: raise SystemExit('waitflip anchor not found')
r=r.replace(old,new,1)

main.write_text(s)
rsx.write_text(r)
print('FLOW MOVIE V2.16: immediate USB mount + startup fast retry + cover diagnostics + RSX flip watchdog')
