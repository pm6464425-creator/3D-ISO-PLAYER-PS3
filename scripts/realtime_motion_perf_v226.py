from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

# V2.26 REALTIME MOTION PERF
# 1) Integrate the spring using real elapsed time, subdivided into <= 1/60 s
#    steps. A 30 Hz frame therefore advances about two simulation steps instead
#    of making the coverflow run at half speed.
# 2) If the previous real frame was already slow, reduce only peripheral REAL
#    cover transfers while moving. Case geometry remains visible and all covers
#    return at full quality as soon as motion settles.

if 'V2.26 REALTIME MOTION PERF' not in s:
    # Frame time exported by flow_update for adaptive moving-cover LOD.
    anchor = 'static bool g_flow_ready = false;\n'
    if anchor not in s:
        raise SystemExit('flow globals anchor not found')
    s = s.replace(anchor, anchor + 'static float g_flow_frame_dt = 1.0f/60.0f;\n', 1)

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

    # Adaptive LOD only affects real artwork transfers during motion. At normal
    # 60 Hz all five visible covers are still sent. If we have already fallen
    # to ~30 Hz, keep the central/adjacent art and skip only the tiny far pair.
    old = '''            for(int i=0;i<nitems;i++) {\n                bool active=fabsf(items[i].d)<0.34f;\n                draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,false,1);\n            }\n'''
    new = '''            const bool cover_lod=(g_flow_frame_dt>0.024f);\n            for(int i=0;i<nitems;i++) {\n                if(cover_lod && fabsf(items[i].d)>1.35f) continue;\n                bool active=fabsf(items[i].d)<0.34f;\n                draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,false,1);\n            }\n'''
    if old not in s:
        raise SystemExit('moving RSX cover loop anchor not found')
    s = s.replace(old,new,1)

markers = [
    'V2.26 REALTIME MOTION PERF',
    'static float g_flow_frame_dt = 1.0f/60.0f;',
    'gettimeofday(&tv,NULL);',
    'while(remaining>0.00001f && substeps<4)',
    'const bool cover_lod=(g_flow_frame_dt>0.024f);',
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
print('V2.26 realtime motion applied: wall-clock spring + adaptive peripheral cover LOD')
