from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()

def replace_once(old,new,label):
    global s
    if old not in s:
        raise SystemExit(f'{label}: anchor not found')
    s=s.replace(old,new,1)

def replace_function(sig,new,label):
    global s
    st=s.find(sig)
    if st<0: raise SystemExit(f'{label}: signature not found')
    br=s.find('{',st)
    if br<0: raise SystemExit(f'{label}: opening brace not found')
    dep=0; end=-1
    for i in range(br,len(s)):
        if s[i]=='{': dep+=1
        elif s[i]=='}':
            dep-=1
            if dep==0:
                end=i+1; break
    if end<0: raise SystemExit(f'{label}: closing brace not found')
    s=s[:st]+new+s[end:]

if '#include <stdarg.h>' not in s:
    s=s.replace('#include <stdio.h>\n','#include <stdio.h>\n#include <stdarg.h>\n',1)

anchor='static unsigned int g_frame = 0;\n'
log_code=r'''

#define BOOT_LOG_PATH "/dev_hdd0/tmp/FLOW_MOVIE_3D_BOOT.LOG"
#define BOOT_LOG_PREV "/dev_hdd0/tmp/FLOW_MOVIE_3D_BOOT_PREV.LOG"
#define BOOT_LOG_FALLBACK "/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE_3D_BOOT.LOG"
static FILE *g_boot_log=NULL;
static volatile int g_log_lock=0;
static volatile int g_boot_stage=0;
static volatile unsigned int g_main_heartbeat=0;
static volatile int g_watchdog_stop=0;
static sys_ppu_thread_t g_watchdog_tid=0;

static void bootlogf(const char *tag,const char *fmt,...)
{
    int tries=100;
    while(__sync_lock_test_and_set(&g_log_lock,1)) {
        if(--tries<=0) return;
        usleep(100);
    }
    if(g_boot_log) {
        fprintf(g_boot_log,"[%s] stage=%d frame=%u hb=%u ",tag?tag:"LOG",(int)g_boot_stage,(unsigned)g_frame,(unsigned)g_main_heartbeat);
        va_list ap; va_start(ap,fmt); vfprintf(g_boot_log,fmt,ap); va_end(ap);
        fputc('\n',g_boot_log);
        fflush(g_boot_log);
    }
    __sync_lock_release(&g_log_lock);
}

static void boot_stage(int stage,const char *name)
{
    g_boot_stage=stage;
    __sync_synchronize();
    bootlogf("STAGE","%s",name?name:"(sin nombre)");
}

static void bootlog_init()
{
    remove(BOOT_LOG_PREV);
    rename(BOOT_LOG_PATH,BOOT_LOG_PREV);
    g_boot_log=fopen(BOOT_LOG_PATH,"w");
    if(!g_boot_log) g_boot_log=fopen(BOOT_LOG_FALLBACK,"w");
    if(g_boot_log) setvbuf(g_boot_log,NULL,_IONBF,0);
    bootlogf("BOOT","FLOW MOVIE 3D V4.5 DIAG inicio");
}

static void bootlog_close()
{
    if(!g_boot_log) return;
    bootlogf("BOOT","cerrando log");
    FILE *f=g_boot_log; g_boot_log=NULL;
    fflush(f); fclose(f);
}

static void watchdog_thread_entry(void *arg)
{
    (void)arg;
    int last_stage=-1;
    unsigned int last_hb=0;
    int stagnant=0;
    while(!g_watchdog_stop) {
        usleep(2000000);
        int st=(int)g_boot_stage;
        unsigned int hb=(unsigned)g_main_heartbeat;
        if(st==last_stage && hb==last_hb) stagnant++;
        else stagnant=0;
        if(stagnant==2) bootlogf("WATCHDOG","posible bloqueo: sin progreso durante ~6 s");
        else if(stagnant>2 && (stagnant%5)==0) bootlogf("WATCHDOG","bloqueo continua");
        last_stage=st; last_hb=hb;
    }
    sysThreadExit(0);
}

static void start_watchdog()
{
    int rc=sysThreadCreate(&g_watchdog_tid,watchdog_thread_entry,NULL,1700,64*1024,0,(char*)"fm3d_watchdog");
    bootlogf("WATCHDOG","create rc=%d",rc);
}
'''
replace_once(anchor,anchor+log_code,'logging globals')

replace_function('static void flow_wait_gpu_frame_done()',r'''static void flow_wait_gpu_frame_done()
{
    /* V4.5: no direct gcmGetFlipStatus polling. tiny3d_Flip owns presentation sync. */
}''','safe gpu wait')
replace_function('static void flow_end_frame()',r'''static void flow_end_frame()
{
    tiny3d_Flip();
    g_gpu_frame_submitted=1;
}''','safe frame end')
replace_function('static void flow_begin_frame()',r'''static void flow_begin_frame()
{
    tiny3d_Clear(0xFF000000,TINY3D_CLEAR_ALL);
    tiny3d_AlphaTest(1,0x10,TINY3D_ALPHA_FUNC_GEQUAL);
    tiny3d_BlendFunc(1,
        (blend_src_func)(TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA),
        (blend_dst_func)(TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO),
        (blend_func)(TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD));
    tiny3d_Project2D();
}''','safe frame begin')

replace_function('static bool refresh_usb_state(bool force_scan)',r'''static bool refresh_usb_state(bool force_scan)
{
    (void)force_scan;
    bootlogf("SCAN","USB scan begin");
    for(int usb=0;usb<8 && app_running;++usb) {
        bootlogf("SCAN","usb=%d PS3_NTFS_IsInserted enter",usb);
        bool inserted=PS3_NTFS_IsInserted(usb);
        bootlogf("SCAN","usb=%d inserted=%d",usb,inserted?1:0);
        if(inserted) {
            g_present[usb]=true;
            if(g_mount_count[usb]<=0 || !g_mounts[usb]) {
                bootlogf("SCAN","usb=%d mount_port enter",usb);
                bool mounted=mount_port(usb);
                bootlogf("SCAN","usb=%d mount_port done ok=%d count=%d",usb,mounted?1:0,g_mount_count[usb]);
            }
        } else if(g_present[usb] || g_mounts[usb] || g_mount_count[usb]>0) {
            bootlogf("SCAN","usb=%d release_port enter",usb);
            g_present[usb]=false;
            release_port(usb,true);
            bootlogf("SCAN","usb=%d release_port done",usb);
        }
    }
    bootlogf("SCAN","rebuild_movies enter");
    rebuild_movies();
    bootlogf("SCAN","rebuild_movies done result_count=%u",(unsigned)g_scan_result.size());
    return true;
}''','instrument refresh')

replace_function('static void scan_thread_entry(void *arg)',r'''static void scan_thread_entry(void *arg)
{
    (void)arg;
    bootlogf("SCAN","worker begin tab=%d",(int)g_scan_tab);
    refresh_usb_state(true);
    bootlogf("SCAN","worker refresh returned");
    __sync_synchronize();
    g_scan_busy=0;
    bootlogf("SCAN","worker end ready=%d",(int)g_scan_ready);
    sysThreadExit(0);
}''','instrument scan worker')

replace_function('static void cover_worker_entry(void *arg)',r'''static void cover_worker_entry(void *arg)
{
    (void)arg;
    Movie m=g_cover_work.movie;
    bootlogf("COVER","worker begin idx=%d movie=%s",g_cover_work.index,m.name.c_str());
    std::string path=m.cover_checked ? m.cover : find_movie_cover(m);
    bootlogf("COVER","cover path=%s",path.empty()?"(none)":path.c_str());
    unsigned char *scaled=NULL; int cw=0,ch=0; bool found=false;
    if(!path.empty()) {
        size_t sz=0;
        bootlogf("COVER","read enter");
        unsigned char *file=read_file_bytes(m,path,&sz);
        bootlogf("COVER","read done bytes=%u ptr=%p",(unsigned)sz,(void*)file);
        if(file) {
            int pw=0,ph=0,pc=0;
            int info_ok=stbi_info_from_memory(file,(int)sz,&pw,&ph,&pc);
            bootlogf("COVER","stbi_info ok=%d w=%d h=%d comp=%d",info_ok,pw,ph,pc);
            if(info_ok && pw>0 && ph>0 && pw<=4096 && ph<=4096 && (uint64_t)pw*(uint64_t)ph<=6000000ULL) {
                int iw=0,ih=0,comp=0;
                bootlogf("COVER","decode enter");
                unsigned char *decoded=stbi_load_from_memory(file,(int)sz,&iw,&ih,&comp,4);
                bootlogf("COVER","decode done ptr=%p w=%d h=%d",(void*)decoded,iw,ih);
                if(decoded) {
                    scaled=scale_rgba(decoded,iw,ih,&cw,&ch);
                    stbi_image_free(decoded);
                    found=(scaled!=NULL);
                    bootlogf("COVER","scale done found=%d w=%d h=%d",found?1:0,cw,ch);
                }
            }
            free(file);
        }
    }
    g_cover_work.found_path=path;
    g_cover_work.scaled=scaled; g_cover_work.w=cw; g_cover_work.h=ch; g_cover_work.found=found;
    __sync_synchronize();
    g_cover_worker_ready=1;
    g_cover_worker_busy=0;
    bootlogf("COVER","worker end");
    sysThreadExit(0);
}''','instrument cover worker')

replace_function('static int mount_bd_iso(const Movie &movie)',r'''static int mount_bd_iso(const Movie &movie)
{
    bootlogf("MOUNT","begin ntfs=%d usb=%d path=%s",movie.ntfs?1:0,movie.usb_id,movie.path.c_str());
    if(!movie.ntfs) {
        char *files[1];
        files[0]=const_cast<char*>(movie.path.c_str());
        bootlogf("MOUNT","cobra_umount_disc_image enter");
        cobra_umount_disc_image();
        usleep(100000);
        bootlogf("MOUNT","cobra_mount_bd_disc_image enter");
        int rc=cobra_mount_bd_disc_image(files,1);
        bootlogf("MOUNT","cobra_mount_bd_disc_image rc=%d",rc);
        return rc;
    }
    struct stat st;
    if(stat(RAWISO_PATH,&st)!=0) { bootlogf("MOUNT","raw_iso missing"); return -103; }
    bootlogf("MOUNT","PS3_NTFS_IsInserted enter usb=%d",movie.usb_id);
    if(movie.usb_id<0 || movie.usb_id>7 || !PS3_NTFS_IsInserted(movie.usb_id)) { bootlogf("MOUNT","USB not inserted"); return -104; }
    void *plugin_args=memalign(128,0x10000);
    uint32_t *sections=(uint32_t*)malloc(MAX_SECTIONS*sizeof(uint32_t));
    uint32_t *sizes=(uint32_t*)malloc(MAX_SECTIONS*sizeof(uint32_t));
    if(!plugin_args || !sections || !sizes) {
        free(plugin_args); free(sections); free(sizes);
        bootlogf("MOUNT","allocation failed");
        return -100;
    }
    memset(plugin_args,0,0x10000);
    memset(sections,0,MAX_SECTIONS*sizeof(uint32_t));
    memset(sizes,0,MAX_SECTIONS*sizeof(uint32_t));
    bootlogf("MOUNT","ps3ntfs_file_to_sectors enter");
    int parts=ps3ntfs_file_to_sectors(movie.path.c_str(),sections,sizes,MAX_SECTIONS,1);
    bootlogf("MOUNT","ps3ntfs_file_to_sectors parts=%d",parts);
    if(parts<=0 || parts>=MAX_SECTIONS) {
        free(plugin_args); free(sections); free(sizes);
        return (parts>=MAX_SECTIONS)?-102:-101;
    }
    rawseciso_args *args=(rawseciso_args*)plugin_args;
    args->device=USB_MASS_STORAGE(movie.usb_id);
    args->emu_mode=EMU_BD;
    args->num_sections=(uint32_t)parts;
    args->num_tracks=0;
    memcpy((uint8_t*)plugin_args+sizeof(rawseciso_args),sections,parts*sizeof(uint32_t));
    memcpy((uint8_t*)plugin_args+sizeof(rawseciso_args)+parts*sizeof(uint32_t),sizes,parts*sizeof(uint32_t));
    bootlogf("MOUNT","cobra_unload_vsh_plugin enter");
    cobra_unload_vsh_plugin(0);
    usleep(100000);
    bootlogf("MOUNT","cobra_load_vsh_plugin enter");
    int ret=cobra_load_vsh_plugin(0,(char*)RAWISO_PATH,plugin_args,0x10000);
    bootlogf("MOUNT","cobra_load_vsh_plugin rc=%d",ret);
    free(plugin_args); free(sections); free(sizes);
    return ret;
}''','instrument bd mount')

old=r'''int main(int argc, char *argv[])
{
    (void)argc; (void)argv;
    int tiny3d_rc = tiny3d_Init(4u*1024u*1024u);
    if(tiny3d_rc != 0) return 10;
    tiny3d_UserViewport(1,0.0f,0.0f,(float)Video_Resolution.width/848.0f,(float)Video_Resolution.height/512.0f,
                        (float)Video_Resolution.width/1920.0f,(float)Video_Resolution.height/1080.0f);
    ioPadInit(7);
    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);

    for(int boot_frame=0; boot_frame<24; ++boot_frame){
'''
new=r'''int main(int argc, char *argv[])
{
    (void)argc; (void)argv;
    bootlog_init();
    boot_stage(1,"process entered; before watchdog");
    start_watchdog();
    boot_stage(2,"tiny3d_Init enter");
    int tiny3d_rc=tiny3d_Init(1024u*1024u);
    bootlogf("TINY3D","tiny3d_Init rc=%d resolution=%ux%u",tiny3d_rc,(unsigned)Video_Resolution.width,(unsigned)Video_Resolution.height);
    if(tiny3d_rc!=0) {
        boot_stage(90,"FATAL tiny3d_Init failed");
        g_watchdog_stop=1; bootlog_close();
        return 10;
    }
    /* Project2D already uses Tiny3D's 848x512 virtual space. */
    boot_stage(3,"Tiny3D ready; ioPadInit enter");
    int pad_rc=ioPadInit(7);
    bootlogf("PAD","ioPadInit rc=%d",pad_rc);
    boot_stage(4,"sysUtilRegisterCallback enter");
    int cb_rc=sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);
    bootlogf("SYSUTIL","register callback rc=%d",cb_rc);
    boot_stage(5,"first minimal Tiny3D frames");
    for(int boot_frame=0; boot_frame<24; ++boot_frame){
        g_main_heartbeat++;
'''
replace_once(old,new,'main startup prefix')
replace_once('''    load_font();\n    flow_init_font_texture();\n    for(int boot_frame=0; boot_frame<24; ++boot_frame){\n''','''    boot_stage(6,"first frames complete; load_font enter");\n    load_font();\n    bootlogf("FONT","load_font ptr=%p",(void*)g_font);\n    boot_stage(7,"flow_init_font_texture enter");\n    int font_tex_rc=flow_init_font_texture();\n    bootlogf("FONT","flow_init_font_texture rc=%d tex=%p",font_tex_rc,(void*)g_font_tex);\n    boot_stage(8,"second splash frames");\n    for(int boot_frame=0; boot_frame<24; ++boot_frame){\n        g_main_heartbeat++;\n''','font startup instrumentation')
replace_once('''    ensure_internal_folders();\n\n    /* Stability rule: never patch LV2/Mamba during application startup. */\n    request_library_scan();\n''','''    boot_stage(9,"ensure_internal_folders enter");\n    ensure_internal_folders();\n    bootlogf("BOOT","ensure_internal_folders done");\n    /* Stability rule: never patch LV2/Mamba during application startup. */\n    boot_stage(10,"request_library_scan");\n    request_library_scan();\n    bootlogf("BOOT","request_library_scan returned busy=%d",(int)g_scan_busy);\n''','startup scan instrumentation')
replace_once('''    while(app_running) {\n        sysUtilCheckCallback();\n''','''    boot_stage(11,"main loop entered");\n    while(app_running) {\n        g_main_heartbeat++;\n        if((g_frame%300u)==0u) bootlogf("HEARTBEAT","main loop alive movies=%u scan_busy=%d cover_busy=%d tab=%d",(unsigned)g_movies.size(),(int)g_scan_busy,(int)g_cover_worker_busy,(int)g_tab);\n        sysUtilCheckCallback();\n''','main loop heartbeat')
replace_once('''                ps3_env_info run_env=ps3_detect_env();\n''','''                bootlogf("INPUT","X on BDISO name=%s source=%s",movie.name.c_str(),movie.source.c_str());\n                bootlogf("ENV","ps3_detect_env enter");\n                ps3_env_info run_env=ps3_detect_env();\n                bootlogf("ENV","ps3_detect_env done env=%s",ps3_env_name(&run_env));\n''','mount env logging')
replace_once('''                int ret=mount_bd_iso(movie);\n''','''                bootlogf("MOUNT","mount_bd_iso call enter");\n                int ret=mount_bd_iso(movie);\n                bootlogf("MOUNT","mount_bd_iso returned ret=%d",ret);\n''','mount call logging')
replace_once('''    cover_cache_clear();\n    if(!g_scan_busy && !g_cover_worker_busy) cleanup_ntfs();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n    if(g_font) free(g_font);\n    return 0;\n''','''    boot_stage(80,"normal shutdown");\n    cover_cache_clear();\n    if(!g_scan_busy && !g_cover_worker_busy) cleanup_ntfs();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n    if(g_font) free(g_font);\n    g_watchdog_stop=1;\n    bootlogf("BOOT","normal exit");\n    bootlog_close();\n    return 0;\n''','shutdown logging')

p.write_text(s)
print('FLOW MOVIE 3D V4.5 diagnostic boot log + conservative Tiny3D startup applied')
