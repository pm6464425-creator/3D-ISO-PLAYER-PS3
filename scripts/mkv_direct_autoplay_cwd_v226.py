from pathlib import Path

# FLOW V2.26 MKV DIRECT AUTOPLAY HANDOFF.
# Deank/IRISMAN Showtime reads "./TEMP/SHOWTIME.TXT" on startup.
# Preparing the file at the SELF's folder alone is NOT sufficient unless the
# launcher sets the working directory. This change only touches MKV startup.
p=Path('source/main.cpp')
s=p.read_text()
anchor='''    /* Verified multiMAN/IRISMAN launch semantics: no fake argv[0] = player!
       SHOWTIME.SELF itself reads TEMP/SHOWTIME.TXT to open the selected movie. */
    sysProcessExitSpawn2(player,NULL,NULL,NULL,0,1200,
                         SYS_PROCESS_SPAWN_STACK_SIZE_1M);
'''
replacement='''    /* FLOW V2.26 MKV DIRECT AUTOPLAY:
       Showtime mmCM/IRISMAN edition looks for ./TEMP/SHOWTIME.TXT, which
       is RELATIVE TO THE CURRENT WORKING DIRECTORY. If CWD is not the
       FLOW USRDIR, launching the SELF succeeds but displays Home instead
       of automatically opening the selected movie.  This was observed
       on a real PS3. */
    char prev_workdir[1024]={0};
    bool have_old_workdir=(getcwd(prev_workdir,sizeof(prev_workdir))!=NULL);
    const char *self_directory="/dev_hdd0/game/3DISO0001/USRDIR";
    if(chdir(self_directory)!=0) {
        flow_log("MKV_CWD_FAIL","Cannot set Showtime working directory");
        return MKV_ERR_PREPARE_FAILED;
    }

    FILE *autoplay=fopen("./TEMP/SHOWTIME.TXT","rb");
    bool autoplay_verified=false;
    if(autoplay) {
        std::string content;
        char buffer[512];
        size_t got=0;
        while((got=fread(buffer,1,sizeof(buffer),autoplay))>0) {
            if(content.size()+got>8192) { content.clear(); break; }
            content.append(buffer,got);
        }
        fclose(autoplay);
        autoplay_verified=(content==url);
    }
    if(!autoplay_verified) {
        flow_log("MKV_AUTOPLAY_VERIFY_FAIL","SHOWTIME.TXT unavailable under relative startup path");
        if(have_old_workdir) chdir(prev_workdir);
        return MKV_ERR_PREPARE_FAILED;
    }

    flow_log("MKV_DIRECT_AUTOPLAY_READY","Relative TEMP/SHOWTIME.TXT verified, cwd set for Showtime SELF");
    /* Official IRISMAN launches this standalone SELF without argv; the
       verified relative startup file supplies the media URL. */
    sysProcessExitSpawn2(player,NULL,NULL,NULL,0,1200,
                         SYS_PROCESS_SPAWN_STACK_SIZE_1M);
    if(have_old_workdir) chdir(prev_workdir);
'''
if s.count(anchor)!=1: raise SystemExit('Unexpected direct MKV spawn anchor')
s=s.replace(anchor,replacement,1)
must=['FLOW V2.26 MKV DIRECT AUTOPLAY','V2.26 VERIFIED SHOWTIME MKV',
      'V2.26 TRANSITION BRIGHTNESS FIX','V2.26 PS MENU STATIC FRONT BUFFER',
      'V2.26 REALTIME MOTION PERF','MKV_DIRECT_AUTOPLAY_READY']
for x in must:
    if x not in s: raise SystemExit('Missing regression marker: '+x)
p.write_text(s)
print('MKV direct autoplay staged: working directory controlled, relative Showtime startup file checked')
