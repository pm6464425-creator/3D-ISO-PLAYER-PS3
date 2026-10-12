from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V26 - lanzamiento correcto de títulos instalados en XMB.
# V25 usaba sysProcessExitSpawn2: ese wrapper genérico puede finalizar
# FLOWPS3 y devolver al VSH sin arrancar correctamente un juego PS3.
# Aquí cambiamos a sys_game_process_exitspawn2, usado por software PS3.

if 'sys_game_process_exitspawn2' not in s:
    inc='#include "cobra.h"\n'
    if inc not in s:
        raise SystemExit('include cobra no encontrado')
    decl='extern void sys_game_process_exitspawn2(const char *path, const char *argv[], const char *envp[], void *data, unsigned int data_size, int prio, unsigned long long flags);\n'
    s=s.replace(inc,inc+decl,1)

old='''static int v25_launch_xmb_game(const Movie &movie)\n{\n    if(movie.content_type!=2) return -360;\n    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";\n    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;\n\n    close_status();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n    /* El firmware sigue aplicando las comprobaciones NPDRM/licencia normales. */\n    sysProcessExitSpawn2(eboot.c_str(),NULL,NULL,NULL,0,3071,SYS_PROCESS_SPAWN_STACK_SIZE_1M);\n    exit(0);\n    return -362;\n}\n'''
new='''static int v26_launch_xmb_game(const Movie &movie)\n{\n    if(movie.content_type!=2) return -360;\n    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";\n    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;\n\n    close_status();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n\n    /* Sustituye el proceso actual por el juego. No modifica licencias,\n       RAP/RIF, act.dat ni NPDRM: el firmware conserva sus comprobaciones. */\n    sys_game_process_exitspawn2(eboot.c_str(),NULL,NULL,NULL,0,1001,SYS_PROCESS_SPAWN_STACK_SIZE_1M);\n\n    /* Normalmente no retorna. */\n    exit(0);\n    return -362;\n}\n'''
if old not in s:
    raise SystemExit('launcher XMB V25 no encontrado')
s=s.replace(old,new,1)
s=s.replace('v25_launch_xmb_game(movie)','v26_launch_xmb_game(movie)',1)
s=s.replace('"V25"','"V26"')

p.write_text(s)
print('FLOWPS3 V26 XMB launch patch aplicado')
