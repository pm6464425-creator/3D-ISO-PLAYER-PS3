#ifndef MOVIE_FLOW_MAMBA_BOOTSTRAP_H
#define MOVIE_FLOW_MAMBA_BOOTSTRAP_H

#include "ps3_env.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Enable a Cobra-compatible Mamba API on classic CFW that has LV2 peek/poke
 * but no active HEN/Cobra/Mamba. Returns 0 on success; positive if already
 * available; negative on a safely rejected/failed bootstrap.
 */
int mamba_bootstrap_if_needed(ps3_env_info *env);
const char *mamba_bootstrap_error(int code);

#ifdef __cplusplus
}
#endif

#endif
