from pathlib import Path

# FLOW V2.26 SELF-CONTAINED NTFS MKV PLAYBACK
# The bundled 7.0.2 multiMAN Showtime SELF is able to auto-open file:// URLs,
# but its old NTFS handler fails to open some files even from its own browser.
# FLOW already has a working libntfs scanner. For MKV on USB NTFS, copy to one
# local HDD playback cache, verify full byte count, then launch the embedded
# player with a file:// URL. Reuse cached film on subsequent opens.
#
# NOTE: This costs temporary internal HDD space and a first-play transfer.
# It does NOT install/require any external PKG, or alter the UI/RSX/pad code.
p=Path('source/main.cpp')
s=p.read_text()
if 'FLOW V2.26 SELF-CONTAINED NTFS MKV PLAYBACK' not in s:
    # Avoid any new include of ppu-lv2 at startup; needed only for fs free size.
    if '#include <lv2/sysfs.h>' not in s:
        marker='#include <sys/stat.h>\n'
        if s.count(marker)!=1: raise SystemExit('missing stat header')
        s=s.replace(marker,marker+'#include <sys/fs.h>\n#include <fcntl.h>\n',1)

    at='static int launch_mkv_in_movian(const Movie &movie)\n{'
    if s.count(at)!=1:raise SystemExit('MKV launch anchor missing')
    helper=r'''/* FLOW V2.26 SELF-CONTAINED NTFS MKV PLAYBACK
   Store at most ONE completed movie in internal HDD; clean the previous one
   when selecting another. Never pass a libntfs URL to the legacy Showtime
   engine after observing its "No such file" on manual/direct NTFS playback.
   This is an automatic X -> cache -> play flow, not another application. */
#define MKV_ERR_NTFS_READ   (-25004)
#define MKV_ERR_HDD_SPACE   (-25005)
#define MKV_ERR_HDD_WRITE   (-25006)

static int mkv_prepare_playback_path(const Movie &movie, std::string &dst)
{
    if(!movie.ntfs) {
        dst=movie.path;
        return 0;
    }

    struct stat st;
    if(ps3ntfs_stat(movie.path.c_str(),&st)!=0) {
        flow_log("MKV_CACHE_STAT_FAIL",movie.path.c_str());
        return MKV_ERR_NTFS_READ;
    }
    uint64_t expected=(uint64_t)st.st_size;
    if(expected==0) {
        flow_log("MKV_CACHE_EMPTY",movie.path.c_str());
        return MKV_ERR_NTFS_READ;
    }

    const std::string folder="/dev_hdd0/game/3DISO0001/USRDIR/MKV_CACHE";
    const std::string cached=folder+"/PLAYBACK.MKV";
    const std::string partial=folder+"/PLAYBACK.PART";
    const std::string manifest=folder+"/PLAYBACK.KEY";
    mkdir(folder.c_str(),0777);

    char sizebuf[64];
    snprintf(sizebuf,sizeof(sizebuf),"%llu",(unsigned long long)expected);
    const std::string key=movie.path+"\n"+sizebuf+"\n";

    struct stat oldst;
    if(stat(cached.c_str(),&oldst)==0 && (uint64_t)oldst.st_size==expected) {
        FILE *meta=fopen(manifest.c_str(),"rb");
        if(meta) {
            char previous[2048]={0};
            size_t n=fread(previous,1,sizeof(previous)-1,meta);
            fclose(meta);
            if(n==key.size() && memcmp(previous,key.data(),n)==0) {
                flow_log("MKV_CACHE_HIT",cached.c_str());
                dst=cached;
                return 0;
            }
        }
    }

    int in=ps3ntfs_open(movie.path.c_str(),O_RDONLY,0);
    if(in<0) {
        flow_log("MKV_CACHE_OPEN_FAIL",movie.path.c_str());
        return MKV_ERR_NTFS_READ;
    }

    /* Previous completed movie belongs to FLOW; never delete user media. */
    remove(partial.c_str());
    remove(cached.c_str());
    remove(manifest.c_str());

    u32 blockSize=0;
    u64 freeBlocks=0;
    int freeRet=sysFsGetFreeSize("/dev_hdd0",&blockSize,&freeBlocks);
    uint64_t available=(uint64_t)blockSize*(uint64_t)freeBlocks;
    if(freeRet!=0 || available<expected+(uint64_t)(64*1024*1024)) {
        ps3ntfs_close(in);
        flow_log("MKV_CACHE_NO_SPACE","HDD needs film size plus 64 MiB");
        return MKV_ERR_HDD_SPACE;
    }

    FILE *out=fopen(partial.c_str(),"wb");
    if(!out) {
        ps3ntfs_close(in);
        flow_log("MKV_CACHE_OUT_OPEN_FAIL",partial.c_str());
        return MKV_ERR_HDD_WRITE;
    }

    const size_t BUFSIZE=256*1024;
    unsigned char *buf=(unsigned char *)malloc(BUFSIZE);
    if(!buf) {
        fclose(out);
        ps3ntfs_close(in);
        remove(partial.c_str());
        return MKV_ERR_HDD_WRITE;
    }

    show_status("PREPARANDO PELICULA MKV DESDE USB NTFS...\n\n"
                "FLOW copiara temporalmente el archivo al HDD interno.\n"
                "No desconectes el USB durante esta operacion.");

    uint64_t done=0;
    uint64_t heartbeat=0;
    int outcome=0;
    while(done<expected && app_running) {
        size_t want=(size_t)((expected-done)<BUFSIZE?(expected-done):BUFSIZE);
        int n=ps3ntfs_read(in,buf,(int)want);
        if(n<=0) { outcome=MKV_ERR_NTFS_READ; break; }
        if(fwrite(buf,1,(size_t)n,out)!=(size_t)n) {
            outcome=MKV_ERR_HDD_WRITE; break;
        }
        done+=(uint64_t)n;
        heartbeat+=(uint64_t)n;
        if(heartbeat>=4u*1024u*1024u) {
            heartbeat=0;
            sysUtilCheckCallback();
            /* Keep the system overlay responsive WITHOUT alternating stale
               framebuffers or rendering/decoding movie covers. */
            rsx_flip_last_complete();
        }
    }
    if(!app_running) outcome=MKV_ERR_NTFS_READ;
    if(done!=expected && outcome==0) outcome=MKV_ERR_NTFS_READ;
    if(fflush(out)!=0) outcome=MKV_ERR_HDD_WRITE;
    if(fclose(out)!=0) outcome=MKV_ERR_HDD_WRITE;
    ps3ntfs_close(in);
    free(buf);
    close_status();

    if(outcome!=0) {
        remove(partial.c_str());
        char detail[120];
        snprintf(detail,sizeof(detail),"ret=%d copied=%llu expected=%llu",
                 outcome,(unsigned long long)done,(unsigned long long)expected);
        flow_log("MKV_CACHE_TRANSFER_FAIL",detail);
        return outcome;
    }
    if(rename(partial.c_str(),cached.c_str())!=0) {
        remove(partial.c_str());
        flow_log("MKV_CACHE_RENAME_FAIL",cached.c_str());
        return MKV_ERR_HDD_WRITE;
    }

    FILE *meta=fopen(manifest.c_str(),"wb");
    if(meta) {
        fwrite(key.data(),1,key.size(),meta);
        fclose(meta);
    }
    char detail[128];
    snprintf(detail,sizeof(detail),"verified copied %llu bytes",
             (unsigned long long)done);
    flow_log("MKV_CACHE_READY",detail);
    dst=cached;
    return 0;
}

'''
    s=s.replace(at,helper+at,1)

    before='''    const std::string url=movian_url_for_movie(movie);
    if(url.find('\\r')!=std::string::npos || url.find('\\n')!=std::string::npos
       || !showtime_autoplay_file(player,url)) {'''
    after='''    /* FLOW V2.26: NTFS is staged locally to bypass Showtime's broken
       libntfs open path; internal movies are launched without copying. */
    std::string playback_path;
    int cache_status=mkv_prepare_playback_path(movie,playback_path);
    if(cache_status!=0) return cache_status;
    const std::string url=std::string("file://")+playback_path;
    if(url.find('\\r')!=std::string::npos || url.find('\\n')!=std::string::npos
       || !showtime_autoplay_file(player,url)) {'''
    if s.count(before)!=1:raise SystemExit('MKV URL launch source missing')
    s=s.replace(before,after,1)

    before_error='''                } else {
                    show_ok("El reproductor Showtime no pudo iniciarse.\\n\\nConsulta FLOW_MOVIE.LOG.");
                }'''
    new_error='''                } else if(ret==MKV_ERR_NTFS_READ) {
                    show_ok("FLOW no pudo leer el MKV desde el USB NTFS.\\n"
                            "Comprueba el archivo y la conexion USB.");
                } else if(ret==MKV_ERR_HDD_SPACE) {
                    show_ok("Espacio insuficiente en el HDD interno.\\n"
                            "La reproduccion MKV desde USB necesita temporalmente\\n"
                            "una copia completa de la pelicula.");
                } else if(ret==MKV_ERR_HDD_WRITE) {
                    show_ok("Error al preparar la copia temporal del MKV.\\n"
                            "Comprueba el espacio libre y FLOW_MOVIE.LOG.");
                } else {
                    show_ok("El reproductor Showtime no pudo iniciarse.\\n\\nConsulta FLOW_MOVIE.LOG.");
                }'''
    if s.count(before_error)!=1:raise SystemExit('MKV error display anchor missing')
    s=s.replace(before_error,new_error,1)

for marker in ('FLOW V2.26 SELF-CONTAINED NTFS MKV PLAYBACK',
               'V2.26 VERIFIED SHOWTIME MKV','V2.26 MKV SAFE HANDOFF',
               'V2.26 TRANSITION BRIGHTNESS FIX','V2.26 PS MENU STATIC FRONT BUFFER',
               'V2.26 REALTIME MOTION PERF',
               'std::string("file://")+playback_path',
               'MKV_CACHE_READY','rsx_flip_last_complete();'):
    if marker not in s: raise SystemExit('Missing preserved marker '+marker)
assert 'chdir(' not in s and 'getcwd(' not in s
p.write_text(s)
print('SELF-CONTAINED MKV: USB NTFS -> checked HDD playback cache -> embedded Showtime (one X, no extra PKG)')
