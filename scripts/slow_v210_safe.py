from pathlib import Path

# FLOW MOVIE V2.10 SAFE
# Start from the proven V2.8 HARD PERF renderer and replace only the spring
# movement with a bounded, constant-speed coverflow. This avoids the V2.9
# slow-spring regression while keeping a visibly slower transition.

p = Path('source/main.cpp')
s = p.read_text()

old = '''    const float w=21.0f;
    float x0=g_flow_pos-target;
    float e=expf(-w*dt);
    float tmp=(g_flow_vel+w*x0)*dt;
    g_flow_pos=target+(x0+tmp)*e;
    g_flow_vel=(g_flow_vel-w*tmp)*e;
    if(fabsf(g_flow_pos-target)<0.0008f && fabsf(g_flow_vel)<0.002f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
    }
'''

new = '''    /* V2.10 SAFE: fixed coverflow travel speed.
       ~0.58 s per cover, no spring, no overshoot. */
    const float covers_per_second=1.72f;
    float delta=target-g_flow_pos;
    float max_step=covers_per_second*dt;
    if(fabsf(delta)<=max_step) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
    } else {
        g_flow_pos += (delta>0.0f ? max_step : -max_step);
        g_flow_vel=0.0f;
    }
'''

if old not in s:
    raise SystemExit('V2.8 flow block anchor not found')

s = s.replace(old, new, 1)
p.write_text(s)
print('FLOW MOVIE V2.10 SAFE: fixed-speed smooth coverflow (~0.58 s/cover)')
