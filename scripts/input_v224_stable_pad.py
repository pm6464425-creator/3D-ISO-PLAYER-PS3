from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.24 INPUT FIX
# Preserve V2.22 RSX stability + V2.23 hotplug exactly.
# ioPadGetData() may return pad.len == 0 when there is no NEW controller packet.
# Do not interpret that as a physical release: retain the last valid pad state.

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.23 AUTO HOTPLUG");',
            'flow_log("SESSION_START","FLOW MOVIE V2.24 INPUT FIX");',1)

old='''        freeze_diag_phase(20); /* PAD_READ */\n        memset(&pad,0,sizeof(pad));\n        ioPadGetData(0,&pad);\n        freeze_diag_phase(21); /* INPUT_UPDATE */'''
new='''        freeze_diag_phase(20); /* PAD_READ */\n        padData pad_sample;\n        memset(&pad_sample,0,sizeof(pad_sample));\n        int pad_ret=ioPadGetData(0,&pad_sample);\n        /* PSL1GHT only provides a fresh packet when pad_sample.len > 0.\n           A zero-length packet means "no change", NOT "all buttons released".\n           Keep the last valid state so held buttons cannot become fake new presses. */\n        if(pad_ret==0 && pad_sample.len>0) {\n            pad=pad_sample;\n        } else if(pad_ret!=0) {\n            /* Real read/disconnect error: clear state safely. */\n            memset(&pad,0,sizeof(pad));\n        }\n        freeze_diag_phase(21); /* INPUT_UPDATE */'''
if old not in s:
    raise SystemExit('pad read anchor not found')
s=s.replace(old,new,1)

old='''        if(left) {\n            if(!p_left || (repeat_left>18 && (repeat_left%4)==0)) move_selection(-1,0);\n            repeat_left++;\n        } else repeat_left=0;\n        if(right) {\n            if(!p_right || (repeat_right>18 && (repeat_right%4)==0)) move_selection(1,0);\n            repeat_right++;\n        } else repeat_right=0;'''
new='''        /* V2.24: one movie per tap. Holding left/right starts repeating only\n           after ~400 ms, then at a controlled ~133 ms interval. */\n        const int nav_repeat_delay=24;\n        const int nav_repeat_rate=8;\n        if(left && !right) {\n            if(!p_left) {\n                move_selection(-1,0);\n                repeat_left=0;\n            } else {\n                repeat_left++;\n                if(repeat_left>=nav_repeat_delay &&\n                   ((repeat_left-nav_repeat_delay)%nav_repeat_rate)==0)\n                    move_selection(-1,0);\n            }\n            repeat_right=0;\n        } else if(right && !left) {\n            if(!p_right) {\n                move_selection(1,0);\n                repeat_right=0;\n            } else {\n                repeat_right++;\n                if(repeat_right>=nav_repeat_delay &&\n                   ((repeat_right-nav_repeat_delay)%nav_repeat_rate)==0)\n                    move_selection(1,0);\n            }\n            repeat_left=0;\n        } else {\n            repeat_left=0;\n            repeat_right=0;\n        }'''
if old not in s:
    raise SystemExit('left/right repeat anchor not found')
s=s.replace(old,new,1)

p.write_text(s)
print('FLOW MOVIE V2.24: persistent pad state + reliable edge triggers + controlled navigation repeat')
