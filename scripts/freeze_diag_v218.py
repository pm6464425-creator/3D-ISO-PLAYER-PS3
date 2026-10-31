from pathlib import Path

main=Path('source/main.cpp')
rsx=Path('source/rsxutil.cpp')
s=main.read_text()
r=rsx.read_text()

# FLOW MOVIE V2.18 DEBUG FREEZE
# Diagnostic-only instrumentation. No visual/FPS/movement/NTFS behavior change.
# A second PPU thread watches the exact phase of the main loop. The main thread
# only updates small values in RAM; disk logging happens only when a phase stays
# stuck for >= 1.5 seconds.

inc='#include "rsxutil.h"\n'
proto='''#include "rsxutil.h"\n\n/* V2.18 DEBUG FREEZE: diagnostic watchdog API. */\nvoid freeze_diag_start();\nvoid freeze_diag_stop();\nvoid freeze_diag_phase(int phase);\nvoid freeze_diag_frame_ok();\n'''
if inc not in s:
    raise SystemExit('rsxutil include anchor not found')
s=s.replace(inc,proto,1)

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.17");',
            'flow_log("SESSION_START","FLOW MOVIE V2.18 DEBUG FREEZE");',1)

anchor='''    flow_log("USB_REFRESH_END","startup");\n\n    padData pad;'''
repl='''    flow_log("USB_REFRESH_END","startup");\n    freeze_diag_start();\n    flow_log("WATCHDOG_START","threshold=1500ms phases=callback,pad,input,render,flip");\n\n    padData pad;'''
if anchor not in s:
    raise SystemExit('startup watchdog anchor not found')
s=s.replace(anchor,repl,1)

s=s.replace('''    while(app_running) {\n        sysUtilCheckCallback();''',
'''    while(app_running) {\n        freeze_diag_phase(10); /* SYSUTIL_CALLBACK */\n        sysUtilCheckCallback();\n        freeze_diag_phase(11); /* AFTER_SYSUTIL */''',1)

s=s.replace('''        memset(&pad,0,sizeof(pad));\n        ioPadGetData(0,&pad);\n\n        bool up=''',
'''        freeze_diag_phase(20); /* PAD_READ */\n        memset(&pad,0,sizeof(pad));\n        ioPadGetData(0,&pad);\n        freeze_diag_phase(21); /* INPUT_UPDATE */\n\n        bool up=''',1)

s=s.replace('''if(l1 && !p_l1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; flow_log("TAB_CHANGE","L1"); rebuild_movies(); g_flow_ready=false; }''',
'''if(l1 && !p_l1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; flow_log("TAB_CHANGE","L1"); freeze_diag_phase(70); rebuild_movies(); freeze_diag_phase(21); g_flow_ready=false; }''',1)
s=s.replace('''if(r1 && !p_r1) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; flow_log("TAB_CHANGE","R1"); rebuild_movies(); g_flow_ready=false; }''',
'''if(r1 && !p_r1) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; flow_log("TAB_CHANGE","R1"); freeze_diag_phase(70); rebuild_movies(); freeze_diag_phase(21); g_flow_ready=false; }''',1)

s=s.replace('''        if(tri && !p_tri) {\n            flow_log("USB_REFRESH_BEGIN","manual");\n            refresh_usb_state(true);\n            flow_log("USB_REFRESH_END","manual");\n        }''',
'''        if(tri && !p_tri) {\n            freeze_diag_phase(80); /* MANUAL_USB_REFRESH */\n            flow_log("USB_REFRESH_BEGIN","manual");\n            refresh_usb_state(true);\n            flow_log("USB_REFRESH_END","manual");\n            freeze_diag_phase(21);\n        }''',1)

anchor='''        if(diag_render) flow_log("RENDER_BEGIN",NULL);\n        render_ui();\n        if(diag_render) flow_log("RENDER_END",NULL);'''
repl='''        if(diag_render) flow_log("RENDER_BEGIN",NULL);\n        freeze_diag_phase(30); /* RENDER_UI / DRAW */\n        render_ui();\n        freeze_diag_frame_ok();\n        freeze_diag_phase(40); /* FRAME_OK / LOOP_TAIL */\n        if(diag_render) flow_log("RENDER_END",NULL);'''
if anchor not in s:
    raise SystemExit('render instrumentation anchor not found')
s=s.replace(anchor,repl,1)

s=s.replace('''    flow_log("SESSION_EXIT","normal");\n    free_case_assets();''',
'''    freeze_diag_stop();\n    flow_log("SESSION_EXIT","normal");\n    free_case_assets();''',1)

if '#include <sys/thread.h>' not in r:
    r=r.replace('#include <sys/time.h>\n','#include <sys/time.h>\n#include <sys/thread.h>\n',1)

anchor=r'''static uint64_t rsx_now_us()
{
    struct timeval tv;
    gettimeofday(&tv,NULL);
    return (uint64_t)tv.tv_sec*1000000ULL+(uint64_t)tv.tv_usec;
}
'''
watchdog=r'''static uint64_t rsx_now_us()
{
    struct timeval tv;
    gettimeofday(&tv,NULL);
    return (uint64_t)tv.tv_sec*1000000ULL+(uint64_t)tv.tv_usec;
}

/* V2.18 DEBUG FREEZE -------------------------------------------------------
   Phase updates are RAM-only and intentionally tiny. A detached PPU watchdog
   writes to FLOW_MOVIE.LOG only when the same watched phase lasts >=1.5 s. */
static volatile int g_freeze_diag_running = 0;
static volatile int g_freeze_diag_phase = 0;
static volatile uint64_t g_freeze_diag_since_us = 0;
static volatile uint64_t g_freeze_diag_frame = 0;
static sys_ppu_thread_t g_freeze_watchdog_thread;

static const char *freeze_diag_phase_name(int p)
{
    switch(p) {
        case 10: return "SYSUTIL_CALLBACK";
        case 11: return "AFTER_SYSUTIL";
        case 20: return "PAD_READ";
        case 21: return "INPUT_UPDATE";
        case 30: return "RENDER_UI_DRAW";
        case 40: return "FRAME_OK_LOOP_TAIL";
        case 50: return "FLIP_ENTER";
        case 51: return "GCM_SET_FLIP";
        case 52: return "RSX_FLUSH";
        case 53: return "WAIT_FLIP";
        case 54: return "SET_RENDER_TARGET";
        case 70: return "REBUILD_MOVIES";
        case 80: return "MANUAL_USB_REFRESH";
        default: return "UNKNOWN";
    }
}

void freeze_diag_phase(int phase)
{
    g_freeze_diag_phase = phase;
    g_freeze_diag_since_us = rsx_now_us();
}

void freeze_diag_frame_ok()
{
    g_freeze_diag_frame++;
}

static void freeze_diag_write_stall(int phase,uint64_t stuck_us,uint64_t frame)
{
    FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");
    if(!f) return;
    fprintf(f,"[WATCHDOG] FREEZE_SUSPECTED | phase=%s code=%d stuck_ms=%llu frame=%llu\\n",
            freeze_diag_phase_name(phase),phase,
            (unsigned long long)(stuck_us/1000ULL),
            (unsigned long long)frame);
    fflush(f);
    fclose(f);
}

static int freeze_diag_is_watched(int phase)
{
    return phase==10 || phase==11 || phase==20 || phase==21 || phase==30 ||
           phase==40 || phase==50 || phase==51 || phase==52 || phase==53 || phase==54;
}

static void freeze_diag_watchdog_entry(void *arg)
{
    (void)arg;
    int reported_phase=-1;
    uint64_t reported_since=0;
    while(g_freeze_diag_running) {
        int phase=g_freeze_diag_phase;
        uint64_t since=g_freeze_diag_since_us;
        uint64_t now=rsx_now_us();
        if(freeze_diag_is_watched(phase) && since && now>since) {
            uint64_t stuck=now-since;
            if(stuck>=1500000ULL && (phase!=reported_phase || since!=reported_since)) {
                freeze_diag_write_stall(phase,stuck,g_freeze_diag_frame);
                reported_phase=phase;
                reported_since=since;
            }
        }
        usleep(250000);
    }
}

void freeze_diag_start()
{
    g_freeze_diag_phase=0;
    g_freeze_diag_since_us=rsx_now_us();
    g_freeze_diag_frame=0;
    g_freeze_diag_running=1;
    sysThreadCreate(&g_freeze_watchdog_thread,freeze_diag_watchdog_entry,NULL,
                    1500,0x4000,0,(char*)"flow_watchdog");
}

void freeze_diag_stop()
{
    g_freeze_diag_running=0;
}
'''
if anchor not in r:
    raise SystemExit('rsx_now_us anchor not found')
r=r.replace(anchor,watchdog,1)

old='''    gcmSetFlip(context,curr_fb);\n    rsxFlushBuffer(context);\n\n    /* Block the CPU until this exact display flip has completed.  This makes\n       the swap itself the 60 Hz frame pacer and keeps the two buffers clean. */\n    waitflip();\n\n    curr_fb ^= 1;\n    setRenderTarget(curr_fb);'''
new='''    freeze_diag_phase(50); /* FLIP_ENTER */\n    freeze_diag_phase(51); /* GCM_SET_FLIP */\n    gcmSetFlip(context,curr_fb);\n    freeze_diag_phase(52); /* RSX_FLUSH */\n    rsxFlushBuffer(context);\n\n    /* Block the CPU until this exact display flip has completed. */\n    freeze_diag_phase(53); /* WAIT_FLIP */\n    waitflip();\n\n    curr_fb ^= 1;\n    freeze_diag_phase(54); /* SET_RENDER_TARGET */\n    setRenderTarget(curr_fb);'''
if old not in r:
    raise SystemExit('flip operation anchor not found')
r=r.replace(old,new,1)

main.write_text(s)
rsx.write_text(r)
print('FLOW MOVIE V2.18 DEBUG FREEZE: phase watchdog instrumentation added')
