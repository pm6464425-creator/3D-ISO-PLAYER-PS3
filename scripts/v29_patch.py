from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V29
# - Oculta/elimina INSTALADOR PKG sin desplazar los indices ya usados por los backends.
# - Deja de detectar juegos instalados en /dev_hdd0/game.
# - Crea las carpetas estandar compartidas y la estructura propia FLOWPS3.
# - En USB/NTFS mantiene todo bajo /FLOWPS3 y usa BDISO para Blu-ray 2D.
# - Prepara deteccion sidecar de arte por contenido.
# - Integra lanzamiento SNES con Snes9x2010 incluido en USRDIR/cores.
# IMPORTANTE: no se modifica v24_mount_ps2_internal ni su secuencia Cobra.

# BLU-RAY 2D externo usa /FLOWPS3/BDISO.
s=s.replace('{"BLU-RAY 2D", "BLURAY2D", "ISO"}',
            '{"BLU-RAY 2D", "BDISO", "ISO"}',1)

# SNES: limitar la categoria SNES a extensiones propias (zip se conserva por comodidad).
needle='    if(!strcmp(k,"ROM")) return ends_with_ci(name,".zip")||ends_with_ci(name,".7z")||ends_with_ci(name,".nes")||ends_with_ci(name,".sfc")||ends_with_ci(name,".smc")||ends_with_ci(name,".gba")||ends_with_ci(name,".gb")||ends_with_ci(name,".gbc")||ends_with_ci(name,".md")||ends_with_ci(name,".gen")||ends_with_ci(name,".sms")||ends_with_ci(name,".gg")||ends_with_ci(name,".pce")||ends_with_ci(name,".ngp")||ends_with_ci(name,".ngc")||ends_with_ci(name,".ws")||ends_with_ci(name,".wsc")||ends_with_ci(name,".a26")||ends_with_ci(name,".a78")||ends_with_ci(name,".lnx")||ends_with_ci(name,".vb")||ends_with_ci(name,".n64")||ends_with_ci(name,".z64")||ends_with_ci(name,".v64");'
if needle not in s: raise SystemExit('matcher ROM no encontrado')
s=s.replace(needle,
'''    if(g_category==10) return ends_with_ci(name,".sfc")||ends_with_ci(name,".smc")||ends_with_ci(name,".zip");\n'''+needle,1)

# No crear la carpeta PKG en los helpers externos ya existentes. Hay dos bucles:
# NTFS ensure_root_folders y FAT32 ensure_fat_folders.
s=s.replace('for(int i=0;i<CATEGORY_COUNT;i++) {', 'for(int i=1;i<CATEGORY_COUNT;i++) {', 2)

# Estructura adicional externa.
s=s.replace('ps3ntfs_mkdir((base+"/GAMES").c_str(),0777);\n    ps3ntfs_mkdir((base+"/SAVESTATES").c_str(),0777);',
'''ps3ntfs_mkdir((base+"/GAMES").c_str(),0777);\n    ps3ntfs_mkdir((base+"/GAMEZ").c_str(),0777);\n    ps3ntfs_mkdir((base+"/SAVESTATES").c_str(),0777);\n    ps3ntfs_mkdir((base+"/SAVES").c_str(),0777);\n    ps3ntfs_mkdir((base+"/CACHE").c_str(),0777);''',1)
s=s.replace('mkdir_fat(base+"/GAMES"); mkdir_fat(base+"/SAVESTATES"); mkdir_fat(base+"/ART");',
'''mkdir_fat(base+"/GAMES"); mkdir_fat(base+"/GAMEZ"); mkdir_fat(base+"/SAVESTATES"); mkdir_fat(base+"/SAVES"); mkdir_fat(base+"/CACHE"); mkdir_fat(base+"/ART");''',1)

# Quitar la deteccion XMB. Se conserva el codigo antiguo sin uso para minimizar riesgo
# sobre el resto del backend, pero nunca se agregan sus entradas a la biblioteca.
s=s.replace('        add_xmb_games(fresh);\n','',1)

# Extender Movie con rutas de arte detectadas.
movie_anchor='    int content_type; /* 0 archivo/ISO, 1 juego carpeta, 2 instalado XMB */\n};'
if movie_anchor not in s: raise SystemExit('struct Movie V15 no encontrado')
s=s.replace(movie_anchor,
'''    int content_type; /* 0 archivo/ISO, 1 juego carpeta; XMB ya no se escanea */\n    std::string art_dir;\n    std::string cover_path;\n    std::string background_path;\n    std::string icon_path;\n    std::string logo_path;\n    std::string info_path;\n};''',1)

# Helpers V29: estructura interna + deteccion de arte sidecar.
marker='static void rebuild_movies()\n{\n'
if marker not in s: raise SystemExit('rebuild_movies no encontrado')
helpers=r'''static void v29_mkdir(const char *path)
{
    mkdir(path,0777);
}

static void v29_prepare_internal_folders()
{
    const char *shared[]={
        "/dev_hdd0/BDISO","/dev_hdd0/DVDISO","/dev_hdd0/PS3ISO",
        "/dev_hdd0/PS2ISO","/dev_hdd0/PSXISO","/dev_hdd0/PSPISO",
        "/dev_hdd0/GAMES","/dev_hdd0/GAMEZ"
    };
    for(unsigned int i=0;i<sizeof(shared)/sizeof(shared[0]);i++) v29_mkdir(shared[i]);

    const char *own[]={
        "/dev_hdd0/FLOWPS3",
        "/dev_hdd0/FLOWPS3/BLURAY3D",
        "/dev_hdd0/FLOWPS3/VIDEOS",
        "/dev_hdd0/FLOWPS3/ROMS",
        "/dev_hdd0/FLOWPS3/ROMS/ARCADE",
        "/dev_hdd0/FLOWPS3/ROMS/SNES",
        "/dev_hdd0/FLOWPS3/ROMS/NES",
        "/dev_hdd0/FLOWPS3/ROMS/N64",
        "/dev_hdd0/FLOWPS3/ROMS/MEGADRIVE",
        "/dev_hdd0/FLOWPS3/ROMS/MASTERSYSTEM",
        "/dev_hdd0/FLOWPS3/ROMS/GAMEGEAR",
        "/dev_hdd0/FLOWPS3/ROMS/GB",
        "/dev_hdd0/FLOWPS3/ROMS/GBC",
        "/dev_hdd0/FLOWPS3/ROMS/GBA",
        "/dev_hdd0/FLOWPS3/ROMS/PCENGINE",
        "/dev_hdd0/FLOWPS3/ROMS/NEOGEO",
        "/dev_hdd0/FLOWPS3/ROMS/NGP",
        "/dev_hdd0/FLOWPS3/ROMS/WONDERSWAN",
        "/dev_hdd0/FLOWPS3/ROMS/ATARI2600",
        "/dev_hdd0/FLOWPS3/ROMS/ATARI7800",
        "/dev_hdd0/FLOWPS3/ROMS/LYNX",
        "/dev_hdd0/FLOWPS3/ROMS/VIRTUALBOY",
        "/dev_hdd0/FLOWPS3/ART",
        "/dev_hdd0/FLOWPS3/ART/COVERS",
        "/dev_hdd0/FLOWPS3/ART/BACKGROUNDS",
        "/dev_hdd0/FLOWPS3/SAVESTATES",
        "/dev_hdd0/FLOWPS3/SAVESTATES/SNES",
        "/dev_hdd0/FLOWPS3/SAVES",
        "/dev_hdd0/FLOWPS3/SAVES/SNES",
        "/dev_hdd0/FLOWPS3/CACHE",
        "/dev_hdd0/FLOWPS3/CACHE/SNES"
    };
    for(unsigned int i=0;i<sizeof(own)/sizeof(own[0]);i++) v29_mkdir(own[i]);
}

static bool v29_path_exists(const std::string &path)
{
    struct stat st;
    if(path.find(":/")!=std::string::npos) return ps3ntfs_stat(path.c_str(),&st)==0;
    return stat(path.c_str(),&st)==0;
}

static std::string v29_stem_path(const Movie &m)
{
    if(m.content_type==1) return m.path+"/FLOWPS3_ART";
    std::string p=m.path;
    const char *exts[]={".iso.00",".iso.0",".iso",".mkv",".mp4",".avi",".mov",".m2ts",".ts",".sfc",".smc",".zip",".7z",".bin",".cue",".cso"};
    for(unsigned int i=0;i<sizeof(exts)/sizeof(exts[0]);i++) {
        size_t n=strlen(exts[i]);
        if(p.size()>=n && !strcasecmp(p.c_str()+p.size()-n,exts[i])) { p.resize(p.size()-n); break; }
    }
    return p;
}

static std::string v29_first_art(const std::string &dir,const char *a,const char *b=NULL)
{
    std::string p=dir+"/"+a; if(v29_path_exists(p)) return p;
    if(b){ p=dir+"/"+b; if(v29_path_exists(p)) return p; }
    return "";
}

static void v29_bind_art(Movie &m)
{
    m.art_dir=v29_stem_path(m);
    if(!v29_path_exists(m.art_dir)) return;
    m.cover_path=v29_first_art(m.art_dir,"cover.jpg","cover.png");
    m.background_path=v29_first_art(m.art_dir,"background.jpg","background.png");
    m.icon_path=v29_first_art(m.art_dir,"icon.png","icon.jpg");
    m.logo_path=v29_first_art(m.art_dir,"logo.png","logo.jpg");
    m.info_path=v29_first_art(m.art_dir,"info.json");
}

'''
s=s.replace(marker,helpers+marker,1)

# Preparar carpetas en cada reconstruccion y enlazar arte de los elementos detectados.
s=s.replace(marker,marker+'    v29_prepare_internal_folders();\n',1)
sort_anchor='    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.source<b.source;});'
if sort_anchor not in s: raise SystemExit('sort final no encontrado')
s=s.replace(sort_anchor,'    for(size_t ai=0;ai<fresh.size();ai++) v29_bind_art(fresh[ai]);\n\n'+sort_anchor,1)

# Ocultar categoria 0 (PKG) SIN renumerar el resto: preserva PS3=5, PS2=6, SNES=10.
# Render V18: no dibujar idx 0.
s=s.replace('        if(idx<0 || idx>=CATEGORY_COUNT) continue;',
            '        if(idx<1 || idx>=CATEGORY_COUNT) continue;',1)
# Navegacion V18: limite izquierdo empieza en categoria 1.
s=s.replace('            if(g_category>0) { g_category--; g_selected=0; rebuild_movies(); }',
            '            if(g_category>1) { g_category--; g_selected=0; rebuild_movies(); }',1)

# Backend SNES. El core es empaquetado por el workflow en USRDIR/cores.
snes_anchor='static int mount_selected_image(const Movie &movie)\n{\n'
if snes_anchor not in s: raise SystemExit('anchor mount_selected no encontrado')
snes=r'''static std::string v29_safe_basename(const std::string &path)
{
    size_t p=path.find_last_of('/');
    std::string n=(p==std::string::npos)?path:path.substr(p+1);
    for(size_t i=0;i<n.size();i++) {
        char c=n[i];
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='_'||c=='-')) n[i]='_';
    }
    return n;
}

static int v29_copy_ntfs_rom(const std::string &src,std::string &dst)
{
    dst=std::string("/dev_hdd0/FLOWPS3/CACHE/SNES/")+v29_safe_basename(src);
    int in=ps3ntfs_open(src.c_str(),O_RDONLY,0);
    if(in<0) return -431;
    int out=open(dst.c_str(),O_WRONLY|O_CREAT|O_TRUNC,0666);
    if(out<0){ ps3ntfs_close(in); return -432; }
    char *buf=(char*)memalign(16,128*1024);
    if(!buf){ close(out); ps3ntfs_close(in); return -433; }
    int ret=0;
    while(1) {
        int r=ps3ntfs_read(in,buf,128*1024);
        if(r<0){ ret=-434; break; }
        if(r==0) break;
        int off=0;
        while(off<r){ int w=write(out,buf+off,r-off); if(w<=0){ ret=-435; break; } off+=w; }
        if(ret) break;
    }
    free(buf); close(out); ps3ntfs_close(in);
    if(ret) unlink(dst.c_str());
    return ret;
}

static int v29_write_snes_cfg(const std::string &rom)
{
    const char *cfg="/dev_hdd0/game/3DISO0001/USRDIR/retroarch.cfg";
    FILE *f=fopen(cfg,"w"); if(!f) return -436;
    fprintf(f,"libretro_rom_path = \\\"%s\\\"\n",rom.c_str());
    fprintf(f,"video_fullscreen = \\\"true\\\"\n");
    fprintf(f,"video_vsync = \\\"true\\\"\n");
    fprintf(f,"video_smooth = \\\"true\\\"\n");
    fprintf(f,"video_force_aspect = \\\"true\\\"\n");
    fprintf(f,"video_aspect_ratio_auto = \\\"false\\\"\n");
    fprintf(f,"video_aspect_ratio = \\\"1.777778\\\"\n");
    fprintf(f,"aspect_ratio_index = \\\"1\\\"\n");
    fprintf(f,"input_autodetect_enable = \\\"true\\\"\n");
    fprintf(f,"input_player1_joypad_index = \\\"0\\\"\n");
    fprintf(f,"input_player2_joypad_index = \\\"1\\\"\n");
    fprintf(f,"savefile_directory = \\\"/dev_hdd0/FLOWPS3/SAVES/SNES\\\"\n");
    fprintf(f,"savestate_directory = \\\"/dev_hdd0/FLOWPS3/SAVESTATES/SNES\\\"\n");
    fclose(f); return 0;
}

static int v29_launch_snes(const Movie &movie)
{
    const char *core="/dev_hdd0/game/3DISO0001/USRDIR/cores/snes9x2010_libretro_ps3.SELF";
    struct stat st; if(stat(core,&st)!=0 || st.st_size<=0) return -430;
    std::string rom=movie.path;
    if(is_ntfs_movie(movie)) {
        std::string cached;
        int cr=v29_copy_ntfs_rom(movie.path,cached);
        if(cr!=0) return cr;
        rom=cached;
    }
    int cfg=v29_write_snes_cfg(rom); if(cfg!=0) return cfg;

    const char *argv[]={rom.c_str(),NULL};
    close_status();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    sysProcessExitSpawn2(core,argv,NULL,NULL,0,3071,SYS_PROCESS_SPAWN_STACK_SIZE_1M);

    /* Si el firmware devuelve control, restaurar FLOWPS3 en vez de cerrarlo. */
    ioPadInit(7);
    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);
    return -437;
}

'''
s=s.replace(snes_anchor,snes+snes_anchor,1)

# Interceptar SNES antes del selector de emulacion Cobra.
action='            int emu=category_emu_mode();'
if action not in s: raise SystemExit('accion emu no encontrada')
s=s.replace(action,r'''            if(g_category==10) {
                show_status("Iniciando Super Nintendo con Snes9x2010...");
                int sr=v29_launch_snes(movie);
                char msg[384]; snprintf(msg,sizeof(msg),"No se pudo iniciar SNES.\n\nCodigo: 0x%08X\n\nEl ROM permanece intacto.",sr);
                show_ok(msg); wait_buttons_release(); p_x=x; render_ui(); usleep(16000); continue;
            }
            int emu=category_emu_mode();''',1)

# Version UI.
s=s.replace('"V28"','"V29"')

p.write_text(s)
print('FLOWPS3 V29 aplicado: limpieza + carpetas + arte + SNES')
