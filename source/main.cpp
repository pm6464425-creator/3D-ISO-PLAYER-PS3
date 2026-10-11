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
#include <sysutil/video.h>

#include "rsxutil.h"
#include "ntfs.h"
extern "C" {
#include "cobra.h"
}

#define RAWISO_PATH "/dev_hdd0/game/3DISO0001/USRDIR/raw_iso.sprx"

typedef struct {
    uint64_t device;
    uint32_t emu_mode;
    uint32_t num_sections;
    uint32_t num_tracks;
} __attribute__((packed)) rawseciso_args;

#define MAX_SECTIONS ((int)((0x10000-sizeof(rawseciso_args))/8))

enum PlayMode { MODE_AUTO = 0, MODE_2D = 1, MODE_3D = 2 };

struct Movie {
    std::string path;
    std::string name;
    int usb_id;
};

struct ScanReport {
    int mounted_ports;
    int mounted_partitions;
    int bdiso_dirs;
    int iso_files;
    int mount_result[8];
};

static volatile s32 dialog_action = 0;
static bool app_running = true;
static bool status_open = false;
static ntfs_md *g_mounts[8] = {0};
static int g_mount_count[8] = {0};

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

static int show_yes_no(const char *text)
{
    if(status_open) { msgDialogAbort(); status_open = false; }
    dialog_action = 0;
    msgDialogOpen2((msgType)(MSG_DIALOG_NORMAL | MSG_DIALOG_BTN_TYPE_YESNO), text, dialog_handler, NULL, NULL);
    while(app_running && !dialog_action) do_flip();
    msgDialogAbort();
    if(dialog_action == 1) return 1;
    if(dialog_action == 2) return 0;
    return -1;
}

static void show_status(const char *text)
{
    if(status_open) msgDialogAbort();
    dialog_action = 0;
    msgDialogOpen2(MSG_DIALOG_NORMAL, text, dialog_handler, NULL, NULL);
    status_open = true;
    for(int i=0;i<4;i++) { do_flip(); usleep(16000); }
}

static void close_status()
{
    if(status_open) {
        msgDialogAbort();
        status_open = false;
        for(int i=0;i<2;i++) do_flip();
    }
}

static bool has_iso_ext(const char *name)
{
    if(!name) return false;
    size_t n = strlen(name);
    return n >= 4 && strcasecmp(name + n - 4, ".iso") == 0;
}

static bool display_supports_3d()
{
    s32 r = videoGetResolutionAvailability(VIDEO_PRIMARY,
                                            VIDEO_RESOLUTION_720_3D_FRAME_PACKING,
                                            VIDEO_ASPECT_AUTO, 0);
    return r > 0;
}

static int force_2d_720p()
{
    videoConfiguration cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.resolution = VIDEO_RESOLUTION_720;
    cfg.format = VIDEO_BUFFER_FORMAT_XRGB;
    cfg.aspect = VIDEO_ASPECT_16_9;
    cfg.pitch = 1280 * 4;
    return videoConfigure(VIDEO_PRIMARY, &cfg, NULL, 1);
}

static PlayMode choose_play_mode(bool has3d)
{
    char msg[768];
    snprintf(msg, sizeof(msg),
        "Modo de reproducción\n\nDetección HDMI 3D: %s\n\n¿Usar modo AUTOMÁTICO?\n\nSí = Automático\nNo = elegir manualmente",
        has3d ? "DISPONIBLE" : "NO DETECTADO");

    int r = show_yes_no(msg);
    if(r < 0) return MODE_AUTO;
    if(r == 1) return MODE_AUTO;

    r = show_yes_no("Selección manual\n\n¿Forzar salida 2D compatible?\n\nSí = 2D 720p\nNo = mantener salida 3D/actual");
    if(r == 1) return MODE_2D;
    return MODE_3D;
}

static std::vector<Movie> scan_movies(ScanReport *report)
{
    std::vector<Movie> movies;
    memset(report, 0, sizeof(*report));
    for(int i=0;i<8;i++) report->mount_result[i] = -999;

    for(int i=0;i<12 && app_running;i++) { do_flip(); usleep(100000); }

    for(int usb=0; usb<8 && app_running; ++usb) {
        char status[256];
        snprintf(status, sizeof(status), "3D ISO PLAYER V6\n\nBuscando películas ISO...\n\nRevisando USB %03d de 007", usb);
        show_status(status);

        PS3_NTFS_Shutdown(usb);
        usleep(120000);
        g_mounts[usb] = NULL;
        g_mount_count[usb] = ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], NTFS_DEFAULT | NTFS_RECOVER);
        report->mount_result[usb] = g_mount_count[usb];

        if(g_mount_count[usb] <= 0) {
            if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb] = NULL; }
            PS3_NTFS_Shutdown(usb);
            usleep(180000);
            g_mount_count[usb] = ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], NTFS_DEFAULT | NTFS_RECOVER);
            report->mount_result[usb] = g_mount_count[usb];
        }

        if(g_mount_count[usb] <= 0 || !g_mounts[usb]) {
            if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb] = NULL; }
            g_mount_count[usb] = 0;
            continue;
        }

        report->mounted_ports++;
        report->mounted_partitions += g_mount_count[usb];

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

            report->bdiso_dirs++;
            char filename[1024];
            struct stat st;
            while(ps3ntfs_dirnext(dir, filename, &st) == 0) {
                if(filename[0] == '.' || !has_iso_ext(filename)) continue;
                Movie m;
                m.name = filename;
                m.path = root + "/" + filename;
                m.usb_id = usb;
                movies.push_back(m);
                report->iso_files++;
                if(movies.size() >= 256) break;
            }
            ps3ntfs_dirclose(dir);
        }
    }

    close_status();
    std::sort(movies.begin(), movies.end(), [](const Movie &a, const Movie &b) {
        return strcasecmp(a.name.c_str(), b.name.c_str()) < 0;
    });
    return movies;
}

static void cleanup_ntfs()
{
    for(int usb=0; usb<8; ++usb) {
        if(g_mounts[usb]) {
            for(int p=0; p<g_mount_count[usb]; ++p)
                if(g_mounts[usb][p].name[0]) ntfsUnmount(g_mounts[usb][p].name, true);
            free(g_mounts[usb]);
            g_mounts[usb] = NULL;
            g_mount_count[usb] = 0;
        }
        PS3_NTFS_Shutdown(usb);
    }
}

static int mount_bd_iso(const Movie &movie)
{
    struct stat st;
    if(stat(RAWISO_PATH, &st) != 0) return -103;

    void *plugin_args = memalign(128, 0x10000);
    uint32_t *sections = (uint32_t*)malloc(MAX_SECTIONS * sizeof(uint32_t));
    uint32_t *sizes = (uint32_t*)malloc(MAX_SECTIONS * sizeof(uint32_t));
    if(!plugin_args || !sections || !sizes) {
        free(plugin_args); free(sections); free(sizes);
        return -100;
    }

    memset(plugin_args, 0, 0x10000);
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

static void exit_to_xmb_after_mount()
{
    close_status();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    /* No desmontar NTFS: raw_iso.sprx necesita seguir leyendo el HDD. */
    exit(0);
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
        cleanup_ntfs(); free(host_addr); return 2;
    }

    bool has3d = display_supports_3d();

    show_status("3D ISO PLAYER V6\n\nBuscando películas ISO en discos USB NTFS...\n\nNo desconectes el disco.");
    ScanReport report;
    std::vector<Movie> movies = scan_movies(&report);

    if(movies.empty()) {
        char msg[1200];
        snprintf(msg, sizeof(msg),
            "No se encontraron películas ISO.\n\nUSB NTFS montados: %d\nParticiones: %d\nCarpetas BDISO: %d\nISO: %d\n\nPuertos 000-007:\n%d, %d, %d, %d, %d, %d, %d, %d",
            report.mounted_ports, report.mounted_partitions, report.bdiso_dirs, report.iso_files,
            report.mount_result[0], report.mount_result[1], report.mount_result[2], report.mount_result[3],
            report.mount_result[4], report.mount_result[5], report.mount_result[6], report.mount_result[7]);
        show_ok(msg); cleanup_ntfs(); free(host_addr); return 0;
    }

    int selected = -1;
    for(size_t i=0; i<movies.size() && app_running; ++i) {
        char msg[1400];
        snprintf(msg, sizeof(msg), "Película %u de %u\n\n%s\n\n¿Montar esta película?\n\nSí = montar     No = siguiente",
                 (unsigned)(i+1), (unsigned)movies.size(), movies[i].name.c_str());
        int r = show_yes_no(msg);
        if(r == 1) { selected = (int)i; break; }
        if(r < 0) break;
    }

    if(selected < 0) {
        show_ok("No se seleccionó ninguna película.");
        cleanup_ntfs(); free(host_addr); return 0;
    }

    PlayMode mode = choose_play_mode(has3d);
    bool use2d = (mode == MODE_2D) || (mode == MODE_AUTO && !has3d);

    if(mode == MODE_AUTO) {
        show_status(use2d ?
            "Modo AUTOMÁTICO\n\nNo se detectó salida 3D.\nSe preparará una salida 2D 720p compatible.\n\nMontando ISO..." :
            "Modo AUTOMÁTICO\n\nSe detectó salida 3D disponible.\nSe conservará la salida HDMI actual.\n\nMontando ISO...");
    } else if(mode == MODE_2D) {
        show_status("Modo 2D\n\nSe forzará salida estándar 720p antes de volver al XMB.\n\nMontando ISO...");
    } else {
        show_status("Modo 3D\n\nSe conservará la salida HDMI/3D actual.\n\nMontando ISO...");
    }

    int ret = mount_bd_iso(movies[selected]);
    close_status();

    if(ret != 0) {
        char err[768];
        if(ret == -103) snprintf(err, sizeof(err), "Falta raw_iso.sprx. Reinstala el PKG.");
        else if(ret == -102) snprintf(err, sizeof(err), "La ISO está demasiado fragmentada en NTFS.");
        else if(ret == -101) snprintf(err, sizeof(err), "No se pudieron obtener los sectores físicos de la ISO.");
        else snprintf(err, sizeof(err), "No se pudo montar la película.\n\nError Cobra: 0x%08X", ret);
        show_ok(err); cleanup_ntfs(); free(host_addr); return 3;
    }

    if(use2d) {
        show_ok("ISO montada correctamente.\n\nSe aplicará salida 2D estándar 720p y volveremos al XMB.\n\nDespués inicia el disco Blu-ray montado.");
        close_status();
        ioPadEnd();
        sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
        force_2d_720p();
        usleep(700000);
        exit(0);
    }

    show_status("ISO montada correctamente.\n\nVolviendo al XMB de forma segura...\n\nNo desconectes el disco USB.");
    for(int i=0;i<10;i++) { do_flip(); usleep(100000); }
    exit_to_xmb_after_mount();
    return 0;
}
