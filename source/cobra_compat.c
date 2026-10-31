#include "ps3_env.h"

/*
 * Compatibility shim for libcobra builds that declare is_cobra_based()
 * without exporting it. Unlike the old stub, this now reflects the
 * active HEN/Cobra/Mamba syscall8 environment.
 */
int is_cobra_based(void)
{
    ps3_env_info env = ps3_detect_env();
    return ps3_env_has_cobra_api(&env);
}
