#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <malloc.h>
#include <vector>
#include <string>
#include <algorithm>

#include <ppu-types.h>
#include <io/pad.h>
#include <sys/stat.h>
#include <sysutil/msg.h>
#include <sysutil/sysutil.h>

#include "rsxutil.h"
#include "ntfs.h"
extern "C" {
#include "cobra.h"
}

#define RAWISO_PATH "/dev_hdd0/game/3DISO0001/USRDIR/raw_iso.sprx"
#define FONT_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/FONT.RAW"
#define GRID_COLS 4
#define GRID_ROWS 2
#define GRID_PAGE (GRID_COLS * GRID_ROWS)
#define FONT_W 16
#define FONT_H 24
#define FONT_FIRST 32
#define FONT_LAST 126
#define FONT_GLYPHS (FONT_LAST-FONT_FIRST+1)
#define MAX_SECTIONS ((int)((0x10000-sizeof(rawseciso_args))/8))

typedef struct {
    uint64_t device;
    uint32_t emu_mode;
    uint32_t num_sections;
    uint32_t num_tracks;
} __attribute__((packed)) rawseciso_args;

struct Movie {
    std::string path;
    std::string name;
    int usb_id;
    uint64_t bytes;
};

static bool app_running = true;
static bool status_open = false;
static volatile s32 dialog_action = 0;
static ntfs_md *g_mounts[8] = {0};
static int g_mount_count[8] = {0};
static bool g_present[8] = {false};
static int g_insert_delay[8] = {0};
static std::vector<Movie> g_movies;
static int g_selected = 0;
static unsigned char *g_font = NULL;
static unsigned int g_frame = 0;

static const DISC_INTERFACE *disc_ntfs[8] = {
    &__io_ntfs_usb000, &__io_ntfs_usb001, &__io_ntfs_usb002, &__io_ntfs_usb003,
    &__io_ntfs_usb004, &__io_ntfs_usb005, &__io_ntfs_usb006, &__io_ntfs_usb007
};

extern "C" {
static void dialog_handler(msgButton button, void *usrData)
{
    (void)usrData;
    switch(button) {
        case MSG_DIALOG_BTN_OK: dialog_action = 1; break;
        case MSG_DIALOG_BTN_NO: dialog_action = 2; break;
        case MSG_DIALOG_BTN_ESCAPE: dialog_action = 3; break;
        default: break;
    }
}

static void sysutil_callback(u64 status, u64 param, void *userdata)
{
    (void)param; (void)userdata;
    if(status == SYSUTIL_EXIT_GAME) app_running = false;
}
}

static void do_flip()
{
    sysUtilCheckCallback();
    flip();
}

static int show_ok(const char *text)
{
    if(status_open) { msgDialogAbort(); status_open = false; }
    dialog_action = 0;
    msgDialogOpen2((msgType)(MSG_DIALOG_NORMAL | MSG_DIALOG_BTN_OK), text, dialog_handler, NULL, NULL);
    while(app_running && !dialog_action) do_flip();
    msgDialogAbort();
    return dialog_action;
}

static void show_status(const char *text)
{
    if(status_open) msgDialogAbort();
    dialog_action = 0;
    msgDialogOpen2(MSG_DIALOG_NORMAL, text, dialog_handler, NULL, NULL);
    status_open = true;
    for(int i=0;i<3;i++) { sysUtilCheckCallback(); usleep(16000); }
}

static void close_status()
{
    if(status_open) {
        msgDialogAbort();
        status_open = false;
        for(int i=0;i<2;i++) { sysUtilCheckCallback(); usleep(16000); }
    }
}

static bool has_iso_ext(const char *name)
{
    if(!name) return false;
    size_t n = strlen(name);
    return n >= 4 && strcasecmp(name + n - 4, ".iso") == 0;
}

static std::string clean_title(const std::string &name)
{
    std::string s = name;
    if(s.size() >= 4 && strcasecmp(s.c_str() + s.size() - 4, ".iso") == 0)
        s.resize(s.size() - 4);
    for(size_t i=0;i<s.size();++i) {
        if(s[i] == '_' || s[i] == '.') s[i] = ' ';
    }
    return s;
}

static void release_port(int usb, bool physical_removed)
{
    if(g_mounts[usb]) {
        if(!physical_removed) {
            for(int p=0; p<g_mount_count[usb]; ++p) {
                if(g_mounts[usb][p].name[0]) ntfsUnmount(g_mounts[usb][p].name, true);
            }
        }
        free(g_mounts[usb]);
        g_mounts[usb] = NULL;
    }
    g_mount_count[usb] = 0;
    PS3_NTFS_Shutdown(usb);
}

static bool mount_port(int usb)
{
    if(g_mounts[usb] || g_mount_count[usb] > 0) release_port(usb, false);
    g_mounts[usb] = NULL;
    g_mount_count[usb] = ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], NTFS_DEFAULT | NTFS_RECOVER);
    if(g_mount_count[usb] <= 0 || !g_mounts[usb]) {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb] = NULL; }
        g_mount_count[usb] = 0;
        return false;
    }
    return true;
}

static void rebuild_movies()
{
    std::string previous_path;
    if(!g_movies.empty() && g_selected >= 0 && g_selected < (int)g_movies.size())
        previous_path = g_movies[g_selected].path;

    std::vector<Movie> fresh;
    for(int usb=0; usb<8; ++usb) {
        if(!g_present[usb] || !g_mounts[usb] || g_mount_count[usb] <= 0) continue;
        for(int p=0; p<g_mount_count[usb]; ++p) {
            if(!g_mounts[usb][p].name[0]) continue;
            std::string root = std::string(g_mounts[usb][p].name) + ":/BDISO";
            DIR_ITER *dir = ps3ntfs_diropen(root.c_str());
            if(!dir) {
                std::string n = g_mounts[usb][p].name;
                if(!n.empty() && n[n.size()-1] == ':') root = n + "/BDISO";
                dir = ps3ntfs_diropen(root.c_str());
            }
            if(!dir) continue;

            char filename[1024];
            struct stat st;
            while(ps3ntfs_dirnext(dir, filename, &st) == 0) {
                if(filename[0] == '.' || !has_iso_ext(filename)) continue;
                Movie m;
                m.name = filename;
                m.path = root + "/" + filename;
                m.usb_id = usb;
                m.bytes = (uint64_t)st.st_size;
                fresh.push_back(m);
                if(fresh.size() >= 512) break;
            }
            ps3ntfs_dirclose(dir);
        }
    }

    std::sort(fresh.begin(), fresh.end(), [](const Movie &a, const Movie &b) {
        int n = strcasecmp(a.name.c_str(), b.name.c_str());
        if(n != 0) return n < 0;
        return a.usb_id < b.usb_id;
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

static bool refresh_usb_state(bool force_scan)
{
    bool changed = force_scan;
    for(int usb=0; usb<8; ++usb) {
        bool inserted = PS3_NTFS_IsInserted(usb);

        if(inserted && !g_present[usb]) {
            g_present[usb] = true;
            g_insert_delay[usb] = 2;
            changed = true;
        } else if(!inserted && g_present[usb]) {
            g_present[usb] = false;
            g_insert_delay[usb] = 0;
            release_port(usb, true);
            changed = true;
        }

        if(g_present[usb] && g_mount_count[usb] <= 0) {
            if(g_insert_delay[usb] > 0) {
                g_insert_delay[usb]--;
            } else if(mount_port(usb)) {
                changed = true;
            }
        }
    }

    if(changed) rebuild_movies();
    return changed;
}

static int mount_bd_iso(const Movie &movie)
{
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

static void cleanup_ntfs()
{
    for(int usb=0; usb<8; ++usb) {
        if(g_mounts[usb] || g_mount_count[usb] > 0) release_port(usb, false);
        else PS3_NTFS_Shutdown(usb);
        g_present[usb] = false;
    }
}

static void exit_to_xmb_after_mount()
{
    close_status();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    /* No desmontar NTFS: raw_iso.sprx debe seguir leyendo el disco USB. */
    exit(0);
}

/* ---------- Tipografia y render cinematografico ---------- */

static const u8* fallback_glyph(char c)
{
    static const u8 Q[7]={14,17,17,17,21,18,13};
    static const u8 A[7]={14,17,17,31,17,17,17}; static const u8 B[7]={30,17,17,30,17,17,30};
    static const u8 C[7]={14,17,16,16,16,17,14}; static const u8 D[7]={30,17,17,17,17,17,30};
    static const u8 E[7]={31,16,16,30,16,16,31}; static const u8 F[7]={31,16,16,30,16,16,16};
    static const u8 G[7]={14,17,16,23,17,17,15}; static const u8 H[7]={17,17,17,31,17,17,17};
    static const u8 I[7]={31,4,4,4,4,4,31}; static const u8 J[7]={7,2,2,2,18,18,12};
    static const u8 K[7]={17,18,20,24,20,18,17}; static const u8 L[7]={16,16,16,16,16,16,31};
    static const u8 M[7]={17,27,21,21,17,17,17}; static const u8 N[7]={17,25,21,19,17,17,17};
    static const u8 O[7]={14,17,17,17,17,17,14}; static const u8 P[7]={30,17,17,30,16,16,16};
    static const u8 R[7]={30,17,17,30,20,18,17}; static const u8 S[7]={15,16,16,14,1,1,30};
    static const u8 T[7]={31,4,4,4,4,4,4}; static const u8 U[7]={17,17,17,17,17,17,14};
    static const u8 V[7]={17,17,17,17,17,10,4}; static const u8 W[7]={17,17,17,21,21,21,10};
    static const u8 X[7]={17,17,10,4,10,17,17}; static const u8 Y[7]={17,17,10,4,4,4,4};
    static const u8 Z[7]={31,1,2,4,8,16,31};
    static const u8 N0[7]={14,17,19,21,25,17,14}; static const u8 N1[7]={4,12,4,4,4,4,14};
    static const u8 N2[7]={14,17,1,2,4,8,31}; static const u8 N3[7]={30,1,1,14,1,1,30};
    static const u8 N4[7]={2,6,10,18,31,2,2}; static const u8 N5[7]={31,16,16,30,1,1,30};
    static const u8 N6[7]={14,16,16,30,17,17,14}; static const u8 N7[7]={31,1,2,4,8,8,8};
    static const u8 N8[7]={14,17,17,14,17,17,14}; static const u8 N9[7]={14,17,17,15,1,1,14};
    static const u8 DASH[7]={0,0,0,31,0,0,0}; static const u8 DOT[7]={0,0,0,0,0,12,12};
    static const u8 COLON[7]={0,12,12,0,12,12,0}; static const u8 SLASH[7]={1,2,2,4,8,8,16};
    static const u8 LP[7]={2,4,8,8,8,4,2}; static const u8 RP[7]={8,4,2,2,2,4,8};
    static const u8 SPACE[7]={0,0,0,0,0,0,0}; static const u8 QM[7]={14,17,1,2,4,0,4};
    if(c>='a' && c<='z') c = (char)(c-'a'+'A');
    switch(c) {
        case 'A': return A; case 'B': return B; case 'C': return C; case 'D': return D; case 'E': return E;
        case 'F': return F; case 'G': return G; case 'H': return H; case 'I': return I; case 'J': return J;
        case 'K': return K; case 'L': return L; case 'M': return M; case 'N': return N; case 'O': return O;
        case 'P': return P; case 'Q': return Q; case 'R': return R; case 'S': return S; case 'T': return T;
        case 'U': return U; case 'V': return V; case 'W': return W; case 'X': return X; case 'Y': return Y; case 'Z': return Z;
        case '0': return N0; case '1': return N1; case '2': return N2; case '3': return N3; case '4': return N4;
        case '5': return N5; case '6': return N6; case '7': return N7; case '8': return N8; case '9': return N9;
        case '-': return DASH; case '.': return DOT; case ':': return COLON; case '/': return SLASH;
        case '(': return LP; case ')': return RP; case ' ': return SPACE; default: return QM;
    }
}

static bool load_font()
{
    FILE *f = fopen(FONT_PATH, "rb");
    if(!f) return false;
    size_t sz = FONT_GLYPHS * FONT_W * FONT_H;
    g_font = (unsigned char*)malloc(sz);
    if(!g_font) { fclose(f); return false; }
    size_t rd = fread(g_font, 1, sz, f);
    fclose(f);
    if(rd != sz) { free(g_font); g_font = NULL; return false; }
    return true;
}

static void fill_rect(int x, int y, int w, int h, u32 color)
{
    u32 sw = get_screen_width(), sh = get_screen_height();
    if(x < 0) { w += x; x = 0; }
    if(y < 0) { h += y; y = 0; }
    if(x+w > (int)sw) w = (int)sw-x;
    if(y+h > (int)sh) h = (int)sh-y;
    if(w <= 0 || h <= 0) return;
    u32 *fb = get_back_buffer();
    for(int yy=0; yy<h; ++yy) {
        u32 *row = fb + (y+yy)*sw + x;
        for(int xx=0; xx<w; ++xx) row[xx] = color;
    }
}

static u32 mix_color(u32 a, u32 b, int t, int maxv)
{
    if(maxv <= 0) return a;
    int ar=(a>>16)&255, ag=(a>>8)&255, ab=a&255;
    int br=(b>>16)&255, bg=(b>>8)&255, bb=b&255;
    int r=ar+(br-ar)*t/maxv, g=ag+(bg-ag)*t/maxv, bl=ab+(bb-ab)*t/maxv;
    return 0xFF000000 | ((u32)r<<16) | ((u32)g<<8) | (u32)bl;
}

static void blend_pixel(int x, int y, u32 color, unsigned int alpha)
{
    u32 sw=get_screen_width(), sh=get_screen_height();
    if(x<0 || y<0 || x>=(int)sw || y>=(int)sh || alpha==0) return;
    u32 *p = get_back_buffer() + y*sw + x;
    u32 d=*p;
    unsigned int sr=(color>>16)&255, sg=(color>>8)&255, sb=color&255;
    unsigned int dr=(d>>16)&255, dg=(d>>8)&255, db=d&255;
    unsigned int ia=255-alpha;
    unsigned int r=(sr*alpha+dr*ia)/255;
    unsigned int g=(sg*alpha+dg*ia)/255;
    unsigned int b=(sb*alpha+db*ia)/255;
    *p=0xFF000000 | (r<<16) | (g<<8) | b;
}

static void draw_char(int x, int y, char c, int scale, u32 color)
{
    unsigned char uc=(unsigned char)c;
    if(g_font && uc>=FONT_FIRST && uc<=FONT_LAST) {
        const unsigned char *src=g_font+(uc-FONT_FIRST)*FONT_W*FONT_H;
        for(int yy=0; yy<FONT_H; ++yy) {
            for(int xx=0; xx<FONT_W; ++xx) {
                unsigned int a=src[yy*FONT_W+xx];
                if(a<18) continue;
                for(int sy=0; sy<scale; ++sy)
                    for(int sx=0; sx<scale; ++sx)
                        blend_pixel(x+xx*scale+sx,y+yy*scale+sy,color,a);
            }
        }
        return;
    }

    const u8 *g=fallback_glyph(c);
    for(int row=0; row<7; ++row)
        for(int col=0; col<5; ++col)
            if(g[row] & (1 << (4-col))) fill_rect(x+col*scale,y+row*scale,scale,scale,color);
}

static int char_advance(int scale)
{
    return g_font ? 13*scale : 6*scale;
}

static int font_height(int scale)
{
    return g_font ? FONT_H*scale : 7*scale;
}

static void draw_text(int x, int y, const std::string &text, int scale, u32 color, int max_chars)
{
    int cx=x, n=0;
    for(size_t i=0; i<text.size() && n<max_chars; ++i) {
        unsigned char ch=(unsigned char)text[i];
        if(ch>=128) continue;
        draw_char(cx,y,(char)ch,scale,color);
        cx += char_advance(scale);
        n++;
    }
}

static void draw_centered(int y, const std::string &text, int scale, u32 color)
{
    int width=(int)text.size()*char_advance(scale);
    int x=((int)get_screen_width()-width)/2;
    if(x<8) x=8;
    draw_text(x,y,text,scale,color,(int)text.size());
}

static void draw_wrapped(int x, int y, int box_w, const std::string &text, int scale, u32 color, int max_lines)
{
    int max_chars=box_w/char_advance(scale);
    if(max_chars<5) max_chars=5;
    std::string remaining=text;
    for(int line=0; line<max_lines && !remaining.empty(); ++line) {
        std::string out;
        if((int)remaining.size()<=max_chars) {
            out=remaining;
            remaining.clear();
        } else {
            int cut=max_chars;
            while(cut>max_chars/2 && remaining[cut]!=' ') cut--;
            if(cut<=max_chars/2) cut=max_chars;
            out=remaining.substr(0,cut);
            size_t start=cut;
            while(start<remaining.size() && remaining[start]==' ') start++;
            remaining=remaining.substr(start);
            if(line==max_lines-1 && !remaining.empty() && max_chars>3) {
                if((int)out.size()>max_chars-3) out.resize(max_chars-3);
                out += "...";
                remaining.clear();
            }
        }
        draw_text(x,y+line*(font_height(scale)+3),out,scale,color,max_chars);
    }
}

static unsigned int title_hash(const std::string &s)
{
    unsigned int h=2166136261u;
    for(size_t i=0;i<s.size();++i) { h^=(unsigned char)s[i]; h*=16777619u; }
    return h;
}

static void draw_circle(int cx, int cy, int radius, u32 color)
{
    u32 sw=get_screen_width(), sh=get_screen_height();
    u32 *fb=get_back_buffer();
    int r2=radius*radius;
    for(int y=-radius;y<=radius;++y) {
        int py=cy+y; if(py<0 || py>=(int)sh) continue;
        for(int x=-radius;x<=radius;++x) {
            if(x*x+y*y>r2) continue;
            int px=cx+x; if(px<0 || px>=(int)sw) continue;
            fb[py*sw+px]=color;
        }
    }
}

static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    u32 top=0xFF050914, bottom=0xFF111B2C;
    for(int y=0;y<sh;y+=8) fill_rect(0,y,sw,8,mix_color(top,bottom,y,sh));

    /* franjas de pelicula discretas a los lados */
    u32 strip=0xFF0A1422, hole=0xFF1A3048;
    fill_rect(0,0,34,sh,strip);
    fill_rect(sw-34,0,34,sh,strip);
    for(int y=18;y<sh;y+=46) {
        fill_rect(8,y,14,25,hole);
        fill_rect(sw-22,y,14,25,hole);
    }
    /* lineas de luz cinematograficas */
    fill_rect(sw/5,0,2,sh,0xFF0D2238);
    fill_rect(sw*4/5,0,2,sh,0xFF0D2238);
}

static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)
{
    static const u32 P1[8]={0xFF12304A,0xFF2D173F,0xFF143D35,0xFF432019,0xFF182B55,0xFF3B243F,0xFF183C4D,0xFF3F2F16};
    static const u32 P2[8]={0xFF1AA6B7,0xFF9C4DD2,0xFF21A47A,0xFFD46A34,0xFF4D7EDD,0xFFD65D9B,0xFF3FB9D1,0xFFD6A53B};
    unsigned int hsh=title_hash(m.name);
    u32 c1=P1[hsh&7], c2=P2[(hsh>>5)&7];

    if(selected) {
        fill_rect(x-7,y-7,w+14,h+14,0xFF42D4FF);
        fill_rect(x-4,y-4,w+8,h+8,0xFFFFFFFF);
    } else {
        fill_rect(x-3,y-3,w+6,h+6,0xFF263A50);
    }

    for(int yy=0; yy<h; yy+=4) fill_rect(x,y+yy,w,4,mix_color(c1,c2,yy,h));

    /* textura geometrica distinta para cada titulo */
    for(int k=0;k<6;k++) {
        int xx=x+(int)((hsh>>(k*4))%((unsigned int)(w>30?w-24:1)));
        fill_rect(xx,y+10,2,h-20,0x553FFFFFF);
    }

    int reel_r=w/9;
    if(reel_r<9) reel_r=9;
    int rcx=x+w/2, rcy=y+h/3;
    draw_circle(rcx,rcy,reel_r+5,0xCC07101A);
    draw_circle(rcx,rcy,reel_r,0xFFE8F6FF);
    int hr=reel_r/4; if(hr<2) hr=2;
    draw_circle(rcx-reel_r/2,rcy,hr,0xFF182635);
    draw_circle(rcx+reel_r/2,rcy,hr,0xFF182635);
    draw_circle(rcx,rcy-reel_r/2,hr,0xFF182635);
    draw_circle(rcx,rcy+reel_r/2,hr,0xFF182635);
    draw_circle(rcx,rcy,hr,0xFF182635);

    std::string title=clean_title(m.name);
    int band_h=h/3;
    fill_rect(x,y+h-band_h,w,band_h,0xE6070D16);
    int body_scale=1;
    draw_wrapped(x+10,y+h-band_h+10,w-20,title,body_scale,0xFFF5FAFF,2);

    char usb[32];
    snprintf(usb,sizeof(usb),"USB %03d",m.usb_id);
    draw_text(x+10,y+h-28,usb,1,0xFF71DCFF,16);
}

static int connected_count()
{
    int n=0;
    for(int i=0;i<8;i++) if(g_present[i]) n++;
    return n;
}

static void format_size(uint64_t bytes, char *out, size_t outsz)
{
    double gb=(double)bytes/(1024.0*1024.0*1024.0);
    if(gb>=1.0) snprintf(out,outsz,"%.2f GB",gb);
    else snprintf(out,outsz,"%.0f MB",(double)bytes/(1024.0*1024.0));
}

static void render_info_panel(int x, int y, int w, int h)
{
    const u32 PANEL=0xE60A111D, WHITE=0xFFF4FAFF, MUTED=0xFF9AB0C6, ACCENT=0xFF56D7FF;
    fill_rect(x,y,w,h,PANEL);
    fill_rect(x,y,3,h,0xFF24445F);
    draw_text(x+20,y+18,"SELECCION",1,ACCENT,20);

    if(g_movies.empty() || g_selected<0 || g_selected>=(int)g_movies.size()) {
        draw_wrapped(x+20,y+70,w-40,"CONECTA UN DISCO NTFS PARA VER TU BIBLIOTECA",1,MUTED,4);
        return;
    }

    const Movie &m=g_movies[g_selected];
    std::string title=clean_title(m.name);
    draw_wrapped(x+20,y+58,w-40,title,1,WHITE,4);

    int base=y+170;
    char line[128];
    snprintf(line,sizeof(line),"DISCO     USB %03d",m.usb_id);
    draw_text(x+20,base,line,1,MUTED,40);
    char sz[48]; format_size(m.bytes,sz,sizeof(sz));
    snprintf(line,sizeof(line),"TAMANO    %s",sz);
    draw_text(x+20,base+34,line,1,MUTED,40);
    draw_text(x+20,base+68,"FORMATO   BLU-RAY ISO",1,MUTED,40);
    draw_text(x+20,base+102,"PORTADA   AUTO CINEMA",1,MUTED,40);

    snprintf(line,sizeof(line),"PELICULA %d DE %u",g_selected+1,(unsigned)g_movies.size());
    draw_text(x+20,y+h-72,line,1,ACCENT,40);
    draw_wrapped(x+20,y+h-43,w-40,"X PARA MONTAR EN COBRA",1,WHITE,2);
}

static void render_ui()
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
    draw_text(60,header_h/2-font_height(title_scale)/2,"3D ISO PLAYER",title_scale,WHITE,30);
    draw_text(60+(sh>=900?360:190),header_h/2-font_height(1)/2,"CINEMA LIBRARY",1,ACCENT,30);

    char info[96];
    snprintf(info,sizeof(info),"USB %d   ISO %u",connected_count(),(unsigned)g_movies.size());
    int iw=(int)strlen(info)*char_advance(1);
    draw_text(sw-60-iw,header_h/2-font_height(1)/2,info,1,MUTED,40);

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
        draw_centered(sh/2+5,"CONECTA UN DISCO NTFS CON BDISO",1,MUTED);
        draw_centered(sh/2+42,"LAS PELICULAS APARECERAN AUTOMATICAMENTE",1,ACCENT);
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
            bool sel=(idx==g_selected);
            draw_poster(x,y,cell_w,cell_h,g_movies[idx],sel);
        }
        render_info_panel(panel_x,content_top,panel_w,content_h);

        int pages=((int)g_movies.size()+GRID_PAGE-1)/GRID_PAGE;
        char pg[64]; snprintf(pg,sizeof(pg),"PAGINA %d/%d",page+1,pages);
        draw_text(panel_x,sh-footer_h+18,pg,1,MUTED,24);
    }

    draw_text(60,sh-footer_h+18,"D-PAD  NAVEGAR     X  MONTAR     TRIANGULO  ACTUALIZAR     O  SALIR",1,WHITE,90);
    g_frame++;
    flip();
}

static void move_selection(int dx, int dy)
{
    if(g_movies.empty()) return;
    if(dx<0) {
        if(g_selected>0) g_selected--;
    } else if(dx>0) {
        if(g_selected+1<(int)g_movies.size()) g_selected++;
    }

    if(dy<0) {
        if(g_selected-GRID_COLS>=0) g_selected-=GRID_COLS;
    } else if(dy>0) {
        if(g_selected+GRID_COLS<(int)g_movies.size()) g_selected+=GRID_COLS;
        else {
            int last=(int)g_movies.size()-1;
            if(last>g_selected) g_selected=last;
        }
    }
}

int main(int argc, char *argv[])
{
    (void)argc; (void)argv;
    void *host_addr=memalign(1024*1024,HOST_SIZE);
    if(!host_addr) return 1;

    init_screen(host_addr,HOST_SIZE);
    ioPadInit(7);
    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);
    load_font();

    if(!is_cobra_based()) {
        show_ok("No se detecto Cobra.\n\nEste programa requiere CFW con Cobra habilitado.");
        ioPadEnd();
        if(g_font) free(g_font);
        free(host_addr);
        return 2;
    }

    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }
    refresh_usb_state(true);

    padData pad;
    memset(&pad,0,sizeof(pad));
    bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false;
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

        if(up && !p_up) move_selection(0,-1);
        if(down && !p_down) move_selection(0,1);
        if(left && !p_left) move_selection(-1,0);
        if(right && !p_right) move_selection(1,0);
        if(tri && !p_tri) refresh_usb_state(true);
        if(o && !p_o) app_running=false;

        if(x && !p_x && !g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) {
            Movie movie=g_movies[g_selected];
            show_status("Montando Blu-ray mediante Cobra...\n\nNo desconectes el disco USB.");
            int ret=mount_bd_iso(movie);
            close_status();

            if(ret==0) {
                show_status("ISO montada correctamente.\n\nVolviendo al XMB...\n\nNo desconectes el disco USB.");
                for(int i=0;i<10;i++) { sysUtilCheckCallback(); usleep(100000); }
                exit_to_xmb_after_mount();
            } else {
                char err[768];
                if(ret==-104) snprintf(err,sizeof(err),"El disco USB fue retirado antes de montar la pelicula.\n\nLa biblioteca se actualizara automaticamente.");
                else if(ret==-103) snprintf(err,sizeof(err),"Falta raw_iso.sprx. Reinstala este PKG.");
                else if(ret==-102) snprintf(err,sizeof(err),"La ISO esta demasiado fragmentada en NTFS.\n\nVuelve a copiar la pelicula al disco.");
                else if(ret==-101) snprintf(err,sizeof(err),"No se pudieron obtener los sectores fisicos de la ISO.");
                else snprintf(err,sizeof(err),"No se pudo montar la pelicula.\n\nError Cobra: 0x%08X",ret);
                show_ok(err);
                refresh_usb_state(true);
            }
        }

        p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri;
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
