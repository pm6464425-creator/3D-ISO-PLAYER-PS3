from pathlib import Path
import sys
s=Path(sys.argv[1] if len(sys.argv)>1 else 'source/main.cpp').read_text()
main=s[s.find('int main('):]
checks=[
('persistent boot log path', 'FLOW_MOVIE_3D_BOOT.LOG' in s and 'bootlog_init()' in main),
('previous boot log preserved', 'FLOW_MOVIE_3D_BOOT_PREV.LOG' in s and 'rename(BOOT_LOG_PATH,BOOT_LOG_PREV)' in s),
('watchdog thread present', 'watchdog_thread_entry' in s and 'sysThreadCreate(&g_watchdog_tid' in s),
('stage logging before Tiny3D', 'boot_stage(2,"tiny3d_Init enter")' in main),
('official conservative Tiny3D 1MiB init', 'tiny3d_Init(1024u*1024u)' in main),
('no custom UserViewport', 'tiny3d_UserViewport(' not in main),
('no direct flip-status polling', 'gcmGetFlipStatus()' not in s),
('no direct RSX depth state in frame begin', 'rsxtiny_DepthTestEnable(ctx' not in s and 'rsxtiny_DepthWriteEnable(ctx' not in s),
('scan and cover operations logged', 'PS3_NTFS_IsInserted enter' in s and 'decode enter' in s),
('mount operations logged', 'ps3ntfs_file_to_sectors enter' in s and 'cobra_load_vsh_plugin enter' in s),
('main-loop heartbeat logged', 'main loop alive movies=' in s),
('L1/R1 retained', 'pad.BTN_L1' in main and 'pad.BTN_R1' in main and 'pad.BTN_R2' not in main),
('Mamba bootstrap still not automatic', 'mamba_bootstrap_if_needed(' not in s),
('scan worker retained', 'sysThreadCreate(&tid,scan_thread_entry' in s),
('cover worker retained', 'sysThreadCreate(&tid,cover_worker_entry' in s),
]
failed=0
for i,(name,ok) in enumerate(checks,1):
    print(('PASS' if ok else 'FAIL'),f'{i:02d}',name)
    failed+=0 if ok else 1
print(f'DIAGNOSTIC/STABILITY GATES: {len(checks)-failed}/{len(checks)} PASS')
raise SystemExit(1 if failed else 0)
