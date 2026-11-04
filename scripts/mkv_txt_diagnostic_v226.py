#!/usr/bin/env python3
"""FLOW V2.26 MKV TXT diagnostics: minimal changes to the exact generated EBOOT source."""
from pathlib import Path
import hashlib
p=Path("source/main.cpp")
s=p.read_text()
expected="4821d18f8050fe7ec4b648f4e3cebe2eb8dc609b1394d86bd5fbff24ec43ec0d"
assert hashlib.sha256(s.encode()).hexdigest()==expected,"Not the verified V2.26 source"

def sub(a,b):
    global s
    assert s.count(a)==1, ("missing/ambiguous patch point",a[:80],s.count(a))
    s=s.replace(a,b,1)

sub('#include <stdio.h>\n','#include <stdio.h>\n#include <errno.h>\n')
helper=r'''
/* Persist MKV handoff checkpoints as plain text.  Never called per-frame. */
static void flow_mkv_diag_txt(const char *stage,const char *detail,int code)
{
    FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_ERROR.TXT","a");
    if(!f) f=fopen("/dev_hdd0/tmp/FLOW_ERROR.TXT","a");
    if(!f) return;
    struct timeval tv;
    gettimeofday(&tv,NULL);
    fprintf(f,"%llu.%03lu | %s | code=%d (0x%08X)",
        (unsigned long long)tv.tv_sec,(unsigned long)(tv.tv_usec/1000),
        stage?stage:"UNKNOWN",code,(unsigned int)code);
    if(detail && detail[0]) {
        fputs(" | ",f);
        for(unsigned int i=0;detail[i] && i<1800;++i)
            fputc((detail[i]=='\n' || detail[i]=='\r')?' ':detail[i],f);
    }
    fputc('\n',f);
    fflush(f);
    fclose(f);
}
'''
sub('static void flow_log_heartbeat()\n',helper+'\nstatic void flow_log_heartbeat()\n')
sub('''    if(!m7_self_valid(player)) {
        flow_log("M7_EMBEDDED_NOT_FOUND",player);
        return MKV_ERR_MOVIAN_NOT_FOUND;
    }
''','''    flow_mkv_diag_txt("M7_SELF_CHECK_BEGIN",player,0);
    if(!m7_self_valid(player)) {
        flow_log("M7_EMBEDDED_NOT_FOUND",player);
        flow_mkv_diag_txt("ERROR_M7_SELF_INVALID",player,MKV_ERR_MOVIAN_NOT_FOUND);
        return MKV_ERR_MOVIAN_NOT_FOUND;
    }
    flow_mkv_diag_txt("M7_SELF_CHECK_OK",player,0);
''')
sub('''        if(ps3ntfs_stat(movie.path.c_str(),&source)!=0 || source.st_size<=0) {
            flow_log("M7_USB_SOURCE_NOT_READABLE",movie.path.c_str());
            return MKV_ERR_NTFS_READ;
        }
''','''        flow_mkv_diag_txt("NTFS_STAT_BEGIN",movie.path.c_str(),0);
        int rc=ps3ntfs_stat(movie.path.c_str(),&source);
        int saved_errno=errno;
        if(rc!=0 || source.st_size<=0) {
            char why[1200];
            snprintf(why,sizeof(why),"stat=%d errno=%d size=%lld path=%s",
                rc,saved_errno,(long long)(rc==0?source.st_size:0),movie.path.c_str());
            flow_log("M7_USB_SOURCE_NOT_READABLE",movie.path.c_str());
            flow_mkv_diag_txt("ERROR_NTFS_SOURCE",why,saved_errno?saved_errno:MKV_ERR_NTFS_READ);
            return MKV_ERR_NTFS_READ;
        }
        flow_mkv_diag_txt("NTFS_STAT_OK",movie.path.c_str(),0);
''')
sub('''        if(stat(movie.path.c_str(),&source)!=0 || source.st_size<=0) {
            flow_log("M7_HDD_SOURCE_NOT_READABLE",movie.path.c_str());
            return MKV_ERR_PREPARE_FAILED;
        }
''','''        flow_mkv_diag_txt("HDD_STAT_BEGIN",movie.path.c_str(),0);
        int rc=stat(movie.path.c_str(),&source);
        int saved_errno=errno;
        if(rc!=0 || source.st_size<=0) {
            flow_log("M7_HDD_SOURCE_NOT_READABLE",movie.path.c_str());
            flow_mkv_diag_txt("ERROR_HDD_SOURCE",movie.path.c_str(),
                              saved_errno?saved_errno:MKV_ERR_PREPARE_FAILED);
            return MKV_ERR_PREPARE_FAILED;
        }
        flow_mkv_diag_txt("HDD_STAT_OK",movie.path.c_str(),0);
''')
sub('''        flow_log("M7_MEDIA_URI_INVALID",url.c_str());
        return MKV_ERR_PREPARE_FAILED;
''','''        flow_log("M7_MEDIA_URI_INVALID",url.c_str());
        flow_mkv_diag_txt("ERROR_M7_URI_INVALID",url.c_str(),MKV_ERR_PREPARE_FAILED);
        return MKV_ERR_PREPARE_FAILED;
''')
sub('    flow_log("M7_DIRECT_NTFS_START",detail);\n','    flow_log("M7_DIRECT_NTFS_START",detail);\n    flow_mkv_diag_txt("M7_HANDOFF_BEGIN",detail,0);\n')
sub('''    flow_log("M7_SPAWN_RETURNED","Failed to start embedded M7");
    return MKV_ERR_SPAWN_RETURNED;
''','''    flow_log("M7_SPAWN_RETURNED","Failed to start embedded M7");
    flow_mkv_diag_txt("ERROR_M7_SPAWN_RETURNED","Spawn2 returned instead of launching",MKV_ERR_SPAWN_RETURNED);
    return MKV_ERR_SPAWN_RETURNED;
''')
sub('    flow_log("SESSION_START","FLOW MOVIE V2.26 INTERNAL PLAYER");\n',
    '    flow_log("SESSION_START","FLOW MOVIE V2.26 INTERNAL PLAYER");\n    flow_mkv_diag_txt("FLOW_SESSION_START","FLOW V2.26 MKV TXT DIAG",0);\n')
sub('''            } else {
                int ret=launch_mkv_in_movian(movie);
''','''            } else {
                flow_mkv_diag_txt("MKV_SELECTED",movie.path.c_str(),movie.usb_id);
                int ret=launch_mkv_in_movian(movie);
''')
sub('    flow_log("SESSION_EXIT","normal");\n',
    '    flow_log("SESSION_EXIT","normal");\n    flow_mkv_diag_txt("FLOW_SESSION_EXIT","normal",0);\n')
for req in ('const char *args[]={url.c_str(),NULL};','sysProcessExitSpawn2(player,args,NULL,NULL,0,1200,',
            '#define COVER_CACHE_SLOTS 16','M7_DIRECT_NTFS_START'):
    assert req in s,req
p.write_text(s)
print("FLOW TXT checkpoints inserted",s.count("flow_mkv_diag_txt(")-1)
print("sha256",hashlib.sha256(s.encode()).hexdigest())
