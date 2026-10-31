from pathlib import Path

main=Path('source/main.cpp')
rsx=Path('source/rsxutil.cpp')
s=main.read_text()
r=rsx.read_text()

# FLOW MOVIE V2.19 STABILITY FIX
# Based on the V2.18 watchdog capture: the main thread stalled inside
# RENDER_UI_DRAW before entering gcmSetFlip/rsxFlushBuffer/waitflip.
# The strongest remaining infinite wait is waitFinish(), used by the RSX
# hardware clear path every frame. V2.19 adds a bounded wait, logs the event,
# returns control instead of hard-locking forever, and keeps the V2.18 watchdog.

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.18 DEBUG FREEZE");',
            'flow_log("SESSION_START","FLOW MOVIE V2.19 STABILITY FIX");',1)

# Finer render phases around the known suspect region. No visual/FPS changes.
old='''    flow_update();\n    fps_tick();\n    draw_background();'''
new='''    flow_update();\n    fps_tick();\n    freeze_diag_phase(31); /* DRAW_BACKGROUND */\n    draw_background();\n    freeze_diag_phase(35); /* DRAW_COVERS_AND_UI */'''
if old not in s:
    raise SystemExit('render background anchor not found')
s=s.replace(old,new,1)

# waitFinish() is near the top of rsxutil.cpp, while the V2.16/V2.18 helpers
# are defined later. Add forward declarations so the bounded wait can use them.
decl_anchor='''static u32 sLabelVal = 1;\n'''
decls='''static u32 sLabelVal = 1;\n\n/* V2.19 forward declarations for the early waitFinish() path. */\nstatic uint64_t rsx_now_us();\nstatic void rsx_log_waitfinish_timeout(u32 label);\nvoid freeze_diag_phase(int phase);\n'''
if decl_anchor not in r:
    raise SystemExit('sLabelVal anchor not found')
r=r.replace(decl_anchor,decls,1)

old='''        case 30: return "RENDER_UI_DRAW";\n        case 40: return "FRAME_OK_LOOP_TAIL";'''
new='''        case 30: return "RENDER_UI_DRAW";\n        case 31: return "DRAW_BACKGROUND";\n        case 32: return "RSX_CLEAR_SUBMIT";\n        case 33: return "RSX_CLEAR_WAIT_LABEL";\n        case 34: return "RSX_CLEAR_DONE";\n        case 35: return "DRAW_COVERS_AND_UI";\n        case 40: return "FRAME_OK_LOOP_TAIL";'''
if old not in r:
    raise SystemExit('phase names anchor not found')
r=r.replace(old,new,1)

old='''    return phase==10 || phase==11 || phase==20 || phase==21 || phase==30 ||\n           phase==40 || phase==50 || phase==51 || phase==52 || phase==53 || phase==54;'''
new='''    return phase==10 || phase==11 || phase==20 || phase==21 || phase==30 ||\n           phase==31 || phase==32 || phase==33 || phase==34 || phase==35 ||\n           phase==40 || phase==50 || phase==51 || phase==52 || phase==53 || phase==54;'''
if old not in r:
    raise SystemExit('watched phase anchor not found')
r=r.replace(old,new,1)

# Separate timeout event for the backend-label wait.
anchor='''static void rsx_log_timeout()\n{\n    FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");\n    if(!f) return;\n    fprintf(f,"[RSX] RSX_FLIP_TIMEOUT | forced recovery after 500 ms\\\\n");\n    fflush(f);\n    fclose(f);\n}\n'''
helper='''static void rsx_log_timeout()\n{\n    FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");\n    if(!f) return;\n    fprintf(f,"[RSX] RSX_FLIP_TIMEOUT | forced recovery after 500 ms\\\\n");\n    fflush(f);\n    fclose(f);\n}\n\nstatic void rsx_log_waitfinish_timeout(u32 label)\n{\n    FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");\n    if(!f) return;\n    fprintf(f,"[RSX] RSX_WAITFINISH_TIMEOUT | label=%u forced return after 500 ms\\\\n",label);\n    fflush(f);\n    fclose(f);\n}\n'''
if anchor not in r:
    raise SystemExit('RSX timeout helper anchor not found')
r=r.replace(anchor,helper,1)

# Replace the only unbounded backend-label wait. Do not forge the label value;
# simply stop waiting after 500 ms, record it, and let the existing watchdog
# show whether another RSX phase subsequently stalls.
old='''static void waitFinish()\n{\n    rsxSetWriteBackendLabel(context,GCM_LABEL_INDEX,sLabelVal);\n    rsxFlushBuffer(context);\n    while(*(vu32*)gcmGetLabelAddress(GCM_LABEL_INDEX)!=sLabelVal) usleep(30);\n    ++sLabelVal;\n}'''
new='''static void waitFinish()\n{\n    const u32 target=sLabelVal;\n    freeze_diag_phase(32); /* RSX_CLEAR_SUBMIT */\n    rsxSetWriteBackendLabel(context,GCM_LABEL_INDEX,target);\n    rsxFlushBuffer(context);\n    freeze_diag_phase(33); /* RSX_CLEAR_WAIT_LABEL */\n    uint64_t start=rsx_now_us();\n    while(*(vu32*)gcmGetLabelAddress(GCM_LABEL_INDEX)!=target) {\n        usleep(30);\n        if(rsx_now_us()-start>=500000ULL) {\n            rsx_log_waitfinish_timeout(target);\n            ++sLabelVal;\n            freeze_diag_phase(34); /* RSX_CLEAR_DONE / timeout return */\n            return;\n        }\n    }\n    ++sLabelVal;\n    freeze_diag_phase(34); /* RSX_CLEAR_DONE */\n}'''
if old not in r:
    raise SystemExit('waitFinish anchor not found')
r=r.replace(old,new,1)

main.write_text(s)
rsx.write_text(r)
print('FLOW MOVIE V2.19: bounded waitFinish + RSX clear diagnostics + watchdog retained')
