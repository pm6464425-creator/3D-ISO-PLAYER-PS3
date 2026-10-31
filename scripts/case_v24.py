from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

start = s.find('static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)')
end = s.find('\nstatic int connected_count()', start)
if start < 0 or end < 0:
    raise SystemExit('draw_poster block not found')

new_poster = r'''static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)
{
    /* Physical Blu-ray style case. x/y/w/h describe the cover-art area. */
    int side=w/28; if(side<5) side=5;
    int top=h/24; if(top<11) top=11;
    int bottom=h/80; if(bottom<4) bottom=4;
    int lip=side/2; if(lip<2) lip=2;

    int cx=x-side;
    int cy=y-top;
    int cw=w+side*2;
    int ch=h+top+bottom;

    /* Soft case shadow gives the box physical depth. */
    fill_rect(cx+9,cy+11,cw+3,ch+4,0x60000000);
    fill_rect(cx+5,cy+7,cw+3,ch+4,0x35000000);

    /* Outer translucent blue plastic shell. */
    u32 shell = selected ? 0xFF2D9BD8 : 0xFF235D82;
    u32 shell_hi = selected ? 0xFF75D3FF : 0xFF4B91B8;
    fill_rect(cx,cy,cw,ch,shell);

    /* Left spine + right plastic edge. */
    fill_rect(cx,cy,side,ch,0xFF174B70);
    fill_rect(cx+cw-side,cy,side,ch,0xFF123D5D);
    fill_rect(cx+2,cy+3,2,ch-6,shell_hi);
    fill_rect(cx+cw-4,cy+3,2,ch-6,0xFF0A2B42);

    /* Blu-ray top cap with a subtle rounded/plastic impression. */
    fill_rect(cx+side,cy,cw-side*2,top,0xFF176A9D);
    fill_rect(cx+side+2,cy+2,cw-side*2-4,3,shell_hi);
    fill_rect(cx+side+3,cy+top-4,cw-side*2-6,2,0xFF0A3855);

    /* Inner black groove around the paper insert. */
    fill_rect(x-lip,y-lip,w+lip*2,h+lip*2,0xFF07131D);
    fill_rect(x-1,y-1,w+2,h+2,0xFF182B38);

    CoverBitmap *c=get_movie_cover(m);
    if(c) {
        draw_rgba_scaled(x,y,w,h,c);
        draw_cover_reflection(x,y+h+bottom+9,w,h,c);
    } else {
        draw_generic_cover(x,y,w,h,m,selected);
    }

    /* Plastic-sheet gloss over the cover art, like a real case sleeve. */
    int gloss=w/22; if(gloss<4) gloss=4;
    fill_rect(x+3,y+3,gloss,h-6,0x173DB7EE);
    fill_rect(x+w-gloss-3,y+4,gloss/2,h-8,0x0F8FD9FF);
    fill_rect(x+4,y+4,w-8,2,0x45D8F4FF);

    /* Bottom plastic seam. */
    fill_rect(cx+side,cy+ch-bottom,cw-side*2,bottom,0xFF0D3B59);
    fill_rect(cx+side+2,cy+ch-bottom,cw-side*2-4,1,0xFF4A92B8);

    /* Small case hinge cues on the spine. */
    int hinge_h=h/9; if(hinge_h<12) hinge_h=12;
    fill_rect(cx+1,cy+top+h/5,side-2,hinge_h,0xFF0D3551);
    fill_rect(cx+1,cy+top+h*3/5,side-2,hinge_h,0xFF0D3551);

    if(selected) {
        /* Selection glow stays outside the physical shell. */
        fill_rect(cx-3,cy-3,cw+6,2,0xFF66D3FF);
        fill_rect(cx-3,cy+ch+1,cw+6,2,0xFF66D3FF);
        fill_rect(cx-3,cy-1,2,ch+2,0xFF66D3FF);
        fill_rect(cx+cw+1,cy-1,2,ch+2,0xFF66D3FF);
    }
}
'''

s = s[:start] + new_poster + s[end:]
p.write_text(s)
print('FLOW MOVIE V2.4: physical Blu-ray case renderer applied')
