from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def replace_once(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'{label}: anchor not found')
    s = s.replace(old, new, 1)

s = s.replace('FLOW MOVIE 3D V4.6.1 NTFS FIX inicio',
              'FLOW MOVIE 3D V4.6.2 NTFS GPT FIX inicio', 1)
s = s.replace('V4.6.1 SAFE no parchea LV2/Mamba durante el arranque.',
              'V4.6.2 SAFE no parchea LV2/Mamba durante el arranque.', 1)

# -----------------------------------------------------------------------------
# Robust NTFS probing:
# 1) Do NOT require PS3_NTFS_IsInserted() before first mount. IRISMAN probes a
#    new device by calling ntfsMountDevice() directly.
# 2) Use read-only + FORCE flags because FLOW MOVIE 3D only needs to read ISOs.
# 3) The classic libntfs_ext partition finder understands MBR/EBR but not GPT.
#    If it returns no partitions, parse GPT here and mount NTFS partitions with
#    ntfsMount() directly.
# -----------------------------------------------------------------------------
mount_anchor = 'static bool mount_port(int usb)\n{'
if mount_anchor not in s:
    raise SystemExit('mount_port anchor not found')

helpers = r'''static uint32_t fm3d_le32(const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static uint64_t fm3d_le64(const unsigned char *p)
{
    return ((uint64_t)fm3d_le32(p)) | ((uint64_t)fm3d_le32(p + 4) << 32);
}

static bool fm3d_nonzero16(const unsigned char *p)
{
    for(int i=0;i<16;i++) if(p[i] != 0) return true;
    return false;
}

static size_t fm3d_detect_sector_size(const unsigned char *buf, size_t cap, unsigned char fill)
{
    size_t last = 0;
    bool changed = false;
    for(size_t i=0;i<cap;i++) {
        if(buf[i] != fill) { last = i; changed = true; }
    }
    if(!changed) return 512;
    size_t n = 512;
    while(n <= last && n < cap) n <<= 1;
    if(n > cap) n = cap;
    return n;
}

static int fm3d_mount_gpt_ntfs(int usb)
{
    if(usb < 0 || usb > 7) return 0;
    const DISC_INTERFACE *iface = disc_ntfs[usb];
    if(!iface) return 0;

    bootlogf("GPT","usb=%d fallback enter",usb);
    if(!iface->startup()) {
        bootlogf("GPT","usb=%d interface startup failed",usb);
        return 0;
    }

    const size_t BUF_CAP = 16384;
    unsigned char *hdr = (unsigned char*)memalign(32, BUF_CAP);
    unsigned char *table = (unsigned char*)memalign(32, BUF_CAP);
    unsigned char *boot = (unsigned char*)memalign(32, BUF_CAP);
    if(!hdr || !table || !boot) {
        free(hdr); free(table); free(boot);
        bootlogf("GPT","usb=%d buffer allocation failed",usb);
        PS3_NTFS_Shutdown(usb);
        return 0;
    }

    const unsigned char sentinel = 0xA5;
    memset(hdr, sentinel, BUF_CAP);
    if(!iface->readSectors((sec_t)1, (sec_t)1, hdr)) {
        bootlogf("GPT","usb=%d cannot read GPT header LBA1",usb);
        free(hdr); free(table); free(boot);
        PS3_NTFS_Shutdown(usb);
        return 0;
    }

    size_t sector_size = fm3d_detect_sector_size(hdr, BUF_CAP, sentinel);
    bootlogf("GPT","usb=%d detected logical sector=%u",usb,(unsigned)sector_size);

    if(memcmp(hdr, "EFI PART", 8) != 0) {
        bootlogf("GPT","usb=%d no EFI PART signature",usb);
        free(hdr); free(table); free(boot);
        PS3_NTFS_Shutdown(usb);
        return 0;
    }

    uint32_t header_size = fm3d_le32(hdr + 12);
    uint64_t entries_lba64 = fm3d_le64(hdr + 72);
    uint32_t entry_count = fm3d_le32(hdr + 80);
    uint32_t entry_size = fm3d_le32(hdr + 84);

    bootlogf("GPT","usb=%d header=%u entries_lba=%llu count=%u entry_size=%u",
             usb,(unsigned)header_size,(unsigned long long)entries_lba64,
             (unsigned)entry_count,(unsigned)entry_size);

    if(header_size < 92 || header_size > sector_size ||
       entries_lba64 == 0 || entries_lba64 > 0xFFFFFFFFULL ||
       entry_count == 0 || entry_count > 4096 ||
       entry_size < 128 || entry_size > sector_size ||
       (entry_size % 128) != 0 || (sector_size % entry_size) != 0) {
        bootlogf("GPT","usb=%d invalid/unsupported GPT geometry",usb);
        free(hdr); free(table); free(boot);
        PS3_NTFS_Shutdown(usb);
        return 0;
    }

    uint32_t entries_per_sector = (uint32_t)(sector_size / entry_size);
    uint32_t sectors_to_scan = (entry_count + entries_per_sector - 1) / entries_per_sector;
    if(sectors_to_scan == 0 || sectors_to_scan > 1024) {
        bootlogf("GPT","usb=%d excessive GPT table sectors=%u",usb,(unsigned)sectors_to_scan);
        free(hdr); free(table); free(boot);
        PS3_NTFS_Shutdown(usb);
        return 0;
    }

    std::vector<ntfs_md> found;
    std::vector<uint32_t> mounted_starts;
    uint32_t global_index = 0;

    for(uint32_t sec=0; sec<sectors_to_scan && global_index<entry_count; ++sec) {
        uint64_t lba64 = entries_lba64 + sec;
        if(lba64 > 0xFFFFFFFFULL) break;
        memset(table, 0, BUF_CAP);
        if(!iface->readSectors((sec_t)lba64, (sec_t)1, table)) {
            bootlogf("GPT","usb=%d failed table read lba=%llu",usb,(unsigned long long)lba64);
            global_index += entries_per_sector;
            continue;
        }

        for(uint32_t slot=0; slot<entries_per_sector && global_index<entry_count; ++slot,++global_index) {
            const unsigned char *e = table + ((size_t)slot * entry_size);
            if(!fm3d_nonzero16(e)) continue; /* unused GPT entry */

            uint64_t start64 = fm3d_le64(e + 32);
            uint64_t end64 = fm3d_le64(e + 40);
            if(start64 == 0 || end64 < start64 || start64 > 0xFFFFFFFFULL) {
                bootlogf("GPT","usb=%d entry=%u unsupported start=%llu end=%llu",
                         usb,(unsigned)global_index,(unsigned long long)start64,(unsigned long long)end64);
                continue;
            }

            uint32_t start = (uint32_t)start64;
            bool duplicate = false;
            for(size_t k=0;k<mounted_starts.size();++k)
                if(mounted_starts[k] == start) { duplicate = true; break; }
            if(duplicate) continue;

            memset(boot, 0, BUF_CAP);
            if(!iface->readSectors((sec_t)start, (sec_t)1, boot)) continue;
            if(memcmp(boot + 3, "NTFS    ", 8) != 0) {
                bootlogf("GPT","usb=%d entry=%u start=%u is not NTFS",usb,(unsigned)global_index,(unsigned)start);
                continue;
            }

            char name[32];
            snprintf(name,sizeof(name),"fm3d%dp%u",usb,(unsigned)found.size());
            u32 flags = NTFS_READ_ONLY | NTFS_FORCE;
            bool ok = ntfsMount(name, iface, (sec_t)start,
                                CACHE_DEFAULT_PAGE_COUNT, CACHE_DEFAULT_PAGE_SIZE, flags);
            int err = ps3ntfs_errno();
            bootlogf("GPT","usb=%d mount name=%s start=%u ok=%d err=%d",
                     usb,name,(unsigned)start,ok?1:0,err);
            if(!ok) continue;

            ntfs_md md;
            memset(&md,0,sizeof(md));
            snprintf(md.name,sizeof(md.name),"%s",name);
            md.interface = iface;
            md.startSector = (sec_t)start;
            found.push_back(md);
            mounted_starts.push_back(start);
            if(found.size() >= 8) break;
        }
        if(found.size() >= 8) break;
    }

    free(hdr); free(table); free(boot);

    if(found.empty()) {
        bootlogf("GPT","usb=%d GPT present but no mountable NTFS partition",usb);
        PS3_NTFS_Shutdown(usb);
        return 0;
    }

    g_mounts[usb] = (ntfs_md*)malloc(found.size() * sizeof(ntfs_md));
    if(!g_mounts[usb]) {
        for(size_t i=0;i<found.size();++i) ntfsUnmount(found[i].name, true);
        PS3_NTFS_Shutdown(usb);
        return 0;
    }
    memcpy(g_mounts[usb], &found[0], found.size() * sizeof(ntfs_md));
    g_mount_count[usb] = (int)found.size();
    bootlogf("GPT","usb=%d fallback mounted partitions=%d",usb,g_mount_count[usb]);
    return g_mount_count[usb];
}

'''
s = s.replace(mount_anchor, helpers + mount_anchor, 1)

old_mount = r'''static bool mount_port(int usb)
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
new_mount = r'''static bool mount_port(int usb)
{
    if(usb < 0 || usb > 7) return false;
    bootlogf("NTFS","mount_port usb=%d direct probe enter",usb);
    if(g_mounts[usb] || g_mount_count[usb] > 0) release_port(usb, false);
    g_mounts[usb] = NULL;
    g_mount_count[usb] = 0;

    /* Important: do not gate first mount on PS3_NTFS_IsInserted().
       IRISMAN probes a new device by calling ntfsMountDevice() directly. */
    const u32 flags = NTFS_READ_ONLY | NTFS_FORCE;
    int classic_count = ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], flags);
    int classic_err = ps3ntfs_errno();
    g_mount_count[usb] = classic_count;
    bootlogf("NTFS","direct ntfsMountDevice usb=%d count=%d err=%d ptr=%p flags=0x%x",
             usb,classic_count,classic_err,(void*)g_mounts[usb],(unsigned)flags);

    if(g_mount_count[usb] <= 0 || !g_mounts[usb]) {
        if(g_mounts[usb]) { free(g_mounts[usb]); g_mounts[usb] = NULL; }
        g_mount_count[usb] = 0;

        /* libntfs_ext's classic partition discovery is MBR/EBR-only.
           Try GPT parsing and direct ntfsMount() as a compatibility fallback. */
        int gpt_count = fm3d_mount_gpt_ntfs(usb);
        bootlogf("NTFS","GPT fallback usb=%d count=%d",usb,gpt_count);
        if(gpt_count <= 0 || !g_mounts[usb]) return false;
    }

    for(int p=0; p<g_mount_count[usb]; ++p) {
        bootlogf("NTFS","usb=%d part=%d mount=%s start=%u",usb,p,g_mounts[usb][p].name,(unsigned)g_mounts[usb][p].startSector);
    }
    return true;
}
'''
replace_once(old_mount, new_mount, 'mount_port direct + GPT')

# Case-insensitive media-folder discovery by enumerating the NTFS root. This
# also protects against odd capitalization such as BdIso/BDIso/bdiso.
rebuild_anchor = 'static void rebuild_movies()\n{'
if rebuild_anchor not in s:
    raise SystemExit('rebuild anchor not found')
folder_helper = r'''static DIR_ITER *fm3d_open_media_folder(const char *mount_name, const char *wanted, std::string &resolved)
{
    resolved = ntfs_folder_path(mount_name, wanted);
    DIR_ITER *dir = ps3ntfs_diropen(resolved.c_str());
    if(dir) {
        bootlogf("NTFS","folder exact ok=%s",resolved.c_str());
        return dir;
    }

    std::string base = mount_name ? mount_name : "";
    if(!base.empty() && base[base.size()-1] != ':') base += ':';
    base += "/";
    DIR_ITER *root = ps3ntfs_diropen(base.c_str());
    if(!root) {
        bootlogf("NTFS","cannot open partition root=%s err=%d",base.c_str(),ps3ntfs_errno());
        return NULL;
    }

    char filename[1024];
    struct stat st;
    std::string match;
    while(ps3ntfs_dirnext(root, filename, &st) == 0) {
        if(filename[0] == '.') continue;
        if(S_ISDIR(st.st_mode) && strcasecmp(filename, wanted) == 0) {
            match = filename;
            break;
        }
    }
    ps3ntfs_dirclose(root);

    if(match.empty()) {
        bootlogf("NTFS","folder not found case-insensitive mount=%s wanted=%s",mount_name?mount_name:"",wanted?wanted:"");
        return NULL;
    }

    resolved = ntfs_folder_path(mount_name, match.c_str());
    dir = ps3ntfs_diropen(resolved.c_str());
    bootlogf("NTFS","folder resolved=%s open=%d err=%d",resolved.c_str(),dir?1:0,dir?0:ps3ntfs_errno());
    return dir;
}

'''
s = s.replace(rebuild_anchor, folder_helper + rebuild_anchor, 1)

old_external_open = r'''            std::string root = ntfs_folder_path(g_mounts[usb][part].name, current_folder());
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
'''
new_external_open = r'''            std::string root;
            bootlogf("NTFS","scan usb=%d part=%d mount=%s wanted=%s",usb,part,g_mounts[usb][part].name,current_folder());
            DIR_ITER *dir = fm3d_open_media_folder(g_mounts[usb][part].name, current_folder(), root);
            if(!dir) {
                bootlogf("NTFS","media folder missing usb=%d part=%d wanted=%s",usb,part,current_folder());
                continue;
            }
'''
replace_once(old_external_open, new_external_open, 'case-insensitive media folder')

old_refresh = r'''static bool refresh_usb_state(bool force_scan)
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
new_refresh = r'''static bool refresh_usb_state(bool force_scan)
{
    bool changed = false;
    bool any_physical = false;
    bool any_mounted = false;

    bootlogf("NTFS","refresh enter force=%d DIRECT_PROBE",force_scan?1:0);
    for(int usb=0; usb<8; ++usb) {
        bool physical_hint = PS3_NTFS_IsInserted(usb);
        bool had_mount = (g_mount_count[usb] > 0 && g_mounts[usb]);
        bootlogf("NTFS","hint usb=%d inserted=%d had_mount=%d present=%d",
                 usb,physical_hint?1:0,had_mount?1:0,g_present[usb]?1:0);
        if(physical_hint) any_physical = true;

        if(had_mount && !physical_hint) {
            /* The hint is useful for unplug detection, but never blocks a new mount. */
            release_port(usb, true);
            g_present[usb] = false;
            had_mount = false;
            changed = true;
        }

        if(force_scan && !had_mount) {
            g_insert_delay[usb] = 0;
            bool mounted = mount_port(usb); /* direct probe regardless of physical_hint */
            g_present[usb] = mounted;
            bootlogf("NTFS","direct manual mount usb=%d hint=%d result=%d count=%d",
                     usb,physical_hint?1:0,mounted?1:0,g_mount_count[usb]);
            if(mounted) {
                any_mounted = true;
                changed = true;
            }
        } else if(had_mount) {
            g_present[usb] = true;
            any_mounted = true;
        }
    }

    if(force_scan || changed) rebuild_movies();
    bootlogf("NTFS","refresh done physical_hint=%d mounted=%d movies=%u",
             any_physical?1:0,any_mounted?1:0,(unsigned)g_movies.size());
    return any_mounted || changed;
}
'''
replace_once(old_refresh, new_refresh, 'refresh direct probe')

# Make internal HDD diagnostics include each accepted ISO/MKV so the log can
# distinguish an external problem from a general library-scan problem.
old_hdd_push = r'''                fresh.push_back(m);
                if(fresh.size() >= 1024) break;
'''
new_hdd_push = r'''                fresh.push_back(m);
                bootlogf("HDD","found file=%s bytes=%llu",de->d_name,(unsigned long long)m.bytes);
                if(fresh.size() >= 1024) break;
'''
# Replace only the first occurrence, which is the internal HDD loop.
replace_once(old_hdd_push, new_hdd_push, 'HDD file diagnostics')

p.write_text(s)
print('FLOW MOVIE 3D V4.6.2 NTFS GPT FIX applied: direct probe, GPT fallback, force read-only mount, case-insensitive BDISO')
