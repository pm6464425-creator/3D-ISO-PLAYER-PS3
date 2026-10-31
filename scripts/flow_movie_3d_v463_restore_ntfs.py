from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

def replace_block(start_marker,end_marker,new_block,label):
    global s
    a=s.find(start_marker)
    if a<0:
        raise SystemExit(f'{label}: start not found')
    b=s.find(end_marker,a)
    if b<0:
        raise SystemExit(f'{label}: end not found')
    s=s[:a]+new_block+s[b:]

# Restore the exact, simple NTFS mount strategy from the previously working V3 scanner:
# shutdown -> wait -> ntfsMountDevice(NTFS_DEFAULT|NTFS_RECOVER) -> one retry.
mount_block=r'''static bool mount_port(int usb)
{
    if(usb < 0 || usb > 7) return false;

    bootlogf("NTFS","V3 restore mount usb=%d begin",usb);

    if(g_mounts[usb] || g_mount_count[usb] > 0)
        release_port(usb, false);
    else
        PS3_NTFS_Shutdown(usb);

    g_mounts[usb] = NULL;
    g_mount_count[usb] = 0;
    usleep(120000);

    g_mount_count[usb] = ntfsMountDevice(
        disc_ntfs[usb],
        &g_mounts[usb],
        NTFS_DEFAULT | NTFS_RECOVER
    );
    bootlogf("NTFS","V3 first mount usb=%d count=%d err=%d ptr=%p",
             usb,g_mount_count[usb],ps3ntfs_errno(),(void*)g_mounts[usb]);

    if(g_mount_count[usb] <= 0)
    {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb]=NULL; }
        PS3_NTFS_Shutdown(usb);
        usleep(180000);
        g_mount_count[usb] = ntfsMountDevice(
            disc_ntfs[usb],
            &g_mounts[usb],
            NTFS_DEFAULT | NTFS_RECOVER
        );
        bootlogf("NTFS","V3 retry mount usb=%d count=%d err=%d ptr=%p",
                 usb,g_mount_count[usb],ps3ntfs_errno(),(void*)g_mounts[usb]);
    }

    if(g_mount_count[usb] <= 0 || !g_mounts[usb])
    {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb]=NULL; }
        g_mount_count[usb]=0;
        g_present[usb]=false;
        return false;
    }

    g_present[usb]=true;
    for(int part=0; part<g_mount_count[usb]; ++part)
        bootlogf("NTFS","V3 mounted usb=%d part=%d name=%s start=%u",
                 usb,part,g_mounts[usb][part].name,(unsigned)g_mounts[usb][part].startSector);
    return true;
}

'''
replace_block('static bool mount_port(int usb)','static void rebuild_movies()',mount_block,'mount_port')

# Rebuild library: preserve current HDD support, but external scanning returns to the old V3 path behavior.
a=s.find('static void rebuild_movies()')
b=s.find('\nstatic bool refresh_usb_state',a)
if a<0 or b<0:
    raise SystemExit('rebuild_movies block not found')
old=s[a:b]
ex_start=old.find('    /* External USB NTFS */')
sort_start=old.find('    std::sort(fresh.begin()',ex_start)
if ex_start<0 or sort_start<0:
    raise SystemExit('external scan anchors not found')
external=r'''    /* External USB NTFS - restored V3 reader */
    for(int usb=0; usb<8; ++usb) {
        if(!g_mounts[usb] || g_mount_count[usb] <= 0) continue;
        for(int part=0; part<g_mount_count[usb]; ++part) {
            if(!g_mounts[usb][part].name[0]) continue;

            std::string root = std::string(g_mounts[usb][part].name) + ":/" + current_folder();
            DIR_ITER *dir = ps3ntfs_diropen(root.c_str());
            if(!dir) {
                std::string n = g_mounts[usb][part].name;
                if(!n.empty() && n[n.size()-1] == ':') root = n + "/" + current_folder();
                dir = ps3ntfs_diropen(root.c_str());
            }

            bootlogf("NTFS","V3 folder usb=%d part=%d root=%s open=%d err=%d",
                     usb,part,root.c_str(),dir?1:0,dir?0:ps3ntfs_errno());
            if(!dir) continue;

            char filename[1024];
            struct stat st;
            int added=0;
            while(ps3ntfs_dirnext(dir, filename, &st) == 0) {
                if(filename[0] == '.' || !matches_current_tab(filename)) continue;
                Movie m;
                m.name = filename;
                m.path = root + "/" + filename;
                char src[32];
                snprintf(src,sizeof(src),"USB %03d",usb);
                m.source = src;
                m.usb_id = usb;
                m.bytes = (uint64_t)st.st_size;
                m.ntfs = true;
                fresh.push_back(m);
                added++;
                bootlogf("NTFS","V3 found usb=%d file=%s bytes=%llu",
                         usb,filename,(unsigned long long)m.bytes);
                if(fresh.size() >= 1024) break;
            }
            ps3ntfs_dirclose(dir);
            bootlogf("NTFS","V3 folder done usb=%d part=%d added=%d",usb,part,added);
        }
    }

'''
new_rebuild=old[:ex_start]+external+old[sort_start:]
s=s[:a]+new_rebuild+s[b:]

refresh_block=r'''static bool refresh_usb_state(bool force_scan)
{
    if(!force_scan) return false;

    bootlogf("NTFS","V3 RESTORE manual scan begin");

    /* This wait is intentionally the same style as the old working scanner:
       let the PS3 USB/storage subsystem finish enumeration before probing. */
    for(int i=0; i<12 && app_running; ++i) {
        sysUtilCheckCallback();
        usleep(100000);
    }

    int mounted_ports=0;
    int mounted_parts=0;
    for(int usb=0; usb<8 && app_running; ++usb) {
        bool ok=mount_port(usb);
        if(ok) {
            mounted_ports++;
            mounted_parts += g_mount_count[usb];
        }
    }

    rebuild_movies();
    bootlogf("NTFS","V3 RESTORE manual scan done ports=%d parts=%d movies=%u",
             mounted_ports,mounted_parts,(unsigned)g_movies.size());
    return mounted_ports>0;
}

'''
replace_block('static bool refresh_usb_state(bool force_scan)','static int mount_bd_iso(const Movie &movie)',refresh_block,'refresh_usb_state')

# Old working NTFS mount backend did NOT reject a selected movie through IsInserted()
# before ps3ntfs_file_to_sectors(). Keep only the usb id sanity check.
old_check='''    if(movie.usb_id < 0 || movie.usb_id > 7 || !PS3_NTFS_IsInserted(movie.usb_id)) return -104;'''
new_check='''    if(movie.usb_id < 0 || movie.usb_id > 7) return -104;'''
if old_check not in s:
    raise SystemExit('mount_bd_iso IsInserted check not found')
s=s.replace(old_check,new_check,1)

# Update log marker so hardware logs identify this restoration build.
s=s.replace('FLOW MOVIE 3D V4.6 SOFTWARE SAFE inicio','FLOW MOVIE 3D V4.6.3 RESTORED NTFS inicio',1)

p.write_text(s)
print('FLOW MOVIE 3D V4.6.3: restored proven V3 NTFS reader (shutdown/wait/mount/retry/direct BDISO)')
