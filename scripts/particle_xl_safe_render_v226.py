from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

# Safe XL renderer: preserve 3/4/5 particle radii, but avoid drawing the full
# large halo four times for bilinear subpixel interpolation. The large halo is
# drawn once at the nearest pixel, while a small core keeps true subpixel
# interpolation. This keeps the large visual size with work comparable to the
# previously stable BIGPART build.
new_helper = r'''/* V226_XL_SAFE_RENDER: one large halo + small bilinear core. */
static void live_glow_point_fp(int xfp,int yfp,int radius,u32 color,unsigned int alpha)
{
    int x=xfp/256, y=yfp/256;
    int fx=xfp-x*256, fy=yfp-y*256;
    if(fx<0) { x--; fx+=256; }
    if(fy<0) { y--; fy+=256; }

    /* Draw the expensive XL halo only once at the nearest pixel. */
    int hx=x + ((fx>=128)?1:0);
    int hy=y + ((fy>=128)?1:0);
    unsigned int halo_alpha=(alpha*3u)/5u;
    if(halo_alpha) live_glow_point(hx,hy,radius,color,halo_alpha);

    /* Keep motion fluid with a much smaller bilinear core. */
    unsigned int w00=(unsigned int)(((256-fx)*(256-fy))>>8);
    unsigned int w10=(unsigned int)((fx*(256-fy))>>8);
    unsigned int w01=(unsigned int)(((256-fx)*fy)>>8);
    unsigned int w11=(unsigned int)((fx*fy)>>8);
    unsigned int core_alpha=(alpha*4u)/5u;
    int core_radius=(radius>=4)?2:1;

    if(w00) live_glow_point(x,  y,  core_radius,color,(core_alpha*w00)>>8);
    if(w10) live_glow_point(x+1,y,  core_radius,color,(core_alpha*w10)>>8);
    if(w01) live_glow_point(x,  y+1,core_radius,color,(core_alpha*w01)>>8);
    if(w11) live_glow_point(x+1,y+1,core_radius,color,(core_alpha*w11)>>8);
}
'''

pat=re.compile(r'static void live_glow_point_fp\(int xfp,int yfp,int radius,u32 color,unsigned int alpha\)\n\{.*?\n\}\n\nstatic void draw_background',re.S)
m=pat.search(s)
if not m:
    raise SystemExit('live_glow_point_fp block not found')
s=s[:m.start()]+new_helper+'\nstatic void draw_background'+s[m.end():]

if 'V226_XL_SAFE_RENDER' not in s:
    raise SystemExit('safe XL renderer insertion failed')

p.write_text(s)
print('V2.26 safe XL renderer applied: large halo once + bilinear small core')
