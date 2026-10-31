from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def replace_once(old: str, new: str, label: str):
    global s
    if old not in s:
        raise SystemExit(f'{label} anchor not found')
    s = s.replace(old, new, 1)

# FLOW V2 DYNAMIC 60FPS keeps the proven software framebuffer/NTFS backend.
# Only input mapping, animation timing and on-screen shoulder labels are changed.

# Correct shoulder mapping: previous tab = L1, next tab = R1.
replace_once(
    'bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_r1=false,p_r2=false;',
    'bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_l1=false,p_r1=false;',
    'previous shoulder state')

replace_once(
    'bool r1=pad.BTN_R1, r2=pad.BTN_R2;',
    'bool l1=pad.BTN_L1, r1=pad.BTN_R1;',
    'shoulder button read')

replace_once(
    'if(r1 && !p_r1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; rebuild_movies(); }\n'
    '        if(r2 && !p_r2) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; rebuild_movies(); }',
    'if(l1 && !p_l1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; rebuild_movies(); g_flow_ready=false; }\n'
    '        if(r1 && !p_r1) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; rebuild_movies(); g_flow_ready=false; }',
    'shoulder actions')

replace_once(
    'p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_r1=r1; p_r2=r2;',
    'p_up=up; p_down=down; p_left=left; p_right=right; p_x=x; p_o=o; p_tri=tri; p_l1=l1; p_r1=r1;',
    'shoulder state update')

# Correct the UI badges and footer help to match the physical buttons.
s = s.replace('text_width("R2",1,4)', 'text_width("L1",1,4)')
s = s.replace('"R2",1,0xFFC7CED4,4', '"L1",1,0xFFC7CED4,4')
s = s.replace('R1/R2  CAMBIAR', 'L1/R1  CAMBIAR')

# The RSX backend already uses GCM_FLIP_VSYNC and flip() waits for the display flip.
# An additional 16-20 ms usleep after every rendered frame effectively throttles the UI.
# Remove that extra sleep so coverflow can present on every VSync (60 Hz on a 60 Hz display).
if '        usleep(30000);\n' in s:
    s = s.replace('        usleep(30000);\n', '', 1)
elif '        usleep(20000);\n' in s:
    s = s.replace('        usleep(20000);\n', '', 1)
elif '        usleep(16000);\n' in s:
    s = s.replace('        usleep(16000);\n', '', 1)
else:
    raise SystemExit('frame pacing anchor not found')

# One spring integration step per VSync/frame at 60 Hz.
# Keeping the physics at 60 Hz prevents the interpolation from looking stepped.
if 'const float dt=1.0f/50.0f;' in s:
    s = s.replace('const float dt=1.0f/50.0f;', 'const float dt=1.0f/60.0f;', 1)
elif 'const float dt=1.0f/60.0f;' not in s:
    raise SystemExit('flow dt anchor not found')

# Responsive critically damped movement without hard jumps.
if 'const float w=20.0f;' in s:
    s = s.replace('const float w=20.0f;', 'const float w=21.0f;', 1)
elif 'const float w=18.0f;' in s:
    s = s.replace('const float w=18.0f;', 'const float w=21.0f;', 1)
else:
    raise SystemExit('flow spring anchor not found')

p.write_text(s)
print('FLOW MOVIE 3D V2 DYNAMIC 60FPS: VSync-paced coverflow + L1/R1 edge-trigger controls applied')
