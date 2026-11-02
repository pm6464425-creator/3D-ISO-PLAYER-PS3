from pathlib import Path
import re, math

p=Path('source/main.cpp')
s=p.read_text()

# ---------------------------------------------------------------------------
# FLOW MOVIE V2.26 INTERNAL PLAYER (preserve existing behavior)
# ---------------------------------------------------------------------------
if 'flow_log("SESSION_START","FLOW MOVIE V2.25 MKV MOVIAN");' in s:
    s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.25 MKV MOVIAN");',
                'flow_log("SESSION_START","FLOW MOVIE V2.26 INTERNAL PLAYER");',1)
elif 'flow_log("SESSION_START","FLOW MOVIE V2.26 INTERNAL PLAYER");' not in s:
    raise SystemExit('V2.25/V2.26 session marker not found')

old_paths='''    static const char *paths[] = {\n        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",'''
new_paths='''    static const char *paths[] = {\n        /* Bundled FLOW MOVIE multimedia engine (Movian Next / FFmpeg core). */\n        "/dev_hdd0/game/3DISO0001/USRDIR/flow_player.self",\n        /* Compatibility fallback for users who already have Movian. */\n        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",'''
if old_paths in s:
    s=s.replace(old_paths,new_paths,1)
elif '/dev_hdd0/game/3DISO0001/USRDIR/flow_player.self' not in s:
    raise SystemExit('V2.25/V2.26 player path list not found')

old_argv='''    const char *launchargv[2];\n    launchargv[0]=url.c_str();\n    launchargv[1]=NULL;'''
new_argv='''    const char *launchargv[3];\n    launchargv[0]=player;\n    launchargv[1]=url.c_str();\n    launchargv[2]=NULL;'''
if old_argv in s:
    s=s.replace(old_argv,new_argv,1)
elif 'launchargv[0]=player;' not in s or 'launchargv[1]=url.c_str();' not in s:
    raise SystemExit('V2.25/V2.26 argv block not found')

s=s.replace('''show_ok("No se encontro Movian/Showtime.\\n\\nInstala Movian (HTSS00003) o Movian Next con movian.self para reproducir MKV.");''',
            '''show_ok("No se encontro el motor multimedia interno.\\n\\nReinstala FLOW MOVIE V2.26 para restaurar flow_player.self.");''',1)
s=s.replace('''show_ok("Movian no pudo iniciarse.\\n\\nRevisa que movian.self este instalado correctamente.");''',
            '''show_ok("El motor multimedia no pudo iniciarse.\\n\\nRevisa FLOW_MOVIE.LOG para diagnostico.");''',1)
s=s.replace('/* V2.25: locate an installed Movian/Showtime plain SELF.',
            '/* V2.26: locate bundled FLOW player first, then external Movian fallback.',1)

# ---------------------------------------------------------------------------
# HQ LIVE BACKGROUND: lossless 1920x1080 base uploaded once to RSX local VRAM.
# The RSX copies the full background into the active backbuffer each frame;
# CPU only draws a few animated particles/glints/symbols on top.
# ---------------------------------------------------------------------------
if '#define APPBG_HQ_PATH' not in s:
    anchor='#define CASE_FRAME_PATH "/dev_hdd0/game/3DISO0001/USRDIR/CASE_FRAME.PNG"\n'
    if anchor not in s:
        raise SystemExit('CASE_FRAME_PATH anchor not found')
    s=s.replace(anchor,anchor+'#define APPBG_HQ_PATH "/dev_hdd0/game/3DISO0001/USRDIR/APPBG_HQ.PNG"\n',1)

if 'static CoverBitmap g_app_bg_hq;' not in s:
    anchor='static CoverBitmap g_case_frame;\n'
    if anchor not in s:
        raise SystemExit('g_case_frame anchor not found')
    s=s.replace(anchor,anchor+'static CoverBitmap g_app_bg_hq;\nstatic bool g_hq_bg_uploaded=false;\n',1)

old_load='''static void load_case_assets()\n{\n    load_app_bitmap(CASE_FRAME_PATH,&g_case_frame);\n}\n'''
new_load=r'''static void load_case_assets()
{
    load_app_bitmap(CASE_FRAME_PATH,&g_case_frame);

    /* V226_HQ_GPU_BG: decode the lossless 1920x1080 artwork once, convert
       RGBA to the framebuffer's X8R8G8B8 layout, then upload it to RSX VRAM. */
    g_hq_bg_uploaded=false;
    if(load_app_bitmap(APPBG_HQ_PATH,&g_app_bg_hq)) {
        size_t count=(size_t)g_app_bg_hq.w*(size_t)g_app_bg_hq.h;
        u32 *argb=(u32*)g_app_bg_hq.rgba;
        for(size_t i=0;i<count;++i) {
            unsigned char *px=g_app_bg_hq.rgba+i*4u;
            u32 r=px[0], g=px[1], b=px[2];
            argb[i]=0xFF000000u|(r<<16)|(g<<8)|b;
        }
        g_hq_bg_uploaded=rsx_upload_hq_background(argb,(u32)g_app_bg_hq.w,(u32)g_app_bg_hq.h)!=0;
        stbi_image_free(g_app_bg_hq.rgba);
        g_app_bg_hq.rgba=NULL;
        g_app_bg_hq.w=g_app_bg_hq.h=0;
    }
    flow_log("HQ_BG",g_hq_bg_uploaded?"RSX_1920X1080_READY":"FALLBACK_PROCEDURAL");
}
'''
if old_load in s:
    s=s.replace(old_load,new_load,1)
elif 'V226_HQ_GPU_BG: decode the lossless' not in s:
    raise SystemExit('load_case_assets block not found')

old_free='''static void free_case_assets()\n{\n    if(g_case_frame.rgba) stbi_image_free(g_case_frame.rgba);\n    g_case_frame.rgba=NULL;\n    g_case_frame.w=g_case_frame.h=0;\n}\n'''
new_free=r'''static void free_case_assets()
{
    if(g_case_frame.rgba) stbi_image_free(g_case_frame.rgba);
    g_case_frame.rgba=NULL;
    g_case_frame.w=g_case_frame.h=0;
    if(g_app_bg_hq.rgba) stbi_image_free(g_app_bg_hq.rgba);
    g_app_bg_hq.rgba=NULL;
    g_app_bg_hq.w=g_app_bg_hq.h=0;
    rsx_free_hq_background();
    g_hq_bg_uploaded=false;
}
'''
if old_free in s:
    s=s.replace(old_free,new_free,1)
elif 'rsx_free_hq_background();' not in s:
    raise SystemExit('free_case_assets block not found')

hq_bg=r'''/* V226_HQ_LIVE_BG: full-HD base image copied by RSX + lightweight animation. */
static int live_tri_wave(unsigned int tick, int period, int amp)
{
    if(period<4 || amp<=0) return 0;
    int p=(int)(tick%(unsigned int)period);
    int half=period/2;
    int v=(p<half)?p:(period-p);
    return (v*(amp*2))/half-amp;
}

static void live_glow_point(int x,int y,int radius,u32 color,unsigned int alpha)
{
    if(alpha>255u) alpha=255u;
    for(int dy=-radius-1;dy<=radius+1;++dy) {
        for(int dx=-radius-1;dx<=radius+1;++dx) {
            int d2=dx*dx+dy*dy;
            int core=radius*radius;
            unsigned int a=0;
            if(d2<=core) a=alpha;
            else if(d2<=(radius+1)*(radius+1)) a=alpha/4u;
            if(a) blend_pixel(x+dx,y+dy,color,a);
        }
    }
}

static void live_aa_line(int x0,int y0,int x1,int y1,u32 color,unsigned int alpha)
{
    int dx=abs(x1-x0), sx=x0<x1?1:-1;
    int dy=-abs(y1-y0), sy=y0<y1?1:-1;
    int err=dx+dy;
    for(;;) {
        blend_pixel(x0,y0,color,alpha);
        blend_pixel(x0-1,y0,color,alpha/5u);
        blend_pixel(x0+1,y0,color,alpha/5u);
        blend_pixel(x0,y0-1,color,alpha/5u);
        blend_pixel(x0,y0+1,color,alpha/5u);
        if(x0==x1 && y0==y1) break;
        int e2=err<<1;
        if(e2>=dy) { err+=dy; x0+=sx; }
        if(e2<=dx) { err+=dx; y0+=sy; }
    }
}

static void live_symbol_triangle(int cx,int cy,int r,u32 c,unsigned int a)
{
    live_aa_line(cx,cy-r,cx-r,cy+r,c,a);
    live_aa_line(cx-r,cy+r,cx+r,cy+r,c,a);
    live_aa_line(cx+r,cy+r,cx,cy-r,c,a);
}

static void live_symbol_square(int cx,int cy,int r,u32 c,unsigned int a)
{
    live_aa_line(cx-r,cy-r,cx+r,cy-r,c,a);
    live_aa_line(cx+r,cy-r,cx+r,cy+r,c,a);
    live_aa_line(cx+r,cy+r,cx-r,cy+r,c,a);
    live_aa_line(cx-r,cy+r,cx-r,cy-r,c,a);
}

static void live_symbol_x(int cx,int cy,int r,u32 c,unsigned int a)
{
    live_aa_line(cx-r,cy-r,cx+r,cy+r,c,a);
    live_aa_line(cx+r,cy-r,cx-r,cy+r,c,a);
}

static void live_symbol_circle(int cx,int cy,int r,u32 c,unsigned int a)
{
    static const signed char px[32]={32,31,30,27,23,18,12,6,0,-6,-12,-18,-23,-27,-30,-31,-32,-31,-30,-27,-23,-18,-12,-6,0,6,12,18,23,27,30,31};
    static const signed char py[32]={0,6,12,18,23,27,30,31,32,31,30,27,23,18,12,6,0,-6,-12,-18,-23,-27,-30,-31,-32,-31,-30,-27,-23,-18,-12,-6};
    for(int i=0;i<32;++i) {
        int j=(i+1)&31;
        live_aa_line(cx+(px[i]*r)/32,cy+(py[i]*r)/32,
                     cx+(px[j]*r)/32,cy+(py[j]*r)/32,c,a);
    }
}

static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    unsigned int f=g_frame;

    /* Exact 1920x1080 artwork at 1080p; RSX scales it only if console output
       is set to a different resolution. The transfer is synchronized before
       CPU/UI drawing, preventing tearing or background/UI races. */
    rsx_draw_hq_background(0xFF03070D);

    /* Independent twinkling points: no fast wrapping and no low-res stepping. */
    for(int i=0;i<30;++i) {
        unsigned int seed=(unsigned int)(37+i*83);
        int bx=24+(int)((seed*97u)%(unsigned int)(sw>48?sw-48:1));
        int by=24+(int)((seed*53u)%(unsigned int)(sh>500?sh/2:sh-48));
        int x=bx+live_tri_wave(f+seed,420+(i%5)*54,5+(i%4)*2);
        int y=by+live_tri_wave(f+seed*3u,510+(i%4)*66,3+(i%3)*2);
        int pulse=128+live_tri_wave(f+seed*5u,78+(i%6)*17,112);
        if(pulse<18) pulse=18;
        if(pulse>240) pulse=240;
        int r=(i%9==0)?2:1;
        live_glow_point(x,y,r,(i%5==0)?0xFF64CFFF:0xFF2498D2,(unsigned int)pulse);
    }

    /* Four subtle symbols float locally instead of crossing the screen fast. */
    int tx=(int)(sw*0.14f)+live_tri_wave(f+17,760,28);
    int ty=(int)(sh*0.18f)+live_tri_wave(f+71,640,14);
    live_symbol_triangle(tx,ty,17,0xFF48BDE8,92u);

    int cx=(int)(sw*0.82f)+live_tri_wave(f+127,840,34);
    int cy=(int)(sh*0.31f)+live_tri_wave(f+193,700,16);
    live_symbol_circle(cx,cy,16,0xFF3AA7D7,84u);

    int xx=(int)(sw*0.70f)+live_tri_wave(f+251,910,26);
    int xy=(int)(sh*0.17f)+live_tri_wave(f+307,780,13);
    live_symbol_x(xx,xy,15,0xFF4697CA,78u);

    int qx=(int)(sw*0.31f)+live_tri_wave(f+359,880,30);
    int qy=(int)(sh*0.34f)+live_tri_wave(f+421,730,15);
    live_symbol_square(qx,qy,14,0xFF3B9FCB,76u);

    /* Slow glints along the wave/horizon region. */
    for(int i=0;i<3;++i) {
        int range=sw+240;
        int gx=(int)(((f/(2u+(unsigned int)i))+i*(unsigned int)(sw/3))%(unsigned int)range)-120;
        int gy=(int)(sh*(0.37f+0.052f*(float)i));
        int pulse=78+live_tri_wave(f+(unsigned int)i*47u,150+(i*23),62);
        if(pulse<18) pulse=18;
        live_glow_point(gx,gy,2,0xFF62CBF3,(unsigned int)pulse);
        live_aa_line(gx-12,gy,gx+12,gy,0xFF3CA7D3,(unsigned int)(pulse/2));
    }

    /* Very faint floor sweep/reflection, kept behind covers. */
    int horizon=(int)(sh*0.627f);
    int sweep=(int)((f*2u)%(unsigned int)(sw+220))-110;
    live_aa_line(sweep,horizon+15,sweep+90,horizon+15,0xFF2D7FA6,42u);
}
'''

pat=re.compile(r'static void draw_background\(\)\n\{.*?\n\}\n\nstatic void draw_rgba_scaled',re.S)
m=pat.search(s)
if not m:
    raise SystemExit('V2.26 draw_background block not found')
s=s[:m.start()]+hq_bg+'\nstatic void draw_rgba_scaled'+s[m.end():]

p.write_text(s)

# ---------------------------------------------------------------------------
# RSX helper API: upload once, local-to-local transfer every frame, wait on
# the same V2.26 safe label path before CPU/UI touches the framebuffer.
# ---------------------------------------------------------------------------
hp=Path('include/rsxutil.h')
h=hp.read_text()
if 'rsx_upload_hq_background' not in h:
    h=h.replace('u32 get_screen_height(void);\n',
                'u32 get_screen_height(void);\nint rsx_upload_hq_background(const u32 *pixels,u32 width,u32 height);\nvoid rsx_draw_hq_background(u32 fallback_color);\nvoid rsx_free_hq_background(void);\n',1)
    hp.write_text(h)

rp=Path('source/rsxutil.cpp')
r=rp.read_text()
if 'V226_HQ_GPU_BG' not in r:
    block=r'''/* V226_HQ_GPU_BG: persistent full-HD background in RSX local memory. */
static u32 *g_hq_bg_buffer=NULL;
static u32 g_hq_bg_offset=0;
static u32 g_hq_bg_width=0;
static u32 g_hq_bg_height=0;

int rsx_upload_hq_background(const u32 *pixels,u32 width,u32 height)
{
    if(!pixels || !width || !height) return 0;
    size_t bytes=(size_t)width*(size_t)height*sizeof(u32);
    if(bytes>32u*1024u*1024u) return 0;
    if(g_hq_bg_buffer) {
        rsxFree(g_hq_bg_buffer);
        g_hq_bg_buffer=NULL;
    }
    g_hq_bg_buffer=(u32*)rsxMemalign(64,bytes);
    if(!g_hq_bg_buffer) return 0;
    memcpy(g_hq_bg_buffer,pixels,bytes);
    if(rsxAddressToOffset(g_hq_bg_buffer,&g_hq_bg_offset)!=0) {
        rsxFree(g_hq_bg_buffer);
        g_hq_bg_buffer=NULL;
        return 0;
    }
    g_hq_bg_width=width;
    g_hq_bg_height=height;
    __asm__ __volatile__("sync" ::: "memory");
    return 1;
}

void rsx_free_hq_background(void)
{
    if(g_hq_bg_buffer) rsxFree(g_hq_bg_buffer);
    g_hq_bg_buffer=NULL;
    g_hq_bg_offset=0;
    g_hq_bg_width=g_hq_bg_height=0;
}

void rsx_draw_hq_background(u32 fallback_color)
{
    if(!g_hq_bg_buffer || !g_hq_bg_width || !g_hq_bg_height) {
        rsx_clear_backbuffer(fallback_color);
        return;
    }

    if(g_hq_bg_width==display_width && g_hq_bg_height==display_height) {
        rsxSetTransferImage(context,GCM_TRANSFER_LOCAL_TO_LOCAL,
            color_offset[curr_fb],color_pitch,0,0,
            g_hq_bg_offset,g_hq_bg_width*sizeof(u32),0,0,
            display_width,display_height,4);
    } else {
        gcmTransferScale scale;
        gcmTransferSurface surface;
        memset(&scale,0,sizeof(scale));
        memset(&surface,0,sizeof(surface));
        scale.conversion=GCM_TRANSFER_CONVERSION_TRUNCATE;
        scale.format=GCM_TRANSFER_SCALE_FORMAT_A8R8G8B8;
        scale.origin=GCM_TRANSFER_ORIGIN_CORNER;
        scale.operation=GCM_TRANSFER_OPERATION_SRCCOPY_AND;
        scale.interp=GCM_TRANSFER_INTERPOLATOR_NEAREST;
        scale.clipX=0; scale.clipY=0;
        scale.clipW=display_width; scale.clipH=display_height;
        scale.outX=0; scale.outY=0;
        scale.outW=display_width; scale.outH=display_height;
        scale.ratioX=rsxGetFixedSint32((float)g_hq_bg_width/(float)display_width);
        scale.ratioY=rsxGetFixedSint32((float)g_hq_bg_height/(float)display_height);
        scale.inX=rsxGetFixedUint16(0.0f);
        scale.inY=rsxGetFixedUint16(0.0f);
        scale.inW=g_hq_bg_width;
        scale.inH=g_hq_bg_height;
        scale.offset=g_hq_bg_offset;
        scale.pitch=g_hq_bg_width*sizeof(u32);
        surface.format=GCM_TRANSFER_SURFACE_FORMAT_A8R8G8B8;
        surface.pitch=color_pitch;
        surface.offset=color_offset[curr_fb];
        rsxSetTransferScaleMode(context,GCM_TRANSFER_LOCAL_TO_LOCAL,GCM_TRANSFER_SURFACE);
        rsxSetTransferScaleSurface(context,&scale,&surface);
    }
    /* Keep the exact V2.26 synchronization semantics. */
    waitFinish();
}
'''
    pat=re.compile(r'(void rsx_clear_backbuffer\(u32 color\)\n\{.*?\n\})\n\nvoid flip\(\)',re.S)
    m=pat.search(r)
    if not m:
        raise SystemExit('rsx_clear_backbuffer/flip anchor not found')
    r=r[:m.end(1)]+'\n\n'+block+'\n\nvoid flip()'+r[m.end():]
    rp.write_text(r)

# ---------------------------------------------------------------------------
# Generate our own lossless Full-HD artwork. 2x supersampling gives smooth
# wave curves and points; final file is a native 1920x1080 PNG.
# ---------------------------------------------------------------------------
from PIL import Image, ImageDraw, ImageFilter
W,H=1920,1080
S=2
w,h=W*S,H*S
img=Image.new('RGB',(w,h),(3,6,10))
pix=img.load()
for y in range(h):
    q=y/(h-1.0)
    if q<0.52:
        t=q/0.52
        c=(int(3+(7-3)*t),int(6+(18-6)*t),int(10+(30-10)*t))
    else:
        t=(q-0.52)/0.48
        c=(int(7+(2-7)*t),int(18+(7-18)*t),int(30+(12-30)*t))
    for x in range(w):
        pix[x,y]=c

d=ImageDraw.Draw(img,'RGB')
for band in range(4):
    pts=[]
    for x in range(-40,w+41,8):
        nx=(x-w*0.54)/w
        y=(0.355+0.050*band + nx*nx*(0.155+0.017*band))*h
        y += math.sin(x*0.0027+band*0.72)*h*0.0055
        pts.append((x,int(y)))
    col=[(14,95,151),(11,78,134),(10,70,116),(9,62,99)][band]
    d.line(pts,fill=col,width=(3 if band==0 else 2)*S,joint='curve')
for i in range(24):
    x=((i*271+31)%W)*S
    y=(18+((i*149+71)%330))*S
    r=(1+(i%3))*S
    col=(18+(i%4)*6,70+(i%5)*8,108+(i%4)*10)
    d.ellipse((x-r,y-r,x+r,y+r),fill=col)
horizon=int(H*0.627)*S
d.line((0,horizon,w,horizon),fill=(22,99,154),width=2*S)
d.line((0,horizon+2*S,w,horizon+2*S),fill=(8,38,60),width=2*S)
for k in range(5):
    yy=horizon+(34+k*55)*S
    alpha_col=(8+k*2,28+k*4,43+k*6)
    d.line((120*S,yy,(W-120)*S,yy),fill=alpha_col,width=1*S)
glow=Image.new('RGBA',(w,h),(0,0,0,0))
gd=ImageDraw.Draw(glow)
gd.rectangle((0,horizon-2*S,w,horizon+3*S),fill=(18,108,170,100))
glow=glow.filter(ImageFilter.GaussianBlur(10*S))
img=Image.alpha_composite(img.convert('RGBA'),glow).convert('RGB')
img=img.resize((W,H),Image.Resampling.LANCZOS)
out=Path('pkgfiles/USRDIR/APPBG_HQ.PNG')
out.parent.mkdir(parents=True,exist_ok=True)
img.save(out,'PNG',optimize=True)
print('APPBG_HQ.PNG',img.size,out.stat().st_size)
print('FLOW MOVIE V2.26: HQ 1080p RSX background + live particles enabled')
