from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# Add RSX flip status/depth helpers. Tiny3D exposes the GCM context; the depth
# helpers are exported by its commands module but not declared in tiny3d.h.
anchor = '#include <tiny3d.h>\n'
extra = '''#include <rsx/gcm_sys.h>\nextern \"C\" {\nvoid rsxtiny_DepthTestEnable(void *context, uint32_t enable);\nvoid rsxtiny_DepthWriteEnable(void *context, uint32_t enable);\n}\n'''
if '#include <rsx/gcm_sys.h>' not in s:
    if anchor not in s:
        raise SystemExit('tiny3d include anchor not found')
    s = s.replace(anchor, anchor + extra, 1)

helper_anchor = 'static inline u32 get_screen_height(){ return 512u; }\n'
helpers = r'''
static void flow_wait_gpu_frame_done(){
    int n=500;
    while(n-- > 0 && (s32)gcmGetFlipStatus() > 0) usleep(200);
}

static void flow_begin_frame(){
    flow_wait_gpu_frame_done();
    tiny3d_Clear(0xFF000000,TINY3D_CLEAR_ALL);
    tiny3d_AlphaTest(1,0x00,TINY3D_ALPHA_FUNC_GREATER);
    tiny3d_BlendFunc(1,
        (blend_src_func)(TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA),
        (blend_dst_func)(TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO),
        (blend_func)(TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD));
    tiny3d_Project2D();
    void *ctx=tiny3d_Get_GCM_Context();
    rsxtiny_DepthTestEnable(ctx,0);
    rsxtiny_DepthWriteEnable(ctx,0);
}
'''
if 'flow_wait_gpu_frame_done' not in s:
    if helper_anchor not in s:
        raise SystemExit('screen helper anchor not found')
    s = s.replace(helper_anchor, helper_anchor + helpers, 1)

# Restore the same vertex-buffer size and full-screen virtual viewport pattern
# used by the reference Tiny3D application.
s = s.replace('''    int tiny3d_rc = tiny3d_Init(1024u*1024u);\n    if(tiny3d_rc != 0) return 10;\n''',
'''    int tiny3d_rc = tiny3d_Init(4u*1024u*1024u);\n    if(tiny3d_rc != 0) return 10;\n    tiny3d_UserViewport(1,0.0f,0.0f,(float)Video_Resolution.width/848.0f,(float)Video_Resolution.height/512.0f,\n                        (float)Video_Resolution.width/1920.0f,(float)Video_Resolution.height/1080.0f);\n''',1)

# Replace every V4.1 frame-state block with one safe helper so all paths use the
# same GPU wait, blend state and disabled 2D depth test.
state = '''    tiny3d_Clear(0xFF050914,TINY3D_CLEAR_ALL);\n    tiny3d_AlphaTest(1,0x10,TINY3D_ALPHA_FUNC_GEQUAL);\n    tiny3d_BlendFunc(1,\n                     (blend_src_func)(TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA),\n                     (blend_dst_func)(TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO),\n                     (blend_func)(TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD));\n    tiny3d_Project2D();\n'''
s = s.replace(state, '    flow_begin_frame();\n')

# V4's normal render path used a black clear state rather than the V4.1 state.
state2 = '''    tiny3d_Clear(0xFF000000,TINY3D_CLEAR_ALL);\n    tiny3d_AlphaTest(1,0x00,TINY3D_ALPHA_FUNC_GREATER);\n    tiny3d_BlendFunc(1,(blend_src_func)(TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA),\n                     (blend_dst_func)(TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO),\n                     (blend_func)(TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD));\n    tiny3d_Project2D();\n'''
s = s.replace(state2, '    flow_begin_frame();\n')

# Make do_flip simple and deterministic for system dialogs.
def replace_function(signature, new_text, label):
    global s
    start=s.find(signature)
    if start<0: raise SystemExit(f'{label} signature not found')
    brace=s.find('{',start)
    depth=0; end=-1
    for i in range(brace,len(s)):
        if s[i]=='{': depth+=1
        elif s[i]=='}':
            depth-=1
            if depth==0:
                end=i+1; break
    if end<0: raise SystemExit(f'{label} closing brace not found')
    s=s[:start]+new_text+s[end:]

replace_function('static void do_flip()', r'''static void do_flip(){
    sysUtilCheckCallback();
    flow_begin_frame();
    fill_rect(0,0,848,512,0xFF050914);
    tiny3d_Flip();
}''', 'do_flip')

# Replace the priming section with a clearly visible, persistent RSX-only splash.
# No font, NTFS, Mamba or cover code participates in these frames.
start = s.find('    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);\n')
load = s.find('    load_font();\n', start)
if start < 0 or load < 0:
    raise SystemExit('startup splash anchors not found')
start += len('    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);\n')
startup = r'''
    for(int boot_frame=0; boot_frame<24; ++boot_frame){
        flow_begin_frame();
        fill_rect(0,0,848,512,0xFF071525);
        fill_rect(0,0,848,10,0xFF42D4FF);
        fill_rect(0,502,848,10,0xFF42D4FF);
        fill_rect(70,205,708,102,0xFF10283C);
        fill_rect(70,205,8,102,0xFFFFFFFF);
        tiny3d_Flip();
        usleep(16000);
    }

'''
s = s[:start] + startup + s[load:]

# Once the font atlas exists, show a second startup frame long enough that a
# backend stall can no longer look like a black-screen renderer failure.
font_anchor = '    flow_init_font_texture();\n'
font_splash = r'''    flow_init_font_texture();
    for(int boot_frame=0; boot_frame<24; ++boot_frame){
        flow_begin_frame();
        fill_rect(0,0,848,512,0xFF071525);
        draw_centered(205,"FLOW MOVIE 3D",2,0xFFFFFFFF);
        draw_centered(270,"INICIANDO BIBLIOTECA...",1,0xFF42D4FF);
        tiny3d_Flip();
        usleep(16000);
    }
'''
if font_anchor not in s:
    raise SystemExit('font texture anchor not found')
s = s.replace(font_anchor, font_splash, 1)

p.write_text(s)
print('FLOW MOVIE 3D V4.2 RSX-safe patch applied: GPU wait, depth off, 4MB buffer, staged splash')
