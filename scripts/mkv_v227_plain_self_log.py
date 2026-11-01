from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.27 PLAIN SELF + PLAYER LOG
# Keep all stable V2.22/V2.23/V2.24 behavior untouched. V2.27 only corrects
# the MKV handoff contract and improves launch diagnostics.

old='flow_log("SESSION_START","FLOW MOVIE V2.26 INTERNAL PLAYER");'
new='flow_log("SESSION_START","FLOW MOVIE V2.27 INTERNAL SELF LOG");'
if old not in s:
    raise SystemExit('V2.26 session marker not found')
s=s.replace(old,new,1)

# sysProcessExitSpawn2 on PS3 prepends the executable to the child process argv.
# Working webMAN/Showtime launchers therefore pass only the media URL as argv[0].
old_argv='''    const char *launchargv[3];\n    launchargv[0]=player;\n    launchargv[1]=url.c_str();\n    launchargv[2]=NULL;'''
new_argv='''    const char *launchargv[2];\n    launchargv[0]=url.c_str();\n    launchargv[1]=NULL;'''
if old_argv not in s:
    raise SystemExit('V2.26 argv block not found')
s=s.replace(old_argv,new_argv,1)

# Add explicit launch-contract logging before process replacement.
old_log='''    char detail[1024];\n    snprintf(detail,sizeof(detail),"player=%s url=%s",player,url.c_str());\n    flow_log("MKV_LAUNCH_BEGIN",detail);'''
new_log='''    char detail[1024];\n    snprintf(detail,sizeof(detail),"player=%s argv0=%s",player,url.c_str());\n    flow_log("MKV_LAUNCH_BEGIN",detail);\n    flow_log("MKV_PLAYER_LOG_PATH","/dev_hdd0/game/3DISO0001/USRDIR/FLOW_PLAYER.LOG");'''
if old_log not in s:
    raise SystemExit('MKV launch log block not found')
s=s.replace(old_log,new_log,1)

s=s.replace('''show_ok("No se encontro el motor multimedia interno.\\n\\nReinstala FLOW MOVIE V2.26 para restaurar flow_player.self.");''',
            '''show_ok("No se encontro el motor multimedia interno.\\n\\nReinstala FLOW MOVIE V2.27 para restaurar flow_player.self.");''',1)
s=s.replace('''show_ok("El motor multimedia no pudo iniciarse.\\n\\nRevisa FLOW_MOVIE.LOG para diagnostico.");''',
            '''show_ok("El motor multimedia no pudo iniciarse.\\n\\nRevisa FLOW_MOVIE.LOG y FLOW_PLAYER.LOG para diagnostico.");''',1)

p.write_text(s)
print('FLOW MOVIE V2.27: plain SELF launch contract + player log diagnostics enabled')
