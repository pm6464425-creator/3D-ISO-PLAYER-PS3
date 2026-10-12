from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# ------------------------------------------------------------
# V22: diagnostico PS2 persistente. Cada etapa crea un archivo
# en /dev_hdd0 para saber exactamente donde se congela.
# ------------------------------------------------------------

anchor='''static int v21_mount_ps2_internal(const Movie &movie)\n{'''
if anchor not in s:
    raise SystemExit('v21_mount_ps2_internal no encontrado')

helper=r'''static void v22_mark_stage(int stage,const char *label,int value)
{
    char path[96];
    snprintf(path,sizeof(path),"/dev_hdd0/FLOWPS3_STAGE%d.txt",stage);
    FILE *fp=fopen(path,"w");
    if(fp) {
        fprintf(fp,"FLOWPS3 V22 PS2 DIAG\nSTAGE=%d\nLABEL=%s\nVALUE=%d\nHEX=0x%08X\n",
                stage,label?label:"",value,(unsigned int)value);
        fflush(fp);
        fclose(fp);
    }

    /* Archivo acumulativo en una ruta muy visible. */
    fp=fopen("/dev_hdd0/FLOWPS3_PS2_DIAG.txt","a");
    if(fp) {
        fprintf(fp,"STAGE %d | %s | %d | 0x%08X\n",
                stage,label?label:"",value,(unsigned int)value);
        fflush(fp);
        fclose(fp);
    }
}

static void v22_clear_stages(void)
{
    unlink("/dev_hdd0/FLOWPS3_PS2_DIAG.txt");
    char path[96];
    for(int i=0;i<=12;i++) {
        snprintf(path,sizeof(path),"/dev_hdd0/FLOWPS3_STAGE%d.txt",i);
        unlink(path);
    }
}

'''
s=s.replace(anchor,helper+anchor,1)

start=s.find('static int v21_mount_ps2_internal(const Movie &movie)')
end=s.find('\n}\n',start)
if start<0 or end<0:
    raise SystemExit('funcion V21 no encontrada')
end+=3

new=r'''static int v22_mount_ps2_internal(const Movie &movie)
{
    v22_mark_stage(3,"ENTER_MOUNT_FUNCTION",0);

    if(v17_ps2_external(movie)) { v22_mark_stage(3,"EXTERNAL_BLOCK",-260); return -260; }
    if(movie.path.find("/dev_hdd0/")!=0) { v22_mark_stage(3,"NOT_INTERNAL",-261); return -261; }

    struct stat st;
    if(stat(movie.path.c_str(),&st)!=0 || st.st_size<=0) {
        v22_mark_stage(4,"STAT_FAIL",-262);
        return -262;
    }
    v22_mark_stage(4,"PATH_OK",(int)(st.st_size & 0x7fffffff));

    char storage[64][MAX_PATH];
    char *files[64];
    memset(storage,0,sizeof(storage));
    memset(files,0,sizeof(files));

    int n=collect_split_files(movie.path,storage,files);
    if(n<=0) { v22_mark_stage(5,"SPLIT_FAIL",n); return -201; }
    if(n>32) n=32;
    v22_mark_stage(5,"FILES_READY",n);

    v22_mark_stage(6,"BEFORE_UMOUNT",0);
    int ret=cobra_umount_disc_image();
    v22_mark_stage(6,"AFTER_UMOUNT",ret);
    usleep(4000);

    v22_mark_stage(7,"BEFORE_FAKE_EJECT",0);
    ret=cobra_send_fake_disc_eject_event();
    v22_mark_stage(7,"AFTER_FAKE_EJECT",ret);
    usleep(20000);

    unlink("/dev_hdd0/classic_ps2");
    unlink("/dev_hdd0/tmp/loadoptical");
    v22_mark_stage(8,"PS2_STATE_CLEAN",0);

    TrackDef track[1];
    memset(track,0,sizeof(track));
    track[0].lba=0;
    track[0].is_audio=0;

    v22_mark_stage(9,"BEFORE_COBRA_MOUNT",n);
    ret=cobra_mount_ps2_disc_image(files,n,track,1);
    v22_mark_stage(10,"AFTER_COBRA_MOUNT",ret);
    if(ret!=0) return ret;

    v22_mark_stage(11,"BEFORE_FAKE_INSERT",0);
    ret=cobra_send_fake_disc_insert_event();
    v22_mark_stage(12,"AFTER_FAKE_INSERT",ret);
    return ret;
}
'''

s=s[:start]+new+s[end:]
s=s.replace('if(g_category==6) return v21_mount_ps2_internal(movie);','if(g_category==6) return v22_mount_ps2_internal(movie);',1)

old=r'''            if(g_category==6) {
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
                else snprintf(ps2err,sizeof(ps2err),"PS2: Cobra rechazo el montaje.\n\nError: 0x%08X",ps2ret);
                show_ok(ps2err);
                wait_buttons_release();
                p_x=x; render_ui(); usleep(16000); continue;
            }
'''
newbranch=r'''            if(g_category==6) {
                /* STAGE 0 ocurre inmediatamente al entrar por X, antes de cualquier otra cosa. */
                v22_clear_stages();
                v22_mark_stage(0,"X_PRESSED_PS2",g_selected);
                render_ui();
                fill_rect(120,620,1040,54,0xDD000000);
                draw_text(150,635,"PS2 DIAG ETAPA 0 - X DETECTADO",1,0xFFFFFFFF,42);
                do_flip();
                usleep(120000);

                close_status();
                v22_mark_stage(1,"STATUS_CLOSED",0);
                render_ui();
                fill_rect(120,620,1040,54,0xDD000000);
                draw_text(150,635,"PS2 DIAG ETAPA 1 - PREPARANDO",1,0xFFFFFFFF,42);
                do_flip();

                wait_buttons_release();
                for(int i=0;i<3;i++){ sysUtilCheckCallback(); render_ui(); usleep(16000); }
                v22_mark_stage(2,"BEFORE_MOUNT_SELECTED",0);
                render_ui();
                fill_rect(120,620,1040,54,0xDD000000);
                draw_text(150,635,"PS2 DIAG ETAPA 2 - ENTRANDO AL MONTADOR",1,0xFFFFFFFF,46);
                do_flip();
                usleep(120000);

                int ps2ret=mount_selected_image(movie);
                if(ps2ret==0) {
                    exit_to_xmb_after_mount();
                }
                char ps2err[512];
                if(ps2ret==-261) snprintf(ps2err,sizeof(ps2err),"PS2: la ruta no esta en /dev_hdd0/.");
                else if(ps2ret==-262) snprintf(ps2err,sizeof(ps2err),"PS2: el ISO no existe o esta vacio.");
                else snprintf(ps2err,sizeof(ps2err),"PS2: error de diagnostico.\n\nCodigo: 0x%08X\nRevisa /dev_hdd0/FLOWPS3_STAGE*.txt",ps2ret);
                show_ok(ps2err);
                wait_buttons_release();
                p_x=x; render_ui(); usleep(16000); continue;
            }
'''
if old not in s:
    raise SystemExit('rama PS2 V21 no encontrada')
s=s.replace(old,newbranch,1)

s=s.replace('"V21"','"V22"')

p.write_text(s)
print('FLOWPS3 V22 diagnostico PS2 por etapas aplicado')
