from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 coverflow motion matched to the supplied 120-fps reference video.
# Measured one-cover transition: about 0.30-0.33 s (~18-20 updates at 60 Hz).
# Best-fit dynamics: damped spring k=250 s^-2, damping=26 s^-1, fixed 60 Hz.
# This patch intentionally keeps the cache/no-JPEG-during-motion changes from
# coverflow_smooth60_v226.py and changes ONLY the coverflow motion law.

new_flow=r'''static void flow_update()
{
    const float target = g_movies.empty() ? 0.0f : (float)g_selected;
    if(!g_flow_ready || fabsf(g_flow_pos-target)>6.0f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
        g_flow_ready=true;
        return;
    }

    /* V2.26 COVERFLOW_REFERENCE_MOTION:
       Matched from the supplied reference video.  The recorded clip is ~120
       fps, while visible cover positions advance on roughly 60 Hz cadence.
       A one-cover move takes ~0.30-0.33 s: quick initial acceleration followed
       by a long smooth ease-out.  Fixed-step integration avoids large jumps if
       one rendered frame happens to be late. */
    const float dt=1.0f/60.0f;
    const float spring_k=250.0f;
    const float damping=26.0f;
    const float max_speed=7.25f; /* covers/second; measured peak is ~7 */

    float delta=target-g_flow_pos;
    float ad=fabsf(delta);
    if(ad<0.0012f && fabsf(g_flow_vel)<0.055f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
        return;
    }

    float accel=spring_k*delta-damping*g_flow_vel;
    g_flow_vel += accel*dt;
    if(g_flow_vel>max_speed) g_flow_vel=max_speed;
    if(g_flow_vel<-max_speed) g_flow_vel=-max_speed;

    float step=g_flow_vel*dt;
    if((delta>0.0f && step>=delta) || (delta<0.0f && step<=delta)) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
    } else {
        g_flow_pos += step;
    }
}
'''

pat=re.compile(r'static void flow_update\(\)\n\{.*?\n\}\n\nstatic void cover_cache_clear',re.S)
m=pat.search(s)
if not m:
    raise SystemExit('flow_update block not found')
s=s[:m.start()]+new_flow+'\nstatic void cover_cache_clear'+s[m.end():]

for marker in [
    'V2.26 COVERFLOW_REFERENCE_MOTION',
    'const float spring_k=250.0f',
    'const float damping=26.0f',
    'const float max_speed=7.25f',
    '#define COVER_CACHE_SLOTS 10',
    'cover_prefetch_idle();',
    'allow_cover_load',
]:
    if marker not in s:
        raise SystemExit('missing marker: '+marker)

p.write_text(s)
print('V2.26 coverflow reference motion applied: ~0.31 s damped-spring transition')
