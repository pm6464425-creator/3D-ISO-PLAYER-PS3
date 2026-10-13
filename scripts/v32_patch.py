from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V32
# - Conserva V24 PS2 sin tocarlo.
# - SNES: 16:9, sin suavizado, VSync.
# - SELECT + START actua como hotkey de salida del frontend SNES.
# - El frontend SNES personalizado relanza FLOWPS3 al cerrar.

marker='    fprintf(f,"input_player2_joypad_index = \\\"1\\\"\\n");'
pos=s.find(marker)
if pos < 0:
    raise SystemExit('linea input_player2_joypad_index no encontrada')
insert_at=pos+len(marker)
extra=r'''

    /* SELECT (RETRO joypad id 2) habilita hotkey; START (id 3) sale. */
    fprintf(f,"input_enable_hotkey_btn = \\\"2\\\"\n");
    fprintf(f,"input_exit_emulator_btn = \\\"3\\\"\n");
    fprintf(f,"input_menu_toggle_btn = \\\"nul\\\"\n");
    fprintf(f,"quit_press_twice = \\\"false\\\"\n");
'''
s=s[:insert_at]+extra+s[insert_at:]
s=s.replace('"V31"','"V32"')

p.write_text(s)
print('FLOWPS3 V32 aplicado: SNES 16:9 nitido + SELECT+START regreso a FLOWPS3')
