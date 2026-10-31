from pathlib import Path
import sys
p=Path(sys.argv[1] if len(sys.argv)>1 else 'source/main.cpp')
s=p.read_text(errors='replace')
main=s[s.find('int main('):]
checks=[
('software renderer only','tiny3d_' not in s and '#include <tiny3d.h>' not in s),
('V4.6.3 marker','FLOW MOVIE 3D V4.6.3 RESTORED NTFS inicio' in s),
('old V3 shutdown before probe','PS3_NTFS_Shutdown(usb);' in s),
('old V3 first wait','usleep(120000);' in s),
('old V3 retry wait','usleep(180000);' in s),
('old V3 mount flags','NTFS_DEFAULT | NTFS_RECOVER' in s),
('no FORCE flags','NTFS_FORCE' not in s),
('no read-only in reader','NTFS_READ_ONLY | NTFS_FORCE' not in s),
('no GPT parser active','fm3d_mount_gpt_ntfs' not in s),
('no IsInserted gate in refresh','PS3_NTFS_IsInserted(usb)' not in s[s.find('static bool refresh_usb_state'):s.find('static int mount_bd_iso')]),
('no IsInserted gate before file_to_sectors','!PS3_NTFS_IsInserted(movie.usb_id)' not in s),
('direct media path','std::string(g_mounts[usb][part].name) + ":/" + current_folder()' in s),
('colon fallback','root = n + "/" + current_folder();' in s),
('no external mkdir','ps3ntfs_mkdir(root.c_str(), 0777)' not in s),
('triangle manual scan','TRIANGLE manual NTFS refresh enter' in main),
('12x100ms enumeration wait','for(int i=0; i<12 && app_running; ++i)' in s),
('two mount attempts','V3 first mount' in s and 'V3 retry mount' in s),
('BDISO and MKV retained','return g_tab == TAB_BDISO ? "BDISO" : "MKV"' in s),
('raw iso sectors retained','ps3ntfs_file_to_sectors(movie.path.c_str()' in s),
('raw iso plugin retained','cobra_load_vsh_plugin' in s),
('persistent log retained','FLOW_MOVIE_3D_BOOT.LOG' in s),
('L1/R1 retained','pad.BTN_L1' in main and 'pad.BTN_R1' in main and 'pad.BTN_R2' not in main),
]
failed=[]
for i,(name,ok) in enumerate(checks,1):
 print(f'{"PASS" if ok else "FAIL"} {i:02d} {name}')
 if not ok: failed.append(name)
print(f'V4.6.3 RESTORED NTFS GATES: {len(checks)-len(failed)}/{len(checks)} PASS')
if failed: raise SystemExit(1)
