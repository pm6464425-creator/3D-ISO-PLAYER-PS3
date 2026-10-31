from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def replace_once(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'{label}: anchor not found')
    s = s.replace(old, new, 1)

s = s.replace('FLOW MOVIE 3D V4.6 SOFTWARE SAFE inicio',
              'FLOW MOVIE 3D V4.6.1 NTFS FIX inicio', 1)

old_mount = r'''static bool mount_port(int usb)
{
    if(g_mounts[usb] || g_mount_count[usb] > 0) release_port(usb, false);
    g_mounts[usb] = NULL;
    g_mount_count[usb] = ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], NTFS_DEFAULT | NTFS_RECOVER);
    if(g_mount_count[usb] <= 0 || !g_mounts[usb]) {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb] = NULL; }
        g_mount_count[usb] = 0;
        return false;
    }
    return true;
}
'''
new_mount = r'''static bool mount_port(int usb)
{
    if(usb < 0 || usb > 7) return false;
    bootlogf("NTFS","mount_port usb=%d enter",usb);
    if(g_mounts[usb] || g_mount_count[usb] > 0) release_port(usb, false);
    g_mounts[usb] = NULL;
    g_mount_count[usb] = ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], NTFS_DEFAULT | NTFS_RECOVER);
    int ntfs_err = ps3ntfs_errno();
    bootlogf("NTFS","ntfsMountDevice usb=%d count=%d err=%d ptr=%p",usb,g_mount_count[usb],ntfs_err,(void*)g_mounts[usb]);
    if(g_mount_count[usb] <= 0 || !g_mounts[usb]) {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb] = NULL; }
        g_mount_count[usb] = 0;
        return false;
    }
    for(int p=0; p<g_mount_count[usb]; ++p) {
        bootlogf("NTFS","usb=%d part=%d mount=%s start=%u",usb,p,g_mounts[usb][p].name,(unsigned)g_mounts[usb][p].startSector);
    }
    return true;
}
'''
replace_once(old_mount, new_mount, 'mount_port')

old_external = r'''            std::string root = ntfs_folder_path(g_mounts[usb][part].name, current_folder());
            ps3ntfs_mkdir(root.c_str(), 0777);
            DIR_ITER *dir = ps3ntfs_diropen(root.c_str());
            if(!dir) continue;

            char filename[1024];
            struct stat st;
            while(ps3ntfs_dirnext(dir, filename, &st) == 0) {
                if(filename[0] == '.' || !matches_current_tab(filename)) continue;
                Movie m;
                m.name = filename;
                m.path = root + "/" + filename;
                char src[32];
                snprintf(src, sizeof(src), "USB %03d", usb);
                m.source = src;
                m.usb_id = usb;
                m.bytes = (uint64_t)st.st_size;
                m.ntfs = true;
                fresh.push_back(m);
                if(fresh.size() >= 1024) break;
            }
            ps3ntfs_dirclose(dir);
'''
new_external = r'''            std::string root = ntfs_folder_path(g_mounts[usb][part].name, current_folder());
            bootlogf("NTFS","scan usb=%d part=%d root=%s",usb,part,root.c_str());
            DIR_ITER *dir = ps3ntfs_diropen(root.c_str());
            if(!dir) {
                const char *lower = (g_tab == TAB_BDISO) ? "bdiso" : "mkv";
                std::string alt = ntfs_folder_path(g_mounts[usb][part].name, lower);
                bootlogf("NTFS","open failed root=%s err=%d; trying=%s",root.c_str(),ps3ntfs_errno(),alt.c_str());
                dir = ps3ntfs_diropen(alt.c_str());
                if(dir) root = alt;
            }
            if(!dir) {
                bootlogf("NTFS","media folder missing usb=%d part=%d wanted=%s err=%d",usb,part,current_folder(),ps3ntfs_errno());
                continue;
            }

            int added = 0;
            char filename[1024];
            struct stat st;
            while(ps3ntfs_dirnext(dir, filename, &st) == 0) {
                if(filename[0] == '.' || !matches_current_tab(filename)) continue;
                Movie m;
                m.name = filename;
                m.path = root + "/" + filename;
                char src[32];
                snprintf(src, sizeof(src), "USB %03d", usb);
                m.source = src;
                m.usb_id = usb;
                m.bytes = (uint64_t)st.st_size;
                m.ntfs = true;
                fresh.push_back(m);
                added++;
                bootlogf("NTFS","found usb=%d file=%s bytes=%llu",usb,filename,(unsigned long long)m.bytes);
                if(fresh.size() >= 1024) break;
            }
            ps3ntfs_dirclose(dir);
            bootlogf("NTFS","scan done usb=%d part=%d root=%s added=%d",usb,part,root.c_str(),added);
'''
replace_once(old_external, new_external, 'external scan')

old_refresh = r'''static bool refresh_usb_state(bool force_scan)
{
    bool changed = force_scan;
    for(int usb=0; usb<8; ++usb) {
        bool inserted = PS3_NTFS_IsInserted(usb);

        if(inserted && !g_present[usb]) {
            g_present[usb] = true;
            g_insert_delay[usb] = 2;
            changed = true;
        } else if(!inserted && g_present[usb]) {
            g_present[usb] = false;
            g_insert_delay[usb] = 0;
            release_port(usb, true);
            changed = true;
        }

        if(g_present[usb] && g_mount_count[usb] <= 0) {
            if(g_insert_delay[usb] > 0) {
                g_insert_delay[usb]--;
            } else if(mount_port(usb)) {
                changed = true;
            }
        }
    }

    if(changed) rebuild_movies();
    return changed;
}
'''
new_refresh = r'''static bool refresh_usb_state(bool force_scan)
{
    bool changed = false;
    bool any_inserted = false;
    bool any_mounted = false;

    bootlogf("NTFS","refresh enter force=%d",force_scan?1:0);
    for(int usb=0; usb<8; ++usb) {
        bool inserted = PS3_NTFS_IsInserted(usb);
        bootlogf("NTFS","probe usb=%d inserted=%d present=%d mounts=%d",usb,inserted?1:0,g_present[usb]?1:0,g_mount_count[usb]);

        if(!inserted) {
            if(g_present[usb] || g_mount_count[usb] > 0 || g_mounts[usb]) {
                g_present[usb] = false;
                g_insert_delay[usb] = 0;
                release_port(usb, true);
                changed = true;
            }
            continue;
        }

        any_inserted = true;
        if(!g_present[usb]) {
            g_present[usb] = true;
            changed = true;
        }

        /* V4.6.1: manual refresh must complete detection + mount in ONE press.
           The old 2-tick delay was inherited from IRISMAN's continuously-polled
           event loop; V4.6 intentionally has no periodic NTFS polling. */
        if(g_mount_count[usb] <= 0 || !g_mounts[usb]) {
            if(force_scan) {
                g_insert_delay[usb] = 0;
                bool mounted = mount_port(usb);
                bootlogf("NTFS","manual mount usb=%d result=%d count=%d",usb,mounted?1:0,g_mount_count[usb]);
                if(mounted) changed = true;
            } else {
                if(g_insert_delay[usb] <= 0) g_insert_delay[usb] = 2;
                g_insert_delay[usb]--;
                if(g_insert_delay[usb] <= 0 && mount_port(usb)) changed = true;
            }
        }

        if(g_mount_count[usb] > 0 && g_mounts[usb]) any_mounted = true;
    }

    /* A forced manual refresh always rebuilds the media list after mount attempts. */
    if(force_scan || changed) rebuild_movies();
    bootlogf("NTFS","refresh done inserted=%d mounted=%d movies=%u",any_inserted?1:0,any_mounted?1:0,(unsigned)g_movies.size());
    return any_mounted || changed;
}
'''
replace_once(old_refresh, new_refresh, 'refresh_usb_state')

# Add explicit HDD path diagnostics so internal /dev_hdd0/BDISO can be distinguished
# from an external NTFS BDISO issue in the user's log.
old_hdd = r'''        std::string root = std::string("/dev_hdd0/") + current_folder();
        DIR *dir = opendir(root.c_str());
        if(dir) {
'''
new_hdd = r'''        std::string root = std::string("/dev_hdd0/") + current_folder();
        DIR *dir = opendir(root.c_str());
        bootlogf("HDD","scan root=%s open=%d",root.c_str(),dir?1:0);
        if(dir) {
'''
replace_once(old_hdd, new_hdd, 'HDD diagnostics')

s = s.replace('V4.6 SAFE no parchea LV2/Mamba durante el arranque.',
              'V4.6.1 SAFE no parchea LV2/Mamba durante el arranque.', 1)

p.write_text(s)
print('FLOW MOVIE 3D V4.6.1 NTFS FIX applied: one-press manual mount, BDISO path diagnostics, no external mkdir')
