from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V27 - lanzador de títulos instalados en /dev_hdd0/game.
# V25/V26 usaban el exitspawn genérico. Para un EBOOT NPDRM instalado,
# el firmware dispone de sceNpDrmProcessExitSpawn2, que conserva las
# comprobaciones normales de licencia y realiza el cambio de proceso.

inc='#include <sys/process.h>\n'
if inc not in s:
    raise SystemExit('include sys/process no encontrado')
if '#include <sysmodule/sysmodule.h>' not in s:
    s=s.replace(inc,inc+'#include <sysmodule/sysmodule.h>\n',1)

decl='''\nextern "C" int sceNpDrmProcessExitSpawn2(const void *k_licensee, const char *path, const char *argv[], const char *envp[], unsigned int data, size_t data_size, int prio, unsigned long long flags);\n'''
if 'sceNpDrmProcessExitSpawn2' not in s:
    s=s.replace('#include <sysmodule/sysmodule.h>\n','#include <sysmodule/sysmodule.h>\n'+decl,1)

start=s.find('static int v26_launch_xmb_game(const Movie &movie)')
if start < 0:
    raise SystemExit('launcher V26 no encontrado')
end=s.find('\n}\n',start)
if end < 0:
    raise SystemExit('fin launcher V26 no encontrado')
end += 3
new=r'''static int v27_launch_xmb_game(const Movie &movie)
{
    if(movie.content_type!=2) return -360;
    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";
    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;

    FILE *lf=fopen("/dev_hdd0/FLOWPS3_XMB_LAUNCH.txt","w");
    if(lf){ fprintf(lf,"V27 BEFORE_NPDRM\nPATH=%s\n",eboot.c_str()); fclose(lf); }

    /* Cargar el módulo NP del firmware. DUPLICATE significa que ya estaba
       cargado y también es válido para continuar. */
    s32 npmod=sysModuleLoad(SYSMODULE_SYSUTIL_NP);
    lf=fopen("/dev_hdd0/FLOWPS3_XMB_LAUNCH.txt","a");
    if(lf){ fprintf(lf,"NP_MODULE=0x%08X\n",(unsigned int)npmod); fclose(lf); }
    if(npmod!=SYSMODULE_OK && (u32)npmod!=SYSMODULE_ERR_DUPLICATE) return npmod;

    static unsigned char spawn_data[256] __attribute__((aligned(16)));
    for(unsigned int i=0;i<sizeof(spawn_data);i++) spawn_data[i]=(unsigned char)i;
    const char *spawn_argv[1]={NULL};

    close_status();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);

    int ret=sceNpDrmProcessExitSpawn2(NULL, eboot.c_str(), spawn_argv, NULL,
                                      (unsigned int)(uintptr_t)spawn_data,
                                      sizeof(spawn_data), 1000,
                                      SYS_PROCESS_SPAWN_STACK_SIZE_1M);

    lf=fopen("/dev_hdd0/FLOWPS3_XMB_LAUNCH.txt","a");
    if(lf){ fprintf(lf,"NPDRM_RET=0x%08X\n",ret); fclose(lf); }

    if(ret<0) {
        sysProcessExitSpawn2(eboot.c_str(),spawn_argv,NULL,NULL,0,1000,
                             SYS_PROCESS_SPAWN_STACK_SIZE_1M);
    }

    exit(0);
    return ret;
}
'''
s=s[:start]+new+s[end:]
s=s.replace('v26_launch_xmb_game(movie)','v27_launch_xmb_game(movie)',1)
s=s.replace('"V26"','"V27"')

mp=Path('Makefile')
m=mp.read_text()
needle='$(TOPDIR)/third_party/lib/libcobra.a \\\n'
if needle not in m:
    raise SystemExit('LIBS cobra no encontrado')
if 'libsysutil_np_stub.a' not in m:
    m=m.replace(needle, needle+'               $(TOPDIR)/third_party/lib/libsysutil_np_stub.a \\\n',1)
mp.write_text(m)

p.write_text(s)
print('FLOWPS3 V27 NPDRM XMB launcher aplicado')
