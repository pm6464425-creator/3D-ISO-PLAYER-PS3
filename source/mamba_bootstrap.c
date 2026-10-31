#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <ppu-lv2.h>

#include "mamba_bootstrap.h"

#define LV2_PEEK_SYSCALL               6
#define LV2_POKE_SYSCALL               7
#define MAMBA_LOADER_BASE              0x80000000007F0000ULL
#define MAMBA_LOADER_SYSCALL           1022
#define MAMBA_OP_IS_ENABLED            0x7750ULL
#define MAMBA_OP_LOAD                  0x7755ULL
#define MAMBA_LOADER_MAGIC             0x222
#define MAMBA_LOADER_MAGIC_BOTH        0x333
#define SYSCALL_TABLE_SIGNATURE        0x3235352E3235352EULL
#define PERMISSION_PATCH_ADDR          0x8000000000003D90ULL
#define PERMISSION_PATCH_VALUE         0x386000014E800020ULL
#define APP_MAMBA_DIR                  "/dev_hdd0/game/3DISO0001/USRDIR/mamba"

static uint64_t lv2_peek64(uint64_t addr)
{
    lv2syscall1(LV2_PEEK_SYSCALL, addr);
    return (uint64_t)p1;
}

static int lv2_poke64(uint64_t addr, uint64_t value)
{
    lv2syscall2(LV2_POKE_SYSCALL, addr, value);
    return_to_user_prog(int);
}

static int syscall1022_one(uint64_t opcode)
{
    lv2syscall1(MAMBA_LOADER_SYSCALL, opcode);
    return_to_user_prog(int);
}

static int syscall1022_load(const char *path)
{
    lv2syscall2(MAMBA_LOADER_SYSCALL, MAMBA_OP_LOAD, (uint64_t)(uintptr_t)path);
    return_to_user_prog(int);
}

static int file_exists_nonzero(const char *path)
{
    struct stat st;
    return path && stat(path, &st) == 0 && st.st_size > 0;
}

static char kernel_suffix(ps3_kernel_type kernel)
{
    if(kernel == PS3_KERNEL_CEX) return 'C';
    if(kernel == PS3_KERNEL_DEX) return 'D';
    if(kernel == PS3_KERNEL_DEH) return 'E';
    return 0;
}

static uint64_t find_syscall_table(ps3_kernel_type kernel)
{
    /*
     * The classic syscall tables from 3.55 onward live in this window.
     * Search the same "255.255." marker used by webMAN rather than tying
     * Movie Flow to one hard-coded table per firmware.
     */
    const uint64_t start = 0x8000000000340000ULL;
    const uint64_t end   = 0x8000000000400000ULL;
    const uint64_t delta = (kernel == PS3_KERNEL_CEX) ? 0x1220ULL : 0x1228ULL;

    /* Quick sanity check: on OFW/disabled syscalls SC6 returns a small error. */
    uint64_t sanity = lv2_peek64(start);
    if((sanity >> 32) == 0) return 0;

    for(uint64_t addr = start; addr < end; addr += 4) {
        if(lv2_peek64(addr) == SYSCALL_TABLE_SIGNATURE) {
            uint64_t table = addr + delta;
            uint64_t sc0 = lv2_peek64(table);
            uint64_t sc6 = lv2_peek64(table + (8ULL * LV2_PEEK_SYSCALL));
            if((sc0 >> 63) && (sc6 >> 63)) return table;
        }
    }
    return 0;
}

static uint64_t pack_be64(const uint8_t *p, size_t count)
{
    uint64_t v = 0;
    for(size_t i=0; i<8; ++i) {
        v <<= 8;
        if(i < count) v |= p[i];
    }
    return v;
}

static int install_loader_binary(const char *loader_path, uint64_t syscall_table, uint64_t *old_sc1022)
{
    FILE *f = fopen(loader_path, "rb");
    if(!f) return -508;

    if(fseek(f, 0, SEEK_END) != 0) { fclose(f); return -508; }
    long fsize = ftell(f);
    if(fsize < 64 || fsize > 0xE000 || (fsize & 7)) { fclose(f); return -509; }
    rewind(f);

    uint8_t *buf = (uint8_t*)malloc((size_t)fsize);
    if(!buf) { fclose(f); return -510; }
    if(fread(buf, 1, (size_t)fsize, f) != (size_t)fsize) {
        free(buf); fclose(f); return -511;
    }
    fclose(f);

    for(long off=0; off<fsize; off+=8) {
        uint64_t q = pack_be64(buf + off, 8);
        if(lv2_poke64(MAMBA_LOADER_BASE + (uint64_t)off, q) != 0) {
            free(buf); return -512;
        }
    }
    free(buf);

    /* IRISMAN installs an OPD after the loader and points syscall 1022 to it. */
    uint64_t payload_opd = MAMBA_LOADER_BASE + (uint64_t)fsize + 0x10ULL;
    if(lv2_poke64(payload_opd, MAMBA_LOADER_BASE) != 0) return -512;
    (void)lv2_poke64(payload_opd + 8, 0);

    uint64_t entry = syscall_table + (8ULL * MAMBA_LOADER_SYSCALL);
    *old_sc1022 = lv2_peek64(entry);
    if(lv2_poke64(entry, payload_opd) != 0) return -513;
    if(lv2_peek64(entry) != payload_opd) {
        (void)lv2_poke64(entry, *old_sc1022);
        return -513;
    }

    int probe = syscall1022_one(MAMBA_OP_IS_ENABLED);
    if(probe != MAMBA_LOADER_MAGIC && probe != MAMBA_LOADER_MAGIC_BOTH) {
        (void)lv2_poke64(entry, *old_sc1022);
        return -514;
    }
    return 0;
}

int mamba_bootstrap_if_needed(ps3_env_info *env)
{
    ps3_env_info current = ps3_detect_env();
    if(ps3_env_has_cobra_api(&current)) {
        if(env) *env = current;
        return 1;
    }

    if(current.firmware_code < 355) return -501;
    char suffix = kernel_suffix(current.kernel);
    if(!suffix) return -502;

    char loader_path[256];
    char payload_path[256];
    snprintf(loader_path, sizeof(loader_path), "%s/mamba_loader_%03d%c.bin",
             APP_MAMBA_DIR, current.firmware_code, suffix);
    snprintf(payload_path, sizeof(payload_path), "%s/mamba_%03d%c.bin",
             APP_MAMBA_DIR, current.firmware_code, suffix);

    /* Never guess offsets or substitute another firmware's payload. */
    if(!file_exists_nonzero(loader_path) || !file_exists_nonzero(payload_path)) return -503;

    uint64_t syscall_table = find_syscall_table(current.kernel);
    if(!syscall_table) return -504;

    uint64_t old_sc1022 = 0;
    int ret = install_loader_binary(loader_path, syscall_table, &old_sc1022);
    if(ret != 0) return ret;

    uint64_t sc1022_entry = syscall_table + (8ULL * MAMBA_LOADER_SYSCALL);

    /* The same permission patch used by IRISMAN for 4.xx, restored afterwards. */
    uint64_t old_permission = 0;
    int patched_permission = 0;
    if(current.firmware_code >= 400) {
        old_permission = lv2_peek64(PERMISSION_PATCH_ADDR);
        if(lv2_poke64(PERMISSION_PATCH_ADDR, PERMISSION_PATCH_VALUE) == 0)
            patched_permission = 1;
    }

    ret = syscall1022_load(payload_path);

    if(patched_permission) (void)lv2_poke64(PERMISSION_PATCH_ADDR, old_permission);
    (void)lv2_poke64(sc1022_entry, old_sc1022);

    if(ret != 0) return -515;

    usleep(150000);
    current = ps3_detect_env();
    if(current.type != PS3_ENV_MAMBA && current.type != PS3_ENV_COBRA) return -516;

    if(env) *env = current;
    return 0;
}

const char *mamba_bootstrap_error(int code)
{
    switch(code) {
        case -501: return "Firmware demasiado antiguo o no identificable";
        case -502: return "Tipo de kernel CEX/DEX/DEH no identificado";
        case -503: return "No existe un payload Mamba exacto para este firmware/kernel";
        case -504: return "CFW sin acceso LV2 peek/poke o tabla syscall no localizada";
        case -508: return "No se pudo abrir el Mamba loader";
        case -509: return "Mamba loader invalido";
        case -510: return "Memoria insuficiente para el Mamba loader";
        case -511: return "No se pudo leer el Mamba loader";
        case -512: return "No se pudo instalar temporalmente el Mamba loader";
        case -513: return "No se pudo enganchar temporalmente syscall 1022";
        case -514: return "El Mamba loader no respondio correctamente";
        case -515: return "El Mamba payload rechazo la carga";
        case -516: return "Mamba no quedo activo despues de cargarlo";
        default:   return "Error desconocido inicializando Mamba";
    }
}
