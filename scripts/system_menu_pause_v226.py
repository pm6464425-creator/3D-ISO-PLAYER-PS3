from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 SYSTEM MENU PAUSE
# The PS3 Home/System Menu must get the CPU/RSX and controller while it is open.
# FLOW MOVIE therefore pumps only sysutil callbacks and sleeps briefly; it does
# not render, poll USB, read pad state, animate, log heartbeat, or submit RSX.

if 'V2.26 SYSTEM MENU PAUSE' not in s:
    anchor='static bool app_running = true;\n'
    if anchor not in s:
        raise SystemExit('app_running anchor missing')
    s=s.replace(anchor,
        anchor+'static volatile bool g_system_menu_open = false; /* V2.26 SYSTEM MENU PAUSE */\n',1)

    old='''static void sysutil_callback(u64 status, u64 param, void *userdata)\n{\n    (void)param; (void)userdata;\n    if(status == SYSUTIL_EXIT_GAME) app_running = false;\n}\n'''
    new='''static void sysutil_callback(u64 status, u64 param, void *userdata)\n{\n    (void)param; (void)userdata;\n    /* V2.26 SYSTEM MENU PAUSE */\n    switch(status) {\n        case SYSUTIL_EXIT_GAME:\n            app_running = false;\n            break;\n        case SYSUTIL_MENU_OPEN:\n            g_system_menu_open = true;\n            break;\n        case SYSUTIL_MENU_CLOSE:\n            g_system_menu_open = false;\n            break;\n        default:\n            break;\n    }\n}\n'''
    if old not in s:
        raise SystemExit('sysutil callback anchor missing')
    s=s.replace(old,new,1)

    old='''        freeze_diag_phase(11); /* AFTER_SYSUTIL */\n\n        /* V2.26 MICROSTUTTER: preserve a full 8-port sweep every ~2 seconds,\n'''
    new='''        freeze_diag_phase(11); /* AFTER_SYSUTIL */\n\n        /* V2.26 SYSTEM MENU PAUSE:\n           Do not compete with the long-press PS-button menu. The system menu\n           owns the controller and compositor until SYSUTIL_MENU_CLOSE. */\n        if(g_system_menu_open) {\n            memset(&pad,0,sizeof(pad));\n            p_up=p_down=p_left=p_right=p_x=p_o=p_tri=p_l1=p_r1=false;\n            repeat_left=repeat_right=0;\n            /* Keep the watchdog informed that this is an intentional pause. */\n            freeze_diag_frame_ok();\n            /* Next loop pumps sysUtilCheckCallback again. ~125 Hz is responsive\n               without burning a PPU core while the XMB overlay is active. */\n            usleep(8000);\n            continue;\n        }\n\n        /* V2.26 MICROSTUTTER: preserve a full 8-port sweep every ~2 seconds,\n'''
    if old not in s:
        raise SystemExit('main-loop sysutil anchor missing')
    s=s.replace(old,new,1)

markers=[
    'static volatile bool g_system_menu_open = false; /* V2.26 SYSTEM MENU PAUSE */',
    'case SYSUTIL_MENU_OPEN:',
    'case SYSUTIL_MENU_CLOSE:',
    'if(g_system_menu_open) {',
    'freeze_diag_frame_ok();',
    'usleep(8000);',
]
for marker in markers:
    if marker not in s:
        raise SystemExit('system-menu invariant missing: '+marker)

p.write_text(s)
print('V2.26 system-menu pause applied: zero FLOW render/input/USB work while PS menu is open')
