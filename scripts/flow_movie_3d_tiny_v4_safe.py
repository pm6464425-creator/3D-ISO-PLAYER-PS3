from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

def replace_once(old,new,label):
    global s
    if old not in s: raise SystemExit(f'{label} anchor not found')
    s=s.replace(old,new,1)

def replace_function(signature,new_text,label):
    global s
    start=s.find(signature)
    if start<0: raise SystemExit(f'{label} signature not found')
    brace=s.find('{',start)
    if brace<0: raise SystemExit(f'{label} opening brace not found')
    depth=0
    end=-1
    for i in range(brace,len(s)):
        if s[i]=='{': depth+=1
        elif s[i]=='}':
            depth-=1
            if depth==0:
                end=i+1
                break
    if end<0: raise SystemExit(f'{label} closing brace not found')
    s=s[:start]+new_text+s[end:]

if '#include <tiny3d.h>' not in s:
    s=s.replace('#include <sysutil/sysutil.h>\n','#include <sysutil/sysutil.h>\n#include <tiny3d.h>\n#include <sysutil/video.h>\n',1)

s=s.replace('#define FONT_W 16','#define FONT_W 32',1)
s=s.replace('#define FONT_H 24','#define FONT_H 48',1)

anchor='static unsigned int g_frame = 0;\n'
extra=r'''
extern u32 display_width;
extern u32 display_height;
static u32 *g_font_tex=NULL;
static u32 g_font_tex_offset=0;
static const int FLOW_FONT_COLS=16;
static const int FLOW_FONT_ROWS=6;
static const int FLOW_FONT_ATLAS_W=FONT_W*FLOW_FONT_COLS;
static const int FLOW_FONT_ATLAS_H=FONT_H*FLOW_FONT_ROWS;
static u32 flow_argb_to_rgba(u32 c){ return ((c&0x00FFFFFFu)<<8)|((c>>24)&0xFFu); }
static void flow_vertex(float x,float y,u32 argb){ tiny3d_VertexPos(x,y,65500.0f); tiny3d_VertexColor(flow_argb_to_rgba(argb)); }
static int flow_init_font_texture(){
    if(!g_font) return -1;
    g_font_tex=(u32*)tiny3d_AllocTexture((u32)FLOW_FONT_ATLAS_W*(u32)FLOW_FONT_ATLAS_H*4u);
    if(!g_font_tex) return -2;
    memset(g_font_tex,0,(size_t)FLOW_FONT_ATLAS_W*FLOW_FONT_ATLAS_H*4u);
    for(int gi=0;gi<FONT_GLYPHS;++gi){
        int col=gi%FLOW_FONT_COLS,row=gi/FLOW_FONT_COLS;
        const unsigned char *src=g_font+(size_t)gi*FONT_W*FONT_H;
        for(int yy=0;yy<FONT_H;++yy){
            u32 *dst=g_font_tex+(row*FONT_H+yy)*FLOW_FONT_ATLAS_W+col*FONT_W;
            for(int xx=0;xx<FONT_W;++xx){ unsigned a=src[yy*FONT_W+xx]; dst[xx]=((u32)a<<24)|0x00FFFFFFu; }
        }
    }
    g_font_tex_offset=tiny3d_TextureOffset(g_font_tex);
    return 0;
}
'''
if anchor not in s: raise SystemExit('g_frame anchor not found')
s=s.replace(anchor,anchor+extra,1)

replace_function('static void do_flip()',r'''static void do_flip(){ sysUtilCheckCallback(); tiny3d_Flip(); }''','do_flip')

replace_function('static void fill_rect(int x, int y, int w, int h, u32 color)',r'''static void fill_rect(int x,int y,int w,int h,u32 color){
    int sw=(int)get_screen_width(),sh=(int)get_screen_height();
    if(x<0){w+=x;x=0;} if(y<0){h+=y;y=0;} if(x+w>sw)w=sw-x; if(y+h>sh)h=sh-y; if(w<=0||h<=0)return;
    tiny3d_SetPolygon(TINY3D_QUADS);
    flow_vertex((float)x,(float)y,color); flow_vertex((float)(x+w),(float)y,color);
    flow_vertex((float)(x+w),(float)(y+h),color); flow_vertex((float)x,(float)(y+h),color);
    tiny3d_End();
}''','fill_rect')

replace_function('static void blend_pixel(int x, int y, u32 color, unsigned int alpha)',r'''static void blend_pixel(int x,int y,u32 color,unsigned int alpha){
    if(!alpha)return; if(alpha>255)alpha=255; fill_rect(x,y,1,1,((u32)alpha<<24)|(color&0x00FFFFFFu));
}''','blend_pixel')

# V3 proportional metrics were measured in source pixels; source is now 2x.
s=s.replace('return (int)g_glyph_adv[uc-FONT_FIRST]*scale;','return ((int)g_glyph_adv[uc-FONT_FIRST]*scale+1)/2;',1)
s=s.replace('return g_font ? FONT_H*scale : 7*scale;','return g_font ? (FONT_H*scale)/2 : 7*scale;',1)

replace_function('static void draw_char(int x, int y, char c, int scale, u32 color)',r'''static void draw_char(int x,int y,char c,int scale,u32 color){
    unsigned char uc=(unsigned char)c; if(!g_font_tex||uc<FONT_FIRST||uc>FONT_LAST)return;
    int gi=uc-FONT_FIRST,left=g_glyph_left[gi],right=g_glyph_right[gi]; if(right<left)return;
    int col=gi%FLOW_FONT_COLS,row=gi/FLOW_FONT_COLS;
    float u0=(float)(col*FONT_W+left)/(float)FLOW_FONT_ATLAS_W;
    float u1=(float)(col*FONT_W+right+1)/(float)FLOW_FONT_ATLAS_W;
    float v0=(float)(row*FONT_H)/(float)FLOW_FONT_ATLAS_H;
    float v1=(float)((row+1)*FONT_H)/(float)FLOW_FONT_ATLAS_H;
    float dw=(float)(right-left+1)*(float)scale*0.5f,dh=(float)FONT_H*(float)scale*0.5f;
    tiny3d_SetTextureWrap(0,g_font_tex_offset,FLOW_FONT_ATLAS_W,FLOW_FONT_ATLAS_H,FLOW_FONT_ATLAS_W*4,
                          TINY3D_TEX_FORMAT_A8R8G8B8,TEXTWRAP_CLAMP,TEXTWRAP_CLAMP,TEXTURE_LINEAR);
    tiny3d_SetPolygon(TINY3D_QUADS); u32 rgba=flow_argb_to_rgba(color);
    tiny3d_VertexPos((float)x,(float)y,65400.0f); tiny3d_VertexColor(rgba); tiny3d_VertexTexture(u0,v0);
    tiny3d_VertexPos((float)x+dw,(float)y,65400.0f); tiny3d_VertexColor(rgba); tiny3d_VertexTexture(u1,v0);
    tiny3d_VertexPos((float)x+dw,(float)y+dh,65400.0f); tiny3d_VertexColor(rgba); tiny3d_VertexTexture(u1,v1);
    tiny3d_VertexPos((float)x,(float)y+dh,65400.0f); tiny3d_VertexColor(rgba); tiny3d_VertexTexture(u0,v1);
    tiny3d_End();
}''','draw_char')

replace_function('static void draw_circle(int cx, int cy, int radius, u32 color)',r'''static void draw_circle(int cx,int cy,int radius,u32 color){
    if(radius<=0)return; int seg=radius<6?12:(radius<16?20:28); u32 rgba=flow_argb_to_rgba(color);
    tiny3d_SetPolygon(TINY3D_TRIANGLES);
    for(int i=0;i<seg;i++){ float a0=(float)i*6.2831853f/seg,a1=(float)(i+1)*6.2831853f/seg;
        tiny3d_VertexPos((float)cx,(float)cy,65500.0f); tiny3d_VertexColor(rgba);
        tiny3d_VertexPos((float)cx+cosf(a0)*radius,(float)cy+sinf(a0)*radius,65500.0f); tiny3d_VertexColor(rgba);
        tiny3d_VertexPos((float)cx+cosf(a1)*radius,(float)cy+sinf(a1)*radius,65500.0f); tiny3d_VertexColor(rgba);
    } tiny3d_End();
}''','draw_circle')

replace_function('static void cover_cache_clear()',r'''static void cover_cache_clear(){
    for(int i=0;i<COVER_CACHE_SLOTS;i++){ g_cover_cache[i].path.clear(); g_cover_cache[i].w=g_cover_cache[i].h=0; g_cover_cache[i].stamp=0; }
    g_cover_stamp=1;
}''','cover_cache_clear')

replace_function('static CoverBitmap *get_movie_cover(const Movie &m)',r'''static CoverBitmap *get_movie_cover(const Movie &m){
    if(m.cover.empty())return NULL;
    for(int i=0;i<COVER_CACHE_SLOTS;i++) if(g_cover_cache[i].rgba&&g_cover_cache[i].path==m.cover){ g_cover_cache[i].stamp=++g_cover_stamp; return &g_cover_cache[i]; }
    int slot=-1; unsigned oldest=0xFFFFFFFFu;
    for(int i=0;i<COVER_CACHE_SLOTS;i++){ if(g_cover_cache[i].path.empty()){slot=i;break;} if(g_cover_cache[i].stamp<oldest){oldest=g_cover_cache[i].stamp;slot=i;} }
    if(slot<0)return NULL;
    size_t sz=0; unsigned char *file=read_file_bytes(m,m.cover,&sz); if(!file)return NULL;
    int pw=0,ph=0,pc=0; if(!stbi_info_from_memory(file,(int)sz,&pw,&ph,&pc)||pw<=0||ph<=0||pw>4096||ph>4096||(uint64_t)pw*(uint64_t)ph>12000000ULL){free(file);return NULL;}
    int iw=0,ih=0,comp=0; unsigned char *decoded=stbi_load_from_memory(file,(int)sz,&iw,&ih,&comp,4); free(file); if(!decoded)return NULL;
    int cw=0,ch=0; unsigned char *scaled=scale_rgba(decoded,iw,ih,&cw,&ch); stbi_image_free(decoded); if(!scaled)return NULL;
    const size_t cap=(size_t)320*480*4;
    if(!g_cover_cache[slot].rgba){ g_cover_cache[slot].rgba=(unsigned char*)tiny3d_AllocTexture((u32)cap); if(!g_cover_cache[slot].rgba){free(scaled);return NULL;} }
    u32 *dst=(u32*)g_cover_cache[slot].rgba; size_t count=(size_t)cw*ch;
    for(size_t i=0;i<count;i++){ const unsigned char *sp=scaled+i*4; dst[i]=((u32)sp[3]<<24)|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2]; }
    free(scaled); g_cover_cache[slot].w=cw; g_cover_cache[slot].h=ch; g_cover_cache[slot].path=m.cover; g_cover_cache[slot].stamp=++g_cover_stamp;
    return &g_cover_cache[slot];
}''','get_movie_cover')

replace_function('static void draw_rgba_scaled(int x, int y, int w, int h, const CoverBitmap *c)',r'''static void draw_rgba_scaled(int x,int y,int w,int h,const CoverBitmap *c){
    if(!c||!c->rgba||c->w<=0||c->h<=0||w<=0||h<=0)return;
    u32 off=tiny3d_TextureOffset(c->rgba); tiny3d_SetTextureWrap(0,off,c->w,c->h,c->w*4,TINY3D_TEX_FORMAT_A8R8G8B8,TEXTWRAP_CLAMP,TEXTWRAP_CLAMP,TEXTURE_LINEAR);
    tiny3d_SetPolygon(TINY3D_QUADS); u32 tint=0xFFFFFFFFu;
    tiny3d_VertexPos((float)x,(float)y,65300.0f); tiny3d_VertexColor(tint); tiny3d_VertexTexture(0,0);
    tiny3d_VertexPos((float)(x+w),(float)y,65300.0f); tiny3d_VertexColor(tint); tiny3d_VertexTexture(1,0);
    tiny3d_VertexPos((float)(x+w),(float)(y+h),65300.0f); tiny3d_VertexColor(tint); tiny3d_VertexTexture(1,1);
    tiny3d_VertexPos((float)x,(float)(y+h),65300.0f); tiny3d_VertexColor(tint); tiny3d_VertexTexture(0,1); tiny3d_End();
}''','draw_rgba_scaled')

replace_function('static void draw_cover_reflection(int x, int y, int w, int h, const CoverBitmap *c)',r'''static void draw_cover_reflection(int x,int y,int w,int h,const CoverBitmap *c){
    if(!c||!c->rgba||c->w<=0||c->h<=0)return; int rh=h/6; if(rh<8)return;
    u32 off=tiny3d_TextureOffset(c->rgba); tiny3d_SetTextureWrap(0,off,c->w,c->h,c->w*4,TINY3D_TEX_FORMAT_A8R8G8B8,TEXTWRAP_CLAMP,TEXTWRAP_CLAMP,TEXTURE_LINEAR);
    tiny3d_SetPolygon(TINY3D_QUADS); u32 tint=0xFFFFFF30u;
    tiny3d_VertexPos((float)x,(float)y,65300.0f); tiny3d_VertexColor(tint); tiny3d_VertexTexture(0,1);
    tiny3d_VertexPos((float)(x+w),(float)y,65300.0f); tiny3d_VertexColor(tint); tiny3d_VertexTexture(1,1);
    tiny3d_VertexPos((float)(x+w),(float)(y+rh),65300.0f); tiny3d_VertexColor(0xFFFFFF00u); tiny3d_VertexTexture(1,0.78f);
    tiny3d_VertexPos((float)x,(float)(y+rh),65300.0f); tiny3d_VertexColor(0xFFFFFF00u); tiny3d_VertexTexture(0,0.78f); tiny3d_End();
}''','draw_cover_reflection')

needle='''    int sw=(int)get_screen_width(), sh=(int)get_screen_height();\n    flow_update();\n    draw_background();'''
repl='''    int sw=(int)get_screen_width(), sh=(int)get_screen_height();\n    tiny3d_Clear(0xFF000000,TINY3D_CLEAR_ALL);\n    tiny3d_AlphaTest(1,0x00,TINY3D_ALPHA_FUNC_GREATER);\n    tiny3d_BlendFunc(1,(blend_src_func)(TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA),\n                     (blend_dst_func)(TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO),\n                     (blend_func)(TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD));\n    tiny3d_Project2D();\n    flow_update();\n    draw_background();'''
replace_once(needle,repl,'frame begin')
s=s.replace('    flip();\n}\n\nstatic void move_selection','    tiny3d_Flip();\n}\n\nstatic void move_selection',1)

old='''    void *host_addr=memalign(1024*1024,HOST_SIZE);\n    if(!host_addr) return 1;\n\n    init_screen(host_addr,HOST_SIZE);\n    ioPadInit(7);'''
new='''    tiny3d_Init(4u*1024u*1024u);\n    display_width=848; display_height=512;\n    tiny3d_UserViewport(1,0.0f,0.0f,(float)Video_Resolution.width/848.0f,(float)Video_Resolution.height/512.0f,\n                        (float)Video_Resolution.width/1920.0f,(float)Video_Resolution.height/1080.0f);\n    ioPadInit(7);'''
replace_once(old,new,'main init')
replace_once('    load_font();\n    ensure_internal_folders();','    load_font();\n    flow_init_font_texture();\n    ensure_internal_folders();','font init')
s=s.replace('            free(host_addr);\n','')
s=s.replace('    free(host_addr);\n','')

s=s.replace('p_tri=false,p_r1=false,p_r2=false;','p_tri=false,p_l1=false,p_r1=false;',1)
s=s.replace('bool r1=pad.BTN_R1, r2=pad.BTN_R2;','bool l1=pad.BTN_L1, r1=pad.BTN_R1;',1)
s=s.replace('''        if(r1 && !p_r1) { g_tab = (g_tab==TAB_BDISO) ? TAB_MKV : TAB_BDISO; g_selected=0; rebuild_movies(); }\n        if(r2 && !p_r2) { g_tab = (g_tab==TAB_MKV) ? TAB_BDISO : TAB_MKV; g_selected=0; rebuild_movies(); }''',
'''        if(r1 && !p_r1) { g_tab=(g_tab==TAB_BDISO)?TAB_MKV:TAB_BDISO; g_selected=0; g_flow_ready=false; rebuild_movies(); }\n        if(l1 && !p_l1) { g_tab=(g_tab==TAB_MKV)?TAB_BDISO:TAB_MKV; g_selected=0; g_flow_ready=false; rebuild_movies(); }''',1)
s=s.replace('p_tri=tri; p_r1=r1; p_r2=r2;','p_tri=tri; p_l1=l1; p_r1=r1;',1)
s=s.replace('"R2"','"L1"')
s=s.replace('R1/R2','L1/R1').replace('R1-R2','L1-R1')

p.write_text(s)
print('FLOW MOVIE 3D V4 SAFE: Tiny3D/RSX, HD font, L1/R1 applied without backend deletion')
