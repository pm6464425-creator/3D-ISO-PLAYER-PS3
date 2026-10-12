from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# Reemplazar el montador PS2 interno de V18 por una secuencia equivalente al flujo
# probado por IRISMAN/Cobra: desmontar -> expulsar -> limpiar estado PS2 -> montar -> insertar.
old=r'''static int v18_mount_ps2_internal(const Movie &movie)
{
    if(v17_ps2_external(movie)) return -260;
    if(movie.path.find("/dev_hdd0/")!=0) return -261;
    char storage[64][MAX_PATH]; char *files[64];
    memset(storage,0,sizeof(storage)); memset(files,0,sizeof(files));
    int n=collect_split_files(movie.path,storage,files); if(n<=0) return -201;
    unlink("/dev_hdd0/classic_ps2");
    unlink("/dev_hdd0/tmp/loadoptical");
    TrackDef track; track.lba=0; track.is_audio=0;
    int ret=cobra_mount_ps2_disc_image(files,n,&track,1);
    if(ret==0) cobra_send_fake_disc_insert_event();
    return ret;
}
'''
new=r'''static int v19_mount_ps2_internal(const Movie &movie)
{
    if(v17_ps2_external(movie)) return -260;
    if(movie.path.find("/dev_hdd0/")!=0) return -261;

    struct stat st;
    if(stat(movie.path.c_str(),&st)!=0 || st.st_size<=0) return -262;

    char storage[64][MAX_PATH];
    char *files[64];
    memset(storage,0,sizeof(storage));
    memset(files,0,sizeof(files));
    int n=collect_split_files(movie.path,storage,files);
    if(n<=0) return -201;

    /* Secuencia usada por managers maduros con Cobra antes de un nuevo montaje. */
    cobra_umount_disc_image();
    usleep(4000);
    cobra_send_fake_disc_eject_event();
    usleep(120000);

    /* Cobra 8.x / PS2 softemu: limpiar marcadores de ejecuciones previas. */
    unlink("/dev_hdd0/classic_ps2");
    unlink("/dev_hdd0/tmp/loadoptical");
    usleep(4000);

    TrackDef track;
    memset(&track,0,sizeof(track));
    track.lba=0;
    track.is_audio=0;

    int ret=cobra_mount_ps2_disc_image(files,n,&track,1);
    if(ret!=0) {
        /* Dejar el lector virtual en estado limpio si Cobra rechaza el ISO. */
        cobra_umount_disc_image();
        return ret;
    }

    usleep(120000);
    ret=cobra_send_fake_disc_insert_event();
    if(ret!=0) {
        cobra_umount_disc_image();
        return ret;
    }
    return 0;
}
'''
if old not in s:
    raise SystemExit('montador PS2 V18 no encontrado')
s=s.replace(old,new,1)

s=s.replace('if(g_category==6) return v18_mount_ps2_internal(movie);',
            'if(g_category==6) return v19_mount_ps2_internal(movie);',1)

# Mensajes PS2 mas especificos para diagnosticar sin congelar deliberadamente.
needle='''                else snprintf(err,sizeof(err),"No se pudo preparar el contenido.\\n\\nError Cobra: 0x%08X",ret);'''
rep='''                else if(ret==-261) snprintf(err,sizeof(err),"PS2: la ruta no esta en el HDD interno.");
                else if(ret==-262) snprintf(err,sizeof(err),"PS2: el ISO interno no existe o tiene tamano 0.");
                else snprintf(err,sizeof(err),"No se pudo montar el juego PS2.\\n\\nError Cobra: 0x%08X",ret);'''
if needle in s:
    s=s.replace(needle,rep,1)

# Etiqueta visible de version.
s=s.replace('draw_text(sw-88,22,"V17",1,SOFT,4);','draw_text(sw-88,22,"V19",1,SOFT,4);')

p.write_text(s)
print('FLOWPS3 V19 PS2 Cobra patch aplicado')
