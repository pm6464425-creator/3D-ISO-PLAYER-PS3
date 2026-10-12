from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# Usar syscall8 PS2 directamente, evitando el wrapper precompilado de libcobra para esta ruta.
s=s.replace('#include <ppu-types.h>','#include <ppu-types.h>\n#include <ppu-lv2.h>',1)

old=r'''static int v19_mount_ps2_internal(const Movie &movie)
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

new=r'''typedef struct {
    uint8_t reserved;
    uint8_t adr_control;
    uint8_t track_number;
    uint8_t reserved2;
    uint32_t track_start_addr;
} __attribute__((packed)) FlowScsiTrackDescriptor;

static void v20_ps2_log(const char *stage,int value)
{
    FILE *fp=fopen("/dev_hdd0/tmp/FLOWPS3_PS2.log","a");
    if(fp){ fprintf(fp,"%s : %d (0x%08X)\n",stage,value,(unsigned int)value); fclose(fp); }
}

static int v20_sys_mount_ps2(char *files[],int num)
{
    if(!files || num<=0) return -270;

    uint32_t files32[64];
    memset(files32,0,sizeof(files32));
    for(int i=0;i<num && i<64;i++) files32[i]=(uint32_t)(uint64_t)files[i];

    FlowScsiTrackDescriptor track;
    memset(&track,0,sizeof(track));
    track.adr_control=0x14;      /* data track */
    track.track_number=1;
    track.track_start_addr=0;

    /* Cobra SYSCALL8_OPCODE_MOUNT_PS2_DISCFILE = 0x7028 */
    lv2syscall5(8,0x7028,(uint64_t)num,(uint64_t)files32,(uint64_t)1,(uint64_t)&track);
    return_to_user_prog(int);
}

static int v20_mount_ps2_internal(const Movie &movie)
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

    int emu=cobra_get_ps2_emu_type();
    v20_ps2_log("emu_type",emu);
    if(emu<PS2_EMU_HW || emu>PS2_EMU_SW) return -263;

    v20_ps2_log("before_umount",0);
    int ret=cobra_umount_disc_image();
    v20_ps2_log("after_umount",ret);
    usleep(4000);

    v20_ps2_log("before_eject",0);
    ret=cobra_send_fake_disc_eject_event();
    v20_ps2_log("after_eject",ret);
    usleep(120000);

    unlink("/dev_hdd0/classic_ps2");
    unlink("/dev_hdd0/tmp/loadoptical");
    usleep(4000);

    v20_ps2_log("before_mount_syscall",n);
    ret=v20_sys_mount_ps2(files,n);
    v20_ps2_log("after_mount_syscall",ret);
    if(ret!=0) {
        cobra_umount_disc_image();
        return ret;
    }

    usleep(120000);
    v20_ps2_log("before_insert",0);
    ret=cobra_send_fake_disc_insert_event();
    v20_ps2_log("after_insert",ret);
    if(ret!=0) {
        cobra_umount_disc_image();
        return ret;
    }

    v20_ps2_log("mount_complete",0);
    return 0;
}
'''

if old not in s:
    raise SystemExit('montador PS2 V19 no encontrado')
s=s.replace(old,new,1)
s=s.replace('if(g_category==6) return v19_mount_ps2_internal(movie);','if(g_category==6) return v20_mount_ps2_internal(movie);',1)

# Mostrar tipo de emulador PS2 en Información para validar hardware/softemu.
needle='''    snprintf(info,sizeof(info),"INFORMACION\\n\\nTitulo: %s\\nPlataforma: %s\\nOrigen: %s\\nTitle ID: %s\\nTipo: %s\\nTamano: %s\\nRuta:\\n%s",'''
if needle in s:
    rep='''    int ps2emu=(g_category==6)?cobra_get_ps2_emu_type():-1;\n    const char *ps2txt=(ps2emu==PS2_EMU_HW)?"HW":(ps2emu==PS2_EMU_GX)?"GX":(ps2emu==PS2_EMU_SW)?"SW":"N/A";\n    snprintf(info,sizeof(info),"INFORMACION\\n\\nTitulo: %s\\nPlataforma: %s\\nOrigen: %s\\nTitle ID: %s\\nTipo: %s\\nTamano: %s\\nPS2 EMU: %s\\nRuta:\\n%s",'''
    s=s.replace(needle,rep,1)
    s=s.replace('m.bytes?sz:"No calculado",m.path.c_str());','m.bytes?sz:"No calculado",ps2txt,m.path.c_str());',1)

# Mensaje adicional si la detección PS2 falla.
needle='''                else if(ret==-262) snprintf(err,sizeof(err),"PS2: el ISO interno no existe o tiene tamano 0.");'''
if needle in s:
    s=s.replace(needle,needle+'\n                else if(ret==-263) snprintf(err,sizeof(err),"PS2: Cobra no pudo determinar el tipo de emulador PS2 de esta consola.");',1)

# Etiqueta visible de versión.
s=s.replace('"V19"','"V20"')

p.write_text(s)
print('FLOWPS3 V20 PS2 direct-syscall patch aplicado')
