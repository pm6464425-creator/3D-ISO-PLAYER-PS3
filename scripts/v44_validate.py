from pathlib import Path
import sys

p=Path(sys.argv[1] if len(sys.argv)>1 else 'source/main.cpp')
s=p.read_text()
main=s[s.find('int main('):] if 'int main(' in s else ''
rs=s.find('static void render_ui()')
re=s.find('static void move_selection',rs)
render=s[rs:re] if rs>=0 and re>rs else ''

checks=[]
def check(name,cond,detail=''):
    checks.append((name,bool(cond),detail))

check('01 Tiny3D se inicializa exactamente una vez', s.count('tiny3d_Init(')==1, f"count={s.count('tiny3d_Init(')}")
check('02 no hay bootstrap Mamba/LV2 automatico', 'mamba_bootstrap_if_needed(' not in s)
startup=main.split('while(app_running)',1)[0] if main else ''
check('03 arranque sin escaneo NTFS sincronico', 'refresh_usb_state(true)' not in startup and 'rebuild_movies();' not in startup)
check('04 render sin filesystem ni stb decode', all(x not in render for x in ('ps3ntfs_','stbi_','fopen(','stat(','read_file_bytes','find_movie_cover')))
check('05 escaneo de biblioteca usa worker PPU', 'scan_thread_entry' in s and 'sysThreadCreate(&tid,scan_thread_entry' in s)
check('06 carga/decode de portadas usa worker PPU', 'cover_worker_entry' in s and 'sysThreadCreate(&tid,cover_worker_entry' in s)
check('07 no hay polling NTFS periodico en UI', 'poll_counter' not in main and 'refresh_usb_state(false)' not in main)
check('08 espera RSX limitada y omite primer frame', 'if(!g_gpu_frame_submitted) return;' in s and 'int n=100;' in s)
check('09 categorias usan L1/R1 y no R2', 'pad.BTN_L1' in main and 'pad.BTN_R1' in main and 'pad.BTN_R2' not in main)
check('10 renderer legado fuera y Flip centralizado', all(x not in s for x in ('init_screen(','get_back_buffer(')) and s.count('tiny3d_Flip();')==1 and 'static void flow_end_frame()' in s, f"direct_flips={s.count('tiny3d_Flip();')}")

failed=0
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL'),name,detail)
    failed += 0 if ok else 1
print(f'STABILITY GATES: {len(checks)-failed}/10 PASS')
if failed: raise SystemExit(1)
