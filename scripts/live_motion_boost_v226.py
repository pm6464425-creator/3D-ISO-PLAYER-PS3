from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 HQ motion visibility fix.
# The previous HQ build was technically animated, but only ~30 tiny 1-2 px
# points changed on a 1920x1080 image, making the background look static on TV.
# Keep the HQ artwork static and add clearly visible, slow, lightweight motion
# behind the coverflow. No BDISO/MKV/USB/input/player logic is changed.

new_bg = r'''static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    unsigned int f=g_frame;

    /* Full-HD master copied by RSX every frame. */
    rsx_draw_hq_background(0xFF03070D);

    /* 96 slow drifting / blinking particles.  Motion stays local so the
       background feels alive without camera shake or fast fragments. */
    for(int i=0;i<96;++i) {
        unsigned int seed=(unsigned int)(41+i*97);
        int usable_w=(sw>80)?sw-80:1;
        int upper_h=(int)(sh*0.60f);
        if(upper_h<100) upper_h=100;
        int bx=40+(int)((seed*71u)%(unsigned int)usable_w);
        int by=28+(int)((seed*43u)%(unsigned int)(upper_h-28));

        int amp_x=7+(i%7)*3;          /* 7..25 px */
        int amp_y=4+(i%5)*2;          /* 4..12 px */
        int x=bx+live_tri_wave(f+seed,330+(i%9)*37,amp_x);
        int y=by+live_tri_wave(f+seed*3u,410+(i%8)*43,amp_y);

        int pulse=162+live_tri_wave(f+seed*5u,72+(i%7)*13,92);
        if(pulse<55) pulse=55;
        if(pulse>250) pulse=250;

        int r=1;
        if((i%13)==0) r=3;
        else if((i%4)==0) r=2;

        u32 col=(i%6==0)?0xFF77D7FF:((i%3==0)?0xFF43B9E8:0xFF278FCA);
        live_glow_point(x,y,r,col,(unsigned int)pulse);
    }

    /* Flowing highlights along the blue ribbon area.  Only the light moves;
       the master artwork itself never shifts, preventing the old 'temblor'. */
    for(int band=0;band<3;++band) {
        int base_y=(int)(sh*(0.355f+0.052f*(float)band));
        int phase=(int)((f*(unsigned int)(band+1))/2u);
        int prev_x=-18;
        int pp=(prev_x+phase+band*53)%180; if(pp<0) pp+=180;
        int tri=(pp<90)?pp:(180-pp);
        int prev_y=base_y+(tri-45)*(4+band)/9;

        for(int x=-4;x<sw+20;x+=14) {
            int q=(x+phase+band*53)%180; if(q<0) q+=180;
            int t=(q<90)?q:(180-q);
            int y=base_y+(t-45)*(4+band)/9;
            unsigned int a=(unsigned int)(48+band*10);
            live_aa_line(prev_x,prev_y,x,y,(band==0)?0xFF55C9F4:0xFF2D95CA,a);
            prev_x=x; prev_y=y;
        }
    }

    /* Slow bright glints, intentionally easy to notice from couch distance. */
    for(int i=0;i<5;++i) {
        int range=sw+280;
        unsigned int div=(unsigned int)(2+(i%3));
        int gx=(int)(((f/div)+(unsigned int)i*(unsigned int)(sw/4+73))%(unsigned int)range)-140;
        int gy=(int)(sh*(0.31f+0.062f*(float)i));
        int pulse=145+live_tri_wave(f+(unsigned int)i*61u,128+i*19,88);
        if(pulse<65) pulse=65;
        if(pulse>245) pulse=245;
        live_glow_point(gx,gy,(i==2)?3:2,0xFF82DEFF,(unsigned int)pulse);
        live_aa_line(gx-18,gy,gx+18,gy,0xFF56BFE8,(unsigned int)(pulse*2/3));
    }

    /* Two calm floor/reflection sweeps. */
    int horizon=(int)(sh*0.627f);
    int sweep1=(int)((f*2u)%(unsigned int)(sw+300))-150;
    int sweep2=sw-(int)(((f*3u)/2u)%(unsigned int)(sw+360))+90;
    live_aa_line(sweep1,horizon+16,sweep1+128,horizon+16,0xFF3988AC,72u);
    live_aa_line(sweep2,horizon+38,sweep2+96,horizon+38,0xFF256782,54u);
}
'''

pat=re.compile(r'static void draw_background\(\)\n\{.*?\n\}\n\nstatic void draw_rgba_scaled',re.S)
m=pat.search(s)
if not m:
    raise SystemExit('draw_background block not found')
s=s[:m.start()]+new_bg+'\nstatic void draw_rgba_scaled'+s[m.end():]

# Fix stale diagnostic label only; it does not affect behavior.
s=s.replace('V2.8 HARD PERF','V2.26 HQ LIVE')

p.write_text(s)
print('V2.26 HQ motion boost applied: 96 particles + 3 ribbon highlights + 5 glints + floor sweeps')
