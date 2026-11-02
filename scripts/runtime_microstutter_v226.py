from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 micro-stutter pass:
# 1) remove periodic heartbeat file I/O from the normal render path
# 2) spread USB presence polling across frames (one port each 15 frames)
# 3) avoid an unnecessary full RGBA copy for already-small covers

old_hb = r'''static void flow_log_heartbeat\(\)\n\{.*?\n\}\n'''
m = re.search(old_hb, s, re.S)
if not m:
    raise SystemExit('flow_log_heartbeat block not found')
new_hb = r'''static void flow_log_heartbeat()
{
    /* V2.26 MICROSTUTTER: keep the timing heartbeat in RAM only.
       Normal browsing must never fopen/fflush/fclose every few seconds. */
    uint64_t now=flow_now_us();
    if(g_last_heartbeat_us && now-g_last_heartbeat_us<5000000ULL) return;
    g_last_heartbeat_us=now;
}
'''
s = s[:m.start()] + new_hb + s[m.end():]

needle = '''static bool refresh_usb_state(bool force_scan)\n{\n'''
pos=s.find(needle)
if pos<0:
    raise SystemExit('refresh_usb_state not found')
brace=s.find('{',pos)
depth=0
end=None
for i in range(brace,len(s)):
    if s[i]=='{': depth+=1
    elif s[i]=='}':
        depth-=1
        if depth==0:
            end=i+1
            break
if end is None:
    raise SystemExit('refresh_usb_state end not found')
helper = r'''

static bool refresh_usb_state_slice(int usb)
{
    if(usb<0 || usb>7) return false;
    bool changed=false;
    bool inserted=PS3_NTFS_IsInserted(usb);

    if(inserted && !g_present[usb]) {
        g_present[usb]=true;
        g_insert_delay[usb]=0;
        changed=true;
    } else if(!inserted && g_present[usb]) {
        g_present[usb]=false;
        g_insert_delay[usb]=0;
        release_port(usb,true);
        changed=true;
    }

    if(g_present[usb] && g_mount_count[usb]<=0) {
        if(mount_port(usb)) changed=true;
    }

    if(changed) rebuild_movies();
    return changed;
}
'''
s=s[:end]+helper+s[end:]

old_poll = '''    int poll_counter=0;\n\n    while(app_running) {'''
new_poll = '''    int poll_counter=0;\n    int poll_usb=0;\n\n    while(app_running) {'''
if old_poll not in s:
    raise SystemExit('poll declarations not found')
s=s.replace(old_poll,new_poll,1)

old_block = r'''        /\* V2\.23: permanent lightweight hot-plug monitor\..*?        \}\n\n        freeze_diag_phase\(20\);'''
m=re.search(old_block,s,re.S)
if not m:
    raise SystemExit('old hotplug monitor block not found')
new_block = r'''        /* V2.26 MICROSTUTTER: preserve a full 8-port sweep every ~2 seconds,
           but distribute it as one port every 15 frames instead of probing all
           eight ports in a single frame. This removes the periodic I/O spike. */
        if(++poll_counter>=15) {
            poll_counter=0;
            if(refresh_usb_state_slice(poll_usb)) {
                flow_log("USB_HOTPLUG_CHANGE","library rebuilt");
                g_flow_ready=false;
            }
            poll_usb=(poll_usb+1)&7;
        }

        freeze_diag_phase(20);'''
s=s[:m.start()]+new_block+s[m.end():]

old_diag = '''        uint64_t before_hb=g_last_heartbeat_us;\n        flow_log_heartbeat();\n        bool diag_render=(g_last_heartbeat_us!=before_hb);\n        if(diag_render) flow_log("RENDER_BEGIN",NULL);\n        freeze_diag_phase(30); /* RENDER_UI / DRAW */\n        render_ui();\n        freeze_diag_frame_ok();\n        freeze_diag_phase(40); /* FRAME_OK / LOOP_TAIL */\n        if(diag_render) flow_log("RENDER_END",NULL);'''
new_diag = '''        flow_log_heartbeat();\n        freeze_diag_phase(30); /* RENDER_UI / DRAW */\n        render_ui();\n        freeze_diag_frame_ok();\n        freeze_diag_phase(40); /* FRAME_OK / LOOP_TAIL */'''
if old_diag not in s:
    raise SystemExit('periodic render diagnostic block not found')
s=s.replace(old_diag,new_diag,1)

old_scale = '''    int cw=0, ch=0;\n    unsigned char *scaled = scale_rgba(decoded, iw, ih, &cw, &ch);\n    stbi_image_free(decoded);\n    if(!scaled) return NULL;'''
new_scale = '''    int cw=0, ch=0;\n    unsigned char *scaled=NULL;\n    if(iw<=320 && ih<=480) {\n        /* Lightweight prepared covers (e.g. 320x380) are already render-ready. */\n        scaled=decoded;\n        decoded=NULL;\n        cw=iw; ch=ih;\n    } else {\n        scaled=scale_rgba(decoded,iw,ih,&cw,&ch);\n    }\n    if(decoded) stbi_image_free(decoded);\n    if(!scaled) return NULL;'''
if old_scale not in s:
    raise SystemExit('cover scale block not found')
s=s.replace(old_scale,new_scale,1)

markers=[
    'V2.26 MICROSTUTTER: keep the timing heartbeat in RAM only.',
    'static bool refresh_usb_state_slice(int usb)',
    'if(++poll_counter>=15)',
    'poll_usb=(poll_usb+1)&7;',
    'Lightweight prepared covers (e.g. 320x380) are already render-ready.',
]
for marker in markers:
    if marker not in s:
        raise SystemExit('missing marker: '+marker)

if 'flow_log("RENDER_BEGIN",NULL)' in s or 'flow_log("RENDER_END",NULL)' in s:
    raise SystemExit('periodic render logging still present')

p.write_text(s)
print('V2.26 microstutter pass applied: RAM heartbeat + sliced USB poll + zero-copy small covers')
