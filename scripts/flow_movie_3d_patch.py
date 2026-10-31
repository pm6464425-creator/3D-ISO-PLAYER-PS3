from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# FLOW MOVIE 3D UI layer. Applied after movie_only_patch.py and env_patch.py.
# It keeps the existing BDISO/MKV backend and replaces only the presentation layer.

if '#include <fcntl.h>' not in s:
    s = s.replace('#include <dirent.h>\n', '#include <dirent.h>\n#include <fcntl.h>\n', 1)
if '#include "stb_image.h"' not in s:
    s = s.replace('#include "ntfs.h"\n', '#include "ntfs.h"\n#include "stb_image.h"\n', 1)

old_movie = '''struct Movie {\n    std::string path;\n    std::string name;\n    std::string source;\n    int usb_id;\n    uint64_t bytes;\n    bool ntfs;\n};'''
new_movie = '''struct Movie {\n    std::string path;\n    std::string name;\n    std::string source;\n    std::string cover;\n    int usb_id;\n    uint64_t bytes;\n    bool ntfs;\n};'''
if old_movie not in s:
    raise SystemExit('movie-only Movie struct not found')
s = s.replace(old_movie, new_movie, 1)

anchor = 'static const char *current_label()  { return g_tab == TAB_BDISO ? "BDISO" : "PELICULAS MKV"; }\n'
extra = r'''

struct CoverBitmap {
    std::string path;
    unsigned char *rgba;
    int w;
    int h;
    unsigned int stamp;
};

#define COVER_CACHE_SLOTS 8
static CoverBitmap g_cover_cache[COVER_CACHE_SLOTS];
static unsigned int g_cover_stamp = 1;

static void cover_cache_clear()
{
    for(int i=0;i<COVER_CACHE_SLOTS;i++) {
        if(g_cover_cache[i].rgba) free(g_cover_cache[i].rgba);
        g_cover_cache[i].rgba = NULL;
        g_cover_cache[i].path.clear();
        g_cover_cache[i].w = g_cover_cache[i].h = 0;
        g_cover_cache[i].stamp = 0;
    }
}
'''
if anchor not in s:
    raise SystemExit('current_label anchor not found')
s = s.replace(anchor, anchor + extra, 1)

helper_anchor = '''static std::string ntfs_folder_path(const char *mount_name, const char *folder)\n{\n    std::string base = mount_name ? mount_name : "";\n    if(!base.empty() && base[base.size()-1] != ':') base += ':';\n    return base + "/" + folder;\n}\n'''
helpers = r'''

static bool movie_path_exists(const Movie &m, const std::string &path)
{
    struct stat st;
    return m.ntfs ? (ps3ntfs_stat(path.c_str(), &st) == 0) : (stat(path.c_str(), &st) == 0);
}

static std::string movie_base_path(const Movie &m)
{
    std::string base = m.path;
    size_t dot = base.find_last_of('.');
    size_t slash = base.find_last_of('/');
    if(dot != std::string::npos && (slash == std::string::npos || dot > slash)) base.resize(dot);
    return base;
}

static std::string movie_parent_path(const Movie &m)
{
    size_t slash = m.path.find_last_of('/');
    if(slash == std::string::npos) return std::string();
    return m.path.substr(0, slash);
}

static std::string movie_base_name(const Movie &m)
{
    std::string n = m.name;
    size_t dot = n.find_last_of('.');
    if(dot != std::string::npos) n.resize(dot);
    return n;
}

static std::string find_movie_cover(const Movie &m)
{
    const char *exts[] = { ".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG" };
    std::string base = movie_base_path(m);
    for(unsigned i=0;i<sizeof(exts)/sizeof(exts[0]);++i) {
        std::string c = base + exts[i];
        if(movie_path_exists(m, c)) return c;
    }

    std::string parent = movie_parent_path(m);
    std::string name = movie_base_name(m);
    if(!parent.empty()) {
        for(unsigned i=0;i<sizeof(exts)/sizeof(exts[0]);++i) {
            std::string c = parent + "/COVERS/" + name + exts[i];
            if(movie_path_exists(m, c)) return c;
        }
    }
    return std::string();
}

static void resolve_cover_paths()
{
    for(size_t i=0;i<g_movies.size();++i) g_movies[i].cover = find_movie_cover(g_movies[i]);
}

static unsigned char *read_file_bytes(const Movie &m, const std::string &path, size_t *out_size)
{
    *out_size = 0;
    struct stat st;
    int sr = m.ntfs ? ps3ntfs_stat(path.c_str(), &st) : stat(path.c_str(), &st);
    if(sr != 0 || st.st_size <= 0 || st.st_size > 16*1024*1024) return NULL;

    size_t sz = (size_t)st.st_size;
    unsigned char *buf = (unsigned char*)malloc(sz);
    if(!buf) return NULL;

    if(m.ntfs) {
        int fd = ps3ntfs_open(path.c_str(), O_RDONLY, 0);
        if(fd < 0) { free(buf); return NULL; }
        size_t off = 0;
        while(off < sz) {
            int n = ps3ntfs_read(fd, (char*)buf + off, sz - off);
            if(n <= 0) break;
            off += (size_t)n;
        }
        ps3ntfs_close(fd);
        if(off != sz) { free(buf); return NULL; }
    } else {
        FILE *f = fopen(path.c_str(), "rb");
        if(!f) { free(buf); return NULL; }
        size_t got = fread(buf, 1, sz, f);
        fclose(f);
        if(got != sz) { free(buf); return NULL; }
    }

    *out_size = sz;
    return buf;
}

static unsigned char *scale_rgba(const unsigned char *src, int sw, int sh, int *dw, int *dh)
{
    const int MAXW = 320, MAXH = 480;
    int tw = sw, th = sh;
    if(tw > MAXW) { th = (int)((long long)th * MAXW / tw); tw = MAXW; }
    if(th > MAXH) { tw = (int)((long long)tw * MAXH / th); th = MAXH; }
    if(tw < 1) tw = 1;
    if(th < 1) th = 1;

    unsigned char *dst = (unsigned char*)malloc((size_t)tw * th * 4);
    if(!dst) return NULL;
    for(int y=0;y<th;y++) {
        int sy = (int)((long long)y * sh / th);
        for(int x=0;x<tw;x++) {
            int sx = (int)((long long)x * sw / tw);
            const unsigned char *sp = src + ((size_t)sy * sw + sx) * 4;
            unsigned char *dp = dst + ((size_t)y * tw + x) * 4;
            dp[0]=sp[0]; dp[1]=sp[1]; dp[2]=sp[2]; dp[3]=sp[3];
        }
    }
    *dw = tw; *dh = th;
    return dst;
}

static CoverBitmap *get_movie_cover(const Movie &m)
{
    if(m.cover.empty()) return NULL;
    for(int i=0;i<COVER_CACHE_SLOTS;i++) {
        if(g_cover_cache[i].rgba && g_cover_cache[i].path == m.cover) {
            g_cover_cache[i].stamp = ++g_cover_stamp;
            return &g_cover_cache[i];
        }
    }

    int slot = -1;
    unsigned int oldest = 0xFFFFFFFFu;
    for(int i=0;i<COVER_CACHE_SLOTS;i++) {
        if(!g_cover_cache[i].rgba) { slot = i; break; }
        if(g_cover_cache[i].stamp < oldest) { oldest = g_cover_cache[i].stamp; slot = i; }
    }
    if(slot < 0) return NULL;

    size_t sz = 0;
    unsigned char *file = read_file_bytes(m, m.cover, &sz);
    if(!file) return NULL;
    int iw=0, ih=0, comp=0;
    unsigned char *decoded = stbi_load_from_memory(file, (int)sz, &iw, &ih, &comp, 4);
    free(file);
    if(!decoded || iw <= 0 || ih <= 0) { if(decoded) stbi_image_free(decoded); return NULL; }

    int cw=0, ch=0;
    unsigned char *scaled = scale_rgba(decoded, iw, ih, &cw, &ch);
    stbi_image_free(decoded);
    if(!scaled) return NULL;

    if(g_cover_cache[slot].rgba) free(g_cover_cache[slot].rgba);
    g_cover_cache[slot].rgba = scaled;
    g_cover_cache[slot].w = cw;
    g_cover_cache[slot].h = ch;
    g_cover_cache[slot].path = m.cover;
    g_cover_cache[slot].stamp = ++g_cover_stamp;
    return &g_cover_cache[slot];
}
'''
if helper_anchor not in s:
    raise SystemExit('ntfs_folder_path helper anchor not found')
s = s.replace(helper_anchor, helper_anchor + helpers, 1)

# Resolve cover art after each scan and invalidate cached bitmaps when media changes.
needle = '    g_movies.swap(fresh);\n    g_selected = 0;'
replacement = '    g_movies.swap(fresh);\n    cover_cache_clear();\n    resolve_cover_paths();\n    g_selected = 0;'
if needle not in s:
    raise SystemExit('g_movies swap anchor not found')
s = s.replace(needle, replacement, 1)

# Replace the old background and poster renderer with the FLOW MOVIE 3D coverflow renderer.
start = s.find('static void draw_background()')
end = s.find('\nstatic int connected_count()', start)
if start < 0 or end < 0:
    raise SystemExit('draw_background/draw_poster block not found')
new_visuals = r'''static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    u32 top=0xFF04070B, bottom=0xFF071826;
    for(int y=0;y<sh;y+=6) fill_rect(0,y,sw,6,mix_color(top,bottom,y,sh));

    /* Blue luminous ribbons: original artwork for FLOW MOVIE 3D. */
    for(int x=0;x<sw;x+=5) {
        int dx=x-sw/2;
        int y1=sh*48/100 + (dx*dx)/(sw*7) - sh/10;
        int y2=sh*54/100 + (dx*dx)/(sw*9) - sh/12;
        if(y1>=0 && y1<sh) fill_rect(x,y1,8,3,0xFF0A69B7);
        if(y2>=0 && y2<sh) fill_rect(x,y2,8,2,0xFF0B3D73);
    }
    for(int x=0;x<sw;x+=6) {
        int y=sh/8 + x*34/100;
        if(y<sh) fill_rect(x,y,10,2,0xFF07518F);
        int yb=sh/7 + (sw-x)*31/100;
        if(yb<sh) fill_rect(x,yb,10,2,0xFF063B6D);
    }

    /* Static bokeh particles. */
    static const int px[18]={5,12,20,28,36,44,52,60,68,76,84,92,15,31,47,63,79,95};
    static const int py[18]={28,14,36,21,31,12,26,17,34,11,25,19,43,9,39,7,42,15};
    for(int i=0;i<18;i++) {
        int r=(i%4)+2;
        draw_circle(sw*px[i]/100, sh*py[i]/100, r*2, 0xFF0C5A91);
    }

    /* Reflective floor. */
    fill_rect(0,sh*66/100,sw,2,0xFF0B4F82);
    for(int y=sh*66/100+2;y<sh;y+=8) fill_rect(0,y,sw,8,mix_color(0xFF071522,0xFF020609,y-sh*66/100,sh*34/100));
}

static void draw_rgba_scaled(int x, int y, int w, int h, const CoverBitmap *c)
{
    if(!c || !c->rgba || w<=0 || h<=0) return;
    u32 sw=get_screen_width(), sh=get_screen_height();
    u32 *fb=get_back_buffer();
    for(int yy=0; yy<h; ++yy) {
        int py=y+yy; if(py<0 || py>=(int)sh) continue;
        int sy=(int)((long long)yy*c->h/h);
        for(int xx=0; xx<w; ++xx) {
            int px=x+xx; if(px<0 || px>=(int)sw) continue;
            int sx=(int)((long long)xx*c->w/w);
            const unsigned char *sp=c->rgba+((size_t)sy*c->w+sx)*4;
            unsigned int a=sp[3];
            if(a==255) fb[py*sw+px]=0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
            else if(a) blend_pixel(px,py,0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2],a);
        }
    }
}

static void draw_cover_reflection(int x, int y, int w, int h, const CoverBitmap *c)
{
    if(!c || !c->rgba || w<=0) return;
    int rh=h/5; if(rh<12) return;
    for(int yy=0;yy<rh;yy+=2) {
        int sy=c->h-1-(int)((long long)yy*c->h/(rh*2));
        unsigned int alpha=(unsigned int)(70*(rh-yy)/rh);
        for(int xx=0;xx<w;xx+=2) {
            int sx=(int)((long long)xx*c->w/w);
            const unsigned char *sp=c->rgba+((size_t)sy*c->w+sx)*4;
            u32 col=0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
            blend_pixel(x+xx,y+yy,col,alpha);
            blend_pixel(x+xx+1,y+yy,col,alpha);
        }
    }
}

static void draw_generic_cover(int x,int y,int w,int h,const Movie &m,bool selected)
{
    u32 c1 = g_tab==TAB_BDISO ? 0xFF31383D : 0xFF174F36;
    u32 c2 = g_tab==TAB_BDISO ? 0xFF11161A : 0xFF082417;
    for(int yy=0;yy<h;yy+=4) fill_rect(x,y+yy,w,4,mix_color(c1,c2,yy,h));
    int band=h/5;
    fill_rect(x,y+h-band,w,band,0xEAF2F5F7);
    draw_centered(y+h/2-font_height(1)/2,g_tab==TAB_BDISO?"BLU-RAY ISO":"MKV",1,0xFFF4FAFF);
    std::string title=clean_title(m.name);
    int maxc=(w-16)/char_advance(1);
    if(maxc>0) draw_text(x+8,y+h-band+8,title,1,0xFF17202A,maxc);
    if(selected) fill_rect(x,y,4,h,0xFF2EA9FF);
}

static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)
{
    /* Shadow + translucent Blu-ray/movie case frame. */
    fill_rect(x+8,y+10,w,h,0x66000000);
    u32 frame=selected?0xFFE8F5FF:0xFF6D7B87;
    fill_rect(x-5,y-5,w+10,h+10,frame);
    fill_rect(x-2,y-2,w+4,h+4,0xFF151A1E);

    CoverBitmap *c=get_movie_cover(m);
    if(c) {
        draw_rgba_scaled(x,y,w,h,c);
        draw_cover_reflection(x,y+h+8,w,h,c);
    } else {
        draw_generic_cover(x,y,w,h,m,selected);
    }

    /* Slim translucent case top lip. */
    fill_rect(x,y,w,10,g_tab==TAB_BDISO?0x883A7A9D:0x8840A46C);
    if(selected) {
        fill_rect(x-7,y-7,w+14,2,0xFF37AFFF);
        fill_rect(x-7,y+h+5,w+14,2,0xFF37AFFF);
    }
}
'''
s = s[:start] + new_visuals + s[end:]

# Replace info panel with a compact title/info strip matching the coverflow layout.
start = s.find('static void render_info_panel(int x, int y, int w, int h)')
end = s.find('\nstatic void render_ui()', start)
if start < 0 or end < 0:
    raise SystemExit('render_info_panel block not found')
new_info = r'''static void render_info_panel(int x, int y, int w, int h)
{
    (void)x; (void)y; (void)w; (void)h;
}
'''
s = s[:start] + new_info + s[end:]

start = s.find('static void render_ui()')
end = s.find('\nstatic void move_selection', start)
if start < 0 or end < 0:
    raise SystemExit('render_ui block not found')
new_ui = r'''static void draw_tab_pill(int x,int y,int w,int h,const char *label,bool active)
{
    u32 border=active?0xFF309FEC:0xFF474E54;
    u32 fill=active?0xCC202A31:0xB815191D;
    fill_rect(x-3,y-3,w+6,h+6,border);
    fill_rect(x,y,w,h,fill);
    int tw=(int)strlen(label)*char_advance(1);
    draw_text(x+(w-tw)/2,y+(h-font_height(1))/2,label,1,0xFFF6F8FA,20);
}

static void render_ui()
{
    const u32 WHITE=0xFFF7F8FA, MUTED=0xFFABB4BC, BLUE=0xFF49B5FF;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    draw_background();

    /* Branding and platform/category bar. */
    draw_text(34,22,"FLOW MOVIE 3D",1,0xFFD7E8F5,24);
    int tab_y=(sh>=900)?48:30;
    int pill_w=(sw>=1600)?170:118, pill_h=(sh>=900)?58:42, gap=18;
    int total=pill_w*2+gap;
    int tab_x=(sw-total)/2;
    draw_tab_pill(tab_x,tab_y,pill_w,pill_h,"BDISO",g_tab==TAB_BDISO);
    draw_tab_pill(tab_x+pill_w+gap,tab_y,pill_w,pill_h,"MKV",g_tab==TAB_MKV);

    int shoulder_w=(sw>=1600)?70:52;
    fill_rect(tab_x-shoulder_w-28,tab_y+5,shoulder_w,pill_h-10,0xCC22272C);
    draw_text(tab_x-shoulder_w-20,tab_y+(pill_h-font_height(1))/2,"R2",1,WHITE,4);
    fill_rect(tab_x+total+28,tab_y+5,shoulder_w,pill_h-10,0xCC22272C);
    draw_text(tab_x+total+36,tab_y+(pill_h-font_height(1))/2,"R1",1,WHITE,4);

    if(g_movies.empty()) {
        draw_centered(sh/2-35,"NO HAY PELICULAS",(sh>=900)?2:1,WHITE);
        std::string p=std::string("COPIA TUS ARCHIVOS EN /")+current_folder();
        draw_centered(sh/2+30,p,1,MUTED);
        draw_centered(sh/2+65,"HDD INTERNO O USB NTFS",1,BLUE);
    } else {
        const Movie &sel=g_movies[g_selected];
        std::string title=clean_title(sel.name);
        int title_scale=(sh>=900)?2:1;
        draw_centered((sh>=900)?145:108,title,title_scale,WHITE);
        fill_rect(sw/2-sw/6,(sh>=900)?197:142,sw/3,2,0xFF1C5072);

        /* Seven-position coverflow with the selected movie enlarged in the middle. */
        int center_x=sw/2;
        int base_y=(sh>=900)?250:180;
        int main_w=(sw>=1600)?350:245;
        int main_h=main_w*145/100;
        int positions[7]={-3,-2,-1,0,1,2,3};
        for(int z=0;z<7;z++) {
            int off=positions[z];
            int idx=g_selected+off;
            if(idx<0 || idx>=(int)g_movies.size()) continue;
            int a=off<0?-off:off;
            int w=main_w, h=main_h, dx=0, yy=base_y;
            if(a==1) { w=main_w*70/100; h=main_h*70/100; dx=main_w*78/100; yy=base_y+main_h*16/100; }
            else if(a==2) { w=main_w*55/100; h=main_h*55/100; dx=main_w*130/100; yy=base_y+main_h*24/100; }
            else if(a==3) { w=main_w*43/100; h=main_h*43/100; dx=main_w*170/100; yy=base_y+main_h*30/100; }
            int xx=center_x-w/2+(off<0?-dx:(off>0?dx:0));
            draw_poster(xx,yy,w,h,g_movies[idx],off==0);
        }

        char sz[48], count[64];
        format_size(sel.bytes,sz,sizeof(sz));
        snprintf(count,sizeof(count),"%s    %d de %u    %s",sz,g_selected+1,(unsigned)g_movies.size(),sel.source.c_str());
        draw_centered(base_y+main_h+main_h/5+20,count,1,MUTED);
    }

    /* Bottom command strip. */
    int footer_h=(sh>=900)?62:46;
    int fy=sh-footer_h;
    fill_rect(18,fy,sw-36,footer_h,0xDD11171C);
    fill_rect(18,fy,sw-36,2,0xFF316E96);
    draw_text(42,fy+(footer_h-font_height(1))/2,"X  REPRODUCIR     TRIANGULO  ACTUALIZAR     R1/R2  BDISO-MKV     O  SALIR",1,WHITE,100);

    g_frame++;
    flip();
}
'''
s = s[:start] + new_ui + s[end:]

start = s.find('static void move_selection(int dx, int dy)')
end = s.find('\nint main(int argc, char *argv[])', start)
if start < 0 or end < 0:
    raise SystemExit('move_selection block not found')
new_move = r'''static void move_selection(int dx, int dy)
{
    if(g_movies.empty()) return;
    int delta=0;
    if(dx<0) delta=-1;
    else if(dx>0) delta=1;
    else if(dy<0) delta=-5;
    else if(dy>0) delta=5;
    int n=g_selected+delta;
    if(n<0) n=0;
    if(n>=(int)g_movies.size()) n=(int)g_movies.size()-1;
    g_selected=n;
}
'''
s = s[:start] + new_move + s[end:]

# Branding and user-facing strings.
s = s.replace('"MOVIE FLOW PS3"', '"FLOW MOVIE 3D"')
s = s.replace('"PELICULAS MKV"', '"MKV"')
s = s.replace('"MKV detectado correctamente.\\n\\nLa ventana MKV ya forma parte de esta version. El motor de reproduccion se integrara en la siguiente etapa."',
              '"MKV detectado.\\n\\nLa reproduccion MKV se conectara al motor multimedia en la siguiente etapa."')

# Clean cached covers on a normal exit.
cleanup_anchor = '    cleanup_ntfs();\n    ioPadEnd();'
if cleanup_anchor in s:
    s = s.replace(cleanup_anchor, '    cover_cache_clear();\n    cleanup_ntfs();\n    ioPadEnd();', 1)

p.write_text(s)
print('FLOW MOVIE 3D coverflow UI applied')
