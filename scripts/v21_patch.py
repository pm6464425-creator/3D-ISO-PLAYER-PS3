from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V21: PS2 interno siguiendo el flujo simple/probado de IRISMAN/Cobra,
# pero SIN mantener un msgDialog del sistema abierto mientras se envian eventos de disco.

old_start=s.find('static int v20_mount_ps2_internal(const Movie &movie)')
old_end=s.find('\n}\n', old_start)
if old_start < 0 or old_end < 0:
    raise SystemExit('v20_mount_ps2_internal no encontrado')
old_end += 3

new=r'''static int v21_mount_ps2_internal(const Movie &movie)
{
    if(v17_ps2_external(movie)) return -260;
    if(movie.path.find("/dev_hdd0/")!=0) return -261;

    struct stat st;
    if(stat(movie.path.c_str(),&st)!=0 || st.st_size<=0) return -262;

    char storage[32][MAX_PATH];
    char *files[32];
    memset(storage,0,sizeof(storage));
    memset(files,0,sizeof(files));

    int n=collect_split_files(movie.path,(char (*)[MAX_PATH])storage,(char **)files);
    if(n<=0) return -201;
    if(n>32) n=32; /* Cobra limita PS2 a 32 partes */

    FILE *log=fopen("/dev_hdd0/tmp/FLOWPS3_PS2.log","w");
    if(log){ fprintf(log,"V21 path=%s size=%llu parts=%d\n",movie.path.c_str(),(unsigned long long)st.st_size,n); fclose(log); }

    /* Igual que los managers maduros: el disco debe estar eyectado antes del mount. */
    cobra_umount_disc_image();
    usleep(4000);
    cobra_send_fake_disc_eject_event();
    usleep(20000);

    /* Marcadores usados por Cobra 8.x para PS2. */
    unlink("/dev_hdd0/classic_ps2");
    unlink("/dev_hdd0/tmp/loadoptical");

    TrackDef track[1];
    memset(track,0,sizeof(track));
    track[0].lba=0;
    track[0].is_audio=0;

    log=fopen("/dev_hdd0/tmp/FLOWPS3_PS2.log","a");
    if(log){ fprintf(log,"before cobra_mount_ps2_disc_image\n"); fclose(log); }

    int ret=cobra_mount_ps2_disc_image(files,n,track,1);

    log=fopen("/dev_hdd0/tmp/FLOWPS3_PS2.log","a");
    if(log){ fprintf(log,"after mount ret=%d 0x%08X\n",ret,(unsigned int)ret); fclose(log); }

    if(ret!=0) return ret;

    ret=cobra_send_fake_disc_insert_event();
    log=fopen("/dev_hdd0/tmp/FLOWPS3_PS2.log","a");
    if(log){ fprintf(log,"insert ret=%d 0x%08X\n",ret,(unsigned int)ret); fclose(log); }
    return ret;
}
'''

s=s[:old_start]+new+s[old_end:]
s=s.replace('if(g_category==6) return v20_mount_ps2_internal(movie);','if(g_category==6) return v21_mount_ps2_internal(movie);',1)

# La llamada de montaje PS2 NO debe hacerse con msgDialogOpen2 activo.
# Los eventos fake eject/insert son procesados por VSH y un dialogo SYSUTIL vivo puede
# bloquear el mismo hilo/event loop. PS2 usa una ruta separada y sale al XMB inmediatamente.
needle='''            show_status("Preparando contenido mediante Cobra...\\n\\nNo desconectes el disco USB.");
            int ret=mount_selected_image(movie);'''
rep='''            if(g_category==6) {
                close_status();
                wait_buttons_release();
                /* un par de ciclos SYSUTIL limpios antes de tocar el lector virtual */
                for(int i=0;i<3;i++){ sysUtilCheckCallback(); render_ui(); usleep(16000); }
                int ps2ret=mount_selected_image(movie);
                if(ps2ret==0) {
                    /* IRISMAN/multiMAN vuelven al XMB justo despues del mount exitoso. */
                    exit_to_xmb_after_mount();
                }
                char ps2err[512];
                if(ps2ret==-261) snprintf(ps2err,sizeof(ps2err),"PS2: la ruta no esta en /dev_hdd0/.");
                else if(ps2ret==-262) snprintf(ps2err,sizeof(ps2err),"PS2: el ISO no existe o esta vacio.");
                else snprintf(ps2err,sizeof(ps2err),"PS2: Cobra rechazo el montaje.\\n\\nError: 0x%08X",ps2ret);
                show_ok(ps2err);
                wait_buttons_release();
                p_x=x; render_ui(); usleep(16000); continue;
            }
            show_status("Preparando contenido mediante Cobra...\\n\\nNo desconectes el disco USB.");
            int ret=mount_selected_image(movie);'''
if needle not in s:
    raise SystemExit('bloque show_status/mount no encontrado')
s=s.replace(needle,rep,1)

# Evitar que la etiqueta de V20 quede en la UI.
s=s.replace('"V20"','"V21"')

p.write_text(s)
print('FLOWPS3 V21 PS2 no-dialog mount patch aplicado')
