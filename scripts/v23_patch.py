from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# V23: el diagnostico V22 demuestra que el bloqueo ocurre despues de STAGE2
# y antes de entrar en v22_mount_ps2_internal (no se crea STAGE3).
# Por tanto se elimina del camino PS2 el dispatcher generico mount_selected_image()
# y se llama directamente al montador PS2 ya instrumentado.

old='''                int ps2ret=mount_selected_image(movie);'''
new='''                v22_mark_stage(21,"BYPASS_GENERIC_DISPATCH",0);\n                int ps2ret=v22_mount_ps2_internal(movie);'''
if old not in s:
    raise SystemExit('llamada mount_selected_image PS2 V22 no encontrada')
s=s.replace(old,new,1)

# Etiqueta visible.
s=s.replace('"V22"','"V23"')

p.write_text(s)
print('FLOWPS3 V23 bypass dispatcher PS2 aplicado')
