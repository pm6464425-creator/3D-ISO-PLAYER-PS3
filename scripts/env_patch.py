from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# movie_only_patch.py has already generated the movie-only source at this point.
include_anchor = '#include "rsxutil.h"\n'
extra = '#include "ps3_env.h"\n#include "mamba_bootstrap.h"\n'
if '#include "mamba_bootstrap.h"' not in s:
    if include_anchor not in s:
        raise SystemExit('rsxutil include anchor not found')
    s = s.replace(include_anchor, include_anchor + extra, 1)

needle = '''    load_font();\n    ensure_internal_folders();\n\n    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }'''
replacement = '''    load_font();\n    ensure_internal_folders();\n\n    ps3_env_info env = ps3_detect_env();\n    if(!ps3_env_has_cobra_api(&env)) {\n        int mr = mamba_bootstrap_if_needed(&env);\n        if(mr < 0 || !ps3_env_has_cobra_api(&env)) {\n            char compat_err[768];\n            snprintf(compat_err,sizeof(compat_err),\n                     "No se pudo activar la capa de compatibilidad.\\n\\nFirmware: %d\\nKernel: %s\\n\\n%s\\n\\nPS3HEN: activa HEN antes de abrir Movie Flow.",\n                     env.firmware_code, ps3_kernel_name(env.kernel), mamba_bootstrap_error(mr));\n            show_ok(compat_err);\n            ioPadEnd();\n            sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n            if(g_font) free(g_font);\n            free(host_addr);\n            return 2;\n        }\n    }\n\n    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }'''
if needle not in s:
    raise SystemExit('main startup anchor not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('compatibility wired: HEN / Cobra / existing Mamba / classic CFW Mamba fallback')
