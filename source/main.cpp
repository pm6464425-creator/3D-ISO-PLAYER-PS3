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
#define GRID_COLS 4
#define GRID_ROWS 3
#define GRID_PAGE (GRID_COLS * GRID_ROWS)
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

/* ---------- Interfaz grafica sencilla ---------- */

static const u8* glyph(char c)
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

static void fill_rect(int x, int y, int w, int h, u32 color)
{
    u32 sw = get_screen_width(), sh = get_screen_height();
    if(x < 0) { w += x; x = 0; } if(y < 0) { h += y; y = 0; }
    if(x+w > (int)sw) w = (int)sw-x; if(y+h > (int)sh) h = (int)sh-y;
    if(w <= 0 || h <= 0) return;
    u32 *fb = get_back_buffer();
    for(int yy=0; yy<h; ++yy) {
        u32 *row = fb + (y+yy)*sw + x;
        for(int xx=0; xx<w; ++xx) row[xx] = color;
    }
}

static void draw_char(int x, int y, char c, int scale, u32 color)
{
    const u8 *g = glyph(c);
    for(int row=0; row<7; ++row) {
        for(int col=0; col<5; ++col) {
            if(g[row] & (1 << (4-col))) fill_rect(x + col*scale, y + row*scale, scale, scale, color);
        }
    }
}

static void draw_text(int x, int y, const std::string &text, int scale, u32 color, int max_chars)
{
    int cx=x, n=0;
    for(size_t i=0; i<text.size() && n<max_chars; ++i) {
        unsigned char ch = (unsigned char)text[i];
        if(ch >= 128) continue;
        draw_char(cx, y, (char)ch, scale, color);
        cx += 6*scale;
        n++;
    }
}

static void draw_centered(int y, const std::string &text, int scale, u32 color)
{
    int chars = (int)text.size();
    int width = chars * 6 * scale;
    int x = ((int)get_screen_width() - width) / 2;
    if(x < 8) x = 8;
    draw_text(x, y, text, scale, color, chars);
}

static void draw_wrapped_name(int x, int y, int box_w, const std::string &name, int scale, u32 color)
{
    std::string title = clean_title(name);
    int max_chars = (box_w - 20) / (6*scale);
    if(max_chars < 6) max_chars = 6;
    std::string line1, line2;
    if((int)title.size() <= max_chars) line1 = title;
    else {
        int cut = max_chars;
        while(cut > max_chars/2 && title[cut] != ' ') cut--;
        if(cut <= max_chars/2) cut = max_chars;
        line1 = title.substr(0, cut);
        size_t start = cut;
        while(start < title.size() && title[start] == ' ') start++;
        line2 = title.substr(start, max_chars);
        if(start + max_chars < title.size() && max_chars >= 3) {
            line2.resize(max_chars-3);
            line2 += "...";
        }
    }
    draw_text(x+10, y, line1, scale, color, max_chars);
    if(!line2.empty()) draw_text(x+10, y + 9*scale, line2, scale, color, max_chars);
}

static int connected_count()
{
    int n=0;
    for(int i=0;i<8;i++) if(g_present[i]) n++;
    return n;
}

static void render_ui()
{
    const u32 BG = 0xFF0B1018;
    const u32 HEADER = 0xFF101A28;
    const u32 TILE = 0xFF1A2533;
    const u32 SELECTED = 0xFF1769AA;
    const u32 BORDER = 0xFF3D526B;
    const u32 WHITE = 0xFFF4F7FB;
    const u32 MUTED = 0xFF9FB1C5;
    const u32 ACCENT = 0xFF66C7FF;

    u32 sw = get_screen_width(), sh = get_screen_height();
    fill_rect(0,0,(int)sw,(int)sh,BG);

    int title_scale = (sw >= 1600) ? 4 : 3;
    int text_scale = (sw >= 1600) ? 3 : 2;
    int small_scale = (sw >= 1600) ? 2 : 2;
    int header_h = (int)sh / 9;
    int footer_h = (int)sh / 11;
    fill_rect(0,0,(int)sw,header_h,HEADER);
    fill_rect(0,(int)sh-footer_h,(int)sw,footer_h,HEADER);

    draw_text(28, header_h/2 - 4*title_scale, "3D ISO PLAYER", title_scale, WHITE, 30);
    char info[128];
    snprintf(info,sizeof(info),"USB: %d   PELICULAS: %u", connected_count(), (unsigned)g_movies.size());
    draw_text((int)sw/2, header_h/2 - 3*small_scale, info, small_scale, ACCENT, 50);

    if(g_movies.empty()) {
        draw_centered((int)sh/2 - 45, "SIN PELICULAS", title_scale, WHITE);
        draw_centered((int)sh/2 + 15, "CONECTA UN DISCO NTFS CON LA CARPETA BDISO", small_scale, MUTED);
        draw_centered((int)sh/2 + 50, "LA LISTA SE ACTUALIZA AUTOMATICAMENTE", small_scale, MUTED);
    } else {
        int margin = (int)sw / 40;
        int gap = (int)sw / 100;
        if(gap < 10) gap = 10;
        int grid_top = header_h + 18;
        int grid_bottom = (int)sh - footer_h - 18;
        int grid_h = grid_bottom - grid_top;
        int cell_w = ((int)sw - 2*margin - (GRID_COLS-1)*gap) / GRID_COLS;
        int cell_h = (grid_h - (GRID_ROWS-1)*gap) / GRID_ROWS;
        int page = g_selected / GRID_PAGE;
        int first = page * GRID_PAGE;

        for(int slot=0; slot<GRID_PAGE; ++slot) {
            int idx = first + slot;
            if(idx >= (int)g_movies.size()) break;
            int col = slot % GRID_COLS;
            int row = slot / GRID_COLS;
            int x = margin + col*(cell_w+gap);
            int y = grid_top + row*(cell_h+gap);
            bool sel = idx == g_selected;

            fill_rect(x,y,cell_w,cell_h, sel ? SELECTED : TILE);
            fill_rect(x,y,cell_w,3, sel ? WHITE : BORDER);
            fill_rect(x,y+cell_h-3,cell_w,3, sel ? WHITE : BORDER);
            fill_rect(x,y,3,cell_h, sel ? WHITE : BORDER);
            fill_rect(x+cell_w-3,y,3,cell_h, sel ? WHITE : BORDER);

            char usb[32];
            snprintf(usb,sizeof(usb),"USB %03d",g_movies[idx].usb_id);
            draw_text(x+12,y+12,usb,small_scale,sel?WHITE:ACCENT,16);

            int name_y = y + cell_h/2 - 9*text_scale;
            draw_wrapped_name(x+2,name_y,cell_w-4,g_movies[idx].name,text_scale,WHITE);

            char num[32];
            snprintf(num,sizeof(num),"%d/%u",idx+1,(unsigned)g_movies.size());
            draw_text(x+12,y+cell_h-26,num,small_scale,MUTED,16);
        }

        char pg[64];
        int pages = ((int)g_movies.size() + GRID_PAGE - 1) / GRID_PAGE;
        snprintf(pg,sizeof(pg),"PAGINA %d/%d", page+1, pages);
        draw_text((int)sw-210,(int)sh-footer_h+18,pg,small_scale,MUTED,24);
    }

    draw_text(28,(int)sh-footer_h+18,"D-PAD NAVEGAR   X MONTAR   O SALIR   TRIANGULO ACTUALIZAR",small_scale,WHITE,80);
    flip();
}

static void move_selection(int dx, int dy)
{
    if(g_movies.empty()) return;
    int page = g_selected / GRID_PAGE;
    int first = page * GRID_PAGE;
    int slot = g_selected - first;
    int col = slot % GRID_COLS;
    int row = slot / GRID_COLS;

    if(dx < 0) {
        if(col > 0) g_selected--;
        else if(g_selected > 0) g_selected--;
    } else if(dx > 0) {
        if(g_selected + 1 < (int)g_movies.size()) g_selected++;
    }

    if(dy < 0) {
        if(g_selected - GRID_COLS >= 0) g_selected -= GRID_COLS;
    } else if(dy > 0) {
        if(g_selected + GRID_COLS < (int)g_movies.size()) g_selected += GRID_COLS;
        else {
            int last = (int)g_movies.size()-1;
            if(last > g_selected && last/GRID_PAGE == g_selected/GRID_PAGE) g_selected = last;
            else if(last > g_selected && g_selected/GRID_PAGE < last/GRID_PAGE) {
                int target = g_selected + GRID_COLS;
                g_selected = target < (int)g_movies.size() ? target : last;
            }
        }
    }

    (void)row;
}

int main(int argc, char *argv[])
{
    (void)argc; (void)argv;
    void *host_addr = memalign(1024*1024, HOST_SIZE);
    if(!host_addr) return 1;

    init_screen(host_addr, HOST_SIZE);
    ioPadInit(7);
    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0, sysutil_callback, NULL);

    if(!is_cobra_based()) {
        show_ok("No se detectó Cobra.\n\nEste programa requiere CFW con Cobra habilitado.");
        ioPadEnd();
        free(host_addr);
        return 2;
    }

    /* Damos tiempo a que USB/NTFS se estabilice y luego empezamos el modo vivo. */
    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }
    refresh_usb_state(true);

    padData pad;
    memset(&pad,0,sizeof(pad));
    bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false;
    int poll_counter = 0;

    while(app_running) {
        sysUtilCheckCallback();

        if(++poll_counter >= 45) {
            poll_counter = 0;
            refresh_usb_state(false);
        }

        memset(&pad,0,sizeof(pad));
        ioPadGetData(0,&pad);

        bool up = pad.BTN_UP;
        bool down = pad.BTN_DOWN;
        bool left = pad.BTN_LEFT;
        bool right = pad.BTN_RIGHT;
        bool x = pad.BTN_CROSS;
        bool o = pad.BTN_CIRCLE;
        bool tri = pad.BTN_TRIANGLE;

        if(up && !p_up) move_selection(0,-1);
        if(down && !p_down) move_selection(0,1);
        if(left && !p_left) move_selection(-1,0);
        if(right && !p_right) move_selection(1,0);

        if(tri && !p_tri) {
            refresh_usb_state(true);
        }

        if(o && !p_o) {
            app_running = false;
        }

        if(x && !p_x && !g_movies.empty() && g_selected >= 0 && g_selected < (int)g_movies.size()) {
            Movie movie = g_movies[g_selected];
            show_status("Montando Blu-ray mediante Cobra...\n\nNo desconectes el disco USB.");
            int ret = mount_bd_iso(movie);
            close_status();

            if(ret == 0) {
                show_status("ISO montada correctamente.\n\nVolviendo al XMB...\n\nNo desconectes el disco USB.");
                for(int i=0;i<10;i++) { sysUtilCheckCallback(); usleep(100000); }
                exit_to_xmb_after_mount();
            } else {
                char err[768];
                if(ret == -104) snprintf(err,sizeof(err),"El disco USB fue retirado antes de montar la película.\n\nLa lista se actualizará automáticamente.");
                else if(ret == -103) snprintf(err,sizeof(err),"Falta raw_iso.sprx. Reinstala este PKG.");
                else if(ret == -102) snprintf(err,sizeof(err),"La ISO está demasiado fragmentada en NTFS.\n\nVuelve a copiar la película al disco.");
                else if(ret == -101) snprintf(err,sizeof(err),"No se pudieron obtener los sectores físicos de la ISO.");
                else snprintf(err,sizeof(err),"No se pudo montar la película.\n\nError Cobra: 0x%08X",ret);
                show_ok(err);
                refresh_usb_state(true);
            }
        }

        p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri;
        render_ui();
        usleep(12000);
    }

    cleanup_ntfs();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    free(host_addr);
    return 0;
}
