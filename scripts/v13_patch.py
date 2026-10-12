from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# Vista vertical tipo XMB.
s=s.replace('#define GRID_COLS 3','#define GRID_COLS 1',1)
s=s.replace('#define GRID_ROWS 2','#define GRID_ROWS 6',1)

anchor='static unsigned int g_frame = 0;\n'
insert=r'''static int g_category = 1;

struct CategoryDef {
    const char *name;
    const char *folder;
    const char *kind;
};

static const CategoryDef g_categories[] = {
    {"INSTALADOR PKG", "PKG", "PKG"},
    {"BLU-RAY 3D", "BLURAY3D", "ISO"},
    {"BLU-RAY 2D", "BLURAY2D", "ISO"},
    {"DVD", "DVDISO", "ISO"},
    {"VIDEOS", "VIDEOS", "VIDEO"},
    {"PLAYSTATION 3", "PS3ISO", "PS3"},
    {"PLAYSTATION 2", "PS2ISO", "ISO"},
    {"PLAYSTATION", "PSXISO", "PS1"},
    {"PSP", "PSPISO", "PSP"},
    {"ARCADE", "ROMS/ARCADE", "ROM"},
    {"SUPER NINTENDO", "ROMS/SNES", "ROM"},
    {"NINTENDO NES", "ROMS/NES", "ROM"},
    {"NINTENDO 64", "ROMS/N64", "ROM"},
    {"SEGA MEGA DRIVE", "ROMS/MEGADRIVE", "ROM"},
    {"MASTER SYSTEM", "ROMS/MASTERSYSTEM", "ROM"},
    {"GAME GEAR", "ROMS/GAMEGEAR", "ROM"},
    {"GAME BOY", "ROMS/GB", "ROM"},
    {"GAME BOY COLOR", "ROMS/GBC", "ROM"},
    {"GAME BOY ADVANCE", "ROMS/GBA", "ROM"},
    {"PC ENGINE", "ROMS/PCENGINE", "ROM"},
    {"NEO GEO", "ROMS/NEOGEO", "ROM"},
    {"NEO GEO POCKET", "ROMS/NGP", "ROM"},
    {"WONDER SWAN", "ROMS/WONDERSWAN", "ROM"},
    {"ATARI 2600", "ROMS/ATARI2600", "ROM"},
    {"ATARI 7800", "ROMS/ATARI7800", "ROM"},
    {"ATARI LYNX", "ROMS/LYNX", "ROM"},
    {"VIRTUAL BOY", "ROMS/VIRTUALBOY", "ROM"},
    {"FAVORITOS", "FAVORITES", "MIX"}
};
static const int CATEGORY_COUNT = sizeof(g_categories)/sizeof(g_categories[0]);
static const char *APP_ROOT = "3D_ISO_PLAYER";

static bool ends_with_ci(const char *name,const char *ext)
{
    if(!name||!ext) return false;
    size_t n=strlen(name), e=strlen(ext);
    return n>=e && strcasecmp(name+n-e,ext)==0;
}

static bool matches_category(const char *name)
{
    const char *k=g_categories[g_category].kind;
    if(!strcmp(k,"PKG")) return ends_with_ci(name,".pkg");
    if(!strcmp(k,"VIDEO")) return ends_with_ci(name,".mkv")||ends_with_ci(name,".mp4")||ends_with_ci(name,".avi")||ends_with_ci(name,".m2ts")||ends_with_ci(name,".ts")||ends_with_ci(name,".mov");
    if(!strcmp(k,"PS1")) return ends_with_ci(name,".bin")||ends_with_ci(name,".cue")||ends_with_ci(name,".iso");
    if(!strcmp(k,"PSP")) return ends_with_ci(name,".iso")||ends_with_ci(name,".cso");
    if(!strcmp(k,"ROM")) return ends_with_ci(name,".zip")||ends_with_ci(name,".7z")||ends_with_ci(name,".nes")||ends_with_ci(name,".sfc")||ends_with_ci(name,".smc")||ends_with_ci(name,".gba")||ends_with_ci(name,".gb")||ends_with_ci(name,".gbc")||ends_with_ci(name,".md")||ends_with_ci(name,".gen")||ends_with_ci(name,".sms")||ends_with_ci(name,".gg")||ends_with_ci(name,".pce")||ends_with_ci(name,".ngp")||ends_with_ci(name,".ngc")||ends_with_ci(name,".ws")||ends_with_ci(name,".wsc")||ends_with_ci(name,".a26")||ends_with_ci(name,".a78")||ends_with_ci(name,".lnx")||ends_with_ci(name,".vb")||ends_with_ci(name,".n64")||ends_with_ci(name,".z64")||ends_with_ci(name,".v64");
    return ends_with_ci(name,".iso") || ends_with_ci(name,".iso.0") || ends_with_ci(name,".iso.00");
}

static void ensure_root_folders(const std::string &mount)
{
    std::string base=mount+":/"+APP_ROOT;
    ps3ntfs_mkdir(base.c_str(),0777);
    ps3ntfs_mkdir((base+"/ROMS").c_str(),0777);
    for(int i=0;i<CATEGORY_COUNT;i++) {
        if(!strcmp(g_categories[i].folder,"FAVORITES")) continue;
        std::string rel=g_categories[i].folder;
        size_t slash=rel.find('/');
        if(slash!=std::string::npos) {
            std::string p1=base+"/"+rel.substr(0,slash);
            ps3ntfs_mkdir(p1.c_str(),0777);
        }
        ps3ntfs_mkdir((base+"/"+rel).c_str(),0777);
    }
}
'''
if anchor not in s: raise SystemExit('anchor globals no encontrado')
s=s.replace(anchor,anchor+insert,1)

# Reemplazar rebuild_movies completo por escaneo por categoria dentro de carpeta madre.
start=s.find('static void rebuild_movies()')
end=s.find('\nstatic bool refresh_usb_state',start)
if start<0 or end<0: raise SystemExit('rebuild_movies no encontrado')
new_rebuild=r'''static void rebuild_movies()
{
    std::string previous_path;
    if(!g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) previous_path=g_movies[g_selected].path;
    std::vector<Movie> fresh;
    for(int usb=0;usb<8;++usb) {
        if(!g_present[usb]||!g_mounts[usb]||g_mount_count[usb]<=0) continue;
        for(int p=0;p<g_mount_count[usb];++p) {
            if(!g_mounts[usb][p].name[0]) continue;
            std::string mount=g_mounts[usb][p].name;
            ensure_root_folders(mount);
            std::string root=mount+":/"+APP_ROOT+"/"+g_categories[g_category].folder;
            DIR_ITER *dir=ps3ntfs_diropen(root.c_str());
            if(!dir) continue;
            char filename[1024]; struct stat st;
            while(ps3ntfs_dirnext(dir,filename,&st)==0) {
                if(filename[0]=='.'||!matches_category(filename)) continue;
                Movie m; m.name=filename; m.path=root+"/"+filename; m.usb_id=usb; m.bytes=(uint64_t)st.st_size;
                fresh.push_back(m); if(fresh.size()>=1024) break;
            }
            ps3ntfs_dirclose(dir);
        }
    }
    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.usb_id<b.usb_id;});
    g_movies.swap(fresh); g_selected=0;
    if(!previous_path.empty()) for(size_t i=0;i<g_movies.size();++i) if(g_movies[i].path==previous_path){g_selected=(int)i;break;}
    if(!g_movies.empty()&&g_selected>=(int)g_movies.size()) g_selected=(int)g_movies.size()-1;
}
'''
s=s[:start]+new_rebuild+s[end:]

# Cabecera XMB con categoria actual y vecinos.
needle='draw_text(60,header_h/2-font_height(title_scale)/2,"3D ISO PLAYER",title_scale,WHITE,30);\n'
rep=r'''draw_text(60,16,"3D ISO PLAYER",1,WHITE,30);
    int center_y=header_h/2+10;
    const char *cur=g_categories[g_category].name;
    int cw=(int)strlen(cur)*char_advance(title_scale);
    draw_text((sw-cw)/2,center_y-font_height(title_scale)/2,cur,title_scale,WHITE,40);
    int prev=(g_category+CATEGORY_COUNT-1)%CATEGORY_COUNT, next=(g_category+1)%CATEGORY_COUNT;
    draw_text(58,center_y-font_height(1)/2,g_categories[prev].name,1,MUTED,24);
    int nw=(int)strlen(g_categories[next].name)*char_advance(1);
    draw_text(sw-58-nw,center_y-font_height(1)/2,g_categories[next].name,1,MUTED,24);
'''
if needle not in s: raise SystemExit('titulo render no encontrado')
s=s.replace(needle,rep,1)
# Quitar texto CINEMA LIBRARY secundario.
s=s.replace('    draw_text(60+(sh>=900?360:190),header_h/2-font_height(1)/2,"CINEMA LIBRARY",1,ACCENT,30);\n','',1)

s=s.replace('"TU BIBLIOTECA ESTA VACIA"','"NO HAY CONTENIDO EN ESTA SECCION"',1)
s=s.replace('"CONECTA UN DISCO NTFS CON BDISO"','"CONECTA UN USB NTFS/FAT32 O COPIA ARCHIVOS EN SU CARPETA"',1)
s=s.replace('"LAS PELICULAS APARECERAN AUTOMATICAMENTE"','"LA BIBLIOTECA SE ACTUALIZA AL ENTRAR"',1)
s=s.replace('"FORMATO   BLU-RAY ISO"','g_categories[g_category].name',1)
s=s.replace('"PELICULA %d DE %u"','"ELEMENTO %d DE %u"',1)
s=s.replace('"X PARA MONTAR EN COBRA"','"X PARA ABRIR / EJECUTAR"',1)
s=s.replace('"D-PAD NAVEGAR   X MONTAR   START PORTADA 3D   TRIANGULO ACTUALIZAR   O SALIR"','"IZQ/DER SECCION   ARR/ABAJO NAVEGAR   X ABRIR   START ARTE   SELECT OPCIONES   O SALIR"',1)

# Navegacion XMB: izquierda/derecha cambia de seccion; arriba/abajo cambia item.
s=s.replace('''        if(up && !p_up) move_selection(0,-1);\n        if(down && !p_down) move_selection(0,1);\n        if(left && !p_left) move_selection(-1,0);\n        if(right && !p_right) move_selection(1,0);''',
'''        if(up && !p_up) move_selection(0,-1);\n        if(down && !p_down) move_selection(0,1);\n        if(left && !p_left) { g_category=(g_category+CATEGORY_COUNT-1)%CATEGORY_COUNT; g_selected=0; rebuild_movies(); }\n        if(right && !p_right) { g_category=(g_category+1)%CATEGORY_COUNT; g_selected=0; rebuild_movies(); }''',1)

# X solo monta de momento Blu-ray 3D/2D; otras bibliotecas ya se reconocen pero requieren su backend.
old='''        if(x && !p_x && !g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) {\n            Movie movie=g_movies[g_selected];\n            show_status("Montando Blu-ray mediante Cobra...\\n\\nNo desconectes el disco USB.");\n            int ret=mount_bd_iso(movie);'''
new='''        if(x && !p_x && !g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) {\n            Movie movie=g_movies[g_selected];\n            if(g_category!=1 && g_category!=2) {\n                show_ok("Contenido reconocido en la biblioteca.\\n\\nEste backend se integrara en la siguiente fase sin alterar el montaje Blu-ray que ya funciona.");\n                wait_buttons_release();\n                p_x=x; render_ui(); usleep(16000); continue;\n            }\n            show_status("Montando Blu-ray mediante Cobra...\\n\\nNo desconectes el disco USB.");\n            int ret=mount_bd_iso(movie);'''
if old not in s: raise SystemExit('bloque X no encontrado')
s=s.replace(old,new,1)

p.write_text(s)
print('V13 XMB base aplicada')
