from pathlib import Path

main=Path('source/main.cpp')
rsx=Path('source/rsxutil.cpp')
s=main.read_text()
r=rsx.read_text()

# FLOW MOVIE V2.20 RSX FIFO FIX
# Root-cause-oriented fix based on rsxkit/PS3DK practice:
# reserve enough command-buffer space BEFORE emitting the frame's RSX commands,
# so PSL1GHT never has to cross a command-buffer segment from inside an rsxSet*
# call. The callback is invoked directly as a normal C function when needed.
# V2.18/V2.19 watchdog diagnostics stay enabled.

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.19 STABILITY FIX");',
            'flow_log("SESSION_START","FLOW MOVIE V2.20 RSX FIFO FIX");',1)

# Forward declaration for the safe reserve helper (used in rsx_clear_backbuffer).
decl_anchor='''static void rsx_log_waitfinish_timeout(u32 label);\nvoid freeze_diag_phase(int phase);\n'''
decls='''static void rsx_log_waitfinish_timeout(u32 label);\nstatic int rsx_reserve_safe(u32 words);\nvoid freeze_diag_phase(int phase);\n'''
if decl_anchor not in r:
    raise SystemExit('V2.19 forward declaration anchor not found')
r=r.replace(decl_anchor,decls,1)

# Add watchdog names for FIFO boundary handling and the actual clear commands.
old='''        case 35: return "DRAW_COVERS_AND_UI";\n        case 40: return "FRAME_OK_LOOP_TAIL";'''
new='''        case 35: return "DRAW_COVERS_AND_UI";\n        case 36: return "FIFO_RESERVE_CALLBACK";\n        case 37: return "FIFO_RESERVE_DONE";\n        case 38: return "RSX_CLEAR_COMMANDS";\n        case 40: return "FRAME_OK_LOOP_TAIL";'''
if old not in r:
    raise SystemExit('V2.19 phase names anchor not found')
r=r.replace(old,new,1)

old='''           phase==31 || phase==32 || phase==33 || phase==34 || phase==35 ||\n           phase==40 || phase==50 || phase==51 || phase==52 || phase==53 || phase==54;'''
new='''           phase==31 || phase==32 || phase==33 || phase==34 || phase==35 ||\n           phase==36 || phase==37 || phase==38 ||\n           phase==40 || phase==50 || phase==51 || phase==52 || phase==53 || phase==54;'''
if old not in r:
    raise SystemExit('V2.19 watched phase anchor not found')
r=r.replace(old,new,1)

# Insert the safe reserve implementation after the watchdog phase API exists.
# gcmContextData::callback is already typed as s32 (*)(gcmContextData*,u32).
anchor='''void freeze_diag_frame_ok()\n{\n    g_freeze_diag_frame++;\n}\n'''
helper='''void freeze_diag_frame_ok()\n{\n    g_freeze_diag_frame++;\n}\n\n/* V2.20: proactively cross the libgcm/PSL1GHT FIFO segment boundary.\n   This mirrors the modern rsxkit approach: never let an rsxSet* function\n   discover the boundary internally after the compiler has cached current. */\nstatic int rsx_reserve_safe(u32 words)\n{\n    if(!context) return -1;\n    if(context->current + words <= context->end) return 0;\n\n    freeze_diag_phase(36); /* FIFO_RESERVE_CALLBACK */\n    s32 rc=context->callback(context,words);\n    /* Compiler barrier: context->current/end may have changed in callback. */\n    __asm__ __volatile__("" ::: "memory");\n    if(rc!=0) {\n        FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");\n        if(f) {\n            fprintf(f,"[RSX] RSX_FIFO_RESERVE_FAIL | words=%u rc=%d\\\\n",words,(int)rc);\n            fflush(f);\n            fclose(f);\n        }\n        return (int)rc;\n    }\n    freeze_diag_phase(37); /* FIFO_RESERVE_DONE */\n    return 0;\n}\n'''
if anchor not in r:
    raise SystemExit('freeze_diag_frame_ok anchor not found')
r=r.replace(anchor,helper,1)

# Reserve a large contiguous budget before ANY per-frame RSX commands.
# 2048 words = 8 KiB, far above this app's actual per-frame RSX command use.
old='''void rsx_clear_backbuffer(u32 color)\n{\n    /* Hardware clear instead of millions of PPU framebuffer writes. */\n    rsxSetClearColor(context,color);\n    rsxClearSurface(context,GCM_CLEAR_R|GCM_CLEAR_G|GCM_CLEAR_B|GCM_CLEAR_A);\n    waitFinish();\n}'''
new='''void rsx_clear_backbuffer(u32 color)\n{\n    /* V2.20: reserve the whole frame's RSX command budget up front. */\n    freeze_diag_phase(38); /* RSX_CLEAR_COMMANDS */\n    if(rsx_reserve_safe(2048)!=0) return;\n    freeze_diag_phase(38); /* reserve may have temporarily changed phase */\n\n    /* Hardware clear instead of millions of PPU framebuffer writes. */\n    rsxSetClearColor(context,color);\n    rsxClearSurface(context,GCM_CLEAR_R|GCM_CLEAR_G|GCM_CLEAR_B|GCM_CLEAR_A);\n    waitFinish();\n}'''
if old not in r:
    raise SystemExit('rsx_clear_backbuffer anchor not found')
r=r.replace(old,new,1)

# Defensive reserve before flip as well. Normally the 2048-word frame budget
# still has plenty of space, so this is a no-op; at a boundary it guarantees
# gcmSetFlip/setRenderTarget also cannot trigger the old internal callback path.
old='''    freeze_diag_phase(50); /* FLIP_ENTER */\n    freeze_diag_phase(51); /* GCM_SET_FLIP */\n    gcmSetFlip(context,curr_fb);'''
new='''    freeze_diag_phase(50); /* FLIP_ENTER */\n    if(rsx_reserve_safe(512)!=0) return;\n    freeze_diag_phase(51); /* GCM_SET_FLIP */\n    gcmSetFlip(context,curr_fb);'''
if old not in r:
    raise SystemExit('flip reserve anchor not found')
r=r.replace(old,new,1)

main.write_text(s)
rsx.write_text(r)
print('FLOW MOVIE V2.20: proactive RSX FIFO reserve + direct callback + watchdog retained')
