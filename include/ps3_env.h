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

typedef struct ps3_env_info {
    ps3_env_type type;
    uint32_t cobra_version;
    int hen_revision;
} ps3_env_info;

/* Detect an already active syscall8 implementation. This function never writes LV1/LV2. */
ps3_env_info ps3_detect_env(void);
const char *ps3_env_name(ps3_env_type type);
int ps3_env_has_cobra_api(const ps3_env_info *env);

#ifdef __cplusplus
}
#endif

#endif
