from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

def rep(old,new,label):
    global s
    if old not in s:
        raise SystemExit(label+' anchor not found')
    s=s.replace(old,new,1)

# Paths for the real case-border strips extracted from the user's reference.
rep('#define FONT_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/FONT.RAW"\n',
    '#define FONT_PATH   "/dev_hdd0/game/3DISO0001/USRDIR/FONT.RAW"\n#define CASE_TOP_PATH "/dev_hdd0/game/3DISO0001/USRDIR/CASE_TOP.JPG"\n#define CASE_LEFT_PATH "/dev_hdd0/game/3DISO0001/USRDIR/CASE_LEFT.PNG"\n#define CASE_RIGHT_PATH "/dev_hdd0/game/3DISO0001/USRDIR/CASE_RIGHT.PNG"\n#define CASE_BOTTOM_PATH "/dev_hdd0/game/3DISO0001/USRDIR/CASE_BOTTOM.PNG"\n',
    'case paths')

anchor='static bool g_flow_ready = false;\n'
extra=r'''static CoverBitmap g_case_top;
static CoverBitmap g_case_left;
static CoverBitmap g_case_right;
static CoverBitmap g_case_bottom;

static bool load_app_bitmap(const char *path, CoverBitmap *out)
{
    memset(out,0,sizeof(CoverBitmap));
    FILE *f=fopen(path,"rb");
    if(!f) return false;
    fseek(f,0,SEEK_END);
    long sz=ftell(f);
    fseek(f,0,SEEK_SET);
    if(sz<=0 || sz>1024*1024) { fclose(f); return false; }
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
    load_app_bitmap(CASE_TOP_PATH,&g_case_top);
    load_app_bitmap(CASE_LEFT_PATH,&g_case_left);
    load_app_bitmap(CASE_RIGHT_PATH,&g_case_right);
    load_app_bitmap(CASE_BOTTOM_PATH,&g_case_bottom);
}

static void free_case_assets()
{
    CoverBitmap *a[4]={&g_case_top,&g_case_left,&g_case_right,&g_case_bottom};
    for(int i=0;i<4;i++) {
        if(a[i]->rgba) stbi_image_free(a[i]->rgba);
        a[i]->rgba=NULL; a[i]->w=a[i]->h=0;
    }
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
    /* V2.5: real Blu-ray case border from the user's reference image.
       x/y/w/h now describe the complete physical case. */
    int top=(h*35)/411; if(top<7) top=7;
    int bottom=(h*8)/411; if(bottom<3) bottom=3;
    int side=(w*5)/320; if(side<2) side=2;

    /* Soft depth only; no synthetic multi-line frame. */
    int shad=(w>220)?7:4;
    fill_rect(x+shad,y+shad,w,h,0x4A000000);

    int ax=x+side;
    int ay=y+top;
    int aw=w-side*2;
    int ah=h-top-bottom;

    CoverBitmap *c=get_movie_cover(m);
    if(c) {
        draw_rgba_scaled(ax,ay,aw,ah,c);
        draw_cover_reflection(x,y+h+7,w,h,c);
    } else {
        draw_generic_cover(ax,ay,aw,ah,m,selected);
    }

    /* Real case pieces are drawn last, exactly over the paper insert. */
    if(g_case_top.rgba) draw_rgba_scaled(x,y,w,top,&g_case_top);
    else fill_rect(x,y,w,top,0xFF087CB9);

    if(g_case_left.rgba) draw_rgba_scaled(x,y+top,side,h-top-bottom,&g_case_left);
    else fill_rect(x,y+top,side,h-top-bottom,0xFF087CB9);

    if(g_case_right.rgba) draw_rgba_scaled(x+w-side,y+top,side,h-top-bottom,&g_case_right);
    else fill_rect(x+w-side,y+top,side,h-top-bottom,0xFF087CB9);

    if(g_case_bottom.rgba) draw_rgba_scaled(x,y+h-bottom,w,bottom,&g_case_bottom);
    else fill_rect(x,y+h-bottom,w,bottom,0xFF087CB9);

    if(selected) {
        /* One clean selection glow outside the physical case. */
        fill_rect(x-3,y-3,w+6,2,0xFF5FD7FF);
        fill_rect(x-3,y+h+1,w+6,2,0xFF5FD7FF);
        fill_rect(x-3,y-1,2,h+2,0xFF5FD7FF);
        fill_rect(x+w+1,y-1,2,h+2,0xFF5FD7FF);
    }
}
'''
s=s[:start]+new+s[end:]

rep('    load_font();\n','    load_font();\n    load_case_assets();\n','case startup')
# Normal shutdown; early process exit does not need explicit cleanup.
rep('    cover_cache_clear();\n    cleanup_ntfs();\n',
    '    free_case_assets();\n    cover_cache_clear();\n    cleanup_ntfs();\n',
    'case shutdown')

p.write_text(s)
print('FLOW MOVIE V2.5: reference Blu-ray border applied')
