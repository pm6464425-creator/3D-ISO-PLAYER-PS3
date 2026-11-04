from pathlib import Path

# V2.26 PS MENU STATIC FRONT BUFFER
# Holding PS: keep dispatching GCM flips, but present the SAME last complete
# framebuffer instead of swapping the two buffers without new rendering.
# Normal RSX coverflow and realtime animation are not changed.
mainp=Path('source/main.cpp')
rsxp=Path('source/rsxutil.cpp')
hdrp=Path('include/rsxutil.h')
s=mainp.read_text(); r=rsxp.read_text(); h=hdrp.read_text()

marker='/* V2.26 PS MENU STATIC FRONT BUFFER */'
if marker not in s:
    begin=s.index('        if(g_system_menu_open) {')
    end=s.index('        /* V2.26 MICROSTUTTER:',begin)
    fragment=s[begin:end]
    old='''            flip();
            freeze_diag_frame_ok();
            continue;'''
    new='''            /* V2.26 PS MENU STATIC FRONT BUFFER:
               Keep the system's VSync flip notifications alive, but show
               ONLY the last fully composited front buffer. Reusing normal
               flip() here alternated two unrendered/stale buffers, causing
               black posters when returning from the PS menu. */
            rsx_flip_last_complete();
            freeze_diag_frame_ok();
            continue;'''
    if fragment.count(old)!=1:
        raise SystemExit('menu flip anchor missing or ambiguous')
    s=s[:begin]+fragment.replace(old,new,1)+s[end:]

if 'void rsx_flip_last_complete(void)' not in r:
    anchor='\n\nvoid flip()\n{'
    if r.count(anchor)!=1: raise SystemExit('flip anchor missing or ambiguous')
    fn=r'''
/* V2.26 PS MENU STATIC FRONT BUFFER
   curr_fb is the back buffer (next normal draw target).
   curr_fb^1 is the framebuffer that normal flip() LAST displayed.
   The PS/XMB overlay needs continuing gcmSetFlip submissions; it does
   NOT need alternating buffers which the app has stopped rendering. */
void rsx_flip_last_complete(void)
{
    if(first_fb) {
        /* Early menu before any complete scene: maintain original behavior. */
        flip();
        return;
    }

    freeze_diag_phase(50); /* FLIP_ENTER */
    freeze_diag_phase(51); /* GCM_SET_FLIP */
    gcmSetFlip(context,curr_fb ^ 1u);
    freeze_diag_phase(52); /* RSX_FLUSH */
    rsxFlushBuffer(context);
    freeze_diag_phase(53); /* WAIT_FLIP */
    waitflip();

    /* No curr_fb toggle, no setRenderTarget. Return to the same pending
       backbuffer on MENU_CLOSE; the next render_ui draws it fully. */

    /* Long PS-menu sessions still need command FIFO maintenance.
       This very infrequent safe backend fence also allows the existing
       maybe_reset_command_buffer() to recycle its 1 MiB FIFO. */
    static u32 menu_flips=0;
    if(++menu_flips>=240u) {
        menu_flips=0;
        waitFinish();
    }
}
'''
    r=r.replace(anchor,'\n'+fn+anchor,1)

if 'void rsx_flip_last_complete(void);' not in h:
    anchor='void flip(void);\n'
    if h.count(anchor)!=1:raise SystemExit('header flip anchor missing')
    h=h.replace(anchor,anchor+'void rsx_flip_last_complete(void);\n',1)

begin=s.index('        if(g_system_menu_open) {')
end=s.index('        /* V2.26 MICROSTUTTER:',begin)
menu=s[begin:end]
assert 'rsx_flip_last_complete();' in menu
assert '\n            flip();' not in menu
for forbidden in ('render_ui(', 'flow_update(', 'ioPadGetData(', 'refresh_usb_state_slice(', 'cover_prefetch_idle('):
    assert forbidden not in menu,forbidden
fn=r[r.index('void rsx_flip_last_complete(void)'):r.index('\n\nvoid flip()',r.index('void rsx_flip_last_complete(void)'))]
assert 'gcmSetFlip(context,curr_fb ^ 1u);' in fn
assert 'curr_fb ^= 1' not in fn and 'setRenderTarget(' not in fn
assert 'waitflip();' in fn and 'waitFinish();' in fn
mainp.write_text(s);rsxp.write_text(r);hdrp.write_text(h)
print('Verified static-front PS menu flip: no buffer toggling, menu still VSync paced, render untouched')
