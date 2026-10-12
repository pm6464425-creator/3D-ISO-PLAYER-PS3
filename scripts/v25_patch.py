from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V25 - backend PS3
if '#include <sys/process.h>' not in s:
    anchor='#include <sys/stat.h>\n'
    if anchor not in s: raise SystemExit('include sys/stat no encontrado')
    s=s.replace(anchor,anchor+'#include <sys/process.h>\n',1)

marker='static void add_xmb_games(std::vector<Movie> &fresh)\n'
if marker not in s: raise SystemExit('add_xmb_games no encontrado')
helper=r'''static void v25_add_external_folder_games(std::vector<Movie> &fresh)
{
    char root[MAX_PATH];
    for(int usb=0;usb<8;usb++) {
        const char *patterns[]={"/dev_usb%03d/GAMES","/dev_usb%03d/GAMEZ","/dev_usb%03d/FLOWPS3/GAMES"};
        const char *tags[]={"USB FAT32 GAMES","USB FAT32 GAMEZ","USB FAT32 FLOWPS3"};
        for(int k=0;k<3;k++) {
            snprintf(root,sizeof(root),patterns[k],usb);
            DIR *d=opendir(root); if(!d) continue;
            struct dirent *de;
            while((de=readdir(d))!=NULL) {
                if(de->d_name[0]=='.') continue;
                std::string dir=std::string(root)+"/"+de->d_name;
                std::string sf=dir+"/PS3_GAME/PARAM.SFO";
                struct stat st; if(stat(sf.c_str(),&st)!=0) continue;
                Movie m;
                std::string title=sfo_value(sf,"TITLE");
                m.name=title.empty()?de->d_name:title;
                m.path=dir;
                m.source=tags[k];
                m.title_id=sfo_value(sf,"TITLE_ID");
                m.usb_id=usb;
                m.bytes=0;
                m.content_type=1;
                fresh.push_back(m);
            }
            closedir(d);
        }
    }
}

static int v25_ps3_entry_priority(const Movie &m)
{
    if(m.content_type==0) return m.path.find("/dev_hdd0/PS3ISO/")==0?0:1;
    if(m.content_type==1) return m.path.find("/dev_hdd0/")==0?2:3;
    if(m.content_type==2) return 4;
    return 9;
}

static void v25_dedupe_ps3(std::vector<Movie> &items)
{
    std::vector<Movie> out;
    for(size_t i=0;i<items.size();i++) {
        Movie m=items[i];
        if(m.title_id.empty()) { out.push_back(m); continue; }
        int found=-1;
        for(size_t j=0;j<out.size();j++)
            if(!out[j].title_id.empty() && !strcasecmp(out[j].title_id.c_str(),m.title_id.c_str())) { found=(int)j; break; }
        if(found<0) out.push_back(m);
        else if(v25_ps3_entry_priority(m)<v25_ps3_entry_priority(out[found])) out[found]=m;
    }
    items.swap(out);
}

'''
s=s.replace(marker,helper+marker,1)

needle='    v17_add_internal_for_category(fresh);\n\n    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.source<b.source;});'
rep='''    v17_add_internal_for_category(fresh);
    if(g_category==5) {
        v25_add_external_folder_games(fresh);
        v25_dedupe_ps3(fresh);
    }

    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.source<b.source;});'''
if needle not in s: raise SystemExit('sort final V17 no encontrado')
s=s.replace(needle,rep,1)

anchor='static int mount_selected_image(const Movie &movie)\n{\n'
if anchor not in s: raise SystemExit('mount_selected_image no encontrado')
backend=r'''static int v25_sys_map_path(const char *oldpath,const char *newpath)
{
    lv2syscall2(35,(uint64_t)oldpath,(uint64_t)newpath);
    return_to_user_prog(int);
}

static int v25_mount_ps3_folder(const Movie &movie)
{
    if(movie.content_type!=1) return -350;
    std::string sfo=movie.path+"/PS3_GAME/PARAM.SFO";
    struct stat st; if(stat(sfo.c_str(),&st)!=0) return -351;

    /* Flujo Cobra de juego en carpeta: limpiar montaje anterior y mapear
       la raiz del juego como /dev_bdvd. Esta ruta funciona tanto en HDD
       como en /dev_usb00x FAT32. NTFS carpeta no se expone como /dev_usb. */
    cobra_umount_disc_image();
    cobra_unset_psp_umd();
    v25_sys_map_path("/dev_bdvd",NULL);
    v25_sys_map_path("//dev_bdvd",NULL);
    v25_sys_map_path("/app_home",NULL);
    cobra_send_fake_disc_eject_event();
    usleep(20000);

    int ret=v25_sys_map_path("/dev_bdvd",movie.path.c_str());
    if(ret!=0) return ret;
    v25_sys_map_path("//dev_bdvd",movie.path.c_str());
    /* Mantener app_home apuntando a PS3_GAME ayuda a los juegos carpeta
       discless sin alterar licencias ni archivos del juego. */
    std::string apphome=movie.path+"/PS3_GAME";
    v25_sys_map_path("/app_home",apphome.c_str());

    cobra_send_fake_disc_insert_event();
    usleep(20000);
    return 0;
}

static int v25_launch_xmb_game(const Movie &movie)
{
    if(movie.content_type!=2) return -360;
    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";
    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;

    close_status();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    /* El firmware sigue aplicando las comprobaciones NPDRM/licencia normales. */
    sysProcessExitSpawn2(eboot.c_str(),NULL,NULL,NULL,0,3071,SYS_PROCESS_SPAWN_STACK_SIZE_1M);
    exit(0);
    return -362;
}

'''
s=s.replace(anchor,backend+anchor,1)

start=s.find('            if(g_category==5 && movie.content_type==2)')
end=s.find('            int emu=category_emu_mode();',start)
if start<0 or end<0: raise SystemExit('bloque acciones PS3 V15 no encontrado')
new=r'''            if(g_category==5 && movie.content_type==2) {
                int xr=v25_launch_xmb_game(movie);
                char msg[512]; snprintf(msg,sizeof(msg),"No se pudo iniciar la instalacion XMB.\n\nCodigo: 0x%08X\n\nEl firmware mantiene sus comprobaciones normales de licencia.",xr);
                show_ok(msg); wait_buttons_release(); p_x=x; render_ui(); usleep(16000); continue;
            }
            if(g_category==5 && movie.content_type==1) {
                close_status();
                int fr=v25_mount_ps3_folder(movie);
                if(fr==0) exit_to_xmb_after_mount();
                char msg[512]; snprintf(msg,sizeof(msg),"No se pudo montar el juego PS3 en carpeta.\n\nCodigo Cobra: 0x%08X",fr);
                show_ok(msg); wait_buttons_release(); p_x=x; render_ui(); usleep(16000); continue;
            }
'''
s=s[:start]+new+s[end:]

s=s.replace('"V24"','"V25"')
p.write_text(s)
print('FLOWPS3 V25 backend PS3 aplicado')
