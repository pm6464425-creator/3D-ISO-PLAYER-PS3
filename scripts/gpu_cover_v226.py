from pathlib import Path
import re

main_p = Path('source/main.cpp')
rsx_p = Path('source/rsxutil.cpp')
hdr_p = Path('include/rsxutil.h')

main = main_p.read_text()
rsx = rsx_p.read_text()
hdr = hdr_p.read_text()

# V2.26 GPU COVER BATCHED
# JPEG decode/resize remains idle-only. Each cached cover is converted once to
# ARGB and uploaded to RSX local memory. During animation all real covers are
# hardware-scaled in one RSX batch, then synchronized exactly once before the
# existing CPU case-frame overlays are drawn.

if 'V2.26 GPU COVER BATCHED: upload once, draw all, sync once.' not in main:
    old = '''static void cover_cache_clear()\n{\n    for(int i=0;i<COVER_CACHE_SLOTS;i++) {\n        if(g_cover_cache[i].rgba) free(g_cover_cache[i].rgba);\n        g_cover_cache[i].rgba = NULL;\n        g_cover_cache[i].path.clear();\n        g_cover_cache[i].w = g_cover_cache[i].h = 0;\n        g_cover_cache[i].stamp = 0;\n    }\n    g_cover_stamp = 1;\n}\n'''
    new = '''static void cover_cache_clear()\n{\n    rsx_cover_free_all();\n    for(int i=0;i<COVER_CACHE_SLOTS;i++) {\n        if(g_cover_cache[i].rgba) free(g_cover_cache[i].rgba);\n        g_cover_cache[i].rgba = NULL;\n        g_cover_cache[i].path.clear();\n        g_cover_cache[i].w = g_cover_cache[i].h = 0;\n        g_cover_cache[i].stamp = 0;\n    }\n    g_cover_stamp = 1;\n}\n'''
    if old not in main:
        raise SystemExit('cover_cache_clear anchor missing')
    main = main.replace(old, new, 1)

    old = '''    if(g_cover_cache[slot].rgba) free(g_cover_cache[slot].rgba);\n    g_cover_cache[slot].rgba = scaled;\n    g_cover_cache[slot].w = cw;\n    g_cover_cache[slot].h = ch;\n    g_cover_cache[slot].path = m.cover;\n    g_cover_cache[slot].stamp = ++g_cover_stamp;\n    flow_log("COVER_LOAD_END",m.cover.c_str());\n    return &g_cover_cache[slot];\n'''
    new = '''    /* V2.26 GPU COVER BATCHED: convert once while idle and upload once. */\n    rsx_cover_free(slot);\n    size_t cover_px=(size_t)cw*(size_t)ch;\n    u32 *argb=(u32*)malloc(cover_px*sizeof(u32));\n    int gpu_ready=0;\n    if(argb) {\n        for(size_t p=0;p<cover_px;++p) {\n            const unsigned char *sp=scaled+p*4u;\n            argb[p]=0xFF000000u|((u32)sp[0]<<16)|((u32)sp[1]<<8)|(u32)sp[2];\n        }\n        gpu_ready=rsx_cover_upload(slot,argb,(u32)cw,(u32)ch);\n        free(argb);\n    }\n\n    if(g_cover_cache[slot].rgba) free(g_cover_cache[slot].rgba);\n    g_cover_cache[slot].rgba = scaled;\n    g_cover_cache[slot].w = cw;\n    g_cover_cache[slot].h = ch;\n    g_cover_cache[slot].path = m.cover;\n    g_cover_cache[slot].stamp = ++g_cover_stamp;\n    flow_log("COVER_LOAD_END",gpu_ready?"RSX_READY":m.cover.c_str());\n    return &g_cover_cache[slot];\n'''
    if old not in main:
        raise SystemExit('cover upload anchor missing')
    main = main.replace(old, new, 1)

    # Replace poster renderer with three phases:
    # 0 = CPU shadow + generic/no-cover art
    # 1 = all real cover pixels queued to RSX (software fallback only if needed)
    # 2 = original case-frame overlays + selection glow after one RSX sync
    pat = re.compile(r'''static void draw_poster\(int x, int y, int w, int h, const Movie &m, bool selected, bool allow_cover_load\)\n\{.*?\n\}\n\nstatic int connected_count\(\)''', re.S)
    m = pat.search(main)
    if not m:
        raise SystemExit('draw_poster function anchor missing')
    replacement = r'''static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected, bool allow_cover_load, int phase)
{
    int screen_w=(int)get_screen_width(), screen_h=(int)get_screen_height();
    if(x>=screen_w || y>=screen_h || x+w<=0 || y+h<=0) return;

    /* Artwork window coordinates match the 640x822 remastered master frame. */
    int ax=x+(w*10)/640;
    int ay=y+(h*70)/822;
    int ar=x+(w*630)/640;
    int ab=y+(h*806)/822;
    int aw=ar-ax;
    int ah=ab-ay;
    if(aw<1) aw=1;
    if(ah<1) ah=1;

    (void)allow_cover_load;
    CoverBitmap *c=find_cached_cover(m);

    if(phase==0) {
        /* Draw every CPU-only underlay before any RSX cover commands are queued. */
        int shad=(w>220)?7:4;
        fill_rect(x+shad,y+shad,w,h,0x44000000);
        if(!c) draw_generic_cover(ax,ay,aw,ah,m,selected);
        return;
    }

    if(phase==1) {
        if(c) {
            int cover_slot=(int)(c-g_cover_cache);
            /* V2.26 GPU COVER BATCHED: upload once, draw all, sync once. */
            if(!rsx_cover_draw(cover_slot,ax,ay,aw,ah))
                draw_rgba_scaled(ax,ay,aw,ah,c);
        }
        return;
    }

    if(phase!=2) return;

    /* Original remastered Blu-ray case renderer, unchanged. It runs only after
       rsx_cover_sync(), so the CPU never races the RSX while drawing borders. */
    if(g_case_frame.rgba) {
        int fw=g_case_frame.w, fh=g_case_frame.h;
        int top_src=fh*88/822; if(top_src<1) top_src=1;
        int bot_y=fh*790/822; if(bot_y<0) bot_y=0;
        int side_y=fh*64/822;
        int side_h=fh*748/822; if(side_y+side_h>fh) side_h=fh-side_y;
        int edge=fw*18/640; if(edge<2) edge=2;

        int top_dst=h*88/822; if(top_dst<2) top_dst=2;
        int bot_dst_y=h*790/822;
        int side_dst_y=h*64/822;
        int side_dst_h=h*748/822;
        int edge_dst=w*18/640; if(edge_dst<2) edge_dst=2;

        draw_rgba_region_scaled(x,y,w,top_dst,&g_case_frame,0,0,fw,top_src);
        draw_rgba_region_scaled(x,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,0,side_y,edge,side_h);
        draw_rgba_region_scaled(x+w-edge_dst,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,fw-edge,side_y,edge,side_h);
        draw_rgba_region_scaled(x,y+bot_dst_y,w,h-bot_dst_y,&g_case_frame,0,bot_y,fw,fh-bot_y);
    }

    if(selected) {
        int glow_w=w*58/100;
        if(glow_w<12) glow_w=12;
        int gx=x+(w-glow_w)/2;
        fill_rect(gx,y+h+2,glow_w,2,0xB85FD7FF);
    }
}

static int connected_count()'''
    main = main[:m.start()] + replacement + main[m.end():]

    old_loop = '''        bool flow_animating = fabsf(g_flow_pos-(float)g_selected)>0.010f || fabsf(g_flow_vel)>0.010f;\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating);\n        }\n'''
    new_loop = '''        bool flow_animating = fabsf(g_flow_pos-(float)g_selected)>0.010f || fabsf(g_flow_vel)>0.010f;\n\n        /* Phase 0: all CPU underlays first. */\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating,0);\n        }\n        /* Phase 1: queue every real cover to RSX, far-to-near. No per-cover fence. */\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating,1);\n        }\n        /* Exactly one GPU fence, and only when at least one RSX cover was queued. */\n        rsx_cover_sync();\n        /* Phase 2: restore the exact original case-frame bands and selected glow. */\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating,2);\n        }\n'''
    if old_loop not in main:
        raise SystemExit('coverflow render loop anchor missing')
    main = main.replace(old_loop, new_loop, 1)

main_p.write_text(main)

if 'V2.26 GPU COVER: persistent poster surfaces in RSX local memory.' not in rsx:
    marker = '\n\nvoid flip()\n{\n'
    if marker not in rsx:
        raise SystemExit('rsx flip anchor missing')
    impl = r'''

/* V2.26 GPU COVER: persistent poster surfaces in RSX local memory.
   Cover scaling is batched: zero fences per cover, at most one fence per frame. */
#define RSX_COVER_SLOTS 16
static u32 *g_cover_gpu_buffer[RSX_COVER_SLOTS]={0};
static u32 g_cover_gpu_offset[RSX_COVER_SLOTS]={0};
static u32 g_cover_gpu_width[RSX_COVER_SLOTS]={0};
static u32 g_cover_gpu_height[RSX_COVER_SLOTS]={0};
static int g_cover_gpu_pending=0;

void rsx_cover_free(int slot)
{
    if(slot<0 || slot>=RSX_COVER_SLOTS) return;
    if(g_cover_gpu_buffer[slot]) rsxFree(g_cover_gpu_buffer[slot]);
    g_cover_gpu_buffer[slot]=NULL;
    g_cover_gpu_offset[slot]=0;
    g_cover_gpu_width[slot]=0;
    g_cover_gpu_height[slot]=0;
}

void rsx_cover_free_all(void)
{
    /* Do not free local surfaces while an outstanding transfer may reference them. */
    rsx_cover_sync();
    for(int i=0;i<RSX_COVER_SLOTS;++i) rsx_cover_free(i);
}

int rsx_cover_upload(int slot,const u32 *pixels,u32 width,u32 height)
{
    if(slot<0 || slot>=RSX_COVER_SLOTS || !pixels || !width || !height) return 0;
    if(width>1024 || height>1024) return 0;
    size_t bytes=(size_t)width*(size_t)height*sizeof(u32);
    if(bytes>4u*1024u*1024u) return 0;

    /* Uploads happen only from idle prefetch, after the prior frame has flipped. */
    rsx_cover_sync();
    rsx_cover_free(slot);
    u32 *buf=(u32*)rsxMemalign(64,bytes);
    if(!buf) return 0;
    memcpy(buf,pixels,bytes);
    u32 off=0;
    if(rsxAddressToOffset(buf,&off)!=0) {
        rsxFree(buf);
        return 0;
    }
    g_cover_gpu_buffer[slot]=buf;
    g_cover_gpu_offset[slot]=off;
    g_cover_gpu_width[slot]=width;
    g_cover_gpu_height[slot]=height;
    __asm__ __volatile__("sync" ::: "memory");
    return 1;
}

int rsx_cover_draw(int slot,int x,int y,int w,int h)
{
    if(slot<0 || slot>=RSX_COVER_SLOTS || !g_cover_gpu_buffer[slot] || w<=0 || h<=0) return 0;

    /* Clipped extreme cards retain the proven software fallback. */
    if(x<0 || y<0 || x+w>(int)display_width || y+h>(int)display_height) return 0;

    gcmTransferScale scale;
    gcmTransferSurface surface;
    memset(&scale,0,sizeof(scale));
    memset(&surface,0,sizeof(surface));

    scale.conversion=GCM_TRANSFER_CONVERSION_TRUNCATE;
    scale.format=GCM_TRANSFER_SCALE_FORMAT_A8R8G8B8;
    scale.origin=GCM_TRANSFER_ORIGIN_CORNER;
    scale.operation=GCM_TRANSFER_OPERATION_SRCCOPY_AND;
    scale.interp=GCM_TRANSFER_INTERPOLATOR_NEAREST;
    scale.clipX=x; scale.clipY=y;
    scale.clipW=w; scale.clipH=h;
    scale.outX=x; scale.outY=y;
    scale.outW=w; scale.outH=h;
    scale.ratioX=rsxGetFixedSint32((float)g_cover_gpu_width[slot]/(float)w);
    scale.ratioY=rsxGetFixedSint32((float)g_cover_gpu_height[slot]/(float)h);
    scale.inX=rsxGetFixedUint16(0.0f);
    scale.inY=rsxGetFixedUint16(0.0f);
    scale.inW=g_cover_gpu_width[slot];
    scale.inH=g_cover_gpu_height[slot];
    scale.offset=g_cover_gpu_offset[slot];
    scale.pitch=g_cover_gpu_width[slot]*sizeof(u32);

    surface.format=GCM_TRANSFER_SURFACE_FORMAT_A8R8G8B8;
    surface.pitch=color_pitch;
    surface.offset=color_offset[curr_fb];

    rsxSetTransferScaleMode(context,GCM_TRANSFER_LOCAL_TO_LOCAL,GCM_TRANSFER_SURFACE);
    rsxSetTransferScaleSurface(context,&scale,&surface);
    g_cover_gpu_pending=1;
    return 1;
}

void rsx_cover_sync(void)
{
    if(!g_cover_gpu_pending) return;
    waitFinish();
    g_cover_gpu_pending=0;
}
'''
    rsx = rsx.replace(marker, impl + marker, 1)

rsx_p.write_text(rsx)

if 'rsx_cover_upload' not in hdr:
    anchor = 'u32 get_screen_height(void);\n'
    if anchor not in hdr:
        raise SystemExit('rsxutil header anchor missing')
    hdr = hdr.replace(anchor, anchor + '''\n/* V2.26 GPU cover cache */\nint rsx_cover_upload(int slot,const u32 *pixels,u32 width,u32 height);\nvoid rsx_cover_free(int slot);\nvoid rsx_cover_free_all(void);\nint rsx_cover_draw(int slot,int x,int y,int w,int h);\nvoid rsx_cover_sync(void);\n''', 1)

hdr_p.write_text(hdr)

checks = [
    'rsx_cover_free_all();',
    'gpu_ready=rsx_cover_upload(slot,argb,(u32)cw,(u32)ch);',
    'V2.26 GPU COVER BATCHED: upload once, draw all, sync once.',
    'rsx_cover_sync();',
    'static int g_cover_gpu_pending=0;',
    'int rsx_cover_draw(int slot,int x,int y,int w,int h)',
    'void rsx_cover_sync(void)',
]
joined = main + rsx + hdr
for c in checks:
    if c not in joined:
        raise SystemExit('GPU cover invariant missing: ' + c)

# Critical regression guard: there must be no GPU completion fence in rsx_cover_draw.
draw_start = rsx.find('int rsx_cover_draw(')
draw_end = rsx.find('void rsx_cover_sync(', draw_start)
if draw_start < 0 or draw_end < 0 or 'waitFinish();' in rsx[draw_start:draw_end]:
    raise SystemExit('per-cover waitFinish regression')

print('V2.26 GPU cover BATCHED applied: all real posters scale on RSX, one conditional sync per frame')
