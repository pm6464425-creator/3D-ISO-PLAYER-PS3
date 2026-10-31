from pathlib import Path
import sys

p=Path(sys.argv[1] if len(sys.argv)>1 else 'source/main.cpp')
s=p.read_text()
main=s[s.find('int main('):]
preloop=main.split('while(app_running)',1)[0] if 'while(app_running)' in main else main
mk=Path('Makefile').read_text()
stb=Path('source/stb_image_impl.c').read_text() if Path('source/stb_image_impl.c').exists() else ''

checks=[
('software renderer only', '#include <tiny3d.h>' not in s and 'tiny3d_' not in s),
('legacy RSX renderer retained', '#include "rsxutil.h"' in s and 'init_screen(host_addr,HOST_SIZE)' in main),
('rsxutil compiled', 'filter-out background.cpp cover_net.cpp cover_udf.cpp' in mk and 'filter-out rsxutil.cpp' not in mk),
('Tiny3D not linked', '-ltiny3d' not in mk),
('stb image implementation present', '#define STB_IMAGE_IMPLEMENTATION' in stb),
('V4.6.1 marker present', 'FLOW MOVIE 3D V4.6.1 NTFS FIX inicio' in s),
('no automatic Mamba bootstrap', 'mamba_bootstrap_if_needed(' not in main),
('no automatic NTFS at startup', 'refresh_usb_state(true)' not in preloop),
('no periodic NTFS polling', 'poll_counter' not in main and 'refresh_usb_state(false)' not in main),
('triangle manual refresh', 'TRIANGLE manual NTFS refresh enter' in main and 'refresh_usb_state(true)' in main),
('manual refresh mounts immediately', 'if(force_scan)' in s and 'bool mounted = mount_port(usb);' in s),
('old first-detection delay removed', 'g_insert_delay[usb] = 2;\n            changed = true;' not in s),
('forced refresh always rebuilds list', 'if(force_scan || changed) rebuild_movies();' in s),
('USB probe diagnostics', 'probe usb=%d inserted=%d present=%d mounts=%d' in s),
('mount result diagnostics', 'manual mount usb=%d result=%d count=%d' in s),
('ntfsMountDevice errno diagnostics', 'ntfsMountDevice usb=%d count=%d err=%d ptr=%p' in s and 'ps3ntfs_errno()' in s),
('BDISO exact root scan', 'ntfs_folder_path(g_mounts[usb][part].name, current_folder())' in s),
('lowercase BDISO fallback', '(g_tab == TAB_BDISO) ? "bdiso" : "mkv"' in s),
('no external mkdir side effect', 'ps3ntfs_mkdir(root.c_str(), 0777)' not in s),
('NTFS folder-open diagnostics', 'media folder missing usb=%d part=%d wanted=%s err=%d' in s),
('NTFS ISO discovery diagnostics', 'found usb=%d file=%s bytes=%llu' in s),
('internal HDD BDISO diagnostics', 'HDD","scan root=%s open=%d' in s),
('L1/R1 tabs', 'pad.BTN_L1' in main and 'pad.BTN_R1' in main and 'pad.BTN_R2' not in main),
('movie extensions retained', 'ends_with_ci(name, ".iso")' in s and 'ends_with_ci(name, ".mkv")' in s),
('persistent boot log', 'FLOW_MOVIE_3D_BOOT.LOG' in s and 'FLOW_MOVIE_3D_BOOT_PREV.LOG' in s),
('mount backend diagnostics', 'mount enter name=' in main and 'mount returned ret=' in main),
]

fail=0
for i,(name,ok) in enumerate(checks,1):
    print(f'{"PASS" if ok else "FAIL"} {i:02d} {name}')
    if not ok: fail += 1
print(f'V4.6.1 NTFS FIX GATES: {len(checks)-fail}/{len(checks)} PASS')
raise SystemExit(1 if fail else 0)
