from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

new_block = r'''/* V226_BIGGER_SMOOTHER_FINAL: large soft sprites + continuous fixed-point drift. */
static inline void live_blend_fast(u32 *fb,int sw,int sh,int x,int y,u32 color,unsigned int alpha)
{
    if((unsigned int)x>=(unsigned int)sw || (unsigned int)y>=(unsigned int)sh || alpha==0) return;
    if(alpha>255u) alpha=255u;
    u32 *p=fb+(size_t)y*(size_t)sw+(size_t)x;
    u32 d=*p;
    unsigned int sr=(color>>16)&255u, sg=(color>>8)&255u, sb=color&255u;
    unsigned int dr=(d>>16)&255u, dg=(d>>8)&255u, db=d&255u;
    unsigned int ia=255u-alpha;
    unsigned int rr=(sr*alpha+dr*ia)/255u;
    unsigned int gg=(sg*alpha+dg*ia)/255u;
    unsigned int bb=(sb*alpha+db*ia)/255u;
    *p=0xFF000000u|(rr<<16)|(gg<<8)|bb;
}

/* One soft particle is rasterized once around its true 8.8 fixed-point center.
   The alpha footprint itself moves subpixel-by-subpixel, so the visible centroid
   changes every frame without drawing four copies of a large halo. */
static void live_soft_particle_fp(u32 *fb,int sw,int sh,int xfp,int yfp,int radius,u32 color,unsigned int alpha)
{
    if(radius<1 || alpha==0) return;
    int cx=xfp>>8, cy=yfp>>8;
    int bound=radius+2;
    long long core_fp=(long long)((radius*3+2)/5)*256LL;
    long long outer_fp=(long long)(radius+2)*256LL;
    long long core2=core_fp*core_fp;
    long long outer2=outer_fp*outer_fp;
    long long fade_den=outer2-core2;
    if(fade_den<1) fade_den=1;

    for(int py=cy-bound;py<=cy+bound;++py) {
        if((unsigned int)py>=(unsigned int)sh) continue;
        long long dy=((long long)py<<8)-(long long)yfp;
        for(int px=cx-bound;px<=cx+bound;++px) {
            if((unsigned int)px>=(unsigned int)sw) continue;
            long long dx=((long long)px<<8)-(long long)xfp;
            long long d2=dx*dx+dy*dy;
            if(d2>outer2) continue;
            unsigned int a;
            if(d2<=core2) a=alpha;
            else a=(unsigned int)(((long long)alpha*(outer2-d2))/fade_den);
            if(a) live_blend_fast(fb,sw,sh,px,py,color,a);
        }
    }
}

static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    unsigned int f=g_frame;

    /* Full-HD artwork remains fixed; only overlays move. */
    rsx_draw_hq_background(0xFF03070D);
    u32 *fb=get_back_buffer();

    /* 60 BIG particles. 40x radius 6, 15x radius 7, 5x radius 8.
       Constant fixed-point velocity + offscreen wrap = continuous drift with
       no triangle-wave reversals and no integer-position pauses. */
    int top=24;
    int bottom=(int)(sh*0.60f);
    if(bottom<top+160) bottom=top+160;
    if(bottom>sh-20) bottom=sh-20;
    const int margin=14;
    int track_w=sw+margin*2;
    int track_h=(bottom-top)+margin*2;
    long long track_w_fp=(long long)track_w<<8;
    long long track_h_fp=(long long)track_h<<8;

    for(int i=0;i<60;++i) {
        unsigned int seed=(unsigned int)(97+i*131);
        int vx_fp=90+(i%7)*14;          /* 0.35 .. 0.68 px/frame */
        int vy_fp=20+(i%6)*7;           /* 0.08 .. 0.21 px/frame */

        long long sx=((long long)((seed*211u)%((unsigned int)track_w))<<8);
        long long sy=((long long)((seed*157u)%((unsigned int)track_h))<<8);
        long long px=(sx+(long long)f*(long long)vx_fp)%track_w_fp;
        long long py=(sy+(long long)f*(long long)vy_fp)%track_h_fp;

        int xfp;
        if(i&1) xfp=((sw+margin)<<8)-(int)px;
        else    xfp=-(margin<<8)+(int)px;

        int yfp;
        if((i%3)==0) yfp=((bottom+margin)<<8)-(int)py;
        else         yfp=((top-margin)<<8)+(int)py;

        int radius=(i<40)?6:((i<55)?7:8);
        int pulse=178+live_tri_wave(f+seed*7u,180+(i%5)*23,46);
        if(pulse<118) pulse=118;
        if(pulse>228) pulse=228;

        u32 col=(i%7==0)?0xFF8CE3FF:((i%3==0)?0xFF54C4ED:0xFF2E98D0);
        live_soft_particle_fp(fb,sw,sh,xfp,yfp,radius,col,(unsigned int)pulse);
    }

    /* Lightweight wave accents: short moving streaks instead of full-width
       CPU blended ribbons. This frees substantial per-frame CPU time. */
    for(int i=0;i<3;++i) {
        int range=sw+220;
        int speed_fp=96+i*18;           /* 0.375 .. 0.516 px/frame */
        long long track=(long long)range<<8;
        long long pos=((long long)f*speed_fp+(long long)i*613*256LL)%track;
        int gx=(int)(pos>>8)-110;
        int gy=(int)(sh*(0.365f+0.055f*(float)i));
        live_aa_line(gx-42,gy,gx+42,gy,0xFF4BBBE8,(unsigned int)(46+i*8));
    }

    /* Four soft glints use the same efficient subpixel sprite renderer. */
    for(int i=0;i<4;++i) {
        int range=sw+260;
        int speed_fp=104+i*13;
        long long track=(long long)range<<8;
        long long pos=((long long)f*speed_fp+(long long)i*(sw/4+91)*256LL)%track;
        int gx_fp=(int)pos-(130<<8);
        int gy=(int)(sh*(0.315f+0.066f*(float)i));
        int pulse=150+live_tri_wave(f+(unsigned int)i*73u,170+i*21,58);
        if(pulse<82) pulse=82;
        if(pulse>220) pulse=220;
        live_soft_particle_fp(fb,sw,sh,gx_fp,gy<<8,(i==1)?5:4,0xFF91E5FF,(unsigned int)pulse);
    }

    /* Calm floor reflections, kept short and inexpensive. */
    int horizon=(int)(sh*0.627f);
    int sweep1=(int)(f%(unsigned int)(sw+300))-150;
    int sweep2=sw-(int)((f+390u)%(unsigned int)(sw+340))-90;
    live_aa_line(sweep1,horizon+16,sweep1+96,horizon+16,0xFF3988AC,58u);
    live_aa_line(sweep2,horizon+36,sweep2+72,horizon+36,0xFF256782,44u);
}
'''

pat=re.compile(r'/\* V226_XL_SAFE_RENDER:.*?\nstatic void draw_background\(\)\n\{.*?\n\}\n\nstatic void draw_rgba_scaled',re.S)
m=pat.search(s)
if not m:
    pat=re.compile(r'/\* V226_SUBPIXEL_60FPS:.*?\nstatic void draw_background\(\)\n\{.*?\n\}\n\nstatic void draw_rgba_scaled',re.S)
    m=pat.search(s)
if not m:
    raise SystemExit('particle/background block not found')

s=s[:m.start()]+new_block+'\nstatic void draw_rgba_scaled'+s[m.end():]

s=s.replace('    fps_tick();\n','')
s=re.sub(r'\n\s*char fpsbuf\[96\];.*?draw_text\(18,18,fpsbuf,1,0xFFFFFFFF,80\);\n','\n',s,count=1,flags=re.S)
if 'fps_tick();' in s or 'FPS %.1f' in s:
    raise SystemExit('FPS overlay unexpectedly present')

p.write_text(s)
print('V2.26 BIGGER+SMOOTHER FINAL applied: 60 soft particles r6/r7/r8, constant fixed-point drift, lightweight accents')
