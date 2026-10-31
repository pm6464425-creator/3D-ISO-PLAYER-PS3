from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# Movie-only build: keep only BDISO + MKV. No emulator/game categories are added.

# Internal HDD scan support.
if '#include <dirent.h>' not in s:
    s = s.replace('#include <unistd.h>\n', '#include <unistd.h>\n#include <dirent.h>\n', 1)

old_movie = '''struct Movie {\n    std::string path;\n    std::string name;\n    int usb_id;\n    uint64_t bytes;\n};'''
new_movie = '''struct Movie {\n    std::string path;\n    std::string name;\n    std::string source;\n    int usb_id;\n    uint64_t bytes;\n    bool ntfs;\n};'''
if old_movie not in s:
    raise SystemExit('Movie struct base not found')
s = s.replace(old_movie, new_movie, 1)

global_anchor = 'static unsigned int g_frame = 0;\n'
global_extra = '''\nenum MediaTab { TAB_BDISO = 0, TAB_MKV = 1 };\nstatic MediaTab g_tab = TAB_BDISO;\n\nstatic const char *current_folder() { return g_tab == TAB_BDISO ? "BDISO" : "MKV"; }\nstatic const char *current_label()  { return g_tab == TAB_BDISO ? "BDISO" : "PELICULAS MKV"; }\n'''
if global_anchor not in s:
    raise SystemExit('global anchor not found')
s = s.replace(global_anchor, global_anchor + global_extra, 1)

start = s.find('static bool has_iso_ext(const char *name)')
end = s.find('\nstatic void release_port', start)
if start < 0 or end < 0:
    raise SystemExit('extension helper block not found')
new_helpers = r'''static bool ends_with_ci(const char *name, const char *ext)
{
    if(!name || !ext) return false;
    size_t n = strlen(name), e = strlen(ext);
    return n >= e && strcasecmp(name + n - e, ext) == 0;
}

static bool matches_current_tab(const char *name)
{
    if(g_tab == TAB_BDISO) return ends_with_ci(name, ".iso");
    return ends_with_ci(name, ".mkv");
}

static std::string clean_title(const std::string &name)
{
    std::string s = name;
    if(ends_with_ci(s.c_str(), ".iso") || ends_with_ci(s.c_str(), ".mkv")) s.resize(s.size() - 4);
    for(size_t i=0;i<s.size();++i) if(s[i] == '_' || s[i] == '.') s[i] = ' ';
    return s;
}

static void ensure_internal_folders()
{
    mkdir("/dev_hdd0/BDISO", 0777);
    mkdir("/dev_hdd0/MKV", 0777);
}

static std::string ntfs_folder_path(const char *mount_name, const char *folder)
{
    std::string base = mount_name ? mount_name : "";
    if(!base.empty() && base[base.size()-1] != ':') base += ':';
    return base + "/" + folder;
}
'''
s = s[:start] + new_helpers + s[end:]

start = s.find('static void rebuild_movies()')
end = s.find('\nstatic bool refresh_usb_state', start)
if start < 0 or end < 0:
    raise SystemExit('rebuild_movies block not found')
new_rebuild = r'''static void rebuild_movies()
{
    std::string previous_path;
    if(!g_movies.empty() && g_selected >= 0 && g_selected < (int)g_movies.size())
        previous_path = g_movies[g_selected].path;

    std::vector<Movie> fresh;
    ensure_internal_folders();

    /* Internal HDD */
    {
        std::string root = std::string("/dev_hdd0/") + current_folder();
        DIR *dir = opendir(root.c_str());
        if(dir) {
            struct dirent *de;
            while((de = readdir(dir)) != NULL) {
                if(de->d_name[0] == '.' || !matches_current_tab(de->d_name)) continue;
                std::string full = root + "/" + de->d_name;
                struct stat st;
                if(stat(full.c_str(), &st) != 0) continue;
                Movie m;
                m.name = de->d_name;
                m.path = full;
                m.source = "HDD INTERNO";
                m.usb_id = -1;
                m.bytes = (uint64_t)st.st_size;
                m.ntfs = false;
                fresh.push_back(m);
                if(fresh.size() >= 1024) break;
            }
            closedir(dir);
        }
    }

    /* External USB NTFS */
    for(int usb=0; usb<8; ++usb) {
        if(!g_present[usb] || !g_mounts[usb] || g_mount_count[usb] <= 0) continue;
        for(int part=0; part<g_mount_count[usb]; ++part) {
            if(!g_mounts[usb][part].name[0]) continue;
            std::string root = ntfs_folder_path(g_mounts[usb][part].name, current_folder());
            ps3ntfs_mkdir(root.c_str(), 0777);
            DIR_ITER *dir = ps3ntfs_diropen(root.c_str());
            if(!dir) continue;

            char filename[1024];
            struct stat st;
            while(ps3ntfs_dirnext(dir, filename, &st) == 0) {
                if(filename[0] == '.' || !matches_current_tab(filename)) continue;
                Movie m;
                m.name = filename;
                m.path = root + "/" + filename;
                char src[32];
                snprintf(src, sizeof(src), "USB %03d", usb);
                m.source = src;
                m.usb_id = usb;
                m.bytes = (uint64_t)st.st_size;
                m.ntfs = true;
                fresh.push_back(m);
                if(fresh.size() >= 1024) break;
            }
            ps3ntfs_dirclose(dir);
        }
    }

    std::sort(fresh.begin(), fresh.end(), [](const Movie &a, const Movie &b) {
        int n = strcasecmp(a.name.c_str(), b.name.c_str());
        if(n != 0) return n < 0;
        return a.source < b.source;
    });

    g_movies.swap(fresh);
    g_selected = 0;
    if(!previous_path.empty()) {
        for(size_t i=0;i<g_movies.size();++i) {
            if(g_movies[i].path == previous_path) { g_selected = (int)i; break; }
        }
    }
    if(g_movies.empty()) g_selected = 0;
    else if(g_selected >= (int)g_movies.size()) g_selected = (int)g_movies.size()-1;
}
'''
s = s[:start] + new_rebuild + s[end:]

start = s.find('static int mount_bd_iso(const Movie &movie)')
end = s.find('\nstatic void cleanup_ntfs', start)
if start < 0 or end < 0:
    raise SystemExit('mount_bd_iso block not found')
new_mount = r'''static int mount_bd_iso(const Movie &movie)
{
    if(!movie.ntfs) {
        char *files[1];
        files[0] = const_cast<char*>(movie.path.c_str());
        cobra_umount_disc_image();
        usleep(100000);
        return cobra_mount_bd_disc_image(files, 1);
    }

    struct stat st;
    if(stat(RAWISO_PATH, &st) != 0) return -103;
    if(movie.usb_id < 0 || movie.usb_id > 7 || !PS3_NTFS_IsInserted(movie.usb_id)) return -104;

    void *plugin_args = memalign(128, 0x10000);
    uint32_t *sections = (uint32_t*)malloc(MAX_SECTIONS * sizeof(uint32_t));
    uint32_t *sizes = (uint32_t*)malloc(MAX_SECTIONS * sizeof(uint32_t));
    if(!plugin_args || !sections || !sizes) {
        free(plugin_args); free(sections); free(sizes);
        return -100;
    }

    memset(plugin_args, 0, 0x10000);
    memset(sections, 0, MAX_SECTIONS * sizeof(uint32_t));
    memset(sizes, 0, MAX_SECTIONS * sizeof(uint32_t));

    int parts = ps3ntfs_file_to_sectors(movie.path.c_str(), sections, sizes, MAX_SECTIONS, 1);
    if(parts <= 0 || parts >= MAX_SECTIONS) {
        free(plugin_args); free(sections); free(sizes);
        return (parts >= MAX_SECTIONS) ? -102 : -101;
    }

    rawseciso_args *args = (rawseciso_args*)plugin_args;
    args->device = USB_MASS_STORAGE(movie.usb_id);
    args->emu_mode = EMU_BD;
    args->num_sections = (uint32_t)parts;
    args->num_tracks = 0;

    memcpy((uint8_t*)plugin_args + sizeof(rawseciso_args), sections, parts * sizeof(uint32_t));
    memcpy((uint8_t*)plugin_args + sizeof(rawseciso_args) + parts * sizeof(uint32_t), sizes, parts * sizeof(uint32_t));

    cobra_unload_vsh_plugin(0);
    usleep(100000);
    int ret = cobra_load_vsh_plugin(0, (char*)RAWISO_PATH, plugin_args, 0x10000);

    free(plugin_args); free(sections); free(sizes);
    return ret;
}
'''
s = s[:start] + new_mount + s[end:]

# Poster source label: HDD or USB instead of assuming every item is USB.
old = '''    char usb[32];\n    snprintf(usb,sizeof(usb),"USB %03d",m.usb_id);\n    draw_text(x+10,y+h-28,usb,1,0xFF71DCFF,16);'''
new = '''    draw_text(x+10,y+h-28,m.source,1,0xFF71DCFF,20);'''
if old not in s:
    raise SystemExit('poster source label block not found')
s = s.replace(old, new, 1)

start = s.find('static void render_info_panel(int x, int y, int w, int h)')
end = s.find('\nstatic void render_ui()', start)
if start < 0 or end < 0:
    raise SystemExit('render_info_panel block not found')
new_info = r'''static void render_info_panel(int x, int y, int w, int h)
{
    const u32 PANEL=0xE60A111D, WHITE=0xFFF4FAFF, MUTED=0xFF9AB0C6, ACCENT=0xFF56D7FF;
    fill_rect(x,y,w,h,PANEL);
    fill_rect(x,y,3,h,0xFF24445F);
    draw_text(x+20,y+18,current_label(),1,ACCENT,24);

    if(g_movies.empty() || g_selected<0 || g_selected>=(int)g_movies.size()) {
        std::string msg = std::string("COLOCA ARCHIVOS EN /") + current_folder();
        draw_wrapped(x+20,y+70,w-40,msg,1,MUTED,4);
        return;
    }

    const Movie &m=g_movies[g_selected];
    std::string title=clean_title(m.name);
    draw_wrapped(x+20,y+58,w-40,title,1,WHITE,4);

    int base=y+170;
    char line[128];
    snprintf(line,sizeof(line),"ORIGEN    %s",m.source.c_str());
    draw_text(x+20,base,line,1,MUTED,48);
    char sz[48]; format_size(m.bytes,sz,sizeof(sz));
    snprintf(line,sizeof(line),"TAMANO    %s",sz);
    draw_text(x+20,base+34,line,1,MUTED,40);
    draw_text(x+20,base+68,g_tab==TAB_BDISO?"FORMATO   BLU-RAY ISO":"FORMATO   MATROSKA MKV",1,MUTED,40);

    snprintf(line,sizeof(line),"PELICULA %d DE %u",g_selected+1,(unsigned)g_movies.size());
    draw_text(x+20,y+h-72,line,1,ACCENT,40);
    draw_wrapped(x+20,y+h-43,w-40,g_tab==TAB_BDISO?"X PARA MONTAR":"X PARA REPRODUCIR",1,WHITE,2);
}
'''
s = s[:start] + new_info + s[end:]

start = s.find('static void render_ui()')
end = s.find('\nstatic void move_selection', start)
if start < 0 or end < 0:
    raise SystemExit('render_ui block not found')
new_ui = r'''static void render_ui()
{
    const u32 WHITE=0xFFF4FAFF, MUTED=0xFF8FA6BC, ACCENT=0xFF56D7FF;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    draw_background();

    int header_h=(sh>=900)?100:76;
    int footer_h=(sh>=900)?72:56;
    fill_rect(34,0,sw-68,header_h,0xD908101C);
    fill_rect(34,sh-footer_h,sw-68,footer_h,0xEC08111D);
    fill_rect(34,header_h-2,sw-68,2,0xFF193A55);

    int title_scale=(sh>=900)?2:1;
    draw_text(60,header_h/2-font_height(title_scale)/2,"MOVIE FLOW PS3",title_scale,WHITE,30);
    draw_text(60+(sh>=900?390:205),header_h/2-font_height(1)/2,current_label(),1,ACCENT,30);

    char info[96];
    snprintf(info,sizeof(info),"USB %d   PELICULAS %u",connected_count(),(unsigned)g_movies.size());
    int iw=(int)strlen(info)*char_advance(1);
    draw_text(sw-60-iw,header_h/2-font_height(1)/2,info,1,MUTED,48);

    int content_top=header_h+18;
    int content_bottom=sh-footer_h-16;
    int content_h=content_bottom-content_top;
    int side_margin=(sw>=1600)?62:44;
    int panel_w=(sw>=1600)?430:290;
    int gap=(sw>=1600)?22:14;
    int panel_x=sw-side_margin-panel_w;
    int grid_x=side_margin;
    int grid_w=panel_x-gap-grid_x;

    if(g_movies.empty()) {
        draw_centered(sh/2-70,"TU BIBLIOTECA ESTA VACIA",title_scale,WHITE);
        std::string folder = std::string("USA LA CARPETA /") + current_folder();
        draw_centered(sh/2+5,folder,1,MUTED);
        draw_centered(sh/2+42,"HDD INTERNO O USB NTFS",1,ACCENT);
        render_info_panel(panel_x,content_top,panel_w,content_h);
    } else {
        int cell_gap=(sw>=1600)?20:12;
        int cell_w=(grid_w-(GRID_COLS-1)*cell_gap)/GRID_COLS;
        int cell_h=(content_h-(GRID_ROWS-1)*cell_gap)/GRID_ROWS;
        int page=g_selected/GRID_PAGE;
        int first=page*GRID_PAGE;

        for(int slot=0; slot<GRID_PAGE; ++slot) {
            int idx=first+slot;
            if(idx>=(int)g_movies.size()) break;
            int col=slot%GRID_COLS, row=slot/GRID_COLS;
            int x=grid_x+col*(cell_w+cell_gap);
            int y=content_top+row*(cell_h+cell_gap);
            draw_poster(x,y,cell_w,cell_h,g_movies[idx],idx==g_selected);
        }
        render_info_panel(panel_x,content_top,panel_w,content_h);

        int pages=((int)g_movies.size()+GRID_PAGE-1)/GRID_PAGE;
        char pg[64]; snprintf(pg,sizeof(pg),"PAGINA %d/%d",page+1,pages);
        draw_text(panel_x,sh-footer_h+18,pg,1,MUTED,24);
    }

    draw_text(60,sh-footer_h+18,"R1/R2  BDISO-MKV     D-PAD  NAVEGAR     X  ABRIR     TRIANGULO  ACTUALIZAR     O  SALIR",1,WHITE,110);
    g_frame++;
    flip();
}
'''
s = s[:start] + new_ui + s[end:]

# Replace main loop with movie-only controls.
start = s.find('int main(int argc, char *argv[])')
if start < 0:
    raise SystemExit('main not found')
new_main = r'''int main(int argc, char *argv[])
{
    (void)argc; (void)argv;
    void *host_addr=memalign(1024*1024,HOST_SIZE);
    if(!host_addr) return 1;

    init_screen(host_addr,HOST_SIZE);
    ioPadInit(7);
    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);
    load_font();
    ensure_internal_folders();

    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }
    refresh_usb_state(true);

    padData pad;
    memset(&pad,0,sizeof(pad));
    bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_r1=false,p_r2=false;
    int poll_counter=0;

    while(app_running) {
        sysUtilCheckCallback();

        if(++poll_counter>=45) {
            poll_counter=0;
            refresh_usb_state(false);
        }

        memset(&pad,0,sizeof(pad));
        ioPadGetData(0,&pad);

        bool up=pad.BTN_UP, down=pad.BTN_DOWN, left=pad.BTN_LEFT, right=pad.BTN_RIGHT;
        bool x=pad.BTN_CROSS, o=pad.BTN_CIRCLE, tri=pad.BTN_TRIANGLE;
        bool r1=pad.BTN_R1, r2=pad.BTN_R2;

        if(r1 && !p_r1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; rebuild_movies(); }
        if(r2 && !p_r2) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; rebuild_movies(); }

        if(up && !p_up) move_selection(0,-1);
        if(down && !p_down) move_selection(0,1);
        if(left && !p_left) move_selection(-1,0);
        if(right && !p_right) move_selection(1,0);
        if(tri && !p_tri) refresh_usb_state(true);
        if(o && !p_o) app_running=false;

        if(x && !p_x && !g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) {
            Movie movie=g_movies[g_selected];
            if(g_tab == TAB_BDISO) {
                show_status("Montando pelicula Blu-ray ISO...\n\nNo desconectes el disco.");
                int ret=mount_bd_iso(movie);
                close_status();

                if(ret==0) {
                    show_status("ISO montada correctamente.\n\nVolviendo al XMB...");
                    for(int i=0;i<10;i++) { sysUtilCheckCallback(); usleep(100000); }
                    exit_to_xmb_after_mount();
                } else {
                    char err[768];
                    if(ret==-104) snprintf(err,sizeof(err),"El disco USB fue retirado antes del montaje.");
                    else if(ret==-103) snprintf(err,sizeof(err),"Falta raw_iso.sprx. Reinstala este PKG.");
                    else if(ret==-102) snprintf(err,sizeof(err),"La ISO esta demasiado fragmentada en NTFS. Vuelve a copiarla al disco.");
                    else if(ret==-101) snprintf(err,sizeof(err),"No se pudieron obtener los sectores fisicos de la ISO.");
                    else snprintf(err,sizeof(err),"No se pudo montar la pelicula. Error: 0x%08X",ret);
                    show_ok(err);
                    refresh_usb_state(true);
                }
            } else {
                show_ok("MKV detectado correctamente.\n\nLa ventana MKV ya forma parte de esta version. El motor de reproduccion se integrara en la siguiente etapa.");
            }
        }

        p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_r1=r1; p_r2=r2;
        render_ui();
        usleep(16000);
    }

    cleanup_ntfs();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    if(g_font) free(g_font);
    free(host_addr);
    return 0;
}
'''
s = s[:start] + new_main

p.write_text(s)
print('movie-only patch applied: BDISO + MKV only')
