from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def replace_once(old: str, new: str, label: str):
    global s
    if old not in s:
        raise SystemExit(f'{label} anchor not found')
    s = s.replace(old, new, 1)

# Use a real lossless Blu-ray case texture extracted from the user's reference image.
# Keep all working V2.4 behavior; only the poster/case drawing changes.

# Add installed case texture path.
replace_once(
    '#define FONT_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/FONT.RAW"\n',
    '#define FONT_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/FONT.RAW"\n#define CASE_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/BLURAY_CASE.PNG"\n',
    'case path')

# Add persistent case texture storage after coverflow state globals.
anchor = 'static bool g_flow_ready = false;\n'
extra = r'''static unsigned char *g_case_rgba = NULL;
static int g_case_w = 0;
static int g_case_h = 0;

static bool load_case_texture()
{
    if(g_case_rgba) return true;
    FILE *f=fopen(CASE_PATH,"rb");
    if(!f) return false;
    fseek(f,0,SEEK_END);
    long sz=ftell(f);
    fseek(f,0,SEEK_SET);
    if(sz<=0 || sz>8*1024*1024) { fclose(f); return false; }
    unsigned char *buf=(unsigned char*)malloc((size_t)sz);
    if(!buf) { fclose(f); return false; }
    size_t rd=fread(buf,1,(size_t)sz,f);
    fclose(f);
    if(rd!=(size_t)sz) { free(buf); return false; }
    int comp=0;
    g_case_rgba=stbi_load_from_memory(buf,(int)sz,&g_case_w,&g_case_h,&comp,4);
    free(buf);
    if(!g_case_rgba || g_case_w<=0 || g_case_h<=0) {
        if(g_case_rgba) stbi_image_free(g_case_rgba);
        g_case_rgba=NULL; g_case_w=g_case_h=0;
        return false;
    }
    return true;
}

static void draw_case_texture(int x,int y,int w,int h)
{
    if(!g_case_rgba || w<=0 || h<=0) return;
    u32 sw=get_screen_width(), sh=get_screen_height();
    u32 *fb=get_back_buffer();
    uint32_t xstep=((uint32_t)g_case_w<<16)/(uint32_t)w;
    uint32_t ystep=((uint32_t)g_case_h<<16)/(uint32_t)h;
    uint32_t syfp=0;
    for(int yy=0;yy<h;++yy,syfp+=ystep) {
        int py=y+yy;
        if(py<0 || py>=(int)sh) continue;
        int sy=(int)(syfp>>16); if(sy>=g_case_h) sy=g_case_h-1;
        uint32_t sxfp=0;
        for(int xx=0;xx<w;++xx,sxfp+=xstep) {
            int px=x+xx;
            if(px<0 || px>=(int)sw) continue;
            int sx=(int)(sxfp>>16); if(sx>=g_case_w) sx=g_case_w-1;
            const unsigned char *sp=g_case_rgba+((size_t)sy*g_case_w+sx)*4;
            unsigned int a=sp[3];
            if(!a) continue;
            u32 col=0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
            if(a==255) fb[py*sw+px]=col;
            else blend_pixel(px,py,col,a);
        }
    }
}
'''
if anchor not in s:
    raise SystemExit('flow globals anchor not found')
s=s.replace(anchor,anchor+extra,1)

# Replace V2.4 synthetic case drawing with the actual PNG case overlay.
start=s.find('static void draw_bluray_case(')
end=s.find('\nstatic void draw_poster(', start)
if start<0 or end<0:
    raise SystemExit('V2.4 bluray case block not found')
new_case=r'''static void draw_bluray_case(int x,int y,int w,int h,bool selected)
{
    /* Subtle shadow only; the visible case itself comes from BLURAY_CASE.PNG. */
    int shadow=(w>220)?7:4;
    fill_rect(x+shadow,y+shadow,w,h,0x44000000);
    if(g_case_rgba) draw_case_texture(x,y,w,h);
    else {
        /* Small fallback if the texture is unexpectedly missing. */
        int rim=(w>220)?4:3;
        fill_rect(x-rim,y-rim,w+rim*2,h+rim*2,0xFF0B71B3);
    }
    if(selected) {
        /* Selection glow outside the physical case, not inside the artwork. */
        fill_rect(x-3,y-3,w+6,2,0xFF66D8FF);
        fill_rect(x-3,y+h+1,w+6,2,0xFF66D8FF);
    }
}
'''
s=s[:start]+new_case+s[end:]

# Draw cover art inside the transparent center of the reference case.
# The source case has an 8.6% top cap, ~1.5% side rims and ~2% bottom rim.
old = '''static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)\n{\n    draw_bluray_case(x,y,w,h,selected);\n\n    CoverBitmap *c=get_movie_cover(m);\n    if(c) {\n        draw_rgba_scaled(x,y,w,h,c);\n        draw_cover_reflection(x,y+h+8,w,h,c);\n    } else {\n        draw_generic_cover(x,y,w,h,m,selected);\n    }\n\n    draw_bluray_case(x,y,w,h,selected);\n}\n'''
new = r'''static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)
{
    int inset_x=(w*12)/777;
    if(inset_x<2) inset_x=2;
    int inset_top=(h*86)/1000;
    if(inset_top<8) inset_top=8;
    int inset_bottom=(h*20)/1000;
    if(inset_bottom<3) inset_bottom=3;
    int art_x=x+inset_x;
    int art_y=y+inset_top;
    int art_w=w-inset_x*2;
    int art_h=h-inset_top-inset_bottom;

    CoverBitmap *c=get_movie_cover(m);
    if(c) {
        draw_rgba_scaled(art_x,art_y,art_w,art_h,c);
        draw_cover_reflection(x,y+h+8,w,h,c);
    } else {
        draw_generic_cover(art_x,art_y,art_w,art_h,m,selected);
    }

    /* PNG overlay is rendered last so the cover sits behind the physical plastic rim. */
    draw_bluray_case(x,y,w,h,selected);
}
'''
replace_once(old,new,'draw poster case composition')

# Load the case once at startup and free it at shutdown.
replace_once('    load_font();\n', '    load_font();\n    load_case_texture();\n', 'load case startup')
replace_once(
    '    if(g_font) free(g_font);\n    free(host_addr);\n',
    '    if(g_case_rgba) { stbi_image_free(g_case_rgba); g_case_rgba=NULL; }\n    if(g_font) free(g_font);\n    free(host_addr);\n',
    'free case shutdown')

p.write_text(s)
print('FLOW MOVIE V2.5: real Blu-ray case PNG overlay applied')
