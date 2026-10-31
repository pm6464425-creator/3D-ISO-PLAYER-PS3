from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageChops

root=Path('pkgfiles/USRDIR')
top=Image.open(root/'CASE_TOP.JPG').convert('RGBA')
left=Image.open(root/'CASE_LEFT.PNG').convert('RGBA')
right=Image.open(root/'CASE_RIGHT.PNG').convert('RGBA')
bottom=Image.open(root/'CASE_BOTTOM.PNG').convert('RGBA')

# 2x master. The application scales this down, which gives cleaner edges on PS3.
W,H=640,822
TOP_H=70
SIDE_W=10
BOTTOM_H=16
INNER=(SIDE_W,TOP_H,W-SIDE_W,H-BOTTOM_H)

def clean(im):
    im=ImageEnhance.Contrast(im).enhance(1.08)
    im=ImageEnhance.Color(im).enhance(1.06)
    im=ImageEnhance.Sharpness(im).enhance(1.35)
    return im

top=clean(top.resize((W,TOP_H),Image.Resampling.LANCZOS))
left=clean(left.resize((SIDE_W,H-TOP_H-BOTTOM_H),Image.Resampling.LANCZOS))
right=clean(right.resize((SIDE_W,H-TOP_H-BOTTOM_H),Image.Resampling.LANCZOS))
bottom=clean(bottom.resize((W,BOTTOM_H),Image.Resampling.LANCZOS))

frame=Image.new('RGBA',(W,H),(0,0,0,0))
frame.alpha_composite(top,(0,0))
frame.alpha_composite(left,(0,TOP_H))
frame.alpha_composite(right,(W-SIDE_W,TOP_H))
frame.alpha_composite(bottom,(0,H-BOTTOM_H))

# Outer rounded silhouette. This removes the pointed corners and the pale corner fringe.
mask=Image.new('L',(W,H),0)
d=ImageDraw.Draw(mask)
d.rounded_rectangle((0,0,W-1,H-1),radius=34,fill=255)
# Paper artwork window stays transparent; the case border is the only overlay.
d.rectangle(INNER,fill=0)
mask=mask.filter(ImageFilter.GaussianBlur(0.45))

alpha=frame.getchannel('A')
alpha=ImageChops.multiply(alpha,mask)
frame.putalpha(alpha)

# Remove light source-background pixels only at the extreme top corners.
pix=frame.load(); ap=frame.getchannel('A').load()
for y in range(0,32):
    for x in list(range(0,48))+list(range(W-48,W)):
        r,g,b,a=pix[x,y]
        if r>225 and g>225 and b>225:
            pix[x,y]=(20,125,200,0)

# Final subtle remastering pass.
rgb=frame.convert('RGB').filter(ImageFilter.UnsharpMask(radius=1.0,percent=135,threshold=2))
final=Image.merge('RGBA',(*rgb.split(),frame.getchannel('A')))
final.save(root/'CASE_FRAME.PNG',optimize=True)
print('CASE_FRAME.PNG',final.size,(root/'CASE_FRAME.PNG').stat().st_size)
