from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# This script is applied after case_v26.py.

# Real-time delta for coverflow physics. Keeps transition duration correct even
# if a frame occasionally misses a VSync.
if '#include <sys/time.h>' not in s:
    s=s.replace('#include <sys/stat.h>\n', '#include <sys/stat.h>\n#include <sys/time.h>\n', 1)

old='''static void flow_update()\n{\n    float target = g_movies.empty() ? 0.0f : (float)g_selected;\n    if(!g_flow_ready || fabsf(g_flow_pos-target)>6.0f) {\n        g_flow_pos=target;\n        g_flow_vel=0.0f;\n        g_flow_ready=true;\n        return;\n    }\n    const float dt=1.0f/60.0f;\n    const float w=21.0f;'''
new='''static void flow_update()\n{\n    static uint64_t last_us=0;\n    struct timeval tv;\n    gettimeofday(&tv,NULL);\n    uint64_t now_us=(uint64_t)tv.tv_sec*1000000ULL+(uint64_t)tv.tv_usec;\n    float dt=1.0f/60.0f;\n    if(last_us!=0 && now_us>last_us) {\n        dt=(float)(now_us-last_us)/1000000.0f;\n        if(dt<1.0f/240.0f) dt=1.0f/240.0f;\n        if(dt>1.0f/20.0f) dt=1.0f/20.0f;\n    }\n    last_us=now_us;\n\n    float target = g_movies.empty() ? 0.0f : (float)g_selected;\n    if(!g_flow_ready || fabsf(g_flow_pos-target)>6.0f) {\n        g_flow_pos=target;\n        g_flow_vel=0.0f;\n        g_flow_ready=true;\n        return;\n    }\n    const float w=21.0f;'''
if old not in s:
    raise SystemExit('flow_update anchor not found')
s=s.replace(old,new,1)

start=s.find('static void draw_rgba_scaled(int x, int y, int w, int h, const CoverBitmap *c)')
end=s.find('\nstatic void draw_cover_reflection',start)
if start<0 or end<0:
    raise SystemExit('draw_rgba_scaled block not found')
new_scaled=r'''static void draw_rgba_scaled(int x, int y, int w, int h, const CoverBitmap *c)
{
    if(!c || !c->rgba || w<=0 || h<=0 || c->w<=0 || c->h<=0) return;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    if(x>=sw || y>=sh || x+w<=0 || y+h<=0) return;
    u32 *fb=get_back_buffer();
    uint32_t xstep=((uint32_t)c->w << 16) / (uint32_t)w;
    uint32_t ystep=((uint32_t)c->h << 16) / (uint32_t)h;

    int y0=y<0?-y:0;
    int y1=(y+h)>sh?sh-y:h;
    int x0=x<0?-x:0;
    int x1=(x+w)>sw?sw-x:w;
    uint32_t syfp=(uint32_t)y0*ystep;

    for(int yy=y0; yy<y1; ++yy, syfp+=ystep) {
        int py=y+yy;
        int sy=(int)(syfp >> 16); if(sy>=c->h) sy=c->h-1;
        uint32_t sxfp=(uint32_t)x0*xstep;
        u32 *dst=fb+(size_t)py*sw+(x+x0);
        for(int xx=x0; xx<x1; ++xx, sxfp+=xstep, ++dst) {
            int sx=(int)(sxfp >> 16); if(sx>=c->w) sx=c->w-1;
            const unsigned char *sp=c->rgba+((size_t)sy*c->w+sx)*4;
            unsigned int a=sp[3];
            u32 col=0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
            if(a==255) *dst=col;
            else if(a) blend_pixel(x+xx,py,col,a);
        }
    }
}

/* Scale only a source rectangle.  V2.6 used the whole 640x822 RGBA frame,
   spending most CPU time walking the transparent artwork window. */
static void draw_rgba_region_scaled(int x,int y,int w,int h,const CoverBitmap *c,
                                    int sx0,int sy0,int sw0,int sh0)
{
    if(!c || !c->rgba || w<=0 || h<=0 || sw0<=0 || sh0<=0) return;
    int screen_w=(int)get_screen_width(), screen_h=(int)get_screen_height();
    if(x>=screen_w || y>=screen_h || x+w<=0 || y+h<=0) return;
    if(sx0<0) { sw0+=sx0; sx0=0; }
    if(sy0<0) { sh0+=sy0; sy0=0; }
    if(sx0+sw0>c->w) sw0=c->w-sx0;
    if(sy0+sh0>c->h) sh0=c->h-sy0;
    if(sw0<=0 || sh0<=0) return;

    u32 *fb=get_back_buffer();
    uint32_t xstep=((uint32_t)sw0 << 16)/(uint32_t)w;
    uint32_t ystep=((uint32_t)sh0 << 16)/(uint32_t)h;
    int dy0=y<0?-y:0;
    int dy1=(y+h)>screen_h?screen_h-y:h;
    int dx0=x<0?-x:0;
    int dx1=(x+w)>screen_w?screen_w-x:w;
    uint32_t syfp=(uint32_t)dy0*ystep;

    for(int yy=dy0;yy<dy1;++yy,syfp+=ystep) {
        int sy=sy0+(int)(syfp>>16); if(sy>=sy0+sh0) sy=sy0+sh0-1;
        uint32_t sxfp=(uint32_t)dx0*xstep;
        int py=y+yy;
        u32 *dst=fb+(size_t)py*screen_w+(x+dx0);
        for(int xx=dx0;xx<dx1;++xx,sxfp+=xstep,++dst) {
            int sx=sx0+(int)(sxfp>>16); if(sx>=sx0+sw0) sx=sx0+sw0-1;
            const unsigned char *sp=c->rgba+((size_t)sy*c->w+sx)*4;
            unsigned int a=sp[3];
            if(!a) continue;
            u32 col=0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
            if(a==255) *dst=col;
            else blend_pixel(x+xx,py,col,a);
        }
    }
}
'''
s=s[:start]+new_scaled+s[end:]

# Cull whole movie cases before doing any scaling.
needle='''static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)\n{\n    /* V2.6: one remastered rounded Blu-ray frame with transparent artwork window.'''
replacement='''static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)\n{\n    int screen_w=(int)get_screen_width(), screen_h=(int)get_screen_height();\n    if(x>=screen_w || y>=screen_h || x+w<=0 || y+h<=0) return;\n\n    /* V2.7: optimized rounded Blu-ray renderer. The visual master is unchanged,\n       but only the non-transparent border bands are sampled. */'''
if needle not in s:
    raise SystemExit('draw_poster header anchor not found')
s=s.replace(needle,replacement,1)

# Reflection only on selected case; side reflections are expensive and mostly invisible.
s=s.replace('''        draw_rgba_scaled(ax,ay,aw,ah,c);\n        draw_cover_reflection(x,y+h+7,w,h,c);''',
            '''        draw_rgba_scaled(ax,ay,aw,ah,c);\n        if(selected) draw_cover_reflection(x,y+h+7,w,h,c);''',1)

old_frame='''    /* The complete anti-aliased case is composited in one pass. */\n    if(g_case_frame.rgba) {\n        draw_rgba_scaled(x,y,w,h,&g_case_frame);\n    }'''
new_frame='''    /* Same single remastered frame, sampled as four overlapping regions.\n       This preserves its curved corners and alpha while avoiding the huge\n       transparent center on every movie, every frame. */\n    if(g_case_frame.rgba) {\n        int fw=g_case_frame.w, fh=g_case_frame.h;\n        int top_src=fh*88/822; if(top_src<1) top_src=1;\n        int bot_y=fh*790/822; if(bot_y<0) bot_y=0;\n        int side_y=fh*64/822;\n        int side_h=fh*748/822; if(side_y+side_h>fh) side_h=fh-side_y;\n        int edge=fw*18/640; if(edge<2) edge=2;\n        int top_dst=h*88/822; if(top_dst<2) top_dst=2;\n        int bot_dst_y=h*790/822;\n        int side_dst_y=h*64/822;\n        int side_dst_h=h*748/822;\n        int edge_dst=w*18/640; if(edge_dst<2) edge_dst=2;\n\n        draw_rgba_region_scaled(x,y,w,top_dst,&g_case_frame,0,0,fw,top_src);\n        draw_rgba_region_scaled(x,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,0,side_y,edge,side_h);\n        draw_rgba_region_scaled(x+w-edge_dst,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,fw-edge,side_y,edge,side_h);\n        draw_rgba_region_scaled(x,y+bot_dst_y,w,h-bot_dst_y,&g_case_frame,0,bot_y,fw,fh-bot_y);\n    }'''
if old_frame not in s:
    raise SystemExit('case frame block anchor not found')
s=s.replace(old_frame,new_frame,1)

# At most seven candidates; with bbox culling this normally means 3-5 actually drawn.
s=s.replace('for(int idx=base-5;idx<=base+5;idx++) {','for(int idx=base-3;idx<=base+3;idx++) {',1)
s=s.replace('if(a>4.6f) continue;','if(a>3.35f) continue;',1)

p.write_text(s)
print('FLOW MOVIE V2.7: real-time motion + clipped blits + border-only frame sampling + culling')
