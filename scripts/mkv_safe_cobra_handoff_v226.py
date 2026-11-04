from pathlib import Path

# V2.26 MKV SAFE HANDOFF: no getcwd/chdir (those regressed PS3 startup).
# Use IRISMAN's exact launch behavior: map multiMAN's legacy save folder
# to FLOW's own install folder immediately before spawning the original SELF.
# This is PS3 Cobra's sys_map_path(), not a userspace cwd change.
p=Path('source/main.cpp')
s=p.read_text()
old='''    /* Verified multiMAN/IRISMAN launch semantics: no fake argv[0] = player!
       SHOWTIME.SELF itself reads TEMP/SHOWTIME.TXT to open the selected movie. */
    sysProcessExitSpawn2(player,NULL,NULL,NULL,0,1200,
                         SYS_PROCESS_SPAWN_STACK_SIZE_1M);
'''
new='''    /* V2.26 MKV SAFE HANDOFF:
       IRISMAN maps /dev_hdd0/game/BLES80608 to its own game directory
       BEFORE launching SHOWTIME.SELF. That redirects the legacy player's
       startup TEMP/SHOWTIME.TXT request into our FLOW USRDIR/TEMP.
       Do not use getcwd/chdir here: the CWD-based revision caused an
       immediate black-screen regression on PS3 and process-spawn need not
       preserve its parent working directory. */
    static const char * const mm_path="/dev_hdd0/game/BLES80608";
    static const char * const flow_path="/dev_hdd0/game/3DISO0001";
    const char *autoplay_path="/dev_hdd0/game/3DISO0001/USRDIR/TEMP/SHOWTIME.TXT";
    FILE *check=fopen(autoplay_path,"rb");
    if(!check) {
        flow_log("MKV_SAFE_AUTOPLAY_MISSING",autoplay_path);
        return MKV_ERR_PREPARE_FAILED;
    }
    fclose(check);
    /* IRISMAN uses a Cobra kernel path table for this same prefix.
       This public libcobra syscall35 helper is supported by Cobra and
       HEN versions that enable path mapping; if unavailable we return
       to the FLOW UI rather than killing the process or black-screening. */
    int map_ret=sys_map_path((char*)mm_path,(char*)flow_path);
    if(map_ret!=0) {
        char info[96];
        snprintf(info,sizeof(info),"sys_map_path=%d",map_ret);
        flow_log("MKV_SAFE_MAP_UNSUPPORTED",info);
        return MKV_ERR_PREPARE_FAILED;
    }
    flow_log("MKV_SAFE_AUTOPLAY_READY","BLES80608 path mapped to FLOW startup file");
    sysProcessExitSpawn2(player,NULL,NULL,NULL,0,1200,
                         SYS_PROCESS_SPAWN_STACK_SIZE_1M);
'''
if s.count(old)!=1: raise SystemExit('MKV starter not found exactly once')
s=s.replace(old,new,1)
assert 'getcwd(' not in s and 'chdir(' not in s
for tok in ('V2.26 MKV SAFE HANDOFF','V2.26 VERIFIED SHOWTIME MKV','V2.26 TRANSITION BRIGHTNESS FIX',
            'V2.26 PS MENU STATIC FRONT BUFFER','V2.26 REALTIME MOTION PERF',
            'sys_map_path((char*)mm_path,(char*)flow_path)'):
    if tok not in s: raise SystemExit('Missing required marker: '+tok)
p.write_text(s)
print('MKV safe handoff applied: prior boot-safe source + original IRISMAN path mapping')
