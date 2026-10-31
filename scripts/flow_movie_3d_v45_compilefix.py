from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()
old='ps3_env_name(&run_env)'
new='ps3_env_name(run_env.type)'
if old not in s:
    raise SystemExit('V4.5 env logging anchor not found')
s=s.replace(old,new,1)
p.write_text(s)
print('V4.5 compile fix applied: ps3_env_name(run_env.type)')
