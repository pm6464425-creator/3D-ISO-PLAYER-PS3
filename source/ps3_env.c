#include <stdint.h>
#include <string.h>
#include <ppu-lv2.h>
#include "ps3_env.h"

#define SC_COBRA_SYSCALL8            8
#define SC_GET_PLATFORM_INFO          387
#define SC_GET_CONSOLE_TYPE           985
#define SC8_IS_HEN                    0x1337ULL
#define SC8_HEN_REV                   0x1339ULL
#define SC8_GET_VERSION               0x7000ULL
#define SC8_GET_MAMBA                 0x7FFFULL
#define MAMBA_MAGIC                   0x666

static int sc8_one(uint64_t opcode)
{
    lv2syscall1(SC_COBRA_SYSCALL8, opcode);
    return_to_user_prog(int);
}

static int sc8_get_version(uint32_t *version)
{
    lv2syscall2(SC_COBRA_SYSCALL8, SC8_GET_VERSION, (uint64_t)(uintptr_t)version);
    return_to_user_prog(int);
}

int ps3_get_firmware_code(void)
{
    /* sys_sm_get_system_info returns bytes like 03 05 50 for firmware 3.55. */
    uint8_t platform[0x20] __attribute__((aligned(16)));
    memset(platform, 0, sizeof(platform));
    lv2syscall1(SC_GET_PLATFORM_INFO, (uint64_t)(uintptr_t)platform);
    if((int)p1 != 0) return 0;

    int major = platform[0] & 0x0F;
    int tens  = platform[1] & 0x0F;
    int ones  = (platform[2] >> 4) & 0x0F;
    if(major < 3 || major > 9 || tens > 9 || ones > 9) return 0;
    return major * 100 + tens * 10 + ones;
}

ps3_kernel_type ps3_get_kernel_type(void)
{
    uint64_t type = 0;
    lv2syscall1(SC_GET_CONSOLE_TYPE, (uint64_t)(uintptr_t)&type);
    if((int)p1 != 0) return PS3_KERNEL_UNKNOWN;

    /* GameOS reports 1=CEX, 2=DEH and 3=DEX. PEX/D-PEX exposes the active kernel. */
    if(type == 1) return PS3_KERNEL_CEX;
    if(type == 2) return PS3_KERNEL_DEH;
    if(type == 3) return PS3_KERNEL_DEX;
    return PS3_KERNEL_UNKNOWN;
}

ps3_env_info ps3_detect_env(void)
{
    ps3_env_info info;
    info.type = PS3_ENV_NONE;
    info.cobra_version = 0;
    info.hen_revision = 0;
    info.firmware_code = ps3_get_firmware_code();
    info.kernel = ps3_get_kernel_type();

    /* PS3HEN identifies itself with syscall8 opcode 0x1337. */
    if(sc8_one(SC8_IS_HEN) == 0x1337) {
        info.type = PS3_ENV_HEN;
        info.hen_revision = sc8_one(SC8_HEN_REV);
        (void)sc8_get_version(&info.cobra_version);
        return info;
    }

    /* Mamba keeps a Cobra-compatible syscall8 and returns 0x666 here. */
    if(sc8_one(SC8_GET_MAMBA) == MAMBA_MAGIC) {
        info.type = PS3_ENV_MAMBA;
        (void)sc8_get_version(&info.cobra_version);
        return info;
    }

    /* Cobra proper answers GET_VERSION and writes a non-zero version. */
    if(sc8_get_version(&info.cobra_version) == 0 && info.cobra_version != 0) {
        info.type = PS3_ENV_COBRA;
        return info;
    }

    info.cobra_version = 0;
    return info;
}

const char *ps3_env_name(ps3_env_type type)
{
    switch(type) {
        case PS3_ENV_HEN:   return "PS3HEN";
        case PS3_ENV_COBRA: return "CFW COBRA";
        case PS3_ENV_MAMBA: return "CFW MAMBA";
        default:            return "SIN COBRA/HEN/MAMBA";
    }
}

const char *ps3_kernel_name(ps3_kernel_type type)
{
    switch(type) {
        case PS3_KERNEL_CEX: return "CEX";
        case PS3_KERNEL_DEH: return "DEH";
        case PS3_KERNEL_DEX: return "DEX";
        default:             return "UNKNOWN";
    }
}

int ps3_env_has_cobra_api(const ps3_env_info *env)
{
    return env && env->type != PS3_ENV_NONE;
}
