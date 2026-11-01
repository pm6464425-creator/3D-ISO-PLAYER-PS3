from pathlib import Path

main=Path('source/main.cpp')
rsx=Path('source/rsxutil.cpp')
s=main.read_text()
r=rsx.read_text()

# FLOW MOVIE V2.22 SAFE CMD BUFFER RESET
# Root cause: V2.18/V2.19/V2.21 all freeze at frame 7349 inside
# rsxSetWriteBackendLabel(), exactly where the 1 MiB default command buffer
# reaches its tail and PSL1GHT enters the FIFO wrap callback.
# Fix: while the RSX is already fully idle after waitFinish(), rewind the
# command buffer well before the tail (512 KiB headroom). This mirrors the
# frame-boundary reset used by stable modern PS3 renderers and avoids any
# mid-command callback/wrap. The current PSL1GHT reset omits rewinding
# context->current, so V2.22 explicitly repairs that invariant.

s=s.replace('flow_log("SESSION_START","FLOW MOVIE V2.19 STABILITY FIX");',
            'flow_log("SESSION_START","FLOW MOVIE V2.22 SAFE CMD RESET");',1)

# Forward declaration used by waitFinish(), which appears near the top.
old='''static uint64_t rsx_now_us();\nstatic void rsx_log_waitfinish_timeout(u32 label);\nvoid freeze_diag_phase(int phase);\n'''
new='''static uint64_t rsx_now_us();\nstatic void rsx_log_waitfinish_timeout(u32 label);\nstatic void maybe_reset_command_buffer();\nvoid freeze_diag_phase(int phase);\n'''
if old not in r:
    raise SystemExit('V2.19 forward declarations anchor not found')
r=r.replace(old,new,1)

# Name/watch the reset phase so the existing watchdog still catches anything
# unexpected inside the SDK reset path.
old='''        case 35: return "DRAW_COVERS_AND_UI";\n        case 40: return "FRAME_OK_LOOP_TAIL";'''
new='''        case 35: return "DRAW_COVERS_AND_UI";\n        case 39: return "CMD_BUFFER_SAFE_RESET";\n        case 40: return "FRAME_OK_LOOP_TAIL";'''
if old not in r:
    raise SystemExit('phase name anchor not found')
r=r.replace(old,new,1)

old='''           phase==31 || phase==32 || phase==33 || phase==34 || phase==35 ||\n           phase==40 || phase==50 || phase==51 || phase==52 || phase==53 || phase==54;'''
new='''           phase==31 || phase==32 || phase==33 || phase==34 || phase==35 || phase==39 ||\n           phase==40 || phase==50 || phase==51 || phase==52 || phase==53 || phase==54;'''
if old not in r:
    raise SystemExit('watched phase anchor not found')
r=r.replace(old,new,1)

# Insert safe frame-boundary rewind after the watchdog API is defined.
anchor='''void freeze_diag_frame_ok()\n{\n    g_freeze_diag_frame++;\n}\n'''
helper='''void freeze_diag_frame_ok()\n{\n    g_freeze_diag_frame++;\n}\n\n/* V2.22: never let the 1 MiB default FIFO reach its tail.\n   waitFinish() calls this only after the backend label proves the RSX has\n   consumed every command before it, so the reset occurs at a true idle\n   boundary, never in the middle of a draw/flip. */\nstatic void maybe_reset_command_buffer()\n{\n    if(!context || !context->begin || !context->current || !context->end) return;\n\n    const u32 remaining_words=(u32)(context->end-context->current);\n    const u32 reset_threshold_words=128u*1024u; /* 512 KiB headroom */\n    if(remaining_words>=reset_threshold_words) return;\n\n    freeze_diag_phase(39); /* CMD_BUFFER_SAFE_RESET */\n\n    FILE *f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");\n    if(f) {\n        fprintf(f,"[RSX] CMD_BUFFER_RESET_BEGIN | remaining_words=%u frame=%llu\\\\n",\n                remaining_words,(unsigned long long)g_freeze_diag_frame);\n        fflush(f);\n        fclose(f);\n    }\n\n    /* PSL1GHT's reset emits a JUMP to the default buffer start and waits\n       until GET reaches it. We invoke it with hundreds of KiB still free,\n       so rsxSetJumpCommand itself cannot hit the problematic tail callback. */\n    rsxResetCommandBuffer(context);\n\n    /* Critical fix present in modern PS3DK but missing from the PSL1GHT\n       build used here: after the hardware rewind, CPU command generation\n       must also resume from the beginning of the command buffer. */\n    context->current=context->begin;\n    __asm__ __volatile__("sync" ::: "memory");\n\n    f=fopen("/dev_hdd0/game/3DISO0001/USRDIR/FLOW_MOVIE.LOG","a");\n    if(f) {\n        fprintf(f,"[RSX] CMD_BUFFER_RESET_END | frame=%llu\\\\n",\n                (unsigned long long)g_freeze_diag_frame);\n        fflush(f);\n        fclose(f);\n    }\n\n    freeze_diag_phase(34); /* return to completed-clear state */\n}\n'''
if anchor not in r:
    raise SystemExit('freeze_diag_frame_ok anchor not found')
r=r.replace(anchor,helper,1)

# Call the safe rewind only after a successful backend-label completion.
old='''    ++sLabelVal;\n    freeze_diag_phase(34); /* RSX_CLEAR_DONE */\n}'''
new='''    ++sLabelVal;\n    freeze_diag_phase(34); /* RSX_CLEAR_DONE */\n    maybe_reset_command_buffer();\n}'''
if old not in r:
    raise SystemExit('successful waitFinish tail anchor not found')
r=r.replace(old,new,1)

main.write_text(s)
rsx.write_text(r)
print('FLOW MOVIE V2.22: safe frame-boundary command buffer reset before FIFO tail')
