#include <stdint.h>
#include <sys/syscall.h>
#include "ps3_env.h"

#define SC_COBRA_SYSCALL8            8
#define SC8_IS_HEN                    0x1337ULL
#define SC8_HEN_REV                   0x1339ULL
#define SC8_GET_VERSION               0x7000ULL
#define SC8_GET_MAMBA                 0x7FFFULL
#define MAMBA_MAGIC                   0x666

static int sc8_one(uint64_t opcode)
{
    system_call_1(SC_COBRA_SYSCALL8, opcode);
    return_to_user_prog(int);
}

static int sc8_get_version(uint32_t *version)
{
    system_call_2(SC_COBRA_SYSCALL8, SC8_GET_VERSION, (uint64_t)(uint32_t)version);
    return_to_user_prog(int);
}

ps3_env_info ps3_detect_env(void)
{
    ps3_env_info info;
    info.type = PS3_ENV_NONE;
    info.cobra_version = 0;
    info.hen_revision = 0;

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

int ps3_env_has_cobra_api(const ps3_env_info *env)
{
    return env && env->type != PS3_ENV_NONE;
}
