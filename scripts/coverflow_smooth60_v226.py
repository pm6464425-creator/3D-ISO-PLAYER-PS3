from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 coverflow smoothness fix.
# Keep the approved background/particles untouched.  This patch changes only
# coverflow motion and cover-loading behavior during transitions.

# Keep a wider neighborhood resident so new side covers do not churn the cache.
s=s.replace('#define COVER_CACHE_SLOTS 6','#define COVER_CACHE_SLOTS 10',1)

new_flow=r'''static void flow_update()
{
    const float target = g_movies.empty() ? 0.0f : (float)g_selected;
    if(!g_flow_ready || fabsf(g_flow_pos-target)>6.0f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
        g_flow_ready=true;
        return;
    }

    /* V2.26 COVERFLOW_SMOOTH60:
       One fixed 60 Hz simulation step per rendered frame means a slow frame
       never becomes a large spatial jump.  Acceleration/braking removes the
       previous abrupt constant-speed start/stop. */
    const float dt=1.0f/60.0f;
    const float max_speed=1.40f; /* covers / second */
    const float accel=7.50f;     /* covers / second^2 */

    float delta=target-g_flow_pos;
    float ad=fabsf(delta);
    if(ad<0.0008f && fabsf(g_flow_vel)<0.025f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
        return;
    }

    float dir=(delta>=0.0f)?1.0f:-1.0f;
    float brake_speed=sqrtf(2.0f*accel*ad);
    float wanted=(brake_speed<max_speed)?brake_speed:max_speed;
    float desired_vel=dir*wanted;
    float max_dv=accel*dt;
    float dv=desired_vel-g_flow_vel;
    if(dv>max_dv) dv=max_dv;
    if(dv<-max_dv) dv=-max_dv;
    g_flow_vel += dv;

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

helper=r'''static CoverBitmap *find_cached_cover(const Movie &m)
{
    if(m.cover.empty()) return NULL;
    for(int i=0;i<COVER_CACHE_SLOTS;i++) {
        if(g_cover_cache[i].rgba && g_cover_cache[i].path == m.cover) {
            g_cover_cache[i].stamp = ++g_cover_stamp;
            return &g_cover_cache[i];
        }
    }
    return NULL;
}

'''
needle='static CoverBitmap *get_movie_cover(const Movie &m)\n'
if needle not in s:
    raise SystemExit('get_movie_cover declaration not found')
s=s.replace(needle,helper+needle,1)

prefetch=r'''
static void cover_prefetch_idle()
{
    static unsigned int idle_tick=0;
    static int phase=0;
    if(g_movies.empty()) { idle_tick=0; phase=0; return; }
    if(fabsf(g_flow_pos-(float)g_selected)>0.010f || fabsf(g_flow_vel)>0.010f) {
        idle_tick=0;
        return;
    }

    /* Any disk/JPEG work happens only while the coverflow is stationary. */
    if((++idle_tick%6u)!=0u) return;
    static const int off[9]={0,1,-1,2,-2,3,-3,4,-4};
    for(int n=0;n<9;n++) {
        int k=(phase+n)%9;
        int idx=g_selected+off[k];
        if(idx<0 || idx>=(int)g_movies.size()) continue;
        if(g_movies[idx].cover.empty()) continue;
        if(find_cached_cover(g_movies[idx])) continue;
        get_movie_cover(g_movies[idx]);
        phase=(k+1)%9;
        return;
    }
    phase=(phase+1)%9;
}
'''
pat2=re.compile(r'(static CoverBitmap \*get_movie_cover\(const Movie &m\)\n\{.*?\n\}\n)(\nstatic void release_port)',re.S)
m2=pat2.search(s)
if not m2:
    raise SystemExit('get_movie_cover body/end not found')
s=s[:m2.start()]+m2.group(1)+prefetch+m2.group(2)+s[m2.end():]

s=s.replace('static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)',
            'static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected, bool allow_cover_load)',1)
s=s.replace('    CoverBitmap *c=get_movie_cover(m);',
            '    CoverBitmap *c=allow_cover_load?get_movie_cover(m):find_cached_cover(m);',1)

old='''        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active);\n        }'''
new='''        bool flow_animating = fabsf(g_flow_pos-(float)g_selected)>0.010f || fabsf(g_flow_vel)>0.010f;\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating);\n        }'''
if old not in s:
    raise SystemExit('draw_poster render loop not found')
s=s.replace(old,new,1)

needle2='''    draw_text((sw-hw)/2,fy+(footer_h-font_height(1))/2,help,1,0xFFD5DADE,110);\n\n    g_frame++;'''
repl2='''    draw_text((sw-hw)/2,fy+(footer_h-font_height(1))/2,help,1,0xFFD5DADE,110);\n\n    cover_prefetch_idle();\n    g_frame++;'''
if needle2 not in s:
    raise SystemExit('render_ui footer anchor not found')
s=s.replace(needle2,repl2,1)

for marker in [
    'V2.26 COVERFLOW_SMOOTH60',
    '#define COVER_CACHE_SLOTS 10',
    'find_cached_cover',
    'cover_prefetch_idle();',
    'allow_cover_load',
    'const float max_speed=1.40f',
]:
    if marker not in s:
        raise SystemExit('missing marker: '+marker)

p.write_text(s)
print('V2.26 coverflow smooth60 applied: fixed-frame accel/decel + idle cover prefetch')
