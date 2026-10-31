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
#define PERMISSION_PATCH_ADDR          0x8000000000003D90ULL
#define PERMISSION_PATCH_VALUE         0x386000014E800020ULL
#define APP_MAMBA_DIR                  "/dev_hdd0/game/3DISO0001/USRDIR/mamba"

static uint64_t lv2_peek64(uint64_t addr)
{
    lv2syscall1(LV2_PEEK_SYSCALL, addr);
    return (uint64_t)p1;
}

static void lv2_poke64_raw(uint64_t addr, uint64_t value)
{
    lv2syscall2(LV2_POKE_SYSCALL, addr, value);
}

static int lv2_write64_verified(uint64_t addr, uint64_t value)
{
    lv2_poke64_raw(addr, value);
    return lv2_peek64(addr) == value ? 0 : -1;
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

static uint64_t syscall_table_for(int fw, ps3_kernel_type kernel)
{
    /* Values are shared with the long-tested webMAN/IRISMAN firmware maps. */
    if(kernel == PS3_KERNEL_CEX) {
        switch(fw) {
            case 421: return 0x800000000035BCA8ULL;
            case 430: case 431: return 0x800000000035DBE0ULL;
            case 440: case 441: return 0x800000000035E260ULL;
            case 446: return 0x800000000035E860ULL;
            case 450: return 0x800000000035F0D0ULL;
            case 453: return 0x800000000035F300ULL;
            case 455: return 0x8000000000362680ULL;
            case 460: case 465: case 466: return 0x8000000000363A18ULL;
            case 470: return 0x8000000000363B60ULL;
            case 475: case 476: case 478: case 480: case 481:
            case 482: case 483: case 484: case 485: case 486: case 487:
            case 488: case 489: case 490: case 491: case 492: case 493:
                return 0x8000000000363BE0ULL;
            default: return 0;
        }
    }

    if(kernel == PS3_KERNEL_DEX) {
        switch(fw) {
            case 421: return 0x800000000037A1B0ULL;
            case 430: case 431: return 0x800000000037C068ULL;
            case 440: case 441: return 0x800000000037C9E8ULL;
            case 446: return 0x800000000037CFE8ULL;
            case 450: return 0x8000000000383658ULL;
            case 453: return 0x8000000000385108ULL;
            case 455: return 0x8000000000388488ULL;
            case 460: case 465: case 466: return 0x800000000038A120ULL;
            case 470: return 0x800000000038A368ULL;
            case 475: case 476: case 478: return 0x800000000038A3E8ULL;
            case 480: case 481: case 482: case 483: case 484: case 485:
            case 486: case 487: case 488: case 489: case 490: case 491:
            case 492: case 493:
                return 0x800000000038A4E8ULL;
            default: return 0;
        }
    }

    /* DEH/DECR Mamba offsets are WIP upstream; never bootstrap them blindly. */
    return 0;
}

static int validate_syscall_table(uint64_t table)
{
    if(!table) return 0;
    uint64_t sc0 = lv2_peek64(table);
    uint64_t sc6 = lv2_peek64(table + (8ULL * LV2_PEEK_SYSCALL));
    uint64_t sc7 = lv2_peek64(table + (8ULL * LV2_POKE_SYSCALL));
    return ((sc0 >> 63) && (sc6 >> 63) && (sc7 >> 63));
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
        if(lv2_write64_verified(MAMBA_LOADER_BASE + (uint64_t)off, q) != 0) {
            free(buf); return -512;
        }
    }
    free(buf);

    /* IRISMAN installs an OPD after the loader and points syscall 1022 to it. */
    uint64_t payload_opd = MAMBA_LOADER_BASE + (uint64_t)fsize + 0x10ULL;
    if(lv2_write64_verified(payload_opd, MAMBA_LOADER_BASE) != 0) return -512;
    lv2_poke64_raw(payload_opd + 8, 0);

    uint64_t entry = syscall_table + (8ULL * MAMBA_LOADER_SYSCALL);
    *old_sc1022 = lv2_peek64(entry);
    if(lv2_write64_verified(entry, payload_opd) != 0) return -513;

    int probe = syscall1022_one(MAMBA_OP_IS_ENABLED);
    if(probe != MAMBA_LOADER_MAGIC && probe != MAMBA_LOADER_MAGIC_BOTH) {
        lv2_poke64_raw(entry, *old_sc1022);
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

    if(current.firmware_code < 421) return -501;
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

    uint64_t syscall_table = syscall_table_for(current.firmware_code, current.kernel);
    if(!validate_syscall_table(syscall_table)) return -504;

    uint64_t old_sc1022 = 0;
    int ret = install_loader_binary(loader_path, syscall_table, &old_sc1022);
    if(ret != 0) return ret;

    uint64_t sc1022_entry = syscall_table + (8ULL * MAMBA_LOADER_SYSCALL);

    /* The same permission patch used by IRISMAN for 4.xx, restored afterwards. */
    uint64_t old_permission = lv2_peek64(PERMISSION_PATCH_ADDR);
    int patched_permission = (lv2_write64_verified(PERMISSION_PATCH_ADDR, PERMISSION_PATCH_VALUE) == 0);

    ret = syscall1022_load(payload_path);

    if(patched_permission) lv2_poke64_raw(PERMISSION_PATCH_ADDR, old_permission);
    lv2_poke64_raw(sc1022_entry, old_sc1022);

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
        case -501: return "CFW clasico anterior a 4.21 requiere backend legado";
        case -502: return "Tipo de kernel CEX/DEX no identificado";
        case -503: return "No existe un payload Mamba exacto para este firmware/kernel";
        case -504: return "CFW sin LV2 peek/poke utilizable o tabla syscall no validada";
        case -508: return "No se pudo abrir el Mamba loader";
        case -509: return "Mamba loader invalido";
        case -510: return "Memoria insuficiente para el Mamba loader";
        case -511: return "No se pudo leer el Mamba loader";
        case -512: return "No se pudo instalar/verificar temporalmente el Mamba loader";
        case -513: return "No se pudo enganchar temporalmente syscall 1022";
        case -514: return "El Mamba loader no respondio correctamente";
        case -515: return "El Mamba payload rechazo la carga";
        case -516: return "Mamba no quedo activo despues de cargarlo";
        default:   return "Error desconocido inicializando Mamba";
    }
}
