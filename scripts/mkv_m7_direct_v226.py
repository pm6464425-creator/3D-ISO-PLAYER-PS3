from pathlib import Path

# FLOW V2.26 EMBEDDED MOVIAN M7 NTFS DIRECT EXPERIMENT
# Only replace old MKV handoff: no internal-HDD caching, no external package,
# preserve all UI/RSX/ISO and PS-menu patches.
p=Path("source/main.cpp")
s=p.read_text()
begin=s.find("/* V2.26 VERIFIED SHOWTIME MKV")
end=s.find("static int mount_bd_iso(const Movie &movie)",begin)
if begin<0 or end<0 or begin>end:
    raise SystemExit("MKV source region not found")

mkv=r'''/* FLOW V2.26 EMBEDDED MOVIAN M7 NTFS DIRECT EXPERIMENT
   Bundled official Movian M7 7.0.273 movian.self. ONE PKG, no other titles.
   FLOW lists files with PS3 libntfs, then passes the original USB URI
   directly to the embedded media engine. Never copy an MKV to internal HDD.
   Uses patched M7 PS3 argv URL startup, without legacy disk handoff.
   IMPORTANT: This cannot certify target Movie playback without PS3 hardware. */
#define MKV_ERR_MOVIAN_NOT_FOUND (-25001)
#define MKV_ERR_SPAWN_RETURNED   (-25002)
#define MKV_ERR_PREPARE_FAILED  (-25003)
#define MKV_ERR_NTFS_READ       (-25004)
#define MKV_ERR_HDD_SPACE       (-25005) /* legacy error code, unused */
#define MKV_ERR_HDD_WRITE       (-25006) /* legacy error code, unused */

static bool m7_self_valid(const char *path)
{
    struct stat st;
    if(stat(path,&st)!=0 || st.st_size<8000000) return false;
    FILE *fp=fopen(path,"rb");
    if(!fp) return false;
    u8 head[8]={0};
    size_t n=fread(head,1,sizeof(head),fp);
    fclose(fp);
    return n==8 && head[0]=='S' && head[1]=='C' &&
           head[2]=='E' && head[3]==0 && head[7]==2;
}

static std::string m7_direct_media_url(const Movie &movie)
{
    if(!movie.ntfs) return std::string("file://")+movie.path;
    /* Movian fileaccess::fa_ntfs uses ntfsN:// as the protocol.
       Its libntfs driver then receives the ORIGINAL, full URL. */
    std::string url=movie.path;
    size_t pos=url.find(":/");
    if(pos!=std::string::npos && url.compare(pos,3,"://")!=0)
        url.replace(pos,2,"://");
    return url;
}

static int launch_mkv_in_movian(const Movie &movie)
{
    static const char * const player=
        "/dev_hdd0/game/3DISO0001/USRDIR/flow_player.self";
    if(!m7_self_valid(player)) {
        flow_log("M7_EMBEDDED_NOT_FOUND",player);
        return MKV_ERR_MOVIAN_NOT_FOUND;
    }

    /* The same source file must be visible to FLOW's own NTFS driver.
       This does not copy, remux, transcode or alter the USB movie. */
    if(movie.ntfs) {
        struct stat source;
        if(ps3ntfs_stat(movie.path.c_str(),&source)!=0 || source.st_size<=0) {
            flow_log("M7_USB_SOURCE_NOT_READABLE",movie.path.c_str());
            return MKV_ERR_NTFS_READ;
        }
    } else {
        struct stat source;
        if(stat(movie.path.c_str(),&source)!=0 || source.st_size<=0) {
            flow_log("M7_HDD_SOURCE_NOT_READABLE",movie.path.c_str());
            return MKV_ERR_PREPARE_FAILED;
        }
    }

    const std::string url=m7_direct_media_url(movie);
    if(url.empty() || url.size()>1016 ||
       url.find('\r')!=std::string::npos ||
       url.find('\n')!=std::string::npos) {
        flow_log("M7_MEDIA_URI_INVALID",url.c_str());
        return MKV_ERR_PREPARE_FAILED;
    }

    char detail[1200];
    snprintf(detail,sizeof(detail),"embedded=%s direct_uri=%s",player,url.c_str());
    flow_log("M7_DIRECT_NTFS_START",detail);

    /* PS3 syscall invocation, without new startup imports (getcwd/chdir
       previously caused a black-screen regression).
       argv[0] must remain a valid SELF path for PS3's Movian init.
       The selected file URI is passed in argv[1], for patched M7 versions
       that accept a startup URL. */
    const char *args[]={player,url.c_str(),NULL};
    sysProcessExitSpawn2(player,args,NULL,NULL,0,1200,
                         SYS_PROCESS_SPAWN_STACK_SIZE_1M);

    /* Successful process replacement does not return to FLOW. */
    flow_log("M7_SPAWN_RETURNED","Failed to start embedded M7");
    return MKV_ERR_SPAWN_RETURNED;
}

'''
s=s[:begin]+mkv+s[end:]
# Replace outdated error UI. The old HDD cache errors are now unreachable.
old='''                } else if(ret==MKV_ERR_HDD_SPACE) {
                    show_ok("Espacio insuficiente en el HDD interno.\\n"
                            "La reproduccion MKV desde USB necesita temporalmente\\n"
                            "una copia completa de la pelicula.");
                } else if(ret==MKV_ERR_HDD_WRITE) {
                    show_ok("Error al preparar la copia temporal del MKV.\\n"
                            "Comprueba el espacio libre y FLOW_MOVIE.LOG.");
'''
if s.count(old)!=1:
    raise SystemExit('Outdated HDD error block missing')
s=s.replace(old,'',1)
s=s.replace('show_ok("No se encontro SHOWTIME.SELF valido.\\n\\nInstala el PKG de FLOW con el motor MKV verificado.");',
            'show_ok("No se encontro el Movian M7 integrado en FLOW.\\n\\nReinstala este PKG.");')
s=s.replace('show_ok("FLOW no pudo leer el MKV desde el USB NTFS.\\n"',
            'show_ok("FLOW no pudo verificar el MKV en el USB NTFS.\\n"')
s=s.replace('show_ok("El reproductor Showtime no pudo iniciarse.\\n\\nConsulta FLOW_MOVIE.LOG.");',
            'show_ok("El motor M7 integrado no pudo iniciarse.\\n\\nConsulta FLOW_MOVIE.LOG.");')
for req in ('FLOW V2.26 EMBEDDED MOVIAN M7 NTFS DIRECT EXPERIMENT',
            'M7_DIRECT_NTFS_START','m7_direct_media_url(movie)',
            'sysProcessExitSpawn2(player,args,NULL,NULL,0,1200,',
            'V2.26 TRANSITION BRIGHTNESS FIX',
            'V2.26 PS MENU STATIC FRONT BUFFER',
            'V2.26 REALTIME MOTION PERF'):
    if req not in s: raise SystemExit('MISSING invariants: '+req)
for forbidden in ('mkv_prepare_playback_path(', 'MKV_CACHE/', 'sysFsGetFreeSize(',
                  'mkv_cobra_map_path(', 'MKV_CACHE_READY',
                  'chdir(', 'getcwd('):
    if forbidden in s: raise SystemExit('Forbidden old behavior still present: '+forbidden)
p.write_text(s)
print('M7 direct NTFS one-PKG experiment patched; no HDD-copy path, preserved stable rendering')
