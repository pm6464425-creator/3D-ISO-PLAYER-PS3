from pathlib import Path
import sys
p=Path(sys.argv[1] if len(sys.argv)>1 else 'source/main.cpp')
s=p.read_text()
main=s[s.find('int main('):]
preloop=main.split('while(app_running)',1)[0] if 'while(app_running)' in main else main
checks=[
('software renderer only', '#include <tiny3d.h>' not in s and 'tiny3d_' not in s),
('legacy RSX renderer retained', '#include "rsxutil.h"' in s and 'init_screen(host_addr,HOST_SIZE)' in main),
('persistent boot log', 'FLOW_MOVIE_3D_BOOT.LOG' in s and 'FLOW_MOVIE_3D_BOOT_PREV.LOG' in s),
('log before renderer init', 'boot_stage(3,"legacy init_screen enter")' in main),
('no automatic Mamba bootstrap', 'mamba_bootstrap_if_needed(' not in main),
('first software frame before library scan', main.find('render_ui();') < main.find('rebuild_movies();')),
('no automatic NTFS startup scan', 'refresh_usb_state(true)' not in preloop),
('no periodic NTFS polling', 'poll_counter' not in main and 'refresh_usb_state(false)' not in main),
('manual triangle NTFS refresh kept', 'TRIANGLE manual NTFS refresh enter' in main and 'refresh_usb_state(true)' in main),
('L1 and R1 tabs', 'pad.BTN_L1' in main and 'pad.BTN_R1' in main and 'pad.BTN_R2' not in main),
('L1/R1 state edges', 'p_l1=l1' in main and 'p_r1=r1' in main),
('software framebuffer drawing retained', 'get_back_buffer()' in s and 'flip();' in s),
('mount diagnostics', 'mount enter name=' in main and 'mount returned ret=' in main),
('main heartbeat', 'HEARTBEAT' in main and 'UI alive movies=' in main),
('movie-only folders retained', '"BDISO"' in s and '"MKV"' in s),
]
fail=0
for i,(name,ok) in enumerate(checks,1):
    print(f'{"PASS" if ok else "FAIL"} {i:02d} {name}')
    if not ok: fail+=1
print(f'V4.6 SOFTWARE SAFE GATES: {len(checks)-fail}/{len(checks)} PASS')
raise SystemExit(1 if fail else 0)
