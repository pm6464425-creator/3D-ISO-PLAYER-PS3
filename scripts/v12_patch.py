from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()
s=s.replace('#define GRID_COLS 4','#define GRID_COLS 3',1)

old='''extern "C" {\n#include "cobra.h"\n}\n'''
new='''extern "C" {\n#include "cobra.h"\nint cover_prepare(const char *iso_path);\nint cover_draw(const char *iso_path, int x, int y, int w, int h);\nint cover_state(const char *iso_path);\nint cover_set_external(const char *iso_path, const u32 *pixels, int count);\nint cover_net_search(const char *iso_path);\nint cover_net_count();\nint cover_net_copy_choice(int index, u32 *out, int count);\nint cover_net_draw_choice(int index, int x, int y, int w, int h);\nint background_load();\nint background_draw();\nvoid background_free();\n}\n'''
if old not in s: raise SystemExit('bloque cobra no encontrado')
s=s.replace(old,new,1)

old='''    for(int yy=0; yy<h; yy+=4) fill_rect(x,y+yy,w,4,mix_color(c1,c2,yy,h));\n'''
new='''    if(cover_draw(m.path.c_str(),x,y,w,h)) {\n        std::string title=clean_title(m.name);\n        int band_h=h/3; fill_rect(x,y+h-band_h,w,band_h,0xE6070D16);\n        draw_wrapped(x+10,y+h-band_h+10,w-20,title,1,0xFFF5FAFF,2);\n        char usb_real[32]; snprintf(usb_real,sizeof(usb_real),"USB %03d",m.usb_id);\n        draw_text(x+10,y+h-28,usb_real,1,0xFF71DCFF,16); return;\n    }\n    for(int yy=0; yy<h; yy+=4) fill_rect(x,y+yy,w,4,mix_color(c1,c2,yy,h));\n'''
if old not in s: raise SystemExit('poster no encontrado')
s=s.replace(old,new,1)

s=s.replace('draw_text(x+20,base+102,"PORTADA   AUTO CINEMA",1,MUTED,40);','draw_text(x+20,base+102,"PORTADA   ISO / INTERNET 3D",1,MUTED,40);',1)
s=s.replace('draw_text(60,sh-footer_h+18,"D-PAD  NAVEGAR     X  MONTAR     TRIANGULO  ACTUALIZAR     O  SALIR",1,WHITE,90);',
            'draw_text(40,sh-footer_h+18,"D-PAD NAVEGAR   X MONTAR   START PORTADA 3D   TRIANGULO ACTUALIZAR   O SALIR",1,WHITE,100);',1)

s=s.replace('''static void draw_background()\n{\n    int sw=(int)get_screen_width(), sh=(int)get_screen_height();''','''static void draw_background()\n{\n    if(background_draw()) return;\n    int sw=(int)get_screen_width(), sh=(int)get_screen_height();''',1)
s=s.replace('''    load_font();\n''','''    load_font();\n    background_load();\n''',1)

picker=r'''
static void wait_buttons_release()
{
    padData p; memset(&p,0,sizeof(p));
    for(int i=0;i<120;i++) {
        ioPadGetData(0,&p);
        if(!p.BTN_CROSS && !p.BTN_CIRCLE && !p.BTN_START && !p.BTN_UP && !p.BTN_DOWN && !p.BTN_LEFT && !p.BTN_RIGHT) break;
        sysUtilCheckCallback(); usleep(16000);
    }
}

static void choose_online_cover(const Movie &movie)
{
    show_status("Buscando portadas Blu-ray 3D en espanol...\n\nEspera unos segundos.");
    int n=cover_net_search(movie.path.c_str());
    close_status();
    if(n<=0) {
        show_ok("No se encontraron portadas en esta busqueda.\n\nVerifica la conexion a Internet o intenta nuevamente.");
        wait_buttons_release();
        return;
    }

    int sel=0;
    bool pu=false,pd=false,pl=false,pr=false,px=false,po=false;
    padData p; memset(&p,0,sizeof(p));
    while(app_running) {
        sysUtilCheckCallback();
        draw_background();
        int sw=(int)get_screen_width(), sh=(int)get_screen_height();
        fill_rect(0,0,sw,82,0xD9050A12);
        draw_text(48,20,"ELIGE PORTADA BLU-RAY 3D",2,0xFFF7FBFF,40);
        std::string ttl=clean_title(movie.name);
        draw_text(48,58,ttl.c_str(),1,0xFF8FE8FF,60);

        int cols=3, gap=22, top=96, footer=62;
        int avail_h=sh-top-footer;
        int ch=(avail_h-gap)/2;
        int cw=(ch*180)/250;
        int max_cw=(sw-120-gap*2)/3;
        if(cw>max_cw){ cw=max_cw; ch=(cw*250)/180; }
        int grid_w=cw*cols+gap*(cols-1);
        int gx=(sw-grid_w)/2;
        int rows=(n+cols-1)/cols;
        int used_h=ch*rows+gap*(rows-1);
        int gy=top+(avail_h-used_h)/2;

        for(int i=0;i<n;i++) {
            int c=i%cols, r=i/cols;
            int x=gx+c*(cw+gap), y=gy+r*(ch+gap);
            fill_rect(x-6,y-6,cw+12,ch+12,(i==sel)?0xFF43D8FF:0xAA101722);
            cover_net_draw_choice(i,x,y,cw,ch);
            if(i==sel) {
                fill_rect(x-6,y-6,cw+12,4,0xFFFFFFFF);
                fill_rect(x-6,y+ch+2,cw+12,4,0xFFFFFFFF);
                fill_rect(x-6,y-6,4,ch+12,0xFFFFFFFF);
                fill_rect(x+cw+2,y-6,4,ch+12,0xFFFFFFFF);
            }
        }
        fill_rect(0,sh-footer,sw,footer,0xE8050A12);
        draw_text(44,sh-footer+18,"D-PAD ELEGIR     X GUARDAR PORTADA     O CANCELAR",1,0xFFFFFFFF,85);
        flip();

        memset(&p,0,sizeof(p)); ioPadGetData(0,&p);
        bool up=p.BTN_UP, down=p.BTN_DOWN, left=p.BTN_LEFT, right=p.BTN_RIGHT;
        bool x=p.BTN_CROSS, o=p.BTN_CIRCLE;
        if(left && !pl && sel>0) sel--;
        if(right && !pr && sel+1<n) sel++;
        if(up && !pu && sel-cols>=0) sel-=cols;
        if(down && !pd && sel+cols<n) sel+=cols;
        if(o && !po){ wait_buttons_release(); return; }
        if(x && !px){
            std::vector<u32> pix(180*250);
            if(cover_net_copy_choice(sel,&pix[0],(int)pix.size()) && cover_set_external(movie.path.c_str(),&pix[0],(int)pix.size())) {
                show_ok("Portada guardada correctamente.\n\nQuedara almacenada en la PS3 incluso sin Internet.");
            } else {
                show_ok("No se pudo guardar la portada seleccionada.");
            }
            wait_buttons_release();
            return;
        }
        pu=up; pd=down; pl=left; pr=right; px=x; po=o;
        usleep(16000);
    }
}

'''
marker='''int main(int argc, char *argv[])\n'''
if marker not in s: raise SystemExit('main no encontrado')
s=s.replace(marker,picker+marker,1)

s=s.replace('''    bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false;''',
            '''    bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_start=false;''',1)
s=s.replace('''        bool x=pad.BTN_CROSS, o=pad.BTN_CIRCLE, tri=pad.BTN_TRIANGLE;''',
            '''        bool x=pad.BTN_CROSS, o=pad.BTN_CIRCLE, tri=pad.BTN_TRIANGLE, start=pad.BTN_START;''',1)
s=s.replace('''        if(tri && !p_tri) refresh_usb_state(true);\n        if(o && !p_o) app_running=false;''',
            '''        if(tri && !p_tri) refresh_usb_state(true);\n        if(start && !p_start && !g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) {\n            choose_online_cover(g_movies[g_selected]);\n        }\n        if(o && !p_o) app_running=false;''',1)
s=s.replace('''        p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri;\n        render_ui();\n''',
            '''        p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_start=start;\n        if(!g_movies.empty() && (g_frame % 30)==0) {\n            static int cover_slot=0; int first=(g_selected/GRID_PAGE)*GRID_PAGE;\n            int idx=first+(cover_slot++ % GRID_PAGE); if(idx>=(int)g_movies.size()) idx=g_selected;\n            if(idx>=0 && idx<(int)g_movies.size() && cover_state(g_movies[idx].path.c_str())==0) cover_prepare(g_movies[idx].path.c_str());\n        }\n        render_ui();\n''',1)
s=s.replace('''    if(g_font) free(g_font);\n    free(host_addr);''','''    background_free();\n    if(g_font) free(g_font);\n    free(host_addr);''',1)
p.write_text(s)

p=Path('source/cover_udf.cpp')
s=p.read_text()
s=s.replace('''static std::vector<CoverEntry> g_covers;''','''static std::vector<CoverEntry> g_covers;\nextern "C" int cover_net_fetch(const char *iso_path, u32 *out, int count);''',1)
s=s.replace('''    if(ok) { entry.state=1; save_disk_cache(iso_path,entry.pixels); return 1; }\n    entry.pixels.clear();\n    entry.state=2;\n    return 0;''','''    if(ok) { entry.state=1; save_disk_cache(iso_path,entry.pixels); return 1; }\n    entry.pixels.resize(COVER_W*COVER_H);\n    if(cover_net_fetch(iso_path,&entry.pixels[0],COVER_W*COVER_H)) { entry.state=1; save_disk_cache(iso_path,entry.pixels); return 1; }\n    entry.pixels.clear(); entry.state=2; return 0;''',1)
s += r'''

extern "C" int cover_set_external(const char *iso_path, const u32 *pixels, int count)
{
    if(!iso_path || !pixels || count<COVER_W*COVER_H) return 0;
    CoverEntry *e=find_entry(iso_path);
    if(!e) {
        if(g_covers.size()>=40) g_covers.erase(g_covers.begin());
        CoverEntry n; n.key=iso_path; n.state=0; g_covers.push_back(n); e=&g_covers.back();
    }
    e->pixels.assign(pixels,pixels+COVER_W*COVER_H);
    e->state=1;
    save_disk_cache(iso_path,e->pixels);
    return 1;
}
'''
p.write_text(s)
print('V12 patch aplicado')
