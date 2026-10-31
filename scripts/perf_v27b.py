from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()
bad='''    /* V2.7: optimized rounded Blu-ray renderer. The visual master is unchanged,\n       but only the non-transparent border bands are sampled. */\n       No strip joins, no square corners, no white corner fringe. */'''
good='''    /* V2.7: optimized rounded Blu-ray renderer. The visual master is unchanged,\n       but only the non-transparent border bands are sampled. */'''
if bad not in s:
    raise SystemExit('V2.7 comment fix anchor not found')
s=s.replace(bad,good,1)
p.write_text(s)
print('V2.7 generated comment fixed')
