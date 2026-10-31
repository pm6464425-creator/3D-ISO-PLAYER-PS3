from pathlib import Path

# FLOW MOVIE V2.8 HARD PERF
# This pass is intentionally aggressive: the previous builds were still
# repainting the complete 720p/1080p framebuffer from the PPU every frame.

main_path = Path('source/main.cpp')
hdr_path = Path('include/rsxutil.h')
rsx_path = Path('source/rsxutil.cpp')

s = main_path.read_text()
h = hdr_path.read_text()
r = rsx_path.read_text()

# ---------------------------------------------------------------------------
# 1. GPU clear. The full-screen software gradient was the largest guaranteed
#    per-frame CPU cost. Clear the current RSX render target in hardware and
#    keep only a few cheap accent lines on the CPU.
# ---------------------------------------------------------------------------
if 'void rsx_clear_backbuffer(u32 color);' not in h:
    h = h.replace('u32 get_screen_height(void);\n',
                  'u32 get_screen_height(void);\nvoid rsx_clear_backbuffer(u32 color);\n', 1)

if 'void rsx_clear_backbuffer(u32 color)' not in r:
    marker = '\nvoid flip()\n'
    pos = r.find(marker)
    if pos < 0:
        raise SystemExit('rsx flip anchor not found')
    helper = '''
void rsx_clear_backbuffer(u32 color)
{
    /* Hardware clear instead of millions of PPU framebuffer writes. */
    rsxSetClearColor(context,color);
    rsxClearSurface(context,GCM_CLEAR_R|GCM_CLEAR_G|GCM_CLEAR_B|GCM_CLEAR_A);
    waitFinish();
}
'''
    r = r[:pos] + helper + r[pos:]

bg_start = s.find('static void draw_background()')
bg_end = s.find('\nstatic void draw_rgba_scaled', bg_start)
if bg_start < 0 or bg_end < 0:
    raise SystemExit('draw_background block not found')

new_bg = r'''static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();

    /* V2.8 HARD PERF: clear the complete frame on the RSX.  V2.7 rebuilt
       several million background pixels on the PPU every frame. */
    rsx_clear_backbuffer(0xFF050A10);

    /* Keep the visual language with only a handful of cheap primitives. */
    int horizon=(int)(sh*0.627f);
    fill_rect(0,horizon,sw,2,0xFF12639A);
    fill_rect(0,horizon+2,sw,3,0xFF071725);
    fill_rect(0,sh-((int)(sh*0.050f)),sw,1,0xFF244B65);
}
'''
s = s[:bg_start] + new_bg + s[bg_end:]

# ---------------------------------------------------------------------------
# 2. Remove the remaining expensive per-pixel alpha effects while measuring.
#    We keep the cover artwork and a lightweight case outline.
# ---------------------------------------------------------------------------
s = s.replace('        if(selected) draw_cover_reflection(x,y+h+7,w,h,c);',
              '        /* V2.8 HARD PERF: reflection disabled; it was CPU alpha blended. */', 1)

case_begin = s.find('    /* Same single remastered frame, sampled as four overlapping regions.')
case_end = s.find('\n    if(selected) {', case_begin)
if case_begin < 0 or case_end < 0:
    raise SystemExit('V2.7 case frame block not found')

simple_case = r'''    /* V2.8 HARD PERF: lightweight case outline.  The previous PNG frame still
       required thousands of alpha blends per visible cover every frame. */
    u32 edge = selected ? 0xFF5FCFFF : 0xFF24465A;
    int bw = selected ? 3 : 2;
    fill_rect(x,y,w,bw,edge);
    fill_rect(x,y+h-bw,w,bw,edge);
    fill_rect(x,y,bw,h,edge);
    fill_rect(x+w-bw,y,bw,h,edge);
'''
s = s[:case_begin] + simple_case + s[case_end:]

# Draw only five candidates. With coverflow geometry this is enough to preserve
# the center + two neighbors per side and removes unnecessary scaling work.
s = s.replace('for(int idx=base-3;idx<=base+3;idx++) {',
              'for(int idx=base-2;idx<=base+2;idx++) {', 1)
s = s.replace('if(a>3.35f) continue;', 'if(a>2.35f) continue;', 1)

# ---------------------------------------------------------------------------
# 3. Real FPS meter. We need a number from the actual PS3 instead of estimating
#    by eye. It updates twice per second and includes output resolution.
# ---------------------------------------------------------------------------
render_anchor = 'static void render_ui()\n{'
if render_anchor not in s:
    raise SystemExit('render_ui anchor not found')

fps_code = r'''static float g_real_fps=0.0f;
static unsigned int g_fps_frames=0;
static uint64_t g_fps_start_us=0;

static void fps_tick()
{
    struct timeval tv;
    gettimeofday(&tv,NULL);
    uint64_t now=(uint64_t)tv.tv_sec*1000000ULL+(uint64_t)tv.tv_usec;
    if(g_fps_start_us==0) g_fps_start_us=now;
    g_fps_frames++;
    uint64_t elapsed=now-g_fps_start_us;
    if(elapsed>=500000ULL) {
        g_real_fps=(float)g_fps_frames*1000000.0f/(float)elapsed;
        g_fps_frames=0;
        g_fps_start_us=now;
    }
}

static void render_ui()
{'''
s = s.replace(render_anchor, fps_code, 1)

s = s.replace('    flow_update();\n    draw_background();',
              '    flow_update();\n    fps_tick();\n    draw_background();', 1)

# Put the meter in the top-left, away from the centered title/tabs.
footer_anchor = '    int footer_h=(int)(sh*0.050f); if(footer_h<34) footer_h=34;'
if footer_anchor not in s:
    raise SystemExit('footer anchor not found')
fps_draw = r'''    char fpsbuf[96];
    snprintf(fpsbuf,sizeof(fpsbuf),"FPS %.1f   %dx%d   V2.8 HARD PERF",g_real_fps,sw,sh);
    draw_text(18,18,fpsbuf,1,0xFFFFFFFF,80);

'''
s = s.replace(footer_anchor, fps_draw + footer_anchor, 1)

main_path.write_text(s)
hdr_path.write_text(h)
rsx_path.write_text(r)

print('FLOW MOVIE V2.8 HARD PERF: RSX clear + simple cases + 5 covers + real FPS meter')
