from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.12
# - Exact physical Blu-ray case proportion requested by the user: 135 mm x 172 mm.
# - Do not just shrink V2.11: make the selected case a little larger again,
#   while preserving the exact 135:172 aspect.
# - Remove all fallback text from inside the case. Movie title remains only in
#   the existing header above the coverflow.

old_geom='''        /* V2.11: compact proportions matched to the reference video.\n           The case master is 640x822, so keep its real 0.779 aspect. */\n        const float sel_h=sh*0.39f;\n        const float nb_h=sh*0.25f;\n        const float aspect=640.0f/822.0f;'''
new_geom='''        /* V2.12: standard Blu-ray keepcase dimensions: 135 mm wide x 172 mm high.\n           Width is always derived from height, so every case keeps 135:172.\n           Slightly larger than V2.11 because V2.11 was only scaled down. */\n        const float sel_h=sh*0.44f;\n        const float nb_h=sh*0.28f;\n        const float aspect=135.0f/172.0f;'''
if old_geom not in s:
    raise SystemExit('V2.11 geometry anchor not found')
s=s.replace(old_geom,new_geom,1)

start=s.find('static void draw_generic_cover(int x,int y,int w,int h,const Movie &m,bool selected)')
end=s.find('\nstatic void draw_poster(',start)
if start<0 or end<0:
    raise SystemExit('draw_generic_cover block not found')

new_generic=r'''static void draw_generic_cover(int x,int y,int w,int h,const Movie &m,bool selected)
{
    /* V2.12: clean fallback artwork.  No "BLU-RAY", no MKV label and no
       filename inside the physical case.  The selected movie title is already
       drawn once above the coverflow, matching the reference video. */
    unsigned int hv=title_hash(m.name);
    int r1=36+(hv&63), g1=42+((hv>>6)&55), b1=54+((hv>>12)&70);
    int r2=r1/3, g2=g1/3, b2=b1/3;
    u32 c1=0xFF000000|((u32)r1<<16)|((u32)g1<<8)|(u32)b1;
    u32 c2=0xFF000000|((u32)r2<<16)|((u32)g2<<8)|(u32)b2;
    for(int yy=0;yy<h;yy+=4) fill_rect(x,y+yy,w,4,mix_color(c1,c2,yy,h));

    /* Very subtle top tint only; the real Blu-ray header comes from CASE_FRAME.PNG. */
    fill_rect(x,y,w,3,g_tab==TAB_BDISO?0xFF245F86:0xFF236B4E);

    if(selected) {
        /* Keep only a restrained inner selection cue; no text. */
        fill_rect(x,y,2,h,0x8848B9F0);
        fill_rect(x+w-2,y,2,h,0x8848B9F0);
    }
}
'''
s=s[:start]+new_generic+s[end:]

p.write_text(s)
print('FLOW MOVIE V2.12: exact 135x172 aspect + larger reference size + no text inside fallback covers')
