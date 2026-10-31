from pathlib import Path
import sys

src=Path(sys.argv[1] if len(sys.argv)>1 else 'source/main.cpp')
s=src.read_text(errors='replace')
main=s[s.find('int main('):]
render=s[s.find('static void render_ui()'):s.find('static void move_selection',s.find('static void render_ui()'))]
mount=s[s.find('static bool mount_port'):s.find('static void rebuild_movies')]
refresh=s[s.find('static bool refresh_usb_state'):s.find('static int mount_bd_iso')]
bdmount=s[s.find('static int mount_bd_iso'):s.find('static void cleanup_ntfs')]
mk=Path('Makefile').read_text(errors='replace') if Path('Makefile').exists() else ''

checks=[
('V4.6.4 marker','FLOW MOVIE 3D V4.6.4 SCREEN FIX inicio' in s),
('Tiny3D source absent','tiny3d_' not in s and '#include <tiny3d.h>' not in s),
('legacy framebuffer include','#include "rsxutil.h"' in s),
('legacy init_screen exactly once',main.count('init_screen(host_addr,HOST_SIZE)')==1),
('legacy back buffer renderer','get_back_buffer()' in s),
('legacy render uses flip',render.count('flip();')==1),
('no spooky spring','flow_spring' not in s and 'g_flow_pos' not in s and 'g_flow_vel' not in s),
('V2 fixed z-order','int positions[7]={-3,3,-2,2,-1,1,0};' in render),
('V2 software frame pacing','usleep(30000);' in main),
('rsxutil compiled','filter-out background.cpp cover_net.cpp cover_udf.cpp' in mk and 'filter-out rsxutil.cpp' not in mk),
('Tiny3D linker removed','-ltiny3d' not in mk),
('V3 NTFS shutdown','PS3_NTFS_Shutdown(usb);' in mount),
('V3 NTFS wait 120ms','usleep(120000);' in mount),
('V3 NTFS retry 180ms','usleep(180000);' in mount),
('V3 flags','NTFS_DEFAULT | NTFS_RECOVER' in mount),
('no FORCE','NTFS_FORCE' not in s),
('no GPT parser','fm3d_mount_gpt_ntfs' not in s),
('refresh direct mount','if(mount_port(usb)) mounted++;' in refresh),
('refresh no IsInserted gate','PS3_NTFS_IsInserted' not in refresh),
('mount backend no IsInserted gate','!PS3_NTFS_IsInserted(movie.usb_id)' not in bdmount),
('direct BDISO/MKV path','current_folder()' in s and 'ps3ntfs_diropen(root.c_str())' in s),
('sector mapping retained','ps3ntfs_file_to_sectors(movie.path.c_str()' in bdmount),
('raw_iso plugin retained','cobra_load_vsh_plugin' in bdmount),
('L1/R1 controls','pad.BTN_L1' in main and 'pad.BTN_R1' in main and 'pad.BTN_R2' not in main),
('persistent log','FLOW_MOVIE_3D_BOOT.LOG' in s),
('no V4.6 software-safe first-frame injection','first SOFTWARE frame enter' not in s),
]

bad=[]
for i,(name,ok) in enumerate(checks,1):
    print(f'{"PASS" if ok else "FAIL"} {i:02d} {name}')
    if not ok: bad.append(name)
print(f'V4.6.4 SCREEN FIX GATES: {len(checks)-len(bad)}/{len(checks)} PASS')
if bad: raise SystemExit(1)
