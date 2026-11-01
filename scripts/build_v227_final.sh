#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
cd "$ROOT"

echo '=== 1/8 Build Movian plain SELF with submodules ==='
rm -rf /tmp/movian-next
git clone --recurse-submodules --shallow-submodules --depth 1 --branch v1.0.0 https://github.com/Cruslan/PS3-Movian-Next.git /tmp/movian-next
python3 scripts/patch_movian_v227_playerlog.py
cd /tmp/movian-next
test -f ext/gumbo-parser/src/attribute.c
test -f ext/mbedtls/include/mbedtls/ssl.h
echo 'Movian submodules OK'
make prepare
make -j2 self
test -s build/movian.self
test "$(stat -c%s build/movian.self)" -gt 1000000
python3 -c "from pathlib import Path; p=Path('build/movian.self'); b=p.read_bytes()[:4]; print('Movian SELF',p.stat().st_size,b.hex()); assert b==b'SCE\\x00'"
grep -q 'FLOW_PLAYER_LOG_PATH' src/arch/ps3/ps3_main.c
grep -q 'PLAYER_START' src/arch/ps3/ps3_main.c
grep -q 'CRASH_EVENT' src/arch/ps3/ps3_main.c
grep -q 'no_sfo_overwrite = 1' src/arch/ps3/ps3_main.c
grep -q 'GLW_START' src/arch/ps3/ps3_main.c

cd "$ROOT"
mkdir -p pkgfiles/USRDIR/licenses
cp /tmp/movian-next/build/movian.self pkgfiles/USRDIR/flow_player.self
cp /tmp/movian-next/LICENSE pkgfiles/USRDIR/licenses/MOVIAN_GPLv3.txt
printf '%s\n' \
  'Movian Next v1.0.0' \
  'https://github.com/Cruslan/PS3-Movian-Next/tree/v1.0.0' \
  'Plain SELF patched for FLOW_PLAYER.LOG and embedded-mode metadata protection.' \
  > pkgfiles/USRDIR/licenses/MOVIAN_SOURCE.txt
sha256sum pkgfiles/USRDIR/flow_player.self | tee internal_player_v227.sha256

echo '=== 2/8 Install PS3DEV for FLOW MOVIE ==='
curl --retry 4 --retry-delay 2 -fL "https://github.com/ps3dev/ps3dev/releases/download/nightly-2026-10-12/ps3dev-linux-X64.tar.gz" -o /tmp/ps3dev-flow.tar.gz
rm -rf "$ROOT/ps3dev"
tar xzf /tmp/ps3dev-flow.tar.gz -C "$ROOT"
export PS3DEV="$ROOT/ps3dev"
export PSL1GHT="$ROOT/ps3dev"
export PATH="$ROOT/ps3dev/bin:$ROOT/ps3dev/ppu/bin:$ROOT/ps3dev/spu/bin:$PATH"

echo '=== 3/8 Prepare FLOW MOVIE libraries ==='
mkdir -p third_party/include third_party/lib pkgfiles/USRDIR
curl -fL https://raw.githubusercontent.com/aldostools/IRISMAN/master/include/ntfs.h -o third_party/include/ntfs.h
curl -fL https://raw.githubusercontent.com/aldostools/IRISMAN/master/include/cobra.h -o third_party/include/cobra.h
curl -fL https://raw.githubusercontent.com/aldostools/IRISMAN/master/lib/libcobra.a -o third_party/lib/libcobra.a
curl -fL https://raw.githubusercontent.com/aldostools/IRISMAN/master/lib/libfatfs.a -o third_party/lib/libfatfs.a
curl -fL https://raw.githubusercontent.com/aldostools/IRISMAN/master/lib/libntfs_ext.a -o third_party/lib/libntfs_ext.a
curl -fL https://raw.githubusercontent.com/ace20022/libudfread/master/src/udfread.h -o third_party/include/udfread.h
curl -fL https://raw.githubusercontent.com/ace20022/libudfread/master/src/blockinput.h -o third_party/include/blockinput.h
curl -fL https://raw.githubusercontent.com/ace20022/libudfread/master/src/default_blockinput.h -o third_party/include/default_blockinput.h
curl -fL https://raw.githubusercontent.com/ace20022/libudfread/master/src/ecma167.h -o third_party/include/ecma167.h
curl -fL https://raw.githubusercontent.com/ace20022/libudfread/master/src/udfread.c -o source/udfread.c
curl -fL https://raw.githubusercontent.com/ace20022/libudfread/master/src/ecma167.c -o source/ecma167.c
curl -fL https://raw.githubusercontent.com/nothings/stb/master/stb_image.h -o third_party/include/stb_image.h

echo '=== 4/8 Generate V2.27 source ==='
python3 scripts/movie_only_patch.py
python3 scripts/env_patch.py
python3 scripts/flow_movie_3d_patch.py
python3 scripts/flow_movie_3d_fix_v2.py
python3 scripts/flow_movie_3d_spooky_v3.py
python3 scripts/v46_linkfix.py
python3 scripts/flow_movie_3d_v2_dynamic_controls.py
python3 scripts/case_v26.py
python3 scripts/perf_v27.py
python3 scripts/perf_v27b.py
python3 scripts/perf_v28_hard.py
python3 scripts/slow_v210_safe.py
python3 scripts/visual_v211_reference.py
python3 scripts/visual_v212_standard_case.py
python3 scripts/stability_v213.py
python3 scripts/zoom_v214.py
python3 scripts/diag_v215.py
python3 scripts/diag_v215_persist.py
python3 scripts/fix_v216_fastusb_watchdog.py
python3 scripts/fix_v217_60fps_runtime_stable.py
python3 scripts/freeze_diag_v218.py
python3 scripts/stability_v219_rsx_waitfinish.py
python3 scripts/stability_v222_safe_cmd_reset.py
python3 scripts/hotplug_v223_auto_usb.py
python3 scripts/input_v224_stable_pad.py
python3 scripts/mkv_v225_movian_launch.py
python3 scripts/mkv_v226_internal_player.py
python3 scripts/mkv_v227_plain_self_log.py
cp source/main.cpp generated_main_v227.cpp
cp source/rsxutil.cpp generated_rsxutil_v227.cpp

echo '=== 5/8 Resources and raw ISO ==='
python3 scripts/write_case_v25.py
python3 scripts/make_case_v26.py
python3 scripts/v17_art.py
test -s pkgfiles/USRDIR/CASE_FRAME.PNG
curl -fL https://raw.githubusercontent.com/aldostools/IRISMAN/master/rawseciso/bin2c/rawseciso.c -o /tmp/rawseciso.c
python3 -c "import re,pathlib; s=pathlib.Path('/tmp/rawseciso.c').read_text(); m=re.search(r'raw_iso_sprx\\[[^\\]]+\\]\\s*=\\s*\\{(.*?)\\};',s,re.S); assert m; pathlib.Path('pkgfiles/USRDIR/raw_iso.sprx').write_bytes(bytes(int(x,16) for x in re.findall(r'0x([0-9A-Fa-f]{2})',m.group(1))))"

echo '=== 6/8 Validate V2.27 ==='
grep -q 'FLOW MOVIE V2.27 INTERNAL SELF LOG' source/main.cpp
grep -q '/dev_hdd0/game/3DISO0001/USRDIR/flow_player.self' source/main.cpp
grep -q 'FLOW_PLAYER.LOG' source/main.cpp
grep -q 'const char \*launchargv\[2\];' source/main.cpp
grep -q 'launchargv\[0\]=url.c_str();' source/main.cpp
grep -q 'launchargv\[1\]=NULL;' source/main.cpp
! grep -q 'launchargv\[0\]=player;' source/main.cpp
! grep -q 'La reproduccion MKV se conectara al motor multimedia' source/main.cpp
test -s pkgfiles/USRDIR/flow_player.self
test -s pkgfiles/USRDIR/licenses/MOVIAN_GPLv3.txt
test -s pkgfiles/USRDIR/licenses/MOVIAN_SOURCE.txt
grep -q 'pad_sample.len>0' source/main.cpp
grep -q 'nav_repeat_delay=24' source/main.cpp
grep -q 'if(++poll_counter>=120)' source/main.cpp
grep -q 'USB_HOTPLUG_CHANGE' source/main.cpp
grep -q 'CMD_BUFFER_SAFE_RESET' source/rsxutil.cpp
grep -q 'rsxResetCommandBuffer(context);' source/rsxutil.cpp
grep -q 'context->current=context->begin;' source/rsxutil.cpp
grep -q 'RSX_WAITFINISH_TIMEOUT' source/rsxutil.cpp
grep -q 'RSX_FLIP_TIMEOUT' source/rsxutil.cpp
grep -q 'GCM_FLIP_VSYNC' source/rsxutil.cpp
grep -q 'covers_per_second=1.72f' source/main.cpp
! grep -q 'rsx_reserve_safe' source/rsxutil.cpp
! grep -q 'FIFO_RESERVE_CALLBACK' source/rsxutil.cpp
! grep -q 'memset(out,0,sizeof(CoverBitmap))' source/main.cpp

echo '=== 7/8 Compile and package FLOW MOVIE ==='
make clean
make
make pkg
test -s 3disoplayer.pkg
test -s 3disoplayer.gnpdrm.pkg
cp 3disoplayer.pkg FLOW_MOVIE_V2_27_INTERNAL_SELF_LOG.pkg
cp 3disoplayer.gnpdrm.pkg FLOW_MOVIE_V2_27_INTERNAL_SELF_LOG_GNPDRM.pkg

echo '=== 8/8 Verify embedded SELF and checksums ==='
rm -rf /tmp/v227_verify
python3 scripts/extract_ps3_debug_pkg.py FLOW_MOVIE_V2_27_INTERNAL_SELF_LOG.pkg --out /tmp/v227_verify --prefix USRDIR/flow_player.self --prefix USRDIR/licenses/MOVIAN_GPLv3.txt --prefix USRDIR/licenses/MOVIAN_SOURCE.txt
test -s /tmp/v227_verify/USRDIR/flow_player.self
cmp pkgfiles/USRDIR/flow_player.self /tmp/v227_verify/USRDIR/flow_player.self
python3 -c "from pathlib import Path; p=Path('/tmp/v227_verify/USRDIR/flow_player.self'); assert p.read_bytes()[:4]==b'SCE\\x00'; assert p.stat().st_size>1000000; print('SELF VERIFIED',p.stat().st_size)"
sha256sum FLOW_MOVIE_V2_27_INTERNAL_SELF_LOG.pkg FLOW_MOVIE_V2_27_INTERNAL_SELF_LOG_GNPDRM.pkg pkgfiles/USRDIR/flow_player.self generated_main_v227.cpp generated_rsxutil_v227.cpp | tee v227_final.sha256

echo 'V2.27 FINAL BUILD OK'
