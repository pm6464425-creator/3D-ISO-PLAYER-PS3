from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

start=s.find('static int v22_mount_ps2_internal(const Movie &movie)')
end=s.find('\n}\n',start)
if start<0 or end<0:
    raise SystemExit('v22_mount_ps2_internal no encontrado')
end+=3

new=r'''static int v24_mount_ps2_internal(const Movie &movie)
{
    /* IMPORTANTE: no reservar 64*MAX_PATH en el stack del hilo principal.
       En PS3 ese frame puede agotar la pila antes de ejecutar la primera instruccion. */
    v22_mark_stage(3,"ENTER_MOUNT_FUNCTION",0);

    if(v17_ps2_external(movie)) { v22_mark_stage(3,"EXTERNAL_BLOCK",-260); return -260; }
    if(movie.path.find("/dev_hdd0/")!=0) { v22_mark_stage(3,"NOT_INTERNAL",-261); return -261; }

    struct stat st;
    if(stat(movie.path.c_str(),&st)!=0 || st.st_size<=0) {
        v22_mark_stage(4,"STAT_FAIL",-262);
        return -262;
    }
    v22_mark_stage(4,"PATH_OK",(int)(st.st_size & 0x7fffffff));

    char (*storage)[MAX_PATH]=(char (*)[MAX_PATH])memalign(16,64*MAX_PATH);
    char **files=(char**)memalign(16,64*sizeof(char*));
    if(!storage || !files) {
        if(storage) free(storage);
        if(files) free(files);
        v22_mark_stage(5,"ALLOC_FAIL",-280);
        return -280;
    }
    memset(storage,0,64*MAX_PATH);
    memset(files,0,64*sizeof(char*));
    v22_mark_stage(5,"HEAP_READY",0);

    int n=collect_split_files(movie.path,storage,files);
    if(n<=0) {
        v22_mark_stage(5,"SPLIT_FAIL",n);
        free(files); free(storage);
        return -201;
    }
    if(n>32) n=32;
    v22_mark_stage(6,"FILES_READY",n);

    int ret=cobra_umount_disc_image();
    v22_mark_stage(7,"AFTER_UMOUNT",ret);
    usleep(4000);

    ret=cobra_send_fake_disc_eject_event();
    v22_mark_stage(8,"AFTER_FAKE_EJECT",ret);
    usleep(20000);

    unlink("/dev_hdd0/classic_ps2");
    unlink("/dev_hdd0/tmp/loadoptical");
    v22_mark_stage(9,"PS2_STATE_CLEAN",0);

    TrackDef track[1];
    memset(track,0,sizeof(track));
    track[0].lba=0;
    track[0].is_audio=0;

    v22_mark_stage(10,"BEFORE_COBRA_MOUNT",n);
    ret=cobra_mount_ps2_disc_image(files,n,track,1);
    v22_mark_stage(11,"AFTER_COBRA_MOUNT",ret);

    if(ret==0) {
        ret=cobra_send_fake_disc_insert_event();
        v22_mark_stage(12,"AFTER_FAKE_INSERT",ret);
    }

    free(files);
    free(storage);
    return ret;
}
'''

s=s[:start]+new+s[end:]
s=s.replace('v22_mount_ps2_internal(movie)','v24_mount_ps2_internal(movie)')
s=s.replace('"V23"','"V24"')
p.write_text(s)
print('FLOWPS3 V24 stack overflow fix aplicado')
