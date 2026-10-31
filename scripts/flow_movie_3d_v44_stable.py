from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()

def replace_function(sig,new,label):
    global s
    st=s.find(sig)
    if st<0: raise SystemExit(f'{label}: signature not found')
    br=s.find('{',st); dep=0; end=-1
    for i in range(br,len(s)):
        if s[i]=='{': dep+=1
        elif s[i]=='}':
            dep-=1
            if dep==0: end=i+1; break
    if end<0: raise SystemExit(f'{label}: close not found')
    s=s[:st]+new+s[end:]

def replace_once(old,new,label):
    global s
    if old not in s: raise SystemExit(f'{label}: anchor not found')
    s=s.replace(old,new,1)

if '#include <sys/thread.h>' not in s:
    s=s.replace('#include <sys/stat.h>\n','#include <sys/stat.h>\n#include <sys/thread.h>\n',1)

replace_function('static void flow_wait_gpu_frame_done()',r'''static volatile int g_gpu_frame_submitted=0;
static void flow_wait_gpu_frame_done(){
    if(!g_gpu_frame_submitted) return;
    int n=100;
    while(n-- > 0 && (s32)gcmGetFlipStatus() > 0) usleep(200);
}''','gpu wait')
s=s.replace('tiny3d_Flip();','flow_end_frame();')
wait_end=s.find('static void flow_begin_frame()')
helper='''static void flow_end_frame(){\n    tiny3d_Flip();\n    g_gpu_frame_submitted=1;\n}\n\n'''
s=s[:wait_end]+helper+s[wait_end:]
s=s.replace('static bool g_cover_allow_io = false;\n','')

anchor='static int g_cover_prefetch_selected = -1;\n'
async_globals=r'''

static volatile int g_scan_busy=0;
static volatile int g_scan_ready=0;
static volatile int g_scan_pending=0;
static int g_scan_tab=0;
static int g_scan_result_tab=0;
static std::vector<Movie> g_scan_result;

struct CoverWork {
    Movie movie;
    int index;
    std::string found_path;
    unsigned char *scaled;
    int w,h;
    bool found;
};
static CoverWork g_cover_work;
static volatile int g_cover_worker_busy=0;
static volatile int g_cover_worker_ready=0;
'''
replace_once(anchor,anchor+async_globals,'async globals')

replace_function('static CoverBitmap *get_movie_cover(Movie &m)',r'''static CoverBitmap *get_movie_cover(Movie &m)
{
    if(!m.cover_checked || m.cover.empty()) return NULL;
    for(int i=0;i<COVER_CACHE_SLOTS;i++) {
        if(g_cover_cache[i].rgba && g_cover_cache[i].path==m.cover) {
            g_cover_cache[i].stamp=++g_cover_stamp;
            return &g_cover_cache[i];
        }
    }
    return NULL;
}''','cache-only cover getter')

replace_function('static void rebuild_movies()',r'''static void rebuild_movies()
{
    const MediaTab scan_tab=(MediaTab)g_scan_tab;
    const char *folder=(scan_tab==TAB_BDISO)?"BDISO":"MKV";
    std::vector<Movie> fresh;
    ensure_internal_folders();
    {
        std::string root=std::string("/dev_hdd0/")+folder;
        DIR *dir=opendir(root.c_str());
        if(dir) {
            struct dirent *de;
            while((de=readdir(dir))!=NULL) {
                bool match=(scan_tab==TAB_BDISO)?ends_with_ci(de->d_name,".iso"):ends_with_ci(de->d_name,".mkv");
                if(de->d_name[0]=='.' || !match) continue;
                std::string full=root+"/"+de->d_name;
                struct stat st;
                if(stat(full.c_str(),&st)!=0) continue;
                Movie m; m.name=de->d_name; m.path=full; m.source="HDD INTERNO";
                m.usb_id=-1; m.bytes=(uint64_t)st.st_size; m.ntfs=false; m.cover_checked=false;
                fresh.push_back(m); if(fresh.size()>=1024) break;
            }
            closedir(dir);
        }
    }
    for(int usb=0;usb<8 && app_running;++usb) {
        if(!g_present[usb] || !g_mounts[usb] || g_mount_count[usb]<=0) continue;
        for(int part=0;part<g_mount_count[usb];++part) {
            if(!g_mounts[usb][part].name[0]) continue;
            std::string root=ntfs_folder_path(g_mounts[usb][part].name,folder);
            DIR_ITER *dir=ps3ntfs_diropen(root.c_str());
            if(!dir) continue;
            char filename[1024]; struct stat st;
            while(app_running && ps3ntfs_dirnext(dir,filename,&st)==0) {
                bool match=(scan_tab==TAB_BDISO)?ends_with_ci(filename,".iso"):ends_with_ci(filename,".mkv");
                if(filename[0]=='.' || !match) continue;
                Movie m; m.name=filename; m.path=root+"/"+filename;
                char src[32]; snprintf(src,sizeof(src),"USB %03d",usb); m.source=src;
                m.usb_id=usb; m.bytes=(uint64_t)st.st_size; m.ntfs=true; m.cover_checked=false;
                fresh.push_back(m); if(fresh.size()>=1024) break;
            }
            ps3ntfs_dirclose(dir);
        }
    }
    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){
        int n=strcasecmp(a.name.c_str(),b.name.c_str()); if(n!=0) return n<0; return a.source<b.source;
    });
    g_scan_result.swap(fresh);
    g_scan_result_tab=(int)scan_tab;
    __sync_synchronize();
    g_scan_ready=1;
}''','async rebuild')

replace_function('static bool refresh_usb_state(bool force_scan)',r'''static bool refresh_usb_state(bool force_scan)
{
    (void)force_scan;
    for(int usb=0;usb<8 && app_running;++usb) {
        bool inserted=PS3_NTFS_IsInserted(usb);
        if(inserted) {
            g_present[usb]=true;
            if(g_mount_count[usb]<=0 || !g_mounts[usb]) (void)mount_port(usb);
        } else if(g_present[usb] || g_mounts[usb] || g_mount_count[usb]>0) {
            g_present[usb]=false;
            release_port(usb,true);
        }
    }
    rebuild_movies();
    return true;
}''','async refresh')

scan_anchor='static int mount_bd_iso(const Movie &movie)\n'
scan_helpers=r'''static void scan_thread_entry(void *arg)
{
    (void)arg;
    refresh_usb_state(true);
    __sync_synchronize();
    g_scan_busy=0;
    sysThreadExit(0);
}

static void request_library_scan()
{
    if(g_scan_busy || g_scan_ready || g_cover_worker_busy || g_cover_worker_ready) { g_scan_pending=1; return; }
    g_scan_pending=0;
    g_scan_ready=0;
    g_scan_tab=(int)g_tab;
    g_scan_busy=1;
    sys_ppu_thread_t tid;
    if(sysThreadCreate(&tid,scan_thread_entry,NULL,1500,256*1024,0,(char*)"fm3d_scan")!=0) g_scan_busy=0;
}

static void apply_library_scan_result()
{
    if(!g_scan_ready) return;
    __sync_synchronize();
    g_scan_ready=0;
    if(g_scan_result_tab==(int)g_tab) {
        g_movies.swap(g_scan_result);
        g_scan_result.clear();
        cover_cache_clear();
        resolve_cover_paths();
        g_selected=0; g_flow_ready=false; g_cover_prefetch_selected=-1;
    } else g_scan_result.clear();
    if(g_scan_pending && !g_scan_busy && !g_scan_ready && !g_cover_worker_busy && !g_cover_worker_ready) request_library_scan();
}

'''
replace_once(scan_anchor,scan_helpers+scan_anchor,'scan helpers')

cover_anchor='static void flow_prefetch_one_cover()\n'
cover_helpers=r'''static void cover_worker_entry(void *arg)
{
    (void)arg;
    Movie m=g_cover_work.movie;
    std::string path=m.cover_checked ? m.cover : find_movie_cover(m);
    unsigned char *scaled=NULL; int cw=0,ch=0; bool found=false;
    if(!path.empty()) {
        size_t sz=0; unsigned char *file=read_file_bytes(m,path,&sz);
        if(file) {
            int pw=0,ph=0,pc=0;
            if(stbi_info_from_memory(file,(int)sz,&pw,&ph,&pc) && pw>0 && ph>0 && pw<=4096 && ph<=4096 && (uint64_t)pw*(uint64_t)ph<=6000000ULL) {
                int iw=0,ih=0,comp=0;
                unsigned char *decoded=stbi_load_from_memory(file,(int)sz,&iw,&ih,&comp,4);
                if(decoded) { scaled=scale_rgba(decoded,iw,ih,&cw,&ch); stbi_image_free(decoded); found=(scaled!=NULL); }
            }
            free(file);
        }
    }
    g_cover_work.found_path=path;
    g_cover_work.scaled=scaled; g_cover_work.w=cw; g_cover_work.h=ch; g_cover_work.found=found;
    __sync_synchronize();
    g_cover_worker_ready=1;
    g_cover_worker_busy=0;
    sysThreadExit(0);
}

static bool cover_cached(const std::string &path)
{
    if(path.empty()) return false;
    for(int i=0;i<COVER_CACHE_SLOTS;i++) if(g_cover_cache[i].rgba && g_cover_cache[i].path==path) return true;
    return false;
}

static void apply_cover_worker_result()
{
    if(!g_cover_worker_ready) return;
    __sync_synchronize();
    g_cover_worker_ready=0;
    int idx=g_cover_work.index;
    if(idx>=0 && idx<(int)g_movies.size() && g_movies[idx].path==g_cover_work.movie.path) {
        Movie &m=g_movies[idx];
        m.cover_checked=true; m.cover=g_cover_work.found_path;
        if(g_cover_work.found && g_cover_work.scaled && g_cover_work.w>0 && g_cover_work.h>0) {
            int slot=-1; unsigned oldest=0xFFFFFFFFu;
            for(int i=0;i<COVER_CACHE_SLOTS;i++) {
                if(g_cover_cache[i].path.empty()) { slot=i; break; }
                if(g_cover_cache[i].stamp<oldest) { oldest=g_cover_cache[i].stamp; slot=i; }
            }
            if(slot>=0) {
                const size_t cap=(size_t)320*480*4;
                if(!g_cover_cache[slot].rgba) g_cover_cache[slot].rgba=(unsigned char*)tiny3d_AllocTexture((u32)cap);
                if(g_cover_cache[slot].rgba) {
                    u32 *dst=(u32*)g_cover_cache[slot].rgba;
                    size_t count=(size_t)g_cover_work.w*g_cover_work.h;
                    for(size_t i=0;i<count;i++) {
                        const unsigned char *sp=g_cover_work.scaled+i*4;
                        dst[i]=((u32)sp[3]<<24)|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
                    }
                    g_cover_cache[slot].w=g_cover_work.w; g_cover_cache[slot].h=g_cover_work.h;
                    g_cover_cache[slot].path=m.cover; g_cover_cache[slot].stamp=++g_cover_stamp;
                }
            }
        }
    }
    if(g_cover_work.scaled) free(g_cover_work.scaled);
    g_cover_work.scaled=NULL; g_cover_work.found_path.clear();
    if(g_scan_pending && !g_scan_busy) request_library_scan();
}

static void start_cover_worker(int idx)
{
    if(idx<0 || idx>=(int)g_movies.size() || g_cover_worker_busy || g_cover_worker_ready || g_scan_busy) return;
    g_cover_work.movie=g_movies[idx]; g_cover_work.index=idx; g_cover_work.scaled=NULL;
    g_cover_worker_busy=1;
    sys_ppu_thread_t tid;
    if(sysThreadCreate(&tid,cover_worker_entry,NULL,1600,256*1024,0,(char*)"fm3d_cover")!=0) g_cover_worker_busy=0;
}

'''
replace_once(cover_anchor,cover_helpers+cover_anchor,'cover helpers')

replace_function('static void flow_prefetch_one_cover()',r'''static void flow_prefetch_one_cover()
{
    apply_cover_worker_result();
    if(g_scan_busy || g_scan_ready || g_cover_worker_busy || g_cover_worker_ready || g_movies.empty() || g_selected<0 || g_selected>=(int)g_movies.size()) return;
    if(g_cover_prefetch_selected!=g_selected) { g_cover_prefetch_selected=g_selected; g_cover_prefetch_step=0; }
    static const int offsets[9]={0,1,-1,2,-2,3,-3,4,-4};
    for(int tries=0;tries<9;++tries) {
        int off=offsets[g_cover_prefetch_step%9]; g_cover_prefetch_step=(g_cover_prefetch_step+1)%9;
        int idx=g_selected+off; if(idx<0 || idx>=(int)g_movies.size()) continue;
        Movie &m=g_movies[idx];
        if(!m.cover_checked || (!m.cover.empty() && !cover_cached(m.cover))) { start_cover_worker(idx); return; }
    }
}''','cover prefetch')

st=s.find('    ps3_env_info env = ps3_detect_env();\n')
en=s.find('    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }\n',st)
if st<0 or en<0: raise SystemExit('startup env block not found')
en += len('    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }\n')
s=s[:st]+'''    /* Stability rule: never patch LV2/Mamba during application startup. */\n    request_library_scan();\n'''+s[en:]
s=s.replace('    refresh_usb_state(true);\n\n    padData pad;','\n    padData pad;',1)
s=s.replace('    int poll_counter=0;\n','')
old='''        if(++poll_counter>=45) {\n            poll_counter=0;\n            refresh_usb_state(false);\n        }\n\n'''
s=s.replace(old,'        apply_library_scan_result();\n\n',1)
s=s.replace('if(r1 && !p_r1) { g_tab=(g_tab==TAB_BDISO)?TAB_MKV:TAB_BDISO; g_selected=0; g_flow_ready=false; rebuild_movies(); }','if(r1 && !p_r1) { g_tab=(g_tab==TAB_BDISO)?TAB_MKV:TAB_BDISO; g_movies.clear(); g_selected=0; g_flow_ready=false; cover_cache_clear(); request_library_scan(); }',1)
s=s.replace('if(l1 && !p_l1) { g_tab=(g_tab==TAB_MKV)?TAB_BDISO:TAB_MKV; g_selected=0; g_flow_ready=false; rebuild_movies(); }','if(l1 && !p_l1) { g_tab=(g_tab==TAB_MKV)?TAB_BDISO:TAB_MKV; g_movies.clear(); g_selected=0; g_flow_ready=false; cover_cache_clear(); request_library_scan(); }',1)
s=s.replace('if(tri && !p_tri) { g_cover_prefetch_selected=-1; refresh_usb_state(true); }','if(tri && !p_tri) { g_cover_prefetch_selected=-1; request_library_scan(); }',1)
s=s.replace('                    refresh_usb_state(true);','                    request_library_scan();',1)
needle='''            if(g_tab == TAB_BDISO) {\n                show_status("Montando pelicula Blu-ray ISO...\\n\\nNo desconectes el disco.");'''
repl='''            if(g_tab == TAB_BDISO) {\n                ps3_env_info run_env=ps3_detect_env();\n                if(!ps3_env_has_cobra_api(&run_env)) {\n                    show_ok("Cobra/Mamba/PS3HEN no esta activo.\\n\\nPor estabilidad FLOW MOVIE 3D no parchea LV2 automaticamente. Activa HEN o Cobra y vuelve a intentarlo.");\n                    p_x=x;\n                    render_ui();\n                    usleep(16000);\n                    continue;\n                }\n                show_status("Montando pelicula Blu-ray ISO...\\n\\nNo desconectes el disco.");'''
replace_once(needle,repl,'on-demand env check')
s=s.replace('''    cover_cache_clear();\n    cleanup_ntfs();\n    ioPadEnd();''','''    cover_cache_clear();\n    if(!g_scan_busy && !g_cover_worker_busy) cleanup_ntfs();\n    ioPadEnd();''',1)
footer='''    std::string help="X  ABRIR     TRIANGULO  ACTUALIZAR     L1/R1  CAMBIAR     O  SALIR";'''
s=s.replace(footer,'''    if(g_scan_busy) draw_text(18,fy-24,"ESCANEANDO BIBLIOTECA...",1,0xFF55BDFD,40);\n    std::string help="X  ABRIR     TRIANGULO  ACTUALIZAR     L1/R1  CAMBIAR     O  SALIR";''',1)

p.write_text(s)
print('FLOW MOVIE 3D V4.4 stable patch applied')
