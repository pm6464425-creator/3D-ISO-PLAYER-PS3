from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V31
# - SNES 16:9 real por defecto y pixel mas nitido (sin blur).
# - Mantiene ZIP auto-extract de V30.
# - Mantiene intacto el backend PS2 V24.
# - El core SNES personalizado que se compila en el workflow usa el mismo APPID de FLOWPS3,
#   por lo que esta configuracion si es leida por el frontend.

start=s.find('static int v29_write_snes_cfg(const std::string &rom)')
if start < 0:
    raise SystemExit('v29_write_snes_cfg no encontrado')
end=s.find('\n}\n', start)
if end < 0:
    raise SystemExit('fin v29_write_snes_cfg no encontrado')
end += 3

new=r'''static int v31_write_snes_cfg(const std::string &rom)
{
    const char *cfg="/dev_hdd0/game/3DISO0001/USRDIR/retroarch.cfg";
    FILE *f=fopen(cfg,"w"); if(!f) return -436;

    /* Lanzamiento directo. */
    fprintf(f,"libretro_rom_path = \\\"%s\\\"\n",rom.c_str());

    /* Imagen: pantalla completa 16:9 y pixel limpio, sin suavizado borroso. */
    fprintf(f,"video_fullscreen = \\\"true\\\"\n");
    fprintf(f,"video_vsync = \\\"true\\\"\n");
    fprintf(f,"video_smooth = \\\"false\\\"\n");
    fprintf(f,"video_scale_integer = \\\"false\\\"\n");
    fprintf(f,"video_force_aspect = \\\"true\\\"\n");
    fprintf(f,"video_aspect_ratio_auto = \\\"false\\\"\n");
    fprintf(f,"video_aspect_ratio = \\\"1.777778\\\"\n");
    fprintf(f,"aspect_ratio_index = \\\"1\\\"\n");
    fprintf(f,"video_shader_enable = \\\"false\\\"\n");
    fprintf(f,"video_crop_overscan = \\\"false\\\"\n");
    fprintf(f,"video_threaded = \\\"false\\\"\n");

    /* Mandos: DS3 #1 jugador 1; DS3 #2 jugador 2. */
    fprintf(f,"input_autodetect_enable = \\\"true\\\"\n");
    fprintf(f,"input_player1_joypad_index = \\\"0\\\"\n");
    fprintf(f,"input_player2_joypad_index = \\\"1\\\"\n");

    /* Guardado propio FLOWPS3. */
    fprintf(f,"savefile_directory = \\\"/dev_hdd0/FLOWPS3/SAVES/SNES\\\"\n");
    fprintf(f,"savestate_directory = \\\"/dev_hdd0/FLOWPS3/SAVESTATES/SNES\\\"\n");

    fclose(f);
    return 0;
}
'''

s=s[:start]+new+s[end:]
s=s.replace('int cfg=v29_write_snes_cfg(rom);','int cfg=v31_write_snes_cfg(rom);',1)
s=s.replace('"V30"','"V31"')

p.write_text(s)
print('FLOWPS3 V31 aplicado: SNES 16:9 nitido + config activa')
