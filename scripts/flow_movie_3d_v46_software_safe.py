from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

def replace_once(old,new,label):
    global s
    if old not in s:
        raise SystemExit(f'{label}: anchor not found')
    s=s.replace(old,new,1)

if '#include <stdarg.h>' not in s:
    s=s.replace('#include <stdio.h>\n','#include <stdio.h>\n#include <stdarg.h>\n',1)

anchor='static unsigned int g_frame = 0;\n'
log_code=r'''

#define BOOT_LOG_PATH "/dev_hdd0/tmp/FLOW_MOVIE_3D_BOOT.LOG"
#define BOOT_LOG_PREV "/dev_hdd0/tmp/FLOW_MOVIE_3D_BOOT_PREV.LOG"
#define BOOT_LOG_FALLBACK "/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE_3D_BOOT.LOG"
static FILE *g_boot_log=NULL;
static int g_boot_stage=0;

static void bootlogf(const char *tag,const char *fmt,...)
{
    if(!g_boot_log) return;
    fprintf(g_boot_log,"[%s] stage=%d frame=%u ",tag?tag:"LOG",g_boot_stage,g_frame);
    va_list ap; va_start(ap,fmt); vfprintf(g_boot_log,fmt,ap); va_end(ap);
    fputc('\n',g_boot_log);
    fflush(g_boot_log);
}

static void boot_stage(int stage,const char *name)
{
    g_boot_stage=stage;
    bootlogf("STAGE","%s",name?name:"(sin nombre)");
}

static void bootlog_init()
{
    mkdir("/dev_hdd0/tmp",0777);
    remove(BOOT_LOG_PREV);
    rename(BOOT_LOG_PATH,BOOT_LOG_PREV);
    g_boot_log=fopen(BOOT_LOG_PATH,"w");
    if(!g_boot_log) g_boot_log=fopen(BOOT_LOG_FALLBACK,"w");
    if(g_boot_log) setvbuf(g_boot_log,NULL,_IONBF,0);
    bootlogf("BOOT","FLOW MOVIE 3D V4.6 SOFTWARE SAFE inicio");
}

static void bootlog_close()
{
    if(!g_boot_log) return;
    bootlogf("BOOT","cerrando log");
    FILE *f=g_boot_log; g_boot_log=NULL; fclose(f);
}
'''
replace_once(anchor,anchor+log_code,'boot log globals')

# L1 = previous tab, R1 = next tab. With two tabs both wrap naturally.
s=s.replace('bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_r1=false,p_r2=false;',
            'bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_l1=false,p_r1=false;',1)
s=s.replace('bool r1=pad.BTN_R1, r2=pad.BTN_R2;', 'bool l1=pad.BTN_L1, r1=pad.BTN_R1;',1)
s=s.replace('if(r1 && !p_r1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; rebuild_movies(); }\n        if(r2 && !p_r2) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; rebuild_movies(); }',
'''if(l1 && !p_l1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; bootlogf("INPUT","L1 tab=%d",(int)g_tab); rebuild_movies(); }
        if(r1 && !p_r1) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; bootlogf("INPUT","R1 tab=%d",(int)g_tab); rebuild_movies(); }''',1)
s=s.replace('p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_r1=r1; p_r2=r2;',
            'p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_l1=l1; p_r1=r1;',1)
# V3 left shoulder badge used R2.
s=s.replace('"R2"','"L1"')

main_pos=s.find('int main(int argc, char *argv[])')
if main_pos<0:
    raise SystemExit('main not found')
body=s[main_pos:]
body=body.replace('    (void)argc; (void)argv;\n',
'''    (void)argc; (void)argv;
    bootlog_init();
    boot_stage(1,"process entered; software renderer selected");
''',1)
body=body.replace('    void *host_addr=memalign(1024*1024,HOST_SIZE);\n    if(!host_addr) return 1;\n\n    init_screen(host_addr,HOST_SIZE);\n    ioPadInit(7);\n    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);\n    load_font();\n    ensure_internal_folders();',
'''    boot_stage(2,"allocate RSX host memory");
    void *host_addr=memalign(1024*1024,HOST_SIZE);
    bootlogf("RSX","host_addr=%p size=%u",host_addr,(unsigned)HOST_SIZE);
    if(!host_addr) { boot_stage(90,"FATAL host allocation failed"); bootlog_close(); return 1; }

    boot_stage(3,"legacy init_screen enter");
    init_screen(host_addr,HOST_SIZE);
    bootlogf("RSX","legacy init_screen returned");
    boot_stage(4,"pad init");
    int pad_rc=ioPadInit(7);
    bootlogf("PAD","ioPadInit rc=%d",pad_rc);
    boot_stage(5,"sysutil callback");
    int cb_rc=sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);
    bootlogf("SYSUTIL","register rc=%d",cb_rc);
    boot_stage(6,"font load");
    bool font_ok=load_font();
    bootlogf("FONT","load_font ok=%d ptr=%p",font_ok?1:0,(void*)g_font);
    ensure_internal_folders();''',1)

# Disable automatic LV2/Mamba bootstrap. Require already active HEN/Cobra.
env_start=body.find('    ps3_env_info env = ps3_detect_env();')
env_end=body.find('    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }',env_start)
if env_start<0 or env_end<0:
    raise SystemExit('environment startup block not found')
env_repl=r'''    boot_stage(7,"read-only HEN/Cobra detection");
    ps3_env_info env=ps3_detect_env();
    bootlogf("ENV","type=%s fw=%d kernel=%s cobra_api=%d",ps3_env_name(env.type),env.firmware_code,ps3_kernel_name(env.kernel),ps3_env_has_cobra_api(&env));
    if(!ps3_env_has_cobra_api(&env)) {
        show_ok("No se detecto HEN/Cobra activo.\n\nActiva HEN antes de abrir FLOW MOVIE 3D.\n\nV4.6 SAFE no parchea LV2/Mamba durante el arranque.");
        ioPadEnd();
        sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
        if(g_font) free(g_font);
        free(host_addr);
        boot_stage(91,"exit: HEN/Cobra unavailable");
        bootlog_close();
        return 2;
    }

    boot_stage(8,"first SOFTWARE frame enter");
    render_ui();
    bootlogf("VIDEO","first software frame returned");
    usleep(50000);

    /* Safe startup: do NOT touch NTFS automatically. First build HDD library only. */
    boot_stage(9,"internal HDD library scan");
    rebuild_movies();
    bootlogf("SCAN","internal scan returned movies=%u",(unsigned)g_movies.size());
'''
# remove old warmup + refresh call too
refresh_pos=body.find('    refresh_usb_state(true);',env_end)
if refresh_pos<0:
    raise SystemExit('startup refresh not found')
refresh_end=refresh_pos+len('    refresh_usb_state(true);')
body=body[:env_start]+env_repl+body[refresh_end:]

# No automatic NTFS polling. Triangle remains explicit refresh.
body=body.replace('    int poll_counter=0;\n','',1)
poll='''        if(++poll_counter>=45) {
            poll_counter=0;
            refresh_usb_state(false);
        }

'''
body=body.replace(poll,'',1)

# Log triangle refresh and mount boundaries.
body=body.replace('        if(tri && !p_tri) refresh_usb_state(true);',
'''        if(tri && !p_tri) {
            bootlogf("SCAN","TRIANGLE manual NTFS refresh enter");
            refresh_usb_state(true);
            bootlogf("SCAN","TRIANGLE manual NTFS refresh done movies=%u",(unsigned)g_movies.size());
        }''',1)
body=body.replace('            int ret=mount_bd_iso(movie);',
'''            bootlogf("MOUNT","mount enter name=%s source=%s ntfs=%d",movie.name.c_str(),movie.source.c_str(),movie.ntfs?1:0);
            int ret=mount_bd_iso(movie);
            bootlogf("MOUNT","mount returned ret=%d",ret);''',1)

# Main-loop heartbeat and shutdown log.
body=body.replace('    while(app_running) {\n        sysUtilCheckCallback();',
'''    boot_stage(10,"main loop entered");
    while(app_running) {
        if((g_frame%300u)==0u) bootlogf("HEARTBEAT","UI alive movies=%u tab=%d",(unsigned)g_movies.size(),(int)g_tab);
        sysUtilCheckCallback();''',1)
body=body.replace('    free(host_addr);\n    return 0;',
'''    free(host_addr);
    boot_stage(80,"normal shutdown");
    bootlog_close();
    return 0;''',1)

s=s[:main_pos]+body
p.write_text(s)
print('FLOW MOVIE 3D V4.6 SOFTWARE SAFE applied: legacy renderer, L1/R1, no automatic NTFS/Mamba, persistent boot log')
