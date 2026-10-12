from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V26 - lanzamiento correcto de títulos instalados en XMB.
# sysProcessExitSpawn2 es el wrapper de proceso genérico y en una aplicación
# homebrew puede simplemente terminar FLOWPS3 y devolver el control al VSH.
# Los juegos PS3 usan sys_game_process_exitspawn2 (sysPrxForUser).

anchor='extern "C" {\n#include "cobra.h"\n}\n'
if anchor not in s:
    raise SystemExit('bloque cobra no encontrado')
if 'sys_game_process_exitspawn2' not in s:
    decl='''extern "C" void sys_game_process_exitspawn2(const char *path, const char *argv[], const char *envp[], void *data, unsigned int data_size, int prio, unsigned long long flags);\n'''
    s=s.replace(anchor,anchor+decl,1)

old='''static int v25_launch_xmb_game(const Movie &movie)\n{\n    if(movie.content_type!=2) return -360;\n    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";\n    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;\n\n    close_status();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n    /* El firmware sigue aplicando las comprobaciones NPDRM/licencia normales. */\n    sysProcessExitSpawn2(eboot.c_str(),NULL,NULL,NULL,0,3071,SYS_PROCESS_SPAWN_STACK_SIZE_1M);\n    exit(0);\n    return -362;\n}\n'''
new='''static int v26_launch_xmb_game(const Movie &movie)\n{\n    if(movie.content_type!=2) return -360;\n    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";\n    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;\n\n    close_status();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n\n    /* Ruta de lanzamiento usada por software PS3 para sustituir el proceso\n       actual por el juego. No modifica RAP, RIF, act.dat ni NPDRM: las\n       comprobaciones normales del firmware siguen activas. */\n    sys_game_process_exitspawn2(eboot.c_str(),NULL,NULL,NULL,0,1001,SYS_PROCESS_SPAWN_STACK_SIZE_1M);\n\n    /* Normalmente no retorna. Si el firmware rechaza el título, terminar\n       limpiamente para no dejar FLOWPS3 bloqueado. */\n    exit(0);\n    return -362;\n}\n'''
if old not in s:
    raise SystemExit('launcher XMB V25 no encontrado')
s=s.replace(old,new,1)
s=s.replace('v25_launch_xmb_game(movie)','v26_launch_xmb_game(movie)',1)
s=s.replace('"V25"','"V26"')

p.write_text(s)
print('FLOWPS3 V26 XMB launch patch aplicado')
