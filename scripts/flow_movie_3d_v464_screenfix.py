from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

def replace_block(start_marker,end_marker,new_block,label):
    global s
    a=s.find(start_marker)
    if a<0: raise SystemExit(f'{label}: start not found')
    b=s.find(end_marker,a)
    if b<0: raise SystemExit(f'{label}: end not found')
    s=s[:a]+new_block+s[b:]

# Keep the V2/FONT-FIX software framebuffer presentation untouched.
# Only add a lightweight persistent log, restore the proven V3 NTFS scanner,
# and use L1/R1 for the two media tabs.
if '#include <stdarg.h>' not in s:
    s=s.replace('#include <stdio.h>\n','#include <stdio.h>\n#include <stdarg.h>\n',1)

anchor='static unsigned int g_frame = 0;\n'
if anchor not in s: raise SystemExit('g_frame anchor not found')
log_code=r'''

#define BOOT_LOG_PATH "/dev_hdd0/tmp/FLOW_MOVIE_3D_BOOT.LOG"
#define BOOT_LOG_PREV "/dev_hdd0/tmp/FLOW_MOVIE_3D_BOOT_PREV.LOG"
static FILE *g_boot_log=NULL;

static void bootlogf(const char *tag,const char *fmt,...)
{
    if(!g_boot_log) return;
    fprintf(g_boot_log,"[%s] frame=%u ",tag?tag:"LOG",g_frame);
    va_list ap; va_start(ap,fmt); vfprintf(g_boot_log,fmt,ap); va_end(ap);
    fputc('\n',g_boot_log);
    fflush(g_boot_log);
}

static void bootlog_init()
{
    mkdir("/dev_hdd0/tmp",0777);
    remove(BOOT_LOG_PREV);
    rename(BOOT_LOG_PATH,BOOT_LOG_PREV);
    g_boot_log=fopen(BOOT_LOG_PATH,"w");
    if(g_boot_log) setvbuf(g_boot_log,NULL,_IONBF,0);
    bootlogf("BOOT","FLOW MOVIE 3D V4.6.4 SCREEN FIX inicio");
}

static void bootlog_close()
{
    if(!g_boot_log) return;
    bootlogf("BOOT","cierre normal");
    FILE *f=g_boot_log; g_boot_log=NULL; fclose(f);
}
'''
s=s.replace(anchor,anchor+log_code,1)

mount_block=r'''static bool mount_port(int usb)
{
    if(usb<0 || usb>7) return false;
    bootlogf("NTFS","V3 mount usb=%d begin",usb);

    if(g_mounts[usb] || g_mount_count[usb]>0) release_port(usb,false);
    else PS3_NTFS_Shutdown(usb);

    g_mounts[usb]=NULL;
    g_mount_count[usb]=0;
    usleep(120000);

    g_mount_count[usb]=ntfsMountDevice(
        disc_ntfs[usb],
        &g_mounts[usb],
        NTFS_DEFAULT | NTFS_RECOVER
    );
    bootlogf("NTFS","first usb=%d count=%d err=%d",usb,g_mount_count[usb],ps3ntfs_errno());

    if(g_mount_count[usb]<=0)
    {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb]=NULL; }
        PS3_NTFS_Shutdown(usb);
        usleep(180000);
        g_mount_count[usb]=ntfsMountDevice(
            disc_ntfs[usb],
            &g_mounts[usb],
            NTFS_DEFAULT | NTFS_RECOVER
        );
        bootlogf("NTFS","retry usb=%d count=%d err=%d",usb,g_mount_count[usb],ps3ntfs_errno());
    }

    if(g_mount_count[usb]<=0 || !g_mounts[usb])
    {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb]=NULL; }
        g_mount_count[usb]=0;
        g_present[usb]=false;
        return false;
    }

    g_present[usb]=true;
    for(int part=0;part<g_mount_count[usb];++part)
        bootlogf("NTFS","mounted usb=%d part=%d name=%s",usb,part,g_mounts[usb][part].name);
    return true;
}

'''
replace_block('static bool mount_port(int usb)','static void rebuild_movies()',mount_block,'mount_port')

rebuild_block=r'''static void rebuild_movies()
{
    std::string previous_path;
    if(!g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size())
        previous_path=g_movies[g_selected].path;

    std::vector<Movie> fresh;
    ensure_internal_folders();

    /* Internal HDD - identical V2/FONT-FIX library behavior. */
    {
        std::string root=std::string("/dev_hdd0/")+current_folder();
        DIR *dir=opendir(root.c_str());
        if(dir) {
            struct dirent *de;
            while((de=readdir(dir))!=NULL) {
                if(de->d_name[0]=='.' || !matches_current_tab(de->d_name)) continue;
                std::string full=root+"/"+de->d_name;
                struct stat st;
                if(stat(full.c_str(),&st)!=0) continue;
                Movie m;
                m.name=de->d_name; m.path=full; m.source="HDD INTERNO"; m.cover.clear();
                m.usb_id=-1; m.bytes=(uint64_t)st.st_size; m.ntfs=false;
                fresh.push_back(m);
                if(fresh.size()>=1024) break;
            }
            closedir(dir);
        }
    }

    /* External USB NTFS - proven V3 mount:/BDISO path. */
    for(int usb=0;usb<8;++usb) {
        if(!g_mounts[usb] || g_mount_count[usb]<=0) continue;
        for(int part=0;part<g_mount_count[usb];++part) {
            if(!g_mounts[usb][part].name[0]) continue;
            std::string root=std::string(g_mounts[usb][part].name)+":"+std::string("/")+current_folder();
            DIR_ITER *dir=ps3ntfs_diropen(root.c_str());
            if(!dir) {
                std::string n=g_mounts[usb][part].name;
                if(!n.empty() && n[n.size()-1]==':') root=n+"/"+current_folder();
                dir=ps3ntfs_diropen(root.c_str());
            }
            bootlogf("NTFS","folder usb=%d part=%d root=%s open=%d err=%d",usb,part,root.c_str(),dir?1:0,dir?0:ps3ntfs_errno());
            if(!dir) continue;

            char filename[1024];
            struct stat st;
            while(ps3ntfs_dirnext(dir,filename,&st)==0) {
                if(filename[0]=='.' || !matches_current_tab(filename)) continue;
                Movie m;
                m.name=filename; m.path=root+"/"+filename; m.cover.clear();
                char src[32]; snprintf(src,sizeof(src),"USB %03d",usb);
                m.source=src; m.usb_id=usb; m.bytes=(uint64_t)st.st_size; m.ntfs=true;
                fresh.push_back(m);
                bootlogf("NTFS","found usb=%d file=%s bytes=%llu",usb,filename,(unsigned long long)m.bytes);
                if(fresh.size()>=1024) break;
            }
            ps3ntfs_dirclose(dir);
        }
    }

    std::sort(fresh.begin(),fresh.end(),[](const Movie &a,const Movie &b){
        int n=strcasecmp(a.name.c_str(),b.name.c_str());
        if(n!=0) return n<0;
        return a.source<b.source;
    });

    g_movies.swap(fresh);
    cover_cache_clear();
    resolve_cover_paths();
    g_selected=0;
    if(!previous_path.empty()) {
        for(size_t i=0;i<g_movies.size();++i)
            if(g_movies[i].path==previous_path) { g_selected=(int)i; break; }
    }
    if(g_movies.empty()) g_selected=0;
    else if(g_selected>=(int)g_movies.size()) g_selected=(int)g_movies.size()-1;
    bootlogf("SCAN","library rebuilt tab=%d movies=%u",(int)g_tab,(unsigned)g_movies.size());
}

'''
replace_block('static void rebuild_movies()','static bool refresh_usb_state(bool force_scan)',rebuild_block,'rebuild_movies')

refresh_block=r'''static bool refresh_usb_state(bool force_scan)
{
    /* Do not use IsInserted as a prerequisite. The old working V3 reader
       mounted every USB interface directly after a short enumeration delay. */
    if(!force_scan) return false;

    bootlogf("NTFS","manual/startup scan begin");
    for(int i=0;i<12 && app_running;++i) { sysUtilCheckCallback(); usleep(100000); }

    int mounted=0;
    for(int usb=0;usb<8 && app_running;++usb)
        if(mount_port(usb)) mounted++;

    rebuild_movies();
    bootlogf("NTFS","scan done mounted_ports=%d movies=%u",mounted,(unsigned)g_movies.size());
    return mounted>0;
}

'''
replace_block('static bool refresh_usb_state(bool force_scan)','static int mount_bd_iso(const Movie &movie)',refresh_block,'refresh_usb_state')

# The proven reader did not reject a mounted NTFS movie with a late IsInserted check.
s=s.replace('if(movie.usb_id < 0 || movie.usb_id > 7 || !PS3_NTFS_IsInserted(movie.usb_id)) return -104;',
            'if(movie.usb_id < 0 || movie.usb_id > 7) return -104;',1)

# L1/R1 only, preserving all old rendering code.
s=s.replace('bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_r1=false,p_r2=false;',
            'bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_l1=false,p_r1=false;',1)
s=s.replace('bool r1=pad.BTN_R1, r2=pad.BTN_R2;',
            'bool l1=pad.BTN_L1, r1=pad.BTN_R1;',1)
s=s.replace('if(r1 && !p_r1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; rebuild_movies(); }\n        if(r2 && !p_r2) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; rebuild_movies(); }',
'''if(l1 && !p_l1) { g_tab=(g_tab==TAB_BDISO)?TAB_MKV:TAB_BDISO; g_selected=0; rebuild_movies(); }
        if(r1 && !p_r1) { g_tab=(g_tab==TAB_MKV)?TAB_BDISO:TAB_MKV; g_selected=0; rebuild_movies(); }''',1)
s=s.replace('p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_r1=r1; p_r2=r2;',
            'p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_l1=l1; p_r1=r1;',1)
s=s.replace('"R2"','"L1"')
s=s.replace('R1/R2  BDISO-MKV','L1/R1  BDISO-MKV')

# Lightweight diagnostic points only. Do not change framebuffer setup or frame order.
mainpos=s.find('int main(int argc, char *argv[])')
if mainpos<0: raise SystemExit('main not found')
body=s[mainpos:]
body=body.replace('    (void)argc; (void)argv;\n',
'''    (void)argc; (void)argv;
    bootlog_init();
    bootlogf("VIDEO","FONT-FIX/V2 renderer selected");
''',1)
body=body.replace('    init_screen(host_addr,HOST_SIZE);',
'''    bootlogf("VIDEO","init_screen enter");
    init_screen(host_addr,HOST_SIZE);
    bootlogf("VIDEO","init_screen returned %ux%u",(unsigned)get_screen_width(),(unsigned)get_screen_height());''',1)
body=body.replace('        if(tri && !p_tri) refresh_usb_state(true);',
'''        if(tri && !p_tri) {
            bootlogf("INPUT","TRIANGLE NTFS refresh");
            refresh_usb_state(true);
        }''',1)
body=body.replace('    while(app_running) {\n        sysUtilCheckCallback();',
'''    while(app_running) {
        if((g_frame%300u)==0u) bootlogf("HEARTBEAT","alive movies=%u tab=%d",(unsigned)g_movies.size(),(int)g_tab);
        sysUtilCheckCallback();''',1)
body=body.replace('    free(host_addr);\n    return 0;',
'''    free(host_addr);
    bootlog_close();
    return 0;''',1)
s=s[:mainpos]+body

p.write_text(s)
print('FLOW MOVIE 3D V4.6.4 SCREEN FIX: V2/FONT-FIX renderer preserved + proven V3 NTFS restored')
