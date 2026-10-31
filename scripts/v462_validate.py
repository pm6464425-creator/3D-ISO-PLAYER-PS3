from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else 'source/main.cpp')
s = p.read_text()
main = s[s.find('int main('):]
preloop = main.split('while(app_running)',1)[0] if 'while(app_running)' in main else main
mk = Path('Makefile').read_text()
stb = Path('source/stb_image_impl.c').read_text() if Path('source/stb_image_impl.c').exists() else ''

checks = [
    ('software renderer only', '#include <tiny3d.h>' not in s and 'tiny3d_' not in s),
    ('legacy RSX renderer retained', '#include "rsxutil.h"' in s and 'init_screen(host_addr,HOST_SIZE)' in main),
    ('rsxutil compiled', 'filter-out background.cpp cover_net.cpp cover_udf.cpp' in mk and 'filter-out rsxutil.cpp' not in mk),
    ('Tiny3D not linked', '-ltiny3d' not in mk),
    ('stb image implementation present', '#define STB_IMAGE_IMPLEMENTATION' in stb),
    ('V4.6.2 marker present', 'FLOW MOVIE 3D V4.6.2 NTFS GPT FIX inicio' in s),
    ('no automatic Mamba bootstrap', 'mamba_bootstrap_if_needed(' not in main),
    ('no automatic NTFS at startup', 'refresh_usb_state(true)' not in preloop),
    ('no periodic NTFS polling', 'poll_counter' not in main and 'refresh_usb_state(false)' not in main),
    ('triangle manual refresh', 'TRIANGLE manual NTFS refresh enter' in main and 'refresh_usb_state(true)' in main),
    ('new mount direct probe', 'mount_port(usb); /* direct probe regardless of physical_hint */' in s),
    ('mount is not gated by IsInserted', 'do not gate first mount on PS3_NTFS_IsInserted()' in s),
    ('read-only force mount flags', 'NTFS_READ_ONLY | NTFS_FORCE' in s),
    ('classic direct ntfsMountDevice retained', 'ntfsMountDevice(disc_ntfs[usb], &g_mounts[usb], flags)' in s),
    ('GPT fallback function present', 'static int fm3d_mount_gpt_ntfs(int usb)' in s),
    ('GPT signature checked', 'memcmp(hdr, "EFI PART", 8)' in s),
    ('GPT partition fields parsed', 'entries_lba64 = fm3d_le64(hdr + 72)' in s and 'entry_count = fm3d_le32(hdr + 80)' in s and 'entry_size = fm3d_le32(hdr + 84)' in s),
    ('GPT NTFS boot sector checked', 'memcmp(boot + 3, "NTFS    ", 8)' in s),
    ('GPT direct ntfsMount used', 'ntfsMount(name, iface, (sec_t)start' in s),
    ('GPT descriptors wired to normal scanner', 'g_mounts[usb] = (ntfs_md*)malloc' in s and 'g_mount_count[usb] = (int)found.size()' in s),
    ('case-insensitive BDISO discovery', 'static DIR_ITER *fm3d_open_media_folder' in s and 'strcasecmp(filename, wanted) == 0' in s),
    ('partition root enumeration', 'ps3ntfs_diropen(base.c_str())' in s),
    ('no external mkdir side effect', 'ps3ntfs_mkdir(root.c_str(), 0777)' not in s),
    ('NTFS ISO discovery diagnostics', 'found usb=%d file=%s bytes=%llu' in s),
    ('internal HDD file diagnostics', 'HDD","found file=%s bytes=%llu' in s),
    ('L1/R1 tabs', 'pad.BTN_L1' in main and 'pad.BTN_R1' in main and 'pad.BTN_R2' not in main),
    ('movie extensions retained', 'ends_with_ci(name, ".iso")' in s and 'ends_with_ci(name, ".mkv")' in s),
    ('persistent boot log', 'FLOW_MOVIE_3D_BOOT.LOG' in s and 'FLOW_MOVIE_3D_BOOT_PREV.LOG' in s),
    ('mount backend diagnostics', 'mount enter name=' in main and 'mount returned ret=' in main),
]

fail = 0
for i, (name, ok) in enumerate(checks, 1):
    print(f'{"PASS" if ok else "FAIL"} {i:02d} {name}')
    if not ok:
        fail += 1
print(f'V4.6.2 NTFS/GPT GATES: {len(checks)-fail}/{len(checks)} PASS')
raise SystemExit(1 if fail else 0)
