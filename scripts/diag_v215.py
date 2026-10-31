from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.15
# 1) Keep V2.14 heights exactly the same; widen cases only by 6%.
# 2) Add low-frequency persistent diagnostics for long-run freezes.

old='''        /* V2.14: uniform +10% zoom. Same 135:172 shape, only closer/larger. */\n        const float sel_h=sh*0.484f;\n        const float nb_h=sh*0.308f;\n        const float aspect=135.0f/172.0f;'''
new='''        /* V2.15: keep V2.14 height, widen only by 6%. */\n        const float sel_h=sh*0.484f;\n        const float nb_h=sh*0.308f;\n        const float aspect=(135.0f/172.0f)*1.06f;'''
if old not in s:
    raise SystemExit('V2.14 geometry anchor not found')
s=s.replace(old,new,1)

# Persistent log helpers. Insert after g_tab so the heartbeat can include the
# current tab/selection/movie count without forward-declaration problems.
anchor='static MediaTab g_tab = TAB_BDISO;\n'
log_code=r'''static const char *FLOW_LOG_PATH="/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG";
static uint64_t g_log_start_us=0;
static uint64_t g_last_heartbeat_us=0;

static uint64_t flow_now_us()
{
    struct timeval tv;
    gettimeofday(&tv,NULL);
    return (uint64_t)tv.tv_sec*1000000ULL+(uint64_t)tv.tv_usec;
}

static void flow_log(const char *event,const char *detail)
{
    uint64_t now=flow_now_us();
    if(g_log_start_us==0) g_log_start_us=now;
    FILE *f=fopen(FLOW_LOG_PATH,"a");
    if(!f) return;
    double sec=(double)(now-g_log_start_us)/1000000.0;
    fprintf(f,"[%8.3f] %s",sec,event?event:"?");
    if(detail && detail[0]) fprintf(f," | %s",detail);
    fputc('\n',f);
    fflush(f);
    fclose(f);
}

static void flow_log_heartbeat()
{
    uint64_t now=flow_now_us();
    if(g_last_heartbeat_us && now-g_last_heartbeat_us<5000000ULL) return;
    g_last_heartbeat_us=now;
    char b[160];
    snprintf(b,sizeof(b),"tab=%d selected=%d movies=%u",(int)g_tab,g_selected,(unsigned)g_movies.size());
    flow_log("HEARTBEAT",b);
}
'''
if anchor not in s:
    raise SystemExit('g_tab anchor not found')
s=s.replace(anchor,anchor+log_code,1)

# Log cover failures, with path suppression so a corrupt cover cannot flood the log.
cover_anchor='''    unsigned char *file = read_file_bytes(m, m.cover, &sz);\n    if(!file) return NULL;'''
cover_new='''    unsigned char *file = read_file_bytes(m, m.cover, &sz);\n    if(!file) {\n        static std::string last_fail;\n        if(last_fail!=m.cover) { flow_log("COVER_READ_FAIL",m.cover.c_str()); last_fail=m.cover; }\n        return NULL;\n    }'''
if cover_anchor not in s:
    raise SystemExit('cover read anchor not found')
s=s.replace(cover_anchor,cover_new,1)

probe_anchor='''        free(file);\n        return NULL;\n    }\n\n    int iw=0, ih=0, comp=0;'''
probe_new='''        static std::string last_bad_probe;\n        if(last_bad_probe!=m.cover) { flow_log("COVER_PROBE_REJECT",m.cover.c_str()); last_bad_probe=m.cover; }\n        free(file);\n        return NULL;\n    }\n\n    int iw=0, ih=0, comp=0;'''
if probe_anchor not in s:
    raise SystemExit('cover probe anchor not found')
s=s.replace(probe_anchor,probe_new,1)

decode_anchor='''    free(file);\n    if(!decoded || iw <= 0 || ih <= 0) { if(decoded) stbi_image_free(decoded); return NULL; }'''
decode_new='''    free(file);\n    if(!decoded || iw <= 0 || ih <= 0) {\n        static std::string last_decode_fail;\n        if(last_decode_fail!=m.cover) { flow_log("COVER_DECODE_FAIL",m.cover.c_str()); last_decode_fail=m.cover; }\n        if(decoded) stbi_image_free(decoded);\n        return NULL;\n    }'''
if decode_anchor not in s:
    raise SystemExit('cover decode anchor not found')
s=s.replace(decode_anchor,decode_new,1)

# Session start after environment is ready but before first USB scan.
start_anchor='''    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }\n    refresh_usb_state(true);'''
start_new='''    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }\n    remove(FLOW_LOG_PATH);\n    g_log_start_us=flow_now_us();\n    flow_log("SESSION_START","FLOW MOVIE V2.15");\n    flow_log("USB_REFRESH_BEGIN","startup");\n    refresh_usb_state(true);\n    flow_log("USB_REFRESH_END","startup");'''
if start_anchor not in s:
    raise SystemExit('startup refresh anchor not found')
s=s.replace(start_anchor,start_new,1)

# Keep automatic polling conservative: 30 seconds instead of 10. Manual
# TRIANGLE refresh stays immediate. Log begin/end so a freeze inside NTFS is obvious.
poll_anchor='''        /* V2.13: do not hammer the NTFS layer every ~0.75 s.\n           A 10-second health check is enough; TRIANGLE remains manual refresh. */\n        if(++poll_counter>=600) {\n            poll_counter=0;\n            refresh_usb_state(false);\n        }'''
poll_new='''        /* V2.15: conservative 30-second automatic NTFS probe. */\n        if(++poll_counter>=1800) {\n            poll_counter=0;\n            flow_log("USB_REFRESH_BEGIN","auto");\n            refresh_usb_state(false);\n            flow_log("USB_REFRESH_END","auto");\n        }'''
if poll_anchor not in s:
    raise SystemExit('poll anchor not found')
s=s.replace(poll_anchor,poll_new,1)

tri_anchor='''        if(tri && !p_tri) refresh_usb_state(true);'''
tri_new='''        if(tri && !p_tri) {\n            flow_log("USB_REFRESH_BEGIN","manual");\n            refresh_usb_state(true);\n            flow_log("USB_REFRESH_END","manual");\n        }'''
if tri_anchor not in s:
    raise SystemExit('triangle refresh anchor not found')
s=s.replace(tri_anchor,tri_new,1)

# Tab changes are useful context in the log.
s=s.replace('''        if(l1 && !p_l1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; rebuild_movies(); g_flow_ready=false; }''',
'''        if(l1 && !p_l1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; flow_log("TAB_CHANGE","L1"); rebuild_movies(); g_flow_ready=false; }''',1)
s=s.replace('''        if(r1 && !p_r1) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; rebuild_movies(); g_flow_ready=false; }''',
'''        if(r1 && !p_r1) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; flow_log("TAB_CHANGE","R1"); rebuild_movies(); g_flow_ready=false; }''',1)

# Every 5 s log a heartbeat. Bracket one render per heartbeat interval so the
# last line identifies a render/flip hang without logging every frame.
render_anchor='''        p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_l1=l1; p_r1=r1;\n        render_ui();'''
render_new='''        p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_l1=l1; p_r1=r1;\n        uint64_t before_hb=g_last_heartbeat_us;\n        flow_log_heartbeat();\n        bool diag_render=(g_last_heartbeat_us!=before_hb);\n        if(diag_render) flow_log("RENDER_BEGIN",NULL);\n        render_ui();\n        if(diag_render) flow_log("RENDER_END",NULL);'''
if render_anchor not in s:
    raise SystemExit('render loop anchor not found')
s=s.replace(render_anchor,render_new,1)

# Normal exit marker.
exit_anchor='''    free_case_assets();\n    cover_cache_clear();'''
exit_new='''    flow_log("SESSION_EXIT","normal");\n    free_case_assets();\n    cover_cache_clear();'''
if exit_anchor not in s:
    raise SystemExit('exit anchor not found')
s=s.replace(exit_anchor,exit_new,1)

p.write_text(s)
print('FLOW MOVIE V2.15: width-only +6% and persistent freeze diagnostics')
