from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

def rep(old,new,label):
    global s
    if old not in s:
        raise SystemExit(label+' anchor not found')
    s=s.replace(old,new,1)

# One complete RGBA frame instead of four separate strips.
rep('#define FONT_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/FONT.RAW"\n',
    '#define FONT_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/FONT.RAW"\n#define CASE_FRAME_PATH "/dev_hdd0/game/3DISO0001/USRDIR/CASE_FRAME.PNG"\n',
    'case frame path')

anchor='static bool g_flow_ready = false;\n'
extra=r'''static CoverBitmap g_case_frame;

static bool load_app_bitmap(const char *path, CoverBitmap *out)
{
    memset(out,0,sizeof(CoverBitmap));
    FILE *f=fopen(path,"rb");
    if(!f) return false;
    fseek(f,0,SEEK_END);
    long sz=ftell(f);
    fseek(f,0,SEEK_SET);
    if(sz<=0 || sz>2*1024*1024) { fclose(f); return false; }
    unsigned char *buf=(unsigned char*)malloc((size_t)sz);
    if(!buf) { fclose(f); return false; }
    size_t got=fread(buf,1,(size_t)sz,f);
    fclose(f);
    if(got!=(size_t)sz) { free(buf); return false; }
    int comp=0;
    out->rgba=stbi_load_from_memory(buf,(int)sz,&out->w,&out->h,&comp,4);
    free(buf);
    if(!out->rgba || out->w<=0 || out->h<=0) {
        if(out->rgba) stbi_image_free(out->rgba);
        out->rgba=NULL; out->w=out->h=0;
        return false;
    }
    return true;
}

static void load_case_assets()
{
    load_app_bitmap(CASE_FRAME_PATH,&g_case_frame);
}

static void free_case_assets()
{
    if(g_case_frame.rgba) stbi_image_free(g_case_frame.rgba);
    g_case_frame.rgba=NULL;
    g_case_frame.w=g_case_frame.h=0;
}
'''
if anchor not in s:
    raise SystemExit('flow state anchor not found')
s=s.replace(anchor,anchor+extra,1)

start=s.find('static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)')
end=s.find('\nstatic int connected_count()',start)
if start<0 or end<0:
    raise SystemExit('draw_poster block not found')

new=r'''static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)
{
    /* V2.6: one remastered rounded Blu-ray frame with transparent artwork window.
       No strip joins, no square corners, no white corner fringe. */
    int shad=(w>220)?7:4;
    fill_rect(x+shad,y+shad,w,h,0x44000000);

    /* Artwork window coordinates match the remastered 635x695 master frame. */
    int ax=x+(w*46)/635;
    int ay=y+(h*104)/695;
    int ar=x+(w*610)/635;
    int ab=y+(h*671)/695;
    int aw=ar-ax;
    int ah=ab-ay;
    if(aw<1) aw=1;
    if(ah<1) ah=1;

    CoverBitmap *c=get_movie_cover(m);
    if(c) {
        draw_rgba_scaled(ax,ay,aw,ah,c);
        draw_cover_reflection(x,y+h+7,w,h,c);
    } else {
        draw_generic_cover(ax,ay,aw,ah,m,selected);
    }

    /* The complete anti-aliased case is composited in one pass. */
    if(g_case_frame.rgba) {
        draw_rgba_scaled(x,y,w,h,&g_case_frame);
    }

    if(selected) {
        /* Small cyan floor cue only; do not square-off the rounded case. */
        int glow_w=w*58/100;
        if(glow_w<12) glow_w=12;
        int gx=x+(w-glow_w)/2;
        fill_rect(gx,y+h+2,glow_w,2,0xB85FD7FF);
    }
}
'''
s=s[:start]+new+s[end:]

rep('    load_font();\n','    load_font();\n    load_case_assets();\n','case startup')
rep('    cover_cache_clear();\n    cleanup_ntfs();\n',
    '    free_case_assets();\n    cover_cache_clear();\n    cleanup_ntfs();\n',
    'case shutdown')

p.write_text(s)
print('FLOW MOVIE V2.6: rounded remastered single-frame Blu-ray renderer applied')
