from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def replace_function(signature, new_text, label):
    global s
    start = s.find(signature)
    if start < 0:
        raise SystemExit(f'{label} signature not found')
    brace = s.find('{', start)
    if brace < 0:
        raise SystemExit(f'{label} opening brace not found')
    depth = 0
    end = -1
    for i in range(brace, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise SystemExit(f'{label} closing brace not found')
    s = s[:start] + new_text + s[end:]


# Tiny3D already maps its virtual 848x512 2D surface to the current PS3 video mode.
# The custom viewport used in V4 is unnecessary and can produce a black frame on
# real hardware/video-mode combinations, so remove it completely.
viewport = '''    tiny3d_UserViewport(1,0.0f,0.0f,(float)Video_Resolution.width/848.0f,(float)Video_Resolution.height/512.0f,\n                        (float)Video_Resolution.width/1920.0f,(float)Video_Resolution.height/1080.0f);\n'''
if viewport not in s:
    raise SystemExit('V4 custom viewport anchor not found')
s = s.replace(viewport, '', 1)

# Follow the official Tiny3D samples more closely: 1 MiB vertex buffer, check init,
# default viewport, and the standard alpha/blend state.
old_init = '    tiny3d_Init(4u*1024u*1024u);\n'
new_init = '''    int tiny3d_rc = tiny3d_Init(1024u*1024u);\n    if(tiny3d_rc != 0) return 10;\n'''
if old_init not in s:
    raise SystemExit('Tiny3D init anchor not found')
s = s.replace(old_init, new_init, 1)

old_state = '''    tiny3d_Clear(0xFF000000,TINY3D_CLEAR_ALL);\n    tiny3d_AlphaTest(1,0x00,TINY3D_ALPHA_FUNC_GREATER);\n    tiny3d_BlendFunc(1,(blend_src_func)(TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA),\n                     (blend_dst_func)(TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO),\n                     (blend_func)(TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD));\n    tiny3d_Project2D();\n'''
new_state = '''    tiny3d_Clear(0xFF050914,TINY3D_CLEAR_ALL);\n    tiny3d_AlphaTest(1,0x10,TINY3D_ALPHA_FUNC_GEQUAL);\n    tiny3d_BlendFunc(1,\n                     TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA,\n                     TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO,\n                     TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD);\n    tiny3d_Project2D();\n'''
if old_state not in s:
    raise SystemExit('Tiny3D frame-state anchor not found')
s = s.replace(old_state, new_state, 1)

# System dialogs can appear before the first normal UI frame (for example on a
# compatibility error). Keep feeding Tiny3D a valid visible frame while waiting.
replace_function('static void do_flip()', r'''static void do_flip(){
    sysUtilCheckCallback();
    tiny3d_Clear(0xFF050914,TINY3D_CLEAR_ALL);
    tiny3d_AlphaTest(1,0x10,TINY3D_ALPHA_FUNC_GEQUAL);
    tiny3d_BlendFunc(1,
                     TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA,
                     TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO,
                     TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD);
    tiny3d_Project2D();
    tiny3d_Flip();
}''', 'do_flip')

# Prime RSX with one known-good 2D frame before font loading, USB/NTFS scanning,
# or compatibility dialogs. This also prevents the user from being left on an
# untouched black framebuffer during startup work.
anchor = '    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);\n    load_font();\n'
prime = '''    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);\n\n    tiny3d_Clear(0xFF050914,TINY3D_CLEAR_ALL);\n    tiny3d_AlphaTest(1,0x10,TINY3D_ALPHA_FUNC_GEQUAL);\n    tiny3d_BlendFunc(1,\n                     TINY3D_BLEND_FUNC_SRC_RGB_SRC_ALPHA|TINY3D_BLEND_FUNC_SRC_ALPHA_SRC_ALPHA,\n                     TINY3D_BLEND_FUNC_DST_RGB_ONE_MINUS_SRC_ALPHA|TINY3D_BLEND_FUNC_DST_ALPHA_ZERO,\n                     TINY3D_BLEND_RGB_FUNC_ADD|TINY3D_BLEND_ALPHA_FUNC_ADD);\n    tiny3d_Project2D();\n    fill_rect(0,0,848,512,0xFF050914);\n    fill_rect(36,36,776,4,0xFF42D4FF);\n    tiny3d_Flip();\n\n    load_font();\n'''
if anchor not in s:
    raise SystemExit('startup prime-frame anchor not found')
s = s.replace(anchor, prime, 1)

if 'tiny3d_UserViewport(' in s:
    raise SystemExit('custom Tiny3D viewport still present')

p.write_text(s)
print('FLOW MOVIE 3D V4.1 black-screen fix applied: default Tiny3D viewport and primed RSX frame')
