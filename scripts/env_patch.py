from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# movie_only_patch.py has already generated the movie-only source at this point.
include_anchor = '#include "rsxutil.h"\n'
if '#include "ps3_env.h"' not in s:
    if include_anchor not in s:
        raise SystemExit('rsxutil include anchor not found')
    s = s.replace(include_anchor, include_anchor + '#include "ps3_env.h"\n', 1)

needle = '''    load_font();\n    ensure_internal_folders();\n\n    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }'''
replacement = '''    load_font();\n    ensure_internal_folders();\n\n    ps3_env_info env = ps3_detect_env();\n    if(!ps3_env_has_cobra_api(&env)) {\n        show_ok("No se detecto PS3HEN, Cobra ni Mamba activo.\\n\\nEn PS3HEN: activa HEN antes de abrir Movie Flow.\\nEn CFW clasico sin Cobra: el cargador Mamba se integrara en la siguiente capa de compatibilidad.");\n        ioPadEnd();\n        sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n        if(g_font) free(g_font);\n        free(host_addr);\n        return 2;\n    }\n\n    for(int i=0;i<8;i++) { sysUtilCheckCallback(); usleep(100000); }'''
if needle not in s:
    raise SystemExit('main startup anchor not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('runtime environment detection wired: HEN / Cobra / Mamba')
