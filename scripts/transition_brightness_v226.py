from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# V2.26 TRANSITION BRIGHTNESS FIX:
# Keep original realtime motion, PS menu rendering and no-fence GPU cover path.
# Fix full-rectangle black shadow and preserve cases even with an uncached cover.
if 'V2.26 TRANSITION BRIGHTNESS FIX' not in s:
    start = s.index('static void draw_poster(int x, int y, int w, int h,')
    end = s.index('\nstatic int connected_count()', start)
    fn = s[start:end]
    old = '''        int shad=(w>220)?7:4;
        fill_rect(x+shad,y+shad,w,h,0x44000000);
        if(!c) {
            draw_generic_cover(ax,ay,aw,ah,m,selected);
        } else if(!allow_cover_load) {'''
    new = '''        /* V2.26 TRANSITION BRIGHTNESS FIX:
           fill_rect writes literally, so 0x44000000 created a solid black
           rectangle under the artwork, not a transparent drop shadow.
           Draw the shadow ONLY outside the physical case instead. */
        int shad=(w>220)?7:4;
        fill_rect(x+shad,y+h,w,shad,0xFF080E14);
        fill_rect(x+w,y+shad,shad,h-shad,0xFF080E14);
        if(!c) {
            draw_generic_cover(ax,ay,aw,ah,m,selected);
        }
        /* The full frame must also be drawn for uncached nearby posters.
           The former 'else if' skipped the case during coverflow motion. */
        if(!allow_cover_load) {'''
    if fn.count(old) != 1: raise SystemExit('poster anchor missing')
    fn = fn.replace(old, new, 1)
    s = s[:start] + fn + s[end:]

    start = s.index('static void cover_prefetch_idle()')
    end = s.index('\nstatic void release_port(', start)
    fn = s[start:end]
    old = '''    /* Give input/animation ~0.20 s of quiet time before any blocking I/O. */
    if(++idle_tick < 12u) return;'''
    new = '''    /* V2.26 TRANSITION BRIGHTNESS FIX: prefetch adjacent JPGs earlier
       only while completely idle. Never decode during movement. */
    if(++idle_tick < 4u) return;'''
    if fn.count(old) != 1: raise SystemExit('prefetch anchor missing')
    fn = fn.replace(old,new,1)
    s = s[:start] + fn + s[end:]

for marker in ('V2.26 TRANSITION BRIGHTNESS FIX',
               'V2.26 PERSISTENT CASE DURING MOTION',
               'V2.26 REALTIME MOTION PERF',
               'V2.26 PS MENU STATIC FRONT BUFFER',
               'rsx_flip_last_complete();',
               'if(cover_lod && fabsf(items[i].d)>1.35f) continue;',
               'if(++idle_tick < 4u) return;'):
    if marker not in s: raise SystemExit('Invariant missing: '+marker)
fn=s[s.index('static void draw_poster(int x, int y, int w, int h,'):
     s.index('\nstatic int connected_count()',s.index('static void draw_poster(int x, int y, int w, int h,'))]
assert 'fill_rect(x+shad,y+shad,w,h,0x44000000)' not in fn
assert 'else if(!allow_cover_load)' not in fn
assert 'if(!allow_cover_load) {' in fn
p.write_text(s)
print('V2.26 transition brightness fix: opaque black underlay removed, case persistent on cache misses, idle prefetch sooner')
