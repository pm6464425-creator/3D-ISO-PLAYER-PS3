from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def replace_once(old: str, new: str, label: str):
    global s
    if old not in s:
        raise SystemExit(f'{label} anchor not found')
    s = s.replace(old, new, 1)


# Reset LRU sequence whenever cover bitmaps are discarded.
replace_once(
'''        g_cover_cache[i].stamp = 0;\n    }\n}\n''',
'''        g_cover_cache[i].stamp = 0;\n    }\n    g_cover_stamp = 1;\n}\n''',
'cover cache reset')

# Reject pathological images before stb_image allocates the full decoded bitmap.
replace_once(
'''    int iw=0, ih=0, comp=0;\n    unsigned char *decoded = stbi_load_from_memory(file, (int)sz, &iw, &ih, &comp, 4);\n    free(file);\n    if(!decoded || iw <= 0 || ih <= 0) { if(decoded) stbi_image_free(decoded); return NULL; }\n''',
'''    int probe_w=0, probe_h=0, probe_comp=0;\n    if(!stbi_info_from_memory(file, (int)sz, &probe_w, &probe_h, &probe_comp) ||\n       probe_w <= 0 || probe_h <= 0 || probe_w > 4096 || probe_h > 4096 ||\n       (uint64_t)probe_w * (uint64_t)probe_h > 12000000ULL) {\n        free(file);\n        return NULL;\n    }\n\n    int iw=0, ih=0, comp=0;\n    unsigned char *decoded = stbi_load_from_memory(file, (int)sz, &iw, &ih, &comp, 4);\n    free(file);\n    if(!decoded || iw <= 0 || ih <= 0) { if(decoded) stbi_image_free(decoded); return NULL; }\n''',
'image sanity check')

# Replace costly per-pixel integer divisions with 16.16 fixed point stepping.
start = s.find('static void draw_rgba_scaled(int x, int y, int w, int h, const CoverBitmap *c)')
end = s.find('\nstatic void draw_cover_reflection', start)
if start < 0 or end < 0:
    raise SystemExit('draw_rgba_scaled block not found')
new_scaled = r'''static void draw_rgba_scaled(int x, int y, int w, int h, const CoverBitmap *c)
{
    if(!c || !c->rgba || w<=0 || h<=0 || c->w<=0 || c->h<=0) return;
    u32 sw=get_screen_width(), sh=get_screen_height();
    u32 *fb=get_back_buffer();
    uint32_t xstep=((uint32_t)c->w << 16) / (uint32_t)w;
    uint32_t ystep=((uint32_t)c->h << 16) / (uint32_t)h;
    uint32_t syfp=0;

    for(int yy=0; yy<h; ++yy, syfp+=ystep) {
        int py=y+yy;
        int sy=(int)(syfp >> 16);
        if(sy>=c->h) sy=c->h-1;
        uint32_t sxfp=0;
        if(py<0 || py>=(int)sh) continue;

        for(int xx=0; xx<w; ++xx, sxfp+=xstep) {
            int px=x+xx;
            if(px<0 || px>=(int)sw) continue;
            int sx=(int)(sxfp >> 16);
            if(sx>=c->w) sx=c->w-1;
            const unsigned char *sp=c->rgba+((size_t)sy*c->w+sx)*4;
            unsigned int a=sp[3];
            u32 col=0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
            if(a==255) fb[py*sw+px]=col;
            else if(a) blend_pixel(px,py,col,a);
        }
    }
}
'''
s = s[:start] + new_scaled + s[end:]

# Reflection is cosmetic; sample it more sparsely to lower PPU load.
start = s.find('static void draw_cover_reflection(int x, int y, int w, int h, const CoverBitmap *c)')
end = s.find('\nstatic void draw_generic_cover', start)
if start < 0 or end < 0:
    raise SystemExit('draw_cover_reflection block not found')
new_reflection = r'''static void draw_cover_reflection(int x, int y, int w, int h, const CoverBitmap *c)
{
    if(!c || !c->rgba || w<=0 || c->w<=0 || c->h<=0) return;
    int rh=h/7;
    if(rh<10) return;
    uint32_t xstep=((uint32_t)c->w << 16) / (uint32_t)w;

    for(int yy=0; yy<rh; yy+=3) {
        int sy=c->h-1-(yy*c->h)/(rh*2);
        if(sy<0) sy=0;
        unsigned int alpha=(unsigned int)(58*(rh-yy)/rh);
        uint32_t sxfp=0;
        for(int xx=0; xx<w; xx+=3, sxfp+=xstep*3) {
            int sx=(int)(sxfp >> 16);
            if(sx>=c->w) sx=c->w-1;
            const unsigned char *sp=c->rgba+((size_t)sy*c->w+sx)*4;
            u32 col=0xFF000000|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
            blend_pixel(x+xx,y+yy,col,alpha);
            if(xx+1<w) blend_pixel(x+xx+1,y+yy,col,alpha);
        }
    }
}
'''
s = s[:start] + new_reflection + s[end:]

# Center the fallback label inside its own movie case, not the whole screen.
replace_once(
'''    draw_centered(y+h/2-font_height(1)/2,g_tab==TAB_BDISO?"BLU-RAY ISO":"MKV",1,0xFFF4FAFF);\n''',
'''    const char *format_label = g_tab==TAB_BDISO ? "BLU-RAY ISO" : "MKV";\n    int format_w=(int)strlen(format_label)*char_advance(1);\n    draw_text(x+(w-format_w)/2,y+h/2-font_height(1)/2,format_label,1,0xFFF4FAFF,16);\n''',
'generic cover centering')

# Render side cases first and selected movie last so nothing can overlap it.
replace_once(
'        int positions[7]={-3,-2,-1,0,1,2,3};\n',
'        int positions[7]={-3,3,-2,2,-1,1,0};\n',
'coverflow z order')

# Avoid snprintf truncation and cap source text to a sensible UI length.
replace_once(
'''        char sz[48], count[64];\n        format_size(sel.bytes,sz,sizeof(sz));\n        snprintf(count,sizeof(count),"%s    %d de %u    %s",sz,g_selected+1,(unsigned)g_movies.size(),sel.source.c_str());\n''',
'''        char sz[48], count[160];\n        format_size(sel.bytes,sz,sizeof(sz));\n        snprintf(count,sizeof(count),"%s    %d de %u    %.32s",sz,g_selected+1,(unsigned)g_movies.size(),sel.source.c_str());\n''',
'info buffer')

# The renderer is software-based. 30 fps keeps navigation responsive with much lower PPU usage.
replace_once('        usleep(16000);\n', '        usleep(30000);\n', 'frame pacing')

p.write_text(s)
print('FLOW MOVIE 3D V2 fixes applied: safer covers, correct z-order, local fallback labels, optimized renderer')
