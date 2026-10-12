from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V28
# Quita el import NPDRM estático de V27 porque puede impedir que FLOWPS3
# llegue a main() en ciertos CFW/firmwares. Recupera un arranque limpio.
# Para juegos instalados usa el launcher genérico exacto y, si retorna,
# NO cierra FLOWPS3: registra que el firmware devolvió el control.

# Eliminar declaración NPDRM añadida por V27.
s=s.replace('\nextern "C" int sceNpDrmProcessExitSpawn2(const void *k_licensee, const char *path, const char *argv[], const char *envp[], unsigned int data, size_t data_size, int prio, unsigned long long flags);\n','\n')

start=s.find('static int v27_launch_xmb_game(const Movie &movie)')
if start < 0:
    raise SystemExit('launcher V27 no encontrado')
end=s.find('\n}\n',start)
if end < 0:
    raise SystemExit('fin launcher V27 no encontrado')
end += 3

new=r'''static int v28_launch_xmb_game(const Movie &movie)
{
    if(movie.content_type!=2) return -360;
    std::string eboot=movie.path+"/USRDIR/EBOOT.BIN";
    struct stat st; if(stat(eboot.c_str(),&st)!=0) return -361;

    FILE *lf=fopen("/dev_hdd0/FLOWPS3_XMB_LAUNCH.txt","w");
    if(lf){
        fprintf(lf,"V28 BEFORE_EXITSPAWN\nPATH=%s\n",eboot.c_str());
        fclose(lf);
    }

    /* Secuencia equivalente al launcher SELF usado por frontends PS3:
       NULL argv/env/data, prioridad 3071 y stack de 1 MiB. No tocamos
       NPDRM/licencias. Si el spawn funciona, esta llamada no vuelve. */
    sysProcessExitSpawn2(eboot.c_str(),NULL,NULL,NULL,0,3071,
                         SYS_PROCESS_SPAWN_STACK_SIZE_1M);

    /* Si vuelve, el lanzamiento no tomó el control. No cerramos FLOWPS3. */
    lf=fopen("/dev_hdd0/FLOWPS3_XMB_LAUNCH.txt","a");
    if(lf){ fprintf(lf,"EXITSPAWN_RETURNED\n"); fclose(lf); }

    show_status("El firmware devolvio el control a FLOWPS3; el juego no inicio.");
    return -362;
}
'''

s=s[:start]+new+s[end:]
s=s.replace('v27_launch_xmb_game(movie)','v28_launch_xmb_game(movie)',1)
s=s.replace('"V27"','"V28"')

# Eliminar el stub NPDRM de la línea de enlace. Sin referencia estática,
# FLOWPS3 vuelve a depender sólo de las bibliotecas que ya arrancaban bien.
mp=Path('Makefile')
m=mp.read_text()
m=m.replace('               $(TOPDIR)/third_party/lib/libsysutil_np_stub.a \\\n','')
mp.write_text(m)

p.write_text(s)
print('FLOWPS3 V28 startup rescue + XMB diagnostic aplicado')
