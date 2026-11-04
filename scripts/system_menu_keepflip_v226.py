from pathlib import Path

# V2.26 PS HOME MENU LIVE-FLIP:
# Keep presenting previously rendered buffers during the in-game PS menu.
# Completely suspending the GCM flip stream caused the console menu to freeze.
# No coverflow calculations, background draw, input/USB polling or cover decode
# runs while g_system_menu_open is true. Keep the watchdog RAM heartbeat.
p=Path('source/main.cpp')
s=p.read_text()
if 'V2.26 PS HOME MENU LIVE-FLIP' not in s:
    old='''            /* Keep the watchdog informed that this is an intentional pause. */
            freeze_diag_frame_ok();
            /* Next loop pumps sysUtilCheckCallback again. ~125 Hz is responsive
               without burning a PPU core while the XMB overlay is active. */
            usleep(8000);
            continue;'''
    new='''            /* V2.26 PS HOME MENU LIVE-FLIP:
               The PS3 in-game menu requires a live GCM presentation stream.
               Present only previously drawn buffers. This is VSync paced,
               and does not draw backgrounds, particles, covers or frames. */
            flip();
            freeze_diag_frame_ok();
            continue;'''
    if s.count(old)!=1:
        raise SystemExit('Missing/ambiguous original SYSUTIL menu pause block')
    s=s.replace(old,new,1)
    anchor='''        freeze_diag_phase(11); /* AFTER_SYSUTIL */

        /* V2.26 SYSTEM MENU PAUSE:'''
    replacement='''        freeze_diag_phase(11); /* AFTER_SYSUTIL */
        /* The exit request may arrive while the PS menu is open. */
        if(!app_running) break;

        /* V2.26 SYSTEM MENU PAUSE:'''
    if s.count(anchor)!=1:
        raise SystemExit('Cannot locate post-callback early exit anchor')
    s=s.replace(anchor,replacement,1)

begin=s.index('if(g_system_menu_open) {')
end=s.index('        /* V2.26 MICROSTUTTER:',begin)
menu=s[begin:end]
assert 'flip();' in menu
for forbidden in ('render_ui(', 'flow_update(', 'ioPadGetData(', 'refresh_usb_state_slice(', 'cover_prefetch_idle(', 'usleep(8000)'):
    if forbidden in menu: raise SystemExit('Forbidden menu action: '+forbidden)
assert 'if(!app_running) break;' in s
p.write_text(s)
print('PS3 menu live flip patched: zero graphics redraws; ongoing GCM VSync flip; immediate exit callback')
