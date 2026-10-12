from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V26 - correccion del lanzamiento de titulos instalados en XMB.
# Mantiene el wrapper enlazable de PSL1GHT, pero usa los parametros de
# lanzamiento empleados por frontends PS3 maduros: prioridad normal,
# argv terminado en NULL y bloque de spawn de 256 bytes.

old='''static int v25_launch_xmb_game(const Movie &movie)\n{\n    if(movie.content_type!=2) return -360;\n    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";\n    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;\n\n    close_status();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n    /* El firmware sigue aplicando las comprobaciones NPDRM/licencia normales. */\n    sysProcessExitSpawn2(eboot.c_str(),NULL,NULL,NULL,0,3071,SYS_PROCESS_SPAWN_STACK_SIZE_1M);\n    exit(0);\n    return -362;\n}\n'''
new='''static int v26_launch_xmb_game(const Movie &movie)\n{\n    if(movie.content_type!=2) return -360;\n    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";\n    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;\n\n    char spawn_data[256];\n    for(unsigned int i=0;i<sizeof(spawn_data);i++) spawn_data[i]=(char)(i & 0xFF);\n    const char *spawn_argv[]={NULL};\n\n    close_status();\n    ioPadEnd();\n    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);\n\n    /* No modifica licencias ni NPDRM. El firmware conserva sus comprobaciones. */\n    sysProcessExitSpawn2(eboot.c_str(),spawn_argv,NULL,spawn_data,sizeof(spawn_data),1000,SYS_PROCESS_SPAWN_STACK_SIZE_1M);\n    exit(0);\n    return -362;\n}\n'''
if old not in s:
    raise SystemExit('launcher XMB V25 no encontrado')
s=s.replace(old,new,1)
s=s.replace('v25_launch_xmb_game(movie)','v26_launch_xmb_game(movie)',1)
s=s.replace('"V25"','"V26"')

p.write_text(s)
print('FLOWPS3 V26 XMB launch patch aplicado')
