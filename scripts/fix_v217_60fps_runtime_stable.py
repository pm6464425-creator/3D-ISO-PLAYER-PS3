from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.17
# Keep the 60 Hz/VSync coverflow untouched.
# Once a library has been detected, stop automatic NTFS polling completely.
# The app's runtime job is browsing/rendering; TRIANGLE remains the explicit
# manual refresh for hot-plug/rescan.  Startup still retries quickly while the
# library is empty.

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.15");',
            'flow_log("SESSION_START","FLOW MOVIE V2.17");',1)

old='''        /* V2.16: while startup still has no movies, retry NTFS at ~1 s for\n           at most 15 attempts. Once the disk is mounted/library is visible,\n           return to the conservative 30 s health probe. */\n        int poll_limit=(g_movies.empty() && fast_usb_attempts<15) ? 60 : 1800;\n        if(++poll_counter>=poll_limit) {\n            poll_counter=0;\n            const char *kind=(poll_limit==60)?"startup-fast":"auto";\n            flow_log("USB_REFRESH_BEGIN",kind);\n            refresh_usb_state(false);\n            flow_log("USB_REFRESH_END",kind);\n            if(poll_limit==60) fast_usb_attempts++;\n        }'''

new='''        /* V2.17: fast USB retry exists only while the initial library is empty.\n           After movies are visible, do NOT touch NTFS automatically during\n           browsing.  This keeps the 60 FPS render path isolated from periodic\n           USB/NTFS state probes. TRIANGLE remains the manual refresh. */\n        if(g_movies.empty() && fast_usb_attempts<15) {\n            if(++poll_counter>=60) {\n                poll_counter=0;\n                flow_log("USB_REFRESH_BEGIN","startup-fast");\n                refresh_usb_state(false);\n                flow_log("USB_REFRESH_END","startup-fast");\n                fast_usb_attempts++;\n            }\n        } else {\n            poll_counter=0;\n        }'''

if old not in s:
    raise SystemExit('V2.16 polling block not found')
s=s.replace(old,new,1)

p.write_text(s)
print('FLOW MOVIE V2.17: 60 FPS preserved; runtime automatic NTFS polling disabled')
