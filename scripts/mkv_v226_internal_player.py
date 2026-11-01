from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.26 INTERNAL PLAYER
# V2.25 already provides the MKV -> Movian spawn path.  V2.26 makes a
# bundled plain SELF the first/normal target, while retaining external
# Movian paths only as a compatibility fallback.

old='flow_log("SESSION_START","FLOW MOVIE V2.25 MKV MOVIAN");'
new='flow_log("SESSION_START","FLOW MOVIE V2.26 INTERNAL PLAYER");'
if old not in s:
    raise SystemExit('V2.25 session marker not found')
s=s.replace(old,new,1)

old_paths='''    static const char *paths[] = {\n        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",'''
new_paths='''    static const char *paths[] = {\n        /* Bundled FLOW MOVIE multimedia engine (Movian Next / FFmpeg core). */\n        "/dev_hdd0/game/3DISO0001/USRDIR/flow_player.self",\n        /* Compatibility fallback for users who already have Movian. */\n        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",'''
if old_paths not in s:
    raise SystemExit('V2.25 player path list not found')
s=s.replace(old_paths,new_paths,1)

s=s.replace('''show_ok("No se encontro Movian/Showtime.\\n\\nInstala Movian (HTSS00003) o Movian Next con movian.self para reproducir MKV.");''',
            '''show_ok("No se encontro el motor multimedia interno.\\n\\nReinstala FLOW MOVIE V2.26 para restaurar flow_player.self.");''',1)
s=s.replace('''show_ok("Movian no pudo iniciarse.\\n\\nRevisa que movian.self este instalado correctamente.");''',
            '''show_ok("El motor multimedia no pudo iniciarse.\\n\\nRevisa FLOW_MOVIE.LOG para diagnostico.");''',1)

# Improve log wording while keeping existing event names useful across versions.
s=s.replace('/* V2.25: locate an installed Movian/Showtime plain SELF.',
            '/* V2.26: locate bundled FLOW player first, then external Movian fallback.',1)

p.write_text(s)
print('FLOW MOVIE V2.26: bundled internal MKV player is primary launch target')
