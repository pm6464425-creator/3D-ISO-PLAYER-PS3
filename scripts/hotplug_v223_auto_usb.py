from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.23 AUTO HOTPLUG
# Keep V2.22 RSX stability fix untouched. Re-enable only lightweight USB
# presence monitoring so removing/inserting external disks updates the library.

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.22 SAFE CMD RESET");',
            'flow_log("SESSION_START","FLOW MOVIE V2.23 AUTO HOTPLUG");',1)

old='''    int repeat_left=0, repeat_right=0;\n    int poll_counter=0;\n    int fast_usb_attempts=0;'''
new='''    int repeat_left=0, repeat_right=0;\n    int poll_counter=0;'''
if old not in s:
    raise SystemExit('poll variable anchor not found')
s=s.replace(old,new,1)

old='''        /* V2.17: fast USB retry exists only while the initial library is empty.\n           After movies are visible, do NOT touch NTFS automatically during\n           browsing.  This keeps the 60 FPS render path isolated from periodic\n           USB/NTFS state probes. TRIANGLE remains the manual refresh. */\n        if(g_movies.empty() && fast_usb_attempts<15) {\n            if(++poll_counter>=60) {\n                poll_counter=0;\n                flow_log("USB_REFRESH_BEGIN","startup-fast");\n                refresh_usb_state(false);\n                flow_log("USB_REFRESH_END","startup-fast");\n                fast_usb_attempts++;\n            }\n        } else {\n            poll_counter=0;\n        }'''

new='''        /* V2.23: permanent lightweight hot-plug monitor.\n           At 60 FPS this checks USB presence about every 2 seconds.\n           refresh_usb_state() rebuilds the movie list only when a device\n           was inserted/removed or a pending mount finally succeeds, so normal\n           browsing does not repeatedly rescan BDISO/MKV folders. */\n        if(++poll_counter>=120) {\n            poll_counter=0;\n            if(refresh_usb_state(false)) {\n                flow_log("USB_HOTPLUG_CHANGE","library rebuilt");\n                g_flow_ready=false;\n            }\n        }'''

if old not in s:
    raise SystemExit('V2.17 polling block not found')
s=s.replace(old,new,1)

p.write_text(s)
print('FLOW MOVIE V2.23: automatic 2-second USB hotplug refresh; V2.22 RSX fix preserved')
