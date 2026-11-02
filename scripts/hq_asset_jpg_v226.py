from pathlib import Path

main=Path('source/main.cpp')
s=main.read_text()
old='APPBG_HQ.PNG'
new='APPBG_HQ.JPG'
if old not in s and new not in s:
    raise SystemExit('HQ background asset path not found')
if old in s:
    s=s.replace(old,new)
    main.write_text(s)

png=Path('pkgfiles/USRDIR/APPBG_HQ.PNG')
jpg=Path('pkgfiles/USRDIR/APPBG_HQ.JPG')
if png.exists():
    if jpg.exists():
        jpg.unlink()
    png.rename(jpg)
if not jpg.exists():
    raise SystemExit('APPBG_HQ asset missing')

print('V2.26 HQ asset path normalized to APPBG_HQ.JPG')
