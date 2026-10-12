from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# 1) Respetar la asignacion Aceptar/Volver configurada en el XMB de la propia PS3.
anchor='static unsigned int g_frame = 0;\n'
extra='''static bool g_confirm_cross = true;\n\nstatic bool flow_accept(const padData &p) { return g_confirm_cross ? p.BTN_CROSS : p.BTN_CIRCLE; }\nstatic bool flow_back(const padData &p)   { return g_confirm_cross ? p.BTN_CIRCLE : p.BTN_CROSS; }\n'''
if extra not in s:
    if anchor not in s: raise SystemExit('anchor globals no encontrado')
    s=s.replace(anchor,anchor+extra,1)

# Inicializar asignacion regional de botones como hace el XMB.
needle='''    ioPadInit(7);\n    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);\n    load_font();'''
rep='''    ioPadInit(7);\n    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);\n    s32 enter_assign=1;\n    if(sysUtilGetSystemParamInt(SYSUTIL_SYSTEMPARAM_ID_ENTER_BUTTON_ASSIGN,&enter_assign)==0) g_confirm_cross=(enter_assign==1);\n    load_font();'''
if needle not in s: raise SystemExit('init main no encontrado')
s=s.replace(needle,rep,1)

# Menu contextual tambien respeta Aceptar/Volver del sistema.
s=s.replace('bool up=p.BTN_UP,down=p.BTN_DOWN,xk=p.BTN_CROSS,o=p.BTN_CIRCLE;',
            'bool up=p.BTN_UP,down=p.BTN_DOWN,xk=flow_accept(p),o=flow_back(p);',1)

# Loop principal: X/O logicos segun configuracion del sistema.
s=s.replace('bool x=pad.BTN_CROSS, o=pad.BTN_CIRCLE, tri=pad.BTN_TRIANGLE, start=pad.BTN_START, select=pad.BTN_SELECT;',
            'bool x=flow_accept(pad), o=flow_back(pad), tri=pad.BTN_TRIANGLE, start=pad.BTN_START, select=pad.BTN_SELECT;',1)

# 2) Navegacion horizontal determinista: un solo paso por pulsacion y sin salto circular aleatorio.
old='''        if(left && !p_left) { g_category=(g_category+CATEGORY_COUNT-1)%CATEGORY_COUNT; g_selected=0; rebuild_movies(); }\n        if(right && !p_right) { g_category=(g_category+1)%CATEGORY_COUNT; g_selected=0; rebuild_movies(); }'''
new='''        if(left && !p_left) {\n            if(g_category>0) { g_category--; g_selected=0; rebuild_movies(); }\n            wait_buttons_release();\n        }\n        if(right && !p_right) {\n            if(g_category<CATEGORY_COUNT-1) { g_category++; g_selected=0; rebuild_movies(); }\n            wait_buttons_release();\n        }'''
if old not in s: raise SystemExit('navegacion V13 no encontrada')
s=s.replace(old,new,1)

# 3) Montaje PS2 interno separado del montador generico. Basado en el flujo seguro usado por IRISMAN/Cobra.
anchor='''static int mount_selected_image(const Movie &movie)\n{\n'''
helper=r'''static int v18_mount_ps2_internal(const Movie &movie)
{
    if(v17_ps2_external(movie)) return -260;
    if(movie.path.find("/dev_hdd0/")!=0) return -261;
    char storage[64][MAX_PATH]; char *files[64];
    memset(storage,0,sizeof(storage)); memset(files,0,sizeof(files));
    int n=collect_split_files(movie.path,storage,files); if(n<=0) return -201;
    unlink("/dev_hdd0/classic_ps2");
    unlink("/dev_hdd0/tmp/loadoptical");
    TrackDef track; track.lba=0; track.is_audio=0;
    int ret=cobra_mount_ps2_disc_image(files,n,&track,1);
    if(ret==0) cobra_send_fake_disc_insert_event();
    return ret;
}

'''
if helper not in s:
    if anchor not in s: raise SystemExit('mount_selected anchor no encontrado')
    s=s.replace(anchor,helper+anchor,1)

old='''static int mount_selected_image(const Movie &movie)\n{\n    int mode=category_emu_mode(); if(mode<0) return -210;\n    if(v17_ps2_external(movie)) return -260;\n    if(is_ntfs_movie(movie)) return mount_image_ntfs(movie,mode);\n    return mount_image_fat(movie,mode);\n}'''
new='''static int mount_selected_image(const Movie &movie)\n{\n    int mode=category_emu_mode(); if(mode<0) return -210;\n    if(g_category==6) return v18_mount_ps2_internal(movie);\n    if(is_ntfs_movie(movie)) return mount_image_ntfs(movie,mode);\n    return mount_image_fat(movie,mode);\n}'''
if old not in s: raise SystemExit('mount_selected V17 no encontrado')
s=s.replace(old,new,1)

# Bloqueo ANTES de abrir estado/montador para PS2 externo: no entra en Cobra bajo ninguna circunstancia.
needle='''            Movie movie=g_movies[g_selected];\n            if(g_category==5 && movie.content_type==2)'''
rep='''            Movie movie=g_movies[g_selected];\n            if(g_category==6 && v17_ps2_external(movie)) {\n                show_ok("PS2 EN USB / HDD EXTERNO\\n\\nNO JUGABLE DIRECTAMENTE desde esta ubicacion.\\n\\nFLOWPS3 ha bloqueado el montaje USB para evitar el congelamiento.\\nLa copia original permanece intacta.");\n                wait_buttons_release(); p_x=x; render_ui(); usleep(16000); continue;\n            }\n            if(g_category==5 && movie.content_type==2)'''
if needle not in s: raise SystemExit('bloque accion X no encontrado')
s=s.replace(needle,rep,1)

# 4) Rehacer el render XMB con iconos sensiblemente mas grandes, proporcion PS3 y columna vertical real.
start=s.find('static const char* cat_short')
end=s.find('\nstatic void move_selection',start)
if start<0 or end<0: raise SystemExit('render V17 no encontrado')
new_render=r'''static const char* cat_short(int idx)
{
    static const char *a[]={"PKG","3D","BD","DVD","VID","PS3","PS2","PS1","PSP","ARC","SNES","NES","N64","MD","SMS","GG","GB","GBC","GBA","PCE","NG","NGP","WS","A26","A78","LYNX","VB","FAV"};
    return (idx>=0&&idx<CATEGORY_COUNT)?a[idx]:"?";
}

static double v18_cat_pos=0.0;
static double v18_item_pos=0.0;
static int v18_prev_cat=-1;
static int v18_prev_item=-1;

static void v18_anim_tick()
{
    if(v18_prev_cat<0) v18_prev_cat=g_category;
    if(v18_prev_cat!=g_category) {
        int d=g_category-v18_prev_cat;
        v18_cat_pos=(d>0)?1.0:-1.0;
        v18_prev_cat=g_category;
    }
    if(v18_prev_item<0) v18_prev_item=g_selected;
    if(v18_prev_item!=g_selected) {
        int d=g_selected-v18_prev_item;
        v18_item_pos=(d>0)?1.0:-1.0;
        v18_prev_item=g_selected;
    }
    v18_cat_pos*=0.72;
    v18_item_pos*=0.68;
    if(fabs(v18_cat_pos)<0.01) v18_cat_pos=0.0;
    if(fabs(v18_item_pos)<0.01) v18_item_pos=0.0;
}

static void draw_xmb_category(int idx,int cx,int cy,bool selected)
{
    const int size=selected?118:86;
    int x=cx-size/2, y=cy-size/2;
    u32 border=selected?0xFFF8FCFF:0xB8DCE9F3;
    u32 fill=selected?0xFF477FA8:0xCC557D9B;
    fill_rect(x+7,y+8,size,size,0x24101A27);
    fill_rect(x-2,y-2,size+4,size+4,border);
    fill_rect(x,y,size,size,fill);
    fill_rect(x+6,y+6,size-12,8,0x55FFFFFF);
    const char *lab=cat_short(idx);
    int tw=(int)strlen(lab)*char_advance(1);
    draw_text(cx-tw/2,cy-font_height(1)/2,lab,1,0xFFFFFFFF,8);
}

static void render_ui()
{
    const u32 WHITE=0xFFF9FCFF, MUTED=0xFFE0E8EF, SOFT=0xFFBED1E0, DIM=0xFF91A8BA;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    v18_anim_tick();
    draw_background();

    draw_text(40,24,"FLOWPS3",1,WHITE,18);

    const int cat_y=(sh>=900)?190:150;
    const int spacing=(sw>=1600)?205:158;
    const int visible=(sw>=1600)?4:3;
    int anim=(int)(v18_cat_pos*spacing);

    for(int off=-visible;off<=visible;off++) {
        int idx=g_category+off;
        if(idx<0 || idx>=CATEGORY_COUNT) continue;
        int cx=sw/2+off*spacing+anim;
        bool selected=(off==0);
        draw_xmb_category(idx,cx,cat_y,selected);
        if(selected) {
            std::string n=g_categories[idx].name;
            int tw=(int)n.size()*char_advance(1);
            draw_text(cx-tw/2,cat_y+78,n,1,WHITE,42);
        }
    }

    /* La columna nace justo debajo del icono activo, como el XMB. */
    const int col_x=sw/2-62;
    const int list_y=cat_y+150;
    const int row_h=(sh>=900)?126:98;
    int max_rows=(sh-list_y-55)/row_h;
    if(max_rows<3) max_rows=3;
    int first=0;
    if(g_selected>=max_rows-1) first=g_selected-(max_rows-2);
    int anim_y=(int)(v18_item_pos*row_h);

    if(g_movies.empty()) {
        draw_text(col_x,list_y,"No hay contenido",1,WHITE,32);
        draw_text(col_x,list_y+42,"TRIANGULO: actualizar",1,SOFT,34);
    } else {
        for(int row=0;row<max_rows;row++) {
            int idx=first+row;
            if(idx>=(int)g_movies.size()) break;
            bool selected=(idx==g_selected);
            int y=list_y+row*row_h+anim_y;
            int iw=selected?112:82;
            int ih=iw;
            int ix=col_x-iw/2;
            int iy=y+(row_h-ih)/2;

            if(selected) {
                fill_rect(ix-9,iy-9,iw+18,ih+18,0x22FFFFFF);
                fill_rect(ix-3,iy-3,iw+6,ih+6,0xB8F5FAFF);
            }
            if(!cover_draw(g_movies[idx].path.c_str(),ix,iy,iw,ih)) {
                fill_rect(ix,iy,iw,ih,selected?0xFFF4F8FB:0xFFD1DCE5);
                fill_rect(ix+4,iy+4,iw-8,ih-8,selected?0xFF4A83AD:0xFF6D8CA4);
                const char *lab=cat_short(g_category);
                int tw=(int)strlen(lab)*char_advance(1);
                draw_text(ix+(iw-tw)/2,iy+ih/2-font_height(1)/2,lab,1,0xFFFFFFFF,8);
            }

            int tx=ix+iw+26;
            std::string title=clean_title(g_movies[idx].name);
            if(selected) {
                draw_text(tx,y+18,title,1,WHITE,52);
                std::string src=g_movies[idx].source.empty()?"BIBLIOTECA":g_movies[idx].source;
                draw_text(tx,y+55,src,1,SOFT,28);
                if(v17_ps2_external(g_movies[idx])) draw_text(tx,y+83,"NO JUGABLE DESDE ESTA UBICACION",1,0xFFFFD58A,42);
            } else {
                draw_text(tx,y+35,title,1,MUTED,52);
                if(v17_ps2_external(g_movies[idx])) draw_text(tx,y+68,"NO JUGABLE",1,DIM,20);
            }
        }
    }

    draw_text(34,sh-34,"ACEPTAR   VOLVER   SELECT Opciones   START Arte   TRIANGULO Actualizar",1,WHITE,90);
    g_frame++;
    flip();
}
'''
s=s[:start]+new_render+s[end:]

# Mensajes de ayuda ya no fuerzan X/O, porque ahora siguen el ajuste del sistema.
s=s.replace('"X ACEPTAR    O VOLVER"','"ACEPTAR    VOLVER"')
s=s.replace('"X Abrir   O Volver   SELECT Opciones   START Arte   TRIANGULO Actualizar"','"ACEPTAR   VOLVER   SELECT Opciones   START Arte   TRIANGULO Actualizar"')

p.write_text(s)
print('FLOWPS3 V18 patch aplicado')
