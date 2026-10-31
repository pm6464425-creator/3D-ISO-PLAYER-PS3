from pathlib import Path

mk=Path('Makefile')
s=mk.read_text()

# V4.x Tiny3D experiments permanently excluded the legacy framebuffer objects.
# V4.6 intentionally restores only rsxutil.cpp; the other old UI modules remain unused.
s=s.replace(
    'CPPFILES    := $(filter-out rsxutil.cpp background.cpp cover_net.cpp cover_udf.cpp,$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp))))',
    'CPPFILES    := $(filter-out background.cpp cover_net.cpp cover_udf.cpp,$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp))))'
)

# V4.6 production UI does not call Tiny3D. Keeping the library out also prevents
# accidental symbol collisions with the restored rsxutil.cpp renderer.
s=s.replace('               -ltiny3d -lrsx -lsimdmath -lgcm_sys -lio -lsysutil -lsysfs -lrt -llv2 -lsysmodule -lm',
            '               -lrsx -lsimdmath -lgcm_sys -lio -lsysutil -lsysfs -lrt -llv2 -lsysmodule -lm')

mk.write_text(s)

# stb_image is header-only; V4 Tiny3D link changes removed the implementation TU.
Path('source/stb_image_impl.c').write_text('''#define STB_IMAGE_IMPLEMENTATION\n#define STBI_NO_STDIO\n#include "stb_image.h"\n''')

print('V4.6 link fix: rsxutil restored, Tiny3D link removed, stb_image implementation restored')
