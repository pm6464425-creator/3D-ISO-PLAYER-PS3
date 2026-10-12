from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# Dependencias ligeras para animación y lectura de SFO.
s=s.replace('#include <dirent.h>','#include <dirent.h>\n#include <math.h>\n#include <stdint.h>',1)

# Ampliar la entrada de biblioteca para distinguir origen/tipo.
old='''struct Movie {\n    std::string path;\n    std::string name;\n    int usb_id;\n    uint64_t bytes;\n};'''
new='''struct Movie {\n    std::string path;\n    std::string name;\n    std::string source;\n    std::string title_id;\n    int usb_id;\n    uint64_t bytes;\n    int content_type; /* 0 archivo/ISO, 1 juego carpeta, 2 instalado XMB */\n};'''
if old not in s: raise SystemExit('struct Movie no encontrado')
s=s.replace(old,new,1)

# Etiquetas para entradas externas existentes.
s=s.replace('Movie m; m.name=filename; m.path=root+"/"+filename; m.usb_id=usb; m.bytes=(uint64_t)st.st_size;',
            'Movie m; m.name=filename; m.path=root+"/"+filename; m.source="USB NTFS"; m.title_id=""; m.usb_id=usb; m.bytes=(uint64_t)st.st_size; m.content_type=0;',1)
s=s.replace('Movie m; m.name=de->d_name; m.path=full; m.usb_id=usb; m.bytes=(uint64_t)st.st_size;',
            'Movie m; m.name=de->d_name; m.path=full; m.source="USB FAT32"; m.title_id=""; m.usb_id=usb; m.bytes=(uint64_t)st.st_size; m.content_type=0;',1)

# Helpers SFO + escaneo HDD interno PS3/multiMAN/XMB.
marker='static void rebuild_movies()\n{\n'
helpers=r'''static uint16_t rd16le(const unsigned char *p){ return (uint16_t)(p[0] | (p[1]<<8)); }
static uint32_t rd32le(const unsigned char *p){ return (uint32_t)p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24); }

static std::string sfo_value(const std::string &path,const char *wanted)
{
    FILE *f=fopen(path.c_str(),"rb"); if(!f) return "";
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    if(sz<20 || sz>1024*1024){ fclose(f); return ""; }
    std::vector<unsigned char> b((size_t)sz); if(fread(&b[0],1,b.size(),f)!=b.size()){ fclose(f); return ""; } fclose(f);
    if(rd32le(&b[0])!=0x46535000) return "";
    uint32_t kt=rd32le(&b[8]), dt=rd32le(&b[12]); uint16_t n=rd16le(&b[16]);
    if(kt>=b.size()||dt>=b.size()) return "";
    for(unsigned i=0;i<n;i++) {
        size_t off=20+i*16; if(off+16>b.size()) break;
        uint16_t ko=rd16le(&b[off]); uint32_t len=rd32le(&b[off+4]); uint32_t doff=rd32le(&b[off+12]);
        if(kt+ko>=b.size()||dt+doff>=b.size()) continue;
        const char *key=(const char*)&b[kt+ko];
        if(!strcmp(key,wanted)) {
            size_t avail=b.size()-(dt+doff), use=len<avail?len:avail; if(use==0) return "";
            std::string v((const char*)&b[dt+doff],use); while(!v.empty()&&(v[v.size()-1]=='\0'||v[v.size()-1]=='\n'||v[v.size()-1]=='\r')) v.resize(v.size()-1); return v;
        }
    }
    return "";
}

static void add_hdd_iso_entries(std::vector<Movie> &fresh)
{
    const char *root="/dev_hdd0/PS3ISO"; DIR *d=opendir(root); if(!d) return;
    struct dirent *de; while((de=readdir(d))!=NULL) {
        if(de->d_name[0]=='.' || !(ends_with_ci(de->d_name,".iso")||ends_with_ci(de->d_name,".iso.0")||ends_with_ci(de->d_name,".iso.00"))) continue;
        std::string full=std::string(root)+"/"+de->d_name; struct stat st; if(stat(full.c_str(),&st)!=0) continue;
        Movie m; m.name=de->d_name; m.path=full; m.source="HDD ISO"; m.title_id=""; m.usb_id=-1; m.bytes=(uint64_t)st.st_size; m.content_type=0; fresh.push_back(m);
    } closedir(d);
}

static void add_folder_games(std::vector<Movie> &fresh,const char *root,const char *tag)
{
    DIR *d=opendir(root); if(!d) return; struct dirent *de;
    while((de=readdir(d))!=NULL) {
        if(de->d_name[0]=='.') continue;
        std::string dir=std::string(root)+"/"+de->d_name;
        std::string sfo=dir+"/PS3_GAME/PARAM.SFO"; struct stat st; if(stat(sfo.c_str(),&st)!=0) continue;
        Movie m; std::string title=sfo_value(sfo,"TITLE"); m.name=title.empty()?de->d_name:title; m.path=dir; m.source=tag; m.title_id=sfo_value(sfo,"TITLE_ID"); m.usb_id=-1; m.bytes=0; m.content_type=1; fresh.push_back(m);
    } closedir(d);
}

static void add_xmb_games(std::vector<Movie> &fresh)
{
    const char *root="/dev_hdd0/game"; DIR *d=opendir(root); if(!d) return; struct dirent *de;
    while((de=readdir(d))!=NULL) {
        if(de->d_name[0]=='.' || !strcmp(de->d_name,"3DISO0001")) continue;
        std::string dir=std::string(root)+"/"+de->d_name; std::string sfo=dir+"/PARAM.SFO"; struct stat st;
        if(stat(sfo.c_str(),&st)!=0) continue;
        std::string cat=sfo_value(sfo,"CATEGORY");
        if(cat.empty()) continue;
        std::string title=sfo_value(sfo,"TITLE");
        Movie m; m.name=title.empty()?de->d_name:title; m.path=dir; m.source="XMB"; m.title_id=sfo_value(sfo,"TITLE_ID"); if(m.title_id.empty()) m.title_id=de->d_name; m.usb_id=-1; m.bytes=0; m.content_type=2; fresh.push_back(m);
    } closedir(d);
}

'''
if marker not in s: raise SystemExit('rebuild marker no encontrado')
s=s.replace(marker,helpers+marker,1)

# Insertar escaneo interno al final del rebuild, antes del sort.
needle='''    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.usb_id<b.usb_id;});'''
rep='''    if(g_category==5) {\n        add_hdd_iso_entries(fresh);\n        add_folder_games(fresh,"/dev_hdd0/GAMES","HDD CARPETA");\n        add_folder_games(fresh,"/dev_hdd0/GAMEZ","HDD GAMEZ");\n        add_xmb_games(fresh);\n    }\n\n    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.source<b.source;});'''
if needle not in s: raise SystemExit('sort rebuild no encontrado')
s=s.replace(needle,rep,1)

# Fondo: quitar imagen Spider-Man y usar fondo animado azul estilo XMB.
start=s.find('static void draw_background()')
end=s.find('\nstatic void draw_poster',start)
if start<0 or end<0: raise SystemExit('draw_background no encontrado')
new_bg=r'''static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    for(int y=0;y<sh;y+=6) {
        int r=5 + (18*y)/sh, g=35 + (55*y)/sh, b=92 + (70*y)/sh;
        fill_rect(0,y,sw,6,0xFF000000 | ((u32)r<<16) | ((u32)g<<8) | (u32)b);
    }
    double t=(double)g_frame*0.018;
    for(int layer=0;layer<4;layer++) {
        int base=sh/2 + layer*32; u32 col=(layer==0)?0xFF78B7E6:(layer==1)?0xFF5B9BD0:(layer==2)?0xFF3F7FBC:0xFF2D6AA8;
        for(int x=0;x<sw;x+=5) {
            double yy=sin((double)x/180.0+t+layer*0.9)*28.0 + sin((double)x/390.0-t*0.7)*18.0;
            int y=base+(int)yy; fill_rect(x,y,6,2,col);
            if(layer<2) fill_rect(x,y+3,6,1,0xFFB6D7F2);
        }
    }
    for(int i=0;i<24;i++) {
        int x=(i*173 + (int)(g_frame*(1+i%3)))%sw; int y=(i*97)%sh; int a=2+(i%3);
        fill_rect(x,y,a,a,0xFFB9D7F0);
    }
}
'''
s=s[:start]+new_bg+s[end:]

# Reemplazar render completo: XMB horizontal + lista vertical, sin panel fijo de detalles.
start=s.find('static void render_ui()')
end=s.find('\nstatic void move_selection',start)
if start<0 or end<0: raise SystemExit('render_ui no encontrado')
new_render=r'''static const char* cat_short(int idx)
{
    static const char *a[]={"PKG","3D","BD","DVD","VID","PS3","PS2","PS1","PSP","ARC","SNES","NES","N64","MD","SMS","GG","GB","GBC","GBA","PCE","NG","NGP","WS","A26","A78","LYNX","VB","FAV"};
    return (idx>=0&&idx<CATEGORY_COUNT)?a[idx]:"?";
}

static void draw_xmb_category(int idx,int cx,int cy,bool selected)
{
    int r=selected?34:25; u32 outer=selected?0xFFF4FAFF:0xAA9FC4E5; u32 inner=selected?0xFF2E75B9:0xFF1D568D;
    draw_circle(cx,cy,r,outer); draw_circle(cx,cy,r-4,inner);
    std::string t=cat_short(idx); int sc=1; int tw=(int)t.size()*char_advance(sc);
    draw_text(cx-tw/2,cy-font_height(sc)/2,t,sc,0xFFFFFFFF,8);
}

static void render_ui()
{
    const u32 WHITE=0xFFF7FBFF, MUTED=0xFFB2CCE4, ACCENT=0xFFFFFFFF;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    draw_background();

    draw_text(46,28,"FLOWPS3",1,WHITE,20);
    draw_text(sw-210,28,"XMB LIBRARY",1,MUTED,20);

    int cy=(sh>=900)?155:118, spacing=(sw>=1600)?150:105;
    int visible=(sw>=1600)?4:3;
    for(int off=-visible;off<=visible;off++) {
        int idx=(g_category+off+CATEGORY_COUNT)%CATEGORY_COUNT; int cx=sw/2+off*spacing;
        draw_xmb_category(idx,cx,cy,off==0);
        if(off==0) {
            std::string name=g_categories[idx].name; int tw=(int)name.size()*char_advance(1);
            draw_text(cx-tw/2,cy+46,name,1,WHITE,36);
        }
    }

    int list_x=(sw>=1600)?190:110; int list_y=cy+105; int row_h=(sh>=900)?72:58;
    int max_rows=(sh-list_y-82)/row_h; if(max_rows<4) max_rows=4;
    int first=0; if(g_selected>=max_rows) first=g_selected-max_rows+1;

    if(g_movies.empty()) {
        draw_text(list_x,list_y+30,"NO HAY CONTENIDO",2,WHITE,30);
        draw_text(list_x,list_y+82,"TRIANGULO: ACTUALIZAR  |  USA /FLOWPS3/ O EL HDD INTERNO",1,MUTED,70);
    } else {
        for(int i=0;i<max_rows;i++) {
            int idx=first+i; if(idx>=(int)g_movies.size()) break;
            int y=list_y+i*row_h; bool sel=idx==g_selected;
            if(sel) fill_rect(list_x-18,y-9,sw-list_x-100,row_h-4,0x442C6EA6);
            int icon_w=sel?46:36, icon_h=sel?58:46, icon_x=list_x, icon_y=y+(row_h-icon_h)/2-4;
            if(!cover_draw(g_movies[idx].path.c_str(),icon_x,icon_y,icon_w,icon_h)) {
                fill_rect(icon_x,icon_y,icon_w,icon_h,sel?0xFFE8F4FF:0xFF6C9BC2);
                draw_text(icon_x+6,icon_y+icon_h/2-8,cat_short(g_category),1,0xFF143A5D,6);
            }
            int tx=icon_x+icon_w+20;
            draw_text(tx,y+4,clean_title(g_movies[idx].name),sel?2:1,sel?WHITE:MUTED,55);
            if(sel) {
                std::string src=g_movies[idx].source.empty()?"BIBLIOTECA":g_movies[idx].source;
                draw_text(tx,y+36,src,1,0xFF9FD1F4,28);
            }
        }
    }

    fill_rect(0,sh-54,sw,54,0x55204163);
    draw_text(42,sh-37,"IZQ/DER CATEGORIA   ARR/ABAJO ELEMENTO   X ABRIR   SELECT OPCIONES   START ARTE   TRIANGULO ACTUALIZAR   O SALIR",1,WHITE,115);
    g_frame++; flip();
}
'''
s=s[:start]+new_render+s[end:]

# Menú contextual SELECT y ficha Información.
marker='int main(int argc, char *argv[])\n'
ctx=r'''static void show_item_information(const Movie &m)
{
    char sz[48]; format_size(m.bytes,sz,sizeof(sz));
    char info[1400];
    snprintf(info,sizeof(info),"INFORMACION\n\nTitulo: %s\nPlataforma: %s\nOrigen: %s\nTitle ID: %s\nTipo: %s\nTamano: %s\nRuta:\n%s",
        clean_title(m.name).c_str(),g_categories[g_category].name,m.source.c_str(),m.title_id.empty()?"No disponible":m.title_id.c_str(),
        m.content_type==2?"Juego instalado XMB":m.content_type==1?"Juego en carpeta":"Archivo / ISO",m.bytes?sz:"No calculado",m.path.c_str());
    show_ok(info); wait_buttons_release();
}

static void item_context_menu(const Movie &m)
{
    const char *opts[]={"JUGAR / ABRIR","INFORMACION","CARATULA","FONDO","FAVORITO","ELIMINAR","CANCELAR"};
    int sel=0; bool pu=false,pd=false,px=false,po=false; padData p; memset(&p,0,sizeof(p));
    while(app_running) {
        draw_background(); int sw=(int)get_screen_width(), sh=(int)get_screen_height();
        int w=(sw>=1600)?520:400, h=410, x=sw-w-80, y=(sh-h)/2;
        fill_rect(x,y,w,h,0xE0184268); fill_rect(x,y,4,h,0xFFFFFFFF);
        draw_text(x+28,y+24,"OPCIONES",2,0xFFFFFFFF,20);
        draw_text(x+28,y+68,clean_title(m.name),1,0xFFB9D8F0,42);
        for(int i=0;i<7;i++) { int yy=y+112+i*40; if(i==sel) fill_rect(x+18,yy-5,w-36,34,0x665DA4DC); draw_text(x+34,yy,opts[i],1,i==sel?0xFFFFFFFF:0xFFB9D2E7,26); }
        draw_text(x+28,y+h-30,"X ACEPTAR    O VOLVER",1,0xFFFFFFFF,30); flip();
        memset(&p,0,sizeof(p)); ioPadGetData(0,&p); bool up=p.BTN_UP,down=p.BTN_DOWN,xk=p.BTN_CROSS,o=p.BTN_CIRCLE;
        if(up&&!pu&&sel>0) sel--; if(down&&!pd&&sel<6) sel++;
        if(o&&!po) { wait_buttons_release(); return; }
        if(xk&&!px) {
            if(sel==1) { show_item_information(m); }
            else if(sel==2) { choose_online_cover(m); }
            else if(sel==3) { show_ok("FONDO\n\nLa seleccion de fondo tipo PIC0/PIC1 queda reservada para el siguiente paso de arte por juego."); wait_buttons_release(); }
            else if(sel==4) { show_ok("FAVORITO\n\nLa opcion esta preparada en el menu. El guardado persistente se activara en la siguiente revision."); wait_buttons_release(); }
            else if(sel==5) { show_ok("ELIMINAR\n\nDesactivado en esta version de prueba para evitar borrar contenido por error."); wait_buttons_release(); }
            else if(sel==6) { wait_buttons_release(); return; }
            else { wait_buttons_release(); return; }
        }
        pu=up; pd=down; px=xk; po=o; usleep(16000);
    }
}

'''
if marker not in s: raise SystemExit('main marker no encontrado')
s=s.replace(marker,ctx+marker,1)

# SELECT en loop principal.
s=s.replace('bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_start=false;',
            'bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_start=false,p_select=false;',1)
s=s.replace('bool x=pad.BTN_CROSS, o=pad.BTN_CIRCLE, tri=pad.BTN_TRIANGLE, start=pad.BTN_START;',
            'bool x=pad.BTN_CROSS, o=pad.BTN_CIRCLE, tri=pad.BTN_TRIANGLE, start=pad.BTN_START, select=pad.BTN_SELECT;',1)
s=s.replace('''        if(tri && !p_tri) refresh_usb_state(true);\n        if(start && !p_start''',
            '''        if(tri && !p_tri) { refresh_usb_state(true); rebuild_movies(); }\n        if(select && !p_select && !g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) { item_context_menu(g_movies[g_selected]); }\n        if(start && !p_start''',1)
s=s.replace('p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_start=start;',
            'p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_start=start; p_select=select;',1)

# En PS3, no intentar montar entradas XMB/carpeta como ISO: reconocerlas y mostrar mensaje seguro.
needle='''            Movie movie=g_movies[g_selected];\n            int emu=category_emu_mode();'''
rep='''            Movie movie=g_movies[g_selected];\n            if(g_category==5 && movie.content_type==2) { show_ok("Juego XMB detectado correctamente.\\n\\nEl lanzamiento directo de instalaciones XMB se activara tras validar el metodo seguro en tu CFW."); wait_buttons_release(); p_x=x; render_ui(); usleep(16000); continue; }\n            if(g_category==5 && movie.content_type==1) { show_ok("Juego en carpeta detectado correctamente.\\n\\nFLOWPS3 lo ha encontrado en la biblioteca multiMAN. El mapeo de carpeta se validara en la siguiente prueba."); wait_buttons_release(); p_x=x; render_ui(); usleep(16000); continue; }\n            int emu=category_emu_mode();'''
if needle not in s: raise SystemExit('bloque X V14 no encontrado')
s=s.replace(needle,rep,1)

# Ya no usar fondo JPG precargado.
s=s.replace('    background_load();\n','',1)
s=s.replace('    background_free();\n','',1)

p.write_text(s)
print('FLOWPS3 V15 patch aplicado')
