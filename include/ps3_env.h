#ifndef MOVIE_FLOW_PS3_ENV_H
#define MOVIE_FLOW_PS3_ENV_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum ps3_env_type {
    PS3_ENV_NONE = 0,
    PS3_ENV_HEN,
    PS3_ENV_COBRA,
    PS3_ENV_MAMBA
} ps3_env_type;

typedef enum ps3_kernel_type {
    PS3_KERNEL_UNKNOWN = 0,
    PS3_KERNEL_CEX,
    PS3_KERNEL_DEH,
    PS3_KERNEL_DEX
} ps3_kernel_type;

typedef struct ps3_env_info {
    ps3_env_type type;
    uint32_t cobra_version;
    int hen_revision;
    int firmware_code;      /* 493 means firmware 4.93 */
    ps3_kernel_type kernel;
} ps3_env_info;

/* Detect platform and an already active syscall8 implementation. Read-only. */
ps3_env_info ps3_detect_env(void);
const char *ps3_env_name(ps3_env_type type);
const char *ps3_kernel_name(ps3_kernel_type type);
int ps3_env_has_cobra_api(const ps3_env_info *env);
int ps3_get_firmware_code(void);
ps3_kernel_type ps3_get_kernel_type(void);

#ifdef __cplusplus
}
#endif

#endif
