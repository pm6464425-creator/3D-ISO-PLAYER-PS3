from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

# V2.26 REALTIME MOTION PERF
# 1) Integrate the spring using real elapsed time, subdivided into <= 1/60 s
#    steps. A 30 Hz frame therefore advances about two simulation steps instead
#    of making the coverflow run at half speed.
# 2) If a real frame has already dropped to ~30 Hz, temporarily reduce only the
#    tiny peripheral REAL-cover transfers while moving. A short hysteresis hold
#    prevents 60/30/60/30 quality oscillation. Full artwork returns at rest.

if 'V2.26 REALTIME MOTION PERF' not in s:
    anchor = 'static bool g_flow_ready = false;\n'
    if anchor not in s:
        raise SystemExit('flow globals anchor not found')
    s = s.replace(anchor,
                  anchor + 'static float g_flow_frame_dt = 1.0f/60.0f;\n'
                           'static int g_cover_lod_hold = 0;\n', 1)

    new_flow = r'''static void flow_update()
{
    const float target = g_movies.empty() ? 0.0f : (float)g_selected;

    struct timeval tv;
    gettimeofday(&tv,NULL);
    uint64_t now_us=(uint64_t)tv.tv_sec*1000000ULL+(uint64_t)tv.tv_usec;
    static uint64_t last_us=0;
    float elapsed=1.0f/60.0f;
    if(last_us!=0 && now_us>last_us) elapsed=(float)(now_us-last_us)/1000000.0f;
    last_us=now_us;

    /* Ignore debugger/IO pauses, but preserve the 30 Hz -> two 60 Hz substeps
       behavior that fixes the visible half-speed bug. */
    if(elapsed<1.0f/240.0f) elapsed=1.0f/240.0f;
    if(elapsed>0.050f) elapsed=0.050f;
    g_flow_frame_dt=elapsed;

    if(!g_flow_ready || fabsf(g_flow_pos-target)>6.0f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
        g_flow_ready=true;
        return;
    }

    /* V2.26 REALTIME MOTION PERF:
       Keep the exact k/damping/max-speed tuning, but advance it by wall-clock
       time. Substeps preserve the original 60 Hz spring shape and stability. */
    const float spring_k=250.0f;
    const float damping=26.0f;
    const float max_speed=7.25f;

    float remaining=elapsed;
    int substeps=0;
    while(remaining>0.00001f && substeps<4) {
        float dt=(remaining>1.0f/60.0f)?(1.0f/60.0f):remaining;
        remaining-=dt;
        ++substeps;

        float delta=target-g_flow_pos;
        float ad=fabsf(delta);
        if(ad<0.0012f && fabsf(g_flow_vel)<0.055f) {
            g_flow_pos=target;
            g_flow_vel=0.0f;
            break;
        }

        float accel=spring_k*delta-damping*g_flow_vel;
        g_flow_vel += accel*dt;
        if(g_flow_vel>max_speed) g_flow_vel=max_speed;
        if(g_flow_vel<-max_speed) g_flow_vel=-max_speed;

        float step=g_flow_vel*dt;
        if((delta>0.0f && step>=delta) || (delta<0.0f && step<=delta)) {
            g_flow_pos=target;
            g_flow_vel=0.0f;
            break;
        }
        g_flow_pos += step;
    }
}
'''

    pat = re.compile(r'static void flow_update\(\)\n\{.*?\n\}\n\nstatic void cover_cache_clear', re.S)
    m = pat.search(s)
    if not m:
        raise SystemExit('flow_update block not found')
    s = s[:m.start()] + new_flow + '\nstatic void cover_cache_clear' + s[m.end():]

    old = '''            for(int i=0;i<nitems;i++) {\n                bool active=fabsf(items[i].d)<0.34f;\n                draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,false,1);\n            }\n'''
    new = '''            if(g_flow_frame_dt>0.024f) g_cover_lod_hold=12;\n            else if(g_cover_lod_hold>0) --g_cover_lod_hold;\n            const bool cover_lod=(g_cover_lod_hold>0);\n            for(int i=0;i<nitems;i++) {\n                if(cover_lod && fabsf(items[i].d)>1.35f) continue;\n                bool active=fabsf(items[i].d)<0.34f;\n                draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,false,1);\n            }\n'''
    if old not in s:
        raise SystemExit('moving RSX cover loop anchor not found')
    s = s.replace(old,new,1)

    # Reset reduced-detail state whenever the coverflow has actually settled.
    old_rest = '''        if(!flow_animating) {\n            /* At rest we keep the exact high-quality case overlay. A fence here\n'''
    new_rest = '''        if(!flow_animating) {\n            g_cover_lod_hold=0;\n            /* At rest we keep the exact high-quality case overlay. A fence here\n'''
    if old_rest not in s:
        raise SystemExit('rest block anchor not found')
    s = s.replace(old_rest,new_rest,1)

markers = [
    'V2.26 REALTIME MOTION PERF',
    'static float g_flow_frame_dt = 1.0f/60.0f;',
    'static int g_cover_lod_hold = 0;',
    'gettimeofday(&tv,NULL);',
    'while(remaining>0.00001f && substeps<4)',
    'if(g_flow_frame_dt>0.024f) g_cover_lod_hold=12;',
    'const bool cover_lod=(g_cover_lod_hold>0);',
    'fabsf(items[i].d)>1.35f',
    'const float spring_k=250.0f',
    'const float damping=26.0f',
    'const float max_speed=7.25f',
]
for marker in markers:
    if marker not in s:
        raise SystemExit('realtime motion invariant missing: '+marker)

if 'const float dt=1.0f/60.0f;' in s[s.find('static void flow_update()'):s.find('static void cover_cache_clear')]:
    raise SystemExit('fixed 60 Hz dt remained in flow_update')

p.write_text(s)
print('V2.26 realtime motion applied: wall-clock spring + hysteretic peripheral cover LOD')
