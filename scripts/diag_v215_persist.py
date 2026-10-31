from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()
old='    remove(FLOW_LOG_PATH);\n    g_log_start_us=flow_now_us();'
new='    /* Keep previous freeze diagnostics across restarts. */\n    g_log_start_us=flow_now_us();'
if old not in s:
    raise SystemExit('persistent log anchor not found')
s=s.replace(old,new,1)
p.write_text(s)
print('FLOW MOVIE V2.15: diagnostics log persists across restarts')
