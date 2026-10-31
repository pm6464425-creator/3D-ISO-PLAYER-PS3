from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.14
# Uniform +10% zoom over V2.13/V2.12 case geometry.
# Preserve exact 135:172 physical Blu-ray proportion and all stability fixes.

old='''        const float sel_h=sh*0.44f;\n        const float nb_h=sh*0.28f;\n        const float aspect=135.0f/172.0f;'''
new='''        /* V2.14: uniform +10% zoom. Same 135:172 shape, only closer/larger. */\n        const float sel_h=sh*0.484f;\n        const float nb_h=sh*0.308f;\n        const float aspect=135.0f/172.0f;'''
if old not in s:
    raise SystemExit('V2.13 geometry anchor not found')
s=s.replace(old,new,1)

p.write_text(s)
print('FLOW MOVIE V2.14: +10% uniform case zoom, exact 135:172 preserved')
