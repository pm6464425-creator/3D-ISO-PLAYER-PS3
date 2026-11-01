from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.25 MKV PLAYBACK
# Keep V2.22 RSX stability, V2.23 hotplug and V2.24 pad fixes untouched.
# Replace the old MKV placeholder dialog with a real launch into Movian.

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.24 INPUT FIX");',
            'flow_log("SESSION_START","FLOW MOVIE V2.25 MKV MOVIAN");',1)

# sysProcessExitSpawn2 + spawn stack constant
if '#include <sys/process.h>' not in s:
    anchor='#include <sys/time.h>\n'
    if anchor not in s:
        raise SystemExit('sys/time include anchor not found')
    s=s.replace(anchor,anchor+'#include <sys/process.h>\n',1)

# Insert the MKV launcher immediately before the existing ISO mount routine.
anchor='''static int mount_bd_iso(const Movie &movie)\n{'''
helper=r'''/* V2.25: locate an installed Movian/Showtime plain SELF.  Legacy Movian
   uses HTSS00003; newer Movian Next uses HTSS00004.  sysProcessExitSpawn2
   needs a plain SELF, not an NPDRM EBOOT.BIN. */
static const char *find_movian_self()
{
    static const char *paths[] = {
        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",
        "/dev_hdd0/game/HTSS00004/USRDIR/showtime.self",
        "/dev_hdd0/game/HTSS00003/USRDIR/movian.self",
        "/dev_hdd0/game/HTSS00003/USRDIR/showtime.self"
    };
    struct stat st;
    for(size_t i=0;i<sizeof(paths)/sizeof(paths[0]);++i) {
        if(stat(paths[i],&st)==0) return paths[i];
    }
    return NULL;
}

static std::string movian_url_for_movie(const Movie &movie)
{
    if(!movie.ntfs) {
        /* /dev_hdd0/... -> file:///dev_hdd0/... */
        return std::string("file://") + movie.path;
    }

    /* FLOW MOVIE/libntfs stores paths as ntfs0:/MKV/file.mkv while
       Movian's NTFS fileaccess protocol exposes ntfs0://... */
    std::string url=movie.path;
    size_t sep=url.find(":/");
    if(sep!=std::string::npos) url.replace(sep,2,"://");
    return url;
}

#define MKV_ERR_MOVIAN_NOT_FOUND (-25001)

static int launch_mkv_in_movian(const Movie &movie)
{
    const char *player=find_movian_self();
    if(!player) return MKV_ERR_MOVIAN_NOT_FOUND;

    std::string url=movian_url_for_movie(movie);
    const char *launchargv[2];
    launchargv[0]=url.c_str();
    launchargv[1]=NULL;

    char detail[1024];
    snprintf(detail,sizeof(detail),"player=%s url=%s",player,url.c_str());
    flow_log("MKV_LAUNCH_BEGIN",detail);

    /* On success this replaces FLOW MOVIE, so the call does not return.
       If it returns, keep the current app alive and report the error. */
    int ret=sysProcessExitSpawn2(player,launchargv,NULL,NULL,0,1001,
                                 SYS_PROCESS_SPAWN_STACK_SIZE_1M);
    snprintf(detail,sizeof(detail),"spawn_ret=0x%08X",ret);
    flow_log("MKV_LAUNCH_FAIL",detail);
    return ret;
}

static int mount_bd_iso(const Movie &movie)
{'''
if anchor not in s:
    raise SystemExit('mount_bd_iso anchor not found')
s=s.replace(anchor,helper,1)

old='''            } else {\n                show_ok("MKV detectado.\\n\\nLa reproduccion MKV se conectara al motor multimedia en la siguiente etapa.");\n            }'''
new='''            } else {\n                int ret=launch_mkv_in_movian(movie);\n                if(ret==MKV_ERR_MOVIAN_NOT_FOUND) {\n                    show_ok("No se encontro Movian/Showtime.\\n\\nInstala Movian (HTSS00003) o Movian Next con movian.self para reproducir MKV.");\n                } else {\n                    char err[512];\n                    snprintf(err,sizeof(err),"No se pudo iniciar Movian. Error: 0x%08X",ret);\n                    show_ok(err);\n                }\n            }'''
if old not in s:
    raise SystemExit('MKV placeholder anchor not found')
s=s.replace(old,new,1)

p.write_text(s)
print('FLOW MOVIE V2.25: MKV launches directly in Movian; placeholder removed')
