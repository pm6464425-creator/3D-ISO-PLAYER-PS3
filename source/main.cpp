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
#include <sys/process.h>
#include <sys/stat.h>
#include <sysutil/msg.h>
#include <sysutil/sysutil.h>

#include "rsxutil.h"
#include "ntfs.h"
#include "cobra.h"

#define APP_TITLE "3D ISO PLAYER"
#define RAWISO_PATH "/dev_hdd0/game/3DISO001/USRDIR/raw_iso.sprx"
#define BDPLAYER_PATH "/dev_flash/bdplayer/bdp_BDMV.self"

typedef struct
{
    uint64_t device;
    uint32_t emu_mode;
    uint32_t num_sections;
    uint32_t num_tracks;
} __attribute__((packed)) rawseciso_args;

#define MAX_SECTIONS ((int)((0x10000-sizeof(rawseciso_args))/8))

struct Movie
{
    std::string path;
    std::string name;
    int usb_id;
};

static volatile s32 dialog_action = 0;
static bool app_running = true;
static ntfs_md *g_mounts[8] = {0};
static int g_mount_count[8] = {0};

static const DISC_INTERFACE *disc_ntfs[8] = {
    &__io_ntfs_usb000,
    &__io_ntfs_usb001,
    &__io_ntfs_usb002,
    &__io_ntfs_usb003,
    &__io_ntfs_usb004,
    &__io_ntfs_usb005,
    &__io_ntfs_usb006,
    &__io_ntfs_usb007
};

extern "C" {
static void dialog_handler(msgButton button, void *usrData)
{
    (void)usrData;
    switch(button)
    {
        case MSG_DIALOG_BTN_OK: dialog_action = 1; break;
        case MSG_DIALOG_BTN_NO: dialog_action = 2; break;
        case MSG_DIALOG_BTN_ESCAPE: dialog_action = 3; break;
        case MSG_DIALOG_BTN_NONE: dialog_action = -1; break;
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
    msgType type = (msgType)(MSG_DIALOG_NORMAL | MSG_DIALOG_BTN_OK);
    dialog_action = 0;
    msgDialogOpen2(type, text, dialog_handler, NULL, NULL);
    while(app_running && !dialog_action) do_flip();
    msgDialogAbort();
    return dialog_action;
}

static int show_yes_no(const char *text)
{
    msgType type = (msgType)(MSG_DIALOG_NORMAL | MSG_DIALOG_BTN_TYPE_YESNO);
    dialog_action = 0;
    msgDialogOpen2(type, text, dialog_handler, NULL, NULL);
    while(app_running && !dialog_action) do_flip();
    msgDialogAbort();
    if(dialog_action == 1) return 1;
    if(dialog_action == 2) return 0;
    return -1;
}

static bool has_iso_ext(const char *name)
{
    if(!name) return false;
    size_t n = strlen(name);
    if(n < 4) return false;
    return strcasecmp(name + n - 4, ".iso") == 0;
}

static std::vector<Movie> scan_movies()
{
    std::vector<Movie> movies;

    for(int usb = 0; usb < 8; ++usb)
    {
        if(!PS3_NTFS_IsInserted(usb)) continue;

        g_mounts[usb] = NULL;
        g_mount_count[usb] = ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], NTFS_DEFAULT | NTFS_RECOVER | NTFS_READ_ONLY);
        if(g_mount_count[usb] <= 0) continue;

        for(int p = 0; p < g_mount_count[usb]; ++p)
        {
            std::string root = std::string(g_mounts[usb][p].name) + ":/BDISO";
            DIR_ITER *dir = ps3ntfs_diropen(root.c_str());
            if(!dir) continue;

            char filename[1024];
            struct stat st;
            while(ps3ntfs_dirnext(dir, filename, &st) == 0)
            {
                if(filename[0] == '.') continue;
                if(!has_iso_ext(filename)) continue;

                Movie m;
                m.name = filename;
                m.path = root + "/" + filename;
                m.usb_id = usb;
                movies.push_back(m);
                if(movies.size() >= 256) break;
            }
            ps3ntfs_dirclose(dir);
        }
    }

    std::sort(movies.begin(), movies.end(), [](const Movie &a, const Movie &b) {
        return strcasecmp(a.name.c_str(), b.name.c_str()) < 0;
    });
    return movies;
}

static void cleanup_ntfs()
{
    for(int usb = 0; usb < 8; ++usb)
    {
        if(g_mounts[usb])
        {
            for(int p = 0; p < g_mount_count[usb]; ++p)
            {
                if(g_mounts[usb][p].name[0]) ntfsUnmount(g_mounts[usb][p].name, true);
            }
            free(g_mounts[usb]);
            g_mounts[usb] = NULL;
            g_mount_count[usb] = 0;
        }
        PS3_NTFS_Shutdown(usb);
    }
}

static int mount_bd_iso(const Movie &movie)
{
    void *plugin_args = memalign(128, 0x10000);
    uint32_t *sections = (uint32_t*)malloc(MAX_SECTIONS * sizeof(uint32_t));
    uint32_t *section_sizes = (uint32_t*)malloc(MAX_SECTIONS * sizeof(uint32_t));

    if(!plugin_args || !sections || !section_sizes)
    {
        free(plugin_args); free(sections); free(section_sizes);
        return -100;
    }

    memset(plugin_args, 0, 0x10000);
    memset(sections, 0, MAX_SECTIONS * sizeof(uint32_t));
    memset(section_sizes, 0, MAX_SECTIONS * sizeof(uint32_t));

    int parts = ps3ntfs_file_to_sectors(movie.path.c_str(), sections, section_sizes, MAX_SECTIONS, 1);
    if(parts <= 0 || parts >= MAX_SECTIONS)
    {
        free(plugin_args); free(sections); free(section_sizes);
        return (parts >= MAX_SECTIONS) ? -102 : -101;
    }

    rawseciso_args *args = (rawseciso_args*)plugin_args;
    args->device = USB_MASS_STORAGE(movie.usb_id);
    args->emu_mode = EMU_BD;
    args->num_sections = (uint32_t)parts;
    args->num_tracks = 0;

    memcpy((uint8_t*)plugin_args + sizeof(rawseciso_args), sections, parts * sizeof(uint32_t));
    memcpy((uint8_t*)plugin_args + sizeof(rawseciso_args) + parts * sizeof(uint32_t), section_sizes, parts * sizeof(uint32_t));

    cobra_unload_vsh_plugin(0);
    int ret = cobra_load_vsh_plugin(0, (char*)RAWISO_PATH, plugin_args, 0x10000);

    free(plugin_args);
    free(sections);
    free(section_sizes);
    return ret;
}

static void launch_bluray_player()
{
    sleep(2);

    const char *argv[] = { BDPLAYER_PATH, NULL };
    sysProcessExitSpawn2(BDPLAYER_PATH, argv, NULL, NULL, 0, 1001, SYS_PROCESS_SPAWN_STACK_SIZE_1M);

    show_ok("La ISO fue montada, pero el reproductor Blu-ray no pudo iniciarse directamente.");
}

int main(int argc, char *argv[])
{
    (void)argc; (void)argv;

    void *host_addr = memalign(1024*1024, HOST_SIZE);
    if(!host_addr) return 1;

    init_screen(host_addr, HOST_SIZE);
    ioPadInit(7);
    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0, sysutil_callback, NULL);

    show_ok("3D ISO PLAYER\n\nBuscando películas Blu-ray ISO en dispositivos USB NTFS...");

    if(!is_cobra_based())
    {
        show_ok("No se detectó Cobra.\n\nEste programa requiere un CFW con Cobra habilitado.");
        cleanup_ntfs();
        return 2;
    }

    std::vector<Movie> movies = scan_movies();
    if(movies.empty())
    {
        show_ok("No se encontraron películas.\n\nConecta un disco USB NTFS y guarda las ISO en la carpeta:\n\nBDISO");
        cleanup_ntfs();
        return 0;
    }

    int selected = -1;
    for(size_t i = 0; i < movies.size() && app_running; ++i)
    {
        char msg[1400];
        snprintf(msg, sizeof(msg), "Película %u de %u\n\n%s\n\n¿Reproducir esta película?\n\nSí = reproducir     No = siguiente", (unsigned)(i+1), (unsigned)movies.size(), movies[i].name.c_str());
        int r = show_yes_no(msg);
        if(r == 1) { selected = (int)i; break; }
        if(r < 0) break;
    }

    if(selected < 0)
    {
        show_ok("No se seleccionó ninguna película.");
        cleanup_ntfs();
        return 0;
    }

    char mounting[1400];
    snprintf(mounting, sizeof(mounting), "Preparando Blu-ray 3D...\n\n%s\n\nPulsa Aceptar y espera unos segundos.", movies[selected].name.c_str());
    show_ok(mounting);

    int ret = mount_bd_iso(movies[selected]);
    if(ret != 0)
    {
        char err[512];
        if(ret == -102)
            snprintf(err, sizeof(err), "No se pudo montar la ISO porque está demasiado fragmentada en el disco NTFS.\n\nVuelve a copiar la película al disco.");
        else
            snprintf(err, sizeof(err), "No se pudo montar la película.\n\nError: 0x%08X", ret);
        show_ok(err);
        cleanup_ntfs();
        return 3;
    }

    launch_bluray_player();

    cleanup_ntfs();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    free(host_addr);
    return 0;
}
