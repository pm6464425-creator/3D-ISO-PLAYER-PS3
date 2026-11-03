from pathlib import Path

main_p = Path('source/main.cpp')
rsx_p = Path('source/rsxutil.cpp')
hdr_p = Path('include/rsxutil.h')

main = main_p.read_text()
rsx = rsx_p.read_text()
hdr = hdr_p.read_text()

# Idempotent marker.
if 'V2.26 GPU COVER: local-to-local RSX transfer + hardware scale.' not in main:
    old = '''static void cover_cache_clear()\n{\n    for(int i=0;i<COVER_CACHE_SLOTS;i++) {\n        if(g_cover_cache[i].rgba) free(g_cover_cache[i].rgba);\n        g_cover_cache[i].rgba = NULL;\n        g_cover_cache[i].path.clear();\n        g_cover_cache[i].w = g_cover_cache[i].h = 0;\n        g_cover_cache[i].stamp = 0;\n    }\n    g_cover_stamp = 1;\n}\n'''
    new = '''static void cover_cache_clear()\n{\n    rsx_cover_free_all();\n    for(int i=0;i<COVER_CACHE_SLOTS;i++) {\n        if(g_cover_cache[i].rgba) free(g_cover_cache[i].rgba);\n        g_cover_cache[i].rgba = NULL;\n        g_cover_cache[i].path.clear();\n        g_cover_cache[i].w = g_cover_cache[i].h = 0;\n        g_cover_cache[i].stamp = 0;\n    }\n    g_cover_stamp = 1;\n}\n'''
    if old not in main:
        raise SystemExit('cover_cache_clear anchor missing')
    main = main.replace(old, new, 1)

    old = '''    if(g_cover_cache[slot].rgba) free(g_cover_cache[slot].rgba);\n    g_cover_cache[slot].rgba = scaled;\n    g_cover_cache[slot].w = cw;\n    g_cover_cache[slot].h = ch;\n    g_cover_cache[slot].path = m.cover;\n    g_cover_cache[slot].stamp = ++g_cover_stamp;\n    flow_log("COVER_LOAD_END",m.cover.c_str());\n    return &g_cover_cache[slot];\n'''
    new = '''    /* V2.26 GPU COVER: convert once while idle and upload once to RSX local memory.\n       Animation frames no longer convert/scale every poster pixel on the PPU. */\n    rsx_cover_free(slot);\n    size_t cover_px=(size_t)cw*(size_t)ch;\n    u32 *argb=(u32*)malloc(cover_px*sizeof(u32));\n    int gpu_ready=0;\n    if(argb) {\n        for(size_t p=0;p<cover_px;++p) {\n            const unsigned char *sp=scaled+p*4u;\n            argb[p]=0xFF000000u|((u32)sp[0]<<16)|((u32)sp[1]<<8)|(u32)sp[2];\n        }\n        gpu_ready=rsx_cover_upload(slot,argb,(u32)cw,(u32)ch);\n        free(argb);\n    }\n\n    if(g_cover_cache[slot].rgba) free(g_cover_cache[slot].rgba);\n    g_cover_cache[slot].rgba = scaled;\n    g_cover_cache[slot].w = cw;\n    g_cover_cache[slot].h = ch;\n    g_cover_cache[slot].path = m.cover;\n    g_cover_cache[slot].stamp = ++g_cover_stamp;\n    flow_log("COVER_LOAD_END",gpu_ready?"RSX_READY":m.cover.c_str());\n    return &g_cover_cache[slot];\n'''
    if old not in main:
        raise SystemExit('cover upload anchor missing')
    main = main.replace(old, new, 1)

    old = '''    CoverBitmap *c=find_cached_cover(m);\n    if(c) {\n        draw_rgba_scaled(ax,ay,aw,ah,c);\n        /* V2.8 HARD PERF: reflection disabled; it was CPU alpha blended. */\n    } else {\n        draw_generic_cover(ax,ay,aw,ah,m,selected);\n    }\n'''
    new = '''    CoverBitmap *c=find_cached_cover(m);\n    if(c) {\n        int cover_slot=(int)(c-g_cover_cache);\n        /* V2.26 GPU COVER: local-to-local RSX transfer + hardware scale.\n           The short fence preserves the exact existing CPU overlay/card order. */\n        if(!rsx_cover_draw(cover_slot,ax,ay,aw,ah))\n            draw_rgba_scaled(ax,ay,aw,ah,c);\n        /* V2.8 HARD PERF: reflection disabled; it was CPU alpha blended. */\n    } else {\n        draw_generic_cover(ax,ay,aw,ah,m,selected);\n    }\n'''
    if old not in main:
        raise SystemExit('draw_poster cover anchor missing')
    main = main.replace(old, new, 1)

main_p.write_text(main)

if 'V2.26 GPU COVER: persistent poster surfaces in RSX local memory.' not in rsx:
    marker = '\n\nvoid flip()\n{\n'
    if marker not in rsx:
        raise SystemExit('rsx flip anchor missing')
    impl = r'''

/* V2.26 GPU COVER: persistent poster surfaces in RSX local memory.
   JPEG decode/resize happens on the PPU only while idle. Animation frames use
   the RSX transfer scaler instead of the old software per-pixel poster loop. */
#define RSX_COVER_SLOTS 16
static u32 *g_cover_gpu_buffer[RSX_COVER_SLOTS]={0};
static u32 g_cover_gpu_offset[RSX_COVER_SLOTS]={0};
static u32 g_cover_gpu_width[RSX_COVER_SLOTS]={0};
static u32 g_cover_gpu_height[RSX_COVER_SLOTS]={0};

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
    for(int i=0;i<RSX_COVER_SLOTS;++i) rsx_cover_free(i);
}

int rsx_cover_upload(int slot,const u32 *pixels,u32 width,u32 height)
{
    if(slot<0 || slot>=RSX_COVER_SLOTS || !pixels || !width || !height) return 0;
    if(width>1024 || height>1024) return 0;
    size_t bytes=(size_t)width*(size_t)height*sizeof(u32);
    if(bytes>4u*1024u*1024u) return 0;

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

    /* Avoid undefined signed transfer coordinates on the far clipped card.
       It falls back to the old safe software path; central/near cards use RSX. */
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

    /* Keep CPU-drawn case bands and near/far ordering exactly as before. */
    waitFinish();
    return 1;
}
'''
    rsx = rsx.replace(marker, impl + marker, 1)

rsx_p.write_text(rsx)

if 'rsx_cover_upload' not in hdr:
    anchor = 'u32 get_screen_height(void);\n'
    if anchor not in hdr:
        raise SystemExit('rsxutil header anchor missing')
    hdr = hdr.replace(anchor, anchor + '''\n/* V2.26 GPU cover cache */\nint rsx_cover_upload(int slot,const u32 *pixels,u32 width,u32 height);\nvoid rsx_cover_free(int slot);\nvoid rsx_cover_free_all(void);\nint rsx_cover_draw(int slot,int x,int y,int w,int h);\n''', 1)

hdr_p.write_text(hdr)

# Final invariants.
checks = [
    'rsx_cover_free_all();',
    'gpu_ready=rsx_cover_upload(slot,argb,(u32)cw,(u32)ch);',
    'if(!rsx_cover_draw(cover_slot,ax,ay,aw,ah))',
    'V2.26 GPU COVER: persistent poster surfaces in RSX local memory.',
    'int rsx_cover_draw(int slot,int x,int y,int w,int h)',
]
joined = main + rsx + hdr
for c in checks:
    if c not in joined:
        raise SystemExit('GPU cover invariant missing: ' + c)

print('V2.26 GPU cover patch applied: real poster scaling moved from PPU to RSX')
