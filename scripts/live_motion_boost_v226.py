from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 HQ smooth-motion fix.
# Goal: visible but moderate motion that updates every 60 Hz frame without the
# integer-position stepping seen in the previous build. Particle positions are
# kept in 8.8 fixed point and bilinearly blended across neighbouring pixels.
# No BDISO/MKV/USB/input/player logic is changed.

new_bg = r'''/* V226_SUBPIXEL_60FPS: 8.8 fixed-point motion for smooth 60 Hz animation. */
static int live_tri_wave_fp(unsigned int tick,int period,int amp_fp)
{
    if(period<4 || amp_fp<=0) return 0;
    int p=(int)(tick%(unsigned int)period);
    int half=period/2;
    int v=(p<half)?p:(period-p);
    long long num=(long long)(v*2-half)*(long long)amp_fp;
    return (int)(num/(long long)half);
}

static void live_glow_point_fp(int xfp,int yfp,int radius,u32 color,unsigned int alpha)
{
    int x=xfp/256, y=yfp/256;
    int fx=xfp-x*256, fy=yfp-y*256;
    if(fx<0) { x--; fx+=256; }
    if(fy<0) { y--; fy+=256; }

    unsigned int w00=(unsigned int)(((256-fx)*(256-fy))>>8);
    unsigned int w10=(unsigned int)((fx*(256-fy))>>8);
    unsigned int w01=(unsigned int)(((256-fx)*fy)>>8);
    unsigned int w11=(unsigned int)((fx*fy)>>8);

    if(w00) live_glow_point(x,  y,  radius,color,(alpha*w00)>>8);
    if(w10) live_glow_point(x+1,y,  radius,color,(alpha*w10)>>8);
    if(w01) live_glow_point(x,  y+1,radius,color,(alpha*w01)>>8);
    if(w11) live_glow_point(x+1,y+1,radius,color,(alpha*w11)>>8);
}

static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    unsigned int f=g_frame;

    /* Full-HD master copied by RSX. The artwork itself never moves, so there
       is no camera shake; only the light/particle layer is animated. */
    rsx_draw_hq_background(0xFF03070D);

    /* 72 particles. Horizontal speed is roughly 0.45-0.55 px/frame and
       vertical speed roughly 0.12-0.22 px/frame. Because positions stay in
       8.8 fixed point, every 60 Hz frame gets a visual interpolation update. */
    for(int i=0;i<72;++i) {
        unsigned int seed=(unsigned int)(53+i*101);
        int usable_w=(sw>100)?sw-100:1;
        int upper_h=(int)(sh*0.60f);
        if(upper_h<120) upper_h=120;

        int bx=50+(int)((seed*73u)%(unsigned int)usable_w);
        int by=34+(int)((seed*47u)%(unsigned int)(upper_h-34));

        int amp_x=22+(i%6)*3;          /* 22..37 px */
        int amp_y=10+(i%5)*2;          /* 10..18 px */
        int per_x=180+(i%8)*18;        /* moderate, continuous drift */
        int per_y=260+(i%7)*24;

        int xfp=(bx<<8)+live_tri_wave_fp(f+seed,per_x,amp_x<<8);
        int yfp=(by<<8)+live_tri_wave_fp(f+seed*3u,per_y,amp_y<<8);

        int pulse=164+live_tri_wave(f+seed*5u,92+(i%7)*13,78);
        if(pulse<72) pulse=72;
        if(pulse>242) pulse=242;

        /* Slightly larger than the previous build, without changing speed:
           most particles are radius 2, some radius 3, with a few radius 4. */
        int r=2;
        if((i%17)==0) r=4;
        else if((i%5)==0) r=3;

        u32 col=(i%6==0)?0xFF78D8FF:((i%3==0)?0xFF45B9E8:0xFF2A91CA);
        live_glow_point_fp(xfp,yfp,r,col,(unsigned int)pulse);
    }

    /* Ribbon highlights move exactly one pixel per rendered frame. At 60 Hz
       this is smooth but still calm: crossing a 1920 px screen takes ~32 s. */
    for(int band=0;band<3;++band) {
        int base_y=(int)(sh*(0.355f+0.052f*(float)band));
        int phase=(int)f+band*61;
        int prev_x=-18;
        int pp=(prev_x+phase)%200; if(pp<0) pp+=200;
        int tri=(pp<100)?pp:(200-pp);
        int prev_y=base_y+(tri-50)*(4+band)/10;

        for(int x=-4;x<sw+20;x+=14) {
            int q=(x+phase)%200; if(q<0) q+=200;
            int t=(q<100)?q:(200-q);
            int y=base_y+(t-50)*(4+band)/10;
            unsigned int a=(unsigned int)(43+band*9);
            live_aa_line(prev_x,prev_y,x,y,(band==0)?0xFF55C9F4:0xFF2D95CA,a);
            prev_x=x; prev_y=y;
        }
    }

    /* Five glints at 0.44-0.56 px/frame, also subpixel blended. */
    for(int i=0;i<5;++i) {
        int range=sw+300;
        int speed_fp=112+(i%3)*16;     /* 0.4375, 0.5, 0.5625 px/frame */
        long long track=(long long)range*256LL;
        long long pos=((long long)f*(long long)speed_fp+
                       (long long)i*(long long)(sw/4+79)*256LL)%track;
        int gx_fp=(int)pos-(150<<8);
        int gy=(int)(sh*(0.31f+0.062f*(float)i));
        int pulse=142+live_tri_wave(f+(unsigned int)i*61u,144+i*17,76);
        if(pulse<72) pulse=72;
        if(pulse>232) pulse=232;

        live_glow_point_fp(gx_fp,gy<<8,(i==2)?3:2,0xFF82DEFF,(unsigned int)pulse);

        int gx=gx_fp/256;
        int frac=gx_fp-gx*256; if(frac<0) { gx--; frac+=256; }
        unsigned int a0=(unsigned int)((pulse*2/3)*(256-frac)>>8);
        unsigned int a1=(unsigned int)((pulse*2/3)*frac>>8);
        if(a0) live_aa_line(gx-18,gy,gx+18,gy,0xFF56BFE8,a0);
        if(a1) live_aa_line(gx-17,gy,gx+19,gy,0xFF56BFE8,a1);
    }

    /* Calm floor reflections: one pixel per frame, no skipped-frame cadence. */
    int horizon=(int)(sh*0.627f);
    int sweep1=(int)(f%(unsigned int)(sw+320))-160;
    int sweep2=sw-(int)((f+420u)%(unsigned int)(sw+360))-100;
    live_aa_line(sweep1,horizon+16,sweep1+128,horizon+16,0xFF3988AC,66u);
    live_aa_line(sweep2,horizon+38,sweep2+96,horizon+38,0xFF256782,50u);
}
'''

pat=re.compile(r'static void draw_background\(\)\n\{.*?\n\}\n\nstatic void draw_rgba_scaled',re.S)
m=pat.search(s)
if not m:
    raise SystemExit('draw_background block not found')
s=s[:m.start()]+new_bg+'\nstatic void draw_rgba_scaled'+s[m.end():]

# Remove the FPS diagnostic system completely from the visible UI and from the
# per-frame path. This also saves the gettimeofday()/snprintf work every frame.
s=re.sub(
    r'\nstatic float g_real_fps=0\.0f;\nstatic unsigned int g_fps_frames=0;\nstatic uint64_t g_fps_start_us=0;\n\nstatic void fps_tick\(\)\n\{.*?\n\}\n',
    '\n',s,count=1,flags=re.S)
s=s.replace('    fps_tick();\n','')
s=re.sub(
    r'\n\s*char fpsbuf\[96\];\n\s*snprintf\(fpsbuf,sizeof\(fpsbuf\),"FPS .*?;\n\s*draw_text\(18,18,fpsbuf,1,0xFFFFFFFF,80\);\n',
    '\n',s,count=1)

if 'FPS %.1f' in s or 'fps_tick();' in s:
    raise SystemExit('FPS overlay/counter removal failed')

p.write_text(s)
print('V2.26 smooth 60 Hz motion applied: slightly larger subpixel particles, moderate speed, FPS overlay removed')
