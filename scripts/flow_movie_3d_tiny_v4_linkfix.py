from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# V4 is fully rendered by Tiny3D. Remove declarations from the legacy rsxutil layer
# and provide the virtual 848x512 coordinate system used by the FLOW UI.
s=s.replace('#include "rsxutil.h"\n','')
s=s.replace('extern u32 display_width;\nextern u32 display_height;\n',
'''static inline u32 get_screen_width(){ return 848u; }\nstatic inline u32 get_screen_height(){ return 512u; }\n''',1)
s=s.replace('    display_width=848; display_height=512;\n','',1)

# Guard against any leftover legacy renderer calls in the generated source.
for forbidden in ('init_screen(', 'get_back_buffer(', '\n    flip();'):
    if forbidden in s:
        raise SystemExit(f'legacy renderer call remains: {forbidden}')

p.write_text(s)
print('V4 linker fix applied: legacy rsxutil dependency removed')
