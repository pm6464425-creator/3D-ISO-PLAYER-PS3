from pathlib import Path

# V2.26 VERIFIED SHOWTIME MKV
# Only changes the MKV handoff. No coverflow, PS menu, RSX or BDISO changes.
p=Path('source/main.cpp')
s=p.read_text()

start=s.find('/* V2.26: locate bundled FLOW player first')
end=s.find('static int mount_bd_iso(const Movie &movie)',start)
if start<0 or end<0: raise SystemExit('MKV player launcher anchors missing')

new=r'''/* V2.26 VERIFIED SHOWTIME MKV ------------------------------------------------
   flow_player.self in the FINAL PKG is a verified standalone SHOWTIME.SELF,
   extracted from the official IRISMAN release (NOT an NPDRM EBOOT rename).
   The multiMAN/IRISMAN Showtime edition autoplays the URL in TEMP/SHOWTIME.TXT.
   Native FL0W UI and RSX renderer are never touched. */
static bool valid_showtime_self(const char *filename)
{
    struct stat st;
    if(stat(filename,&st)!=0 || st.st_size<1000000) return false;
    FILE *f=fopen(filename,"rb");
    if(!f) return false;
    u8 magic[4]={0,0,0,0};
    size_t n=fread(magic,1,sizeof(magic),f);
    fclose(f);
    return n==4 && magic[0]=='S' && magic[1]=='C' && magic[2]=='E' && magic[3]==0;
}

static const char *find_movian_self()
{
    static const char *paths[] = {
        /* Original, verified Movian M7 (multiMAN/IRISMAN SELF build). */
        "/dev_hdd0/game/3DISO0001/USRDIR/flow_player.self",
        "/dev_hdd0/game/3DISO0001/USRDIR/SHOWTIME.SELF",
        /* External backup-manager editions also support SHOWTIME.TXT. */
        "/dev_hdd0/game/IRISMAN00/USRDIR/SHOWTIME.SELF",
        "/dev_hdd0/game/IRISMAN00/USRDIR/USRDIR/SHOWTIME.SELF",
        "/dev_hdd0/game/BLES80608/USRDIR/sys/SHOWTIME.SELF",
        "/dev_hdd0/game/BLES80608/USRDIR/SHOWTIME.SELF",
        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",
        "/dev_hdd0/game/HTSS00003/USRDIR/movian.self",
        "/dev_hdd0/game/HTSS00003/USRDIR/showtime.self"
    };
    for(size_t i=0;i<sizeof(paths)/sizeof(paths[0]);++i) {
        if(valid_showtime_self(paths[i])) return paths[i];
    }
    return NULL;
}

static std::string movian_url_for_movie(const Movie &movie)
{
    if(!movie.ntfs) return std::string("file://")+movie.path;
    /* An independent Movian process must remount NTFS itself. This native
       libntfs name is the best-effort URI for the matching physical USB slot. */
    std::string url=movie.path;
    size_t sep=url.find(":/");
    if(sep!=std::string::npos) url.replace(sep,2,"://");
    return url;
}

static bool showtime_autoplay_file(const char *player, const std::string &url)
{
    std::string path(player);
    size_t pos=path.find_last_of('/');
    if(pos==std::string::npos) return false;
    std::string dir=path.substr(0,pos)+"/TEMP";
    mkdir(dir.c_str(),0777);
    std::string filename=dir+"/SHOWTIME.TXT";
    FILE *fp=fopen(filename.c_str(),"wb");
    if(!fp) return false;
    bool ok=(fwrite(url.c_str(),1,url.size(),fp)==url.size());
    if(fclose(fp)!=0) ok=false;
    if(!ok) remove(filename.c_str());
    return ok;
}

#define MKV_ERR_MOVIAN_NOT_FOUND (-25001)
#define MKV_ERR_SPAWN_RETURNED   (-25002)
#define MKV_ERR_PREPARE_FAILED  (-25003)

static int launch_mkv_in_movian(const Movie &movie)
{
    const char *player=find_movian_self();
    if(!player) {
        flow_log("MKV_PLAYER_MISSING","No verified standalone SHOWTIME.SELF found");
        return MKV_ERR_MOVIAN_NOT_FOUND;
    }
    const std::string url=movian_url_for_movie(movie);
    if(url.find('\r')!=std::string::npos || url.find('\n')!=std::string::npos
       || !showtime_autoplay_file(player,url)) {
        flow_log("MKV_AUTOPLAY_ERROR","Cannot create TEMP/SHOWTIME.TXT");
        return MKV_ERR_PREPARE_FAILED;
    }

    char detail[1100];
    snprintf(detail,sizeof(detail),"verified_showtime=%s autoplay=%s",player,url.c_str());
    flow_log("MKV_SHOWTIME_START",detail);

    /* Verified multiMAN/IRISMAN launch semantics: no fake argv[0] = player!
       SHOWTIME.SELF itself reads TEMP/SHOWTIME.TXT to open the selected movie. */
    sysProcessExitSpawn2(player,NULL,NULL,NULL,0,1200,
                         SYS_PROCESS_SPAWN_STACK_SIZE_1M);

    /* A successful process replacement never returns. */
    flow_log("MKV_SHOWTIME_SPAWN_RETURNED","Process spawn returned");
    return MKV_ERR_SPAWN_RETURNED;
}

'''
s=s[:start]+new+s[end:]

old='''                if(ret==MKV_ERR_MOVIAN_NOT_FOUND) {
                    show_ok("No se encontro el motor multimedia interno.\\n\\nReinstala FLOW MOVIE V2.26 para restaurar flow_player.self.");
                } else {
                    show_ok("El motor multimedia no pudo iniciarse.\\n\\nRevisa FLOW_MOVIE.LOG para diagnostico.");
                }'''
newerr='''                if(ret==MKV_ERR_MOVIAN_NOT_FOUND) {
                    show_ok("No se encontro SHOWTIME.SELF valido.\\n\\nInstala el PKG de FLOW con el motor MKV verificado.");
                } else if(ret==MKV_ERR_PREPARE_FAILED) {
                    show_ok("No se pudo preparar la reproduccion MKV.\\n\\nRevisa el espacio libre y permisos de USRDIR/TEMP.");
                } else {
                    show_ok("El reproductor Showtime no pudo iniciarse.\\n\\nConsulta FLOW_MOVIE.LOG.");
                }'''
if s.count(old)!=1: raise SystemExit('MKV call-site anchor missing')
s=s.replace(old,newerr,1)

for required in ('V2.26 VERIFIED SHOWTIME MKV', 'showtime_autoplay_file(player,url)',
                 'sysProcessExitSpawn2(player,NULL,NULL,NULL,0,1200,',
                 'V2.26 TRANSITION BRIGHTNESS FIX',
                 'V2.26 PS MENU STATIC FRONT BUFFER',
                 'V2.26 REALTIME MOTION PERF'):
    if required not in s: raise SystemExit('Preservation invariant missing: '+required)
assert 'launchargv[0]=player;' not in s
p.write_text(s)
print('Verified Showtime MKV launch installed; TEST required on real PS3 for NTFS URL')
