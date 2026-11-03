from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

# V2.26 LARGE_LIBRARY_100PLUS
# Scale metadata/list capacity without scaling per-frame GPU work.

if '#define MAX_LIBRARY_ITEMS 1024' not in s:
    anchor = '#define MAX_SECTIONS'
    if anchor not in s:
        raise SystemExit('MAX_SECTIONS anchor not found')
    s = s.replace(anchor,
                  '/* V2.26 LARGE_LIBRARY_100PLUS: metadata may scale, GPU work may not. */\n#define MAX_LIBRARY_ITEMS 1024\n' + anchor,
                  1)

# Raise any numeric fresh-vector scan cap to the common metadata limit.
# Different earlier patch stages used slightly different numeric caps, so keep
# this deliberately generic rather than assuming exactly 512.
s, replaced_caps = re.subn(r'fresh\.size\(\)\s*>=\s*[0-9]+',
                           'fresh.size() >= MAX_LIBRARY_ITEMS', s)

# Reserve metadata capacity once when the scanner builds the library. If an
# earlier patch already reserves it, leave it untouched.
if 'fresh.reserve(MAX_LIBRARY_ITEMS);' not in s:
    s, reserve_count = re.subn(
        r'(\s*std::vector<Movie>\s+fresh\s*;\s*\n)',
        lambda m: m.group(1) + '    fresh.reserve(MAX_LIBRARY_ITEMS);\n',
        s,
        count=1)
else:
    reserve_count = 1

# The performance-critical invariants are already established by the V2.26
# coverflow/cache patches. Verify them with regex so whitespace changes do not
# make the build fail spuriously.
checks = {
    '1024 metadata limit': r'#define\s+MAX_LIBRARY_ITEMS\s+1024',
    '16-slot cover cache': r'#define\s+COVER_CACHE_SLOTS\s+16',
    '11-card render window': r'FlowDrawItem\s+items\s*\[\s*11\s*\]',
    'selected +/-5 render bounds': r'for\s*\(\s*int\s+idx\s*=\s*base\s*-\s*5\s*;\s*idx\s*<=\s*base\s*\+\s*5\s*;',
    'render uses cached cover only': r'CoverBitmap\s*\*\s*c\s*=\s*find_cached_cover\s*\(\s*m\s*\)',
    'idle prefetch': r'cover_prefetch_idle\s*\(\s*\)\s*;',
    'bounded 13-cover prefetch': r'off\s*\[\s*13\s*\]\s*=\s*\{\s*0\s*,\s*1\s*,\s*-1\s*,\s*2\s*,\s*-2\s*,\s*3\s*,\s*-3\s*,\s*4\s*,\s*-4\s*,\s*5\s*,\s*-5\s*,\s*6\s*,\s*-6\s*\}',
}
for label, pattern in checks.items():
    if not re.search(pattern, s):
        raise SystemExit('large-library invariant missing: ' + label)

# If the final scanner still has a numeric cap, that would bypass the common
# 1024-item limit. Fail only for that real regression.
if re.search(r'fresh\.size\(\)\s*>=\s*[0-9]+', s):
    raise SystemExit('numeric fresh-vector cap remained after large-library patch')

# A scanner without an explicit cap is also safe for 100+ titles; otherwise the
# common MAX_LIBRARY_ITEMS cap must now be present.
if replaced_caps > 0 and 'fresh.size() >= MAX_LIBRARY_ITEMS' not in s:
    raise SystemExit('large-library cap replacement did not persist')

p.write_text(s)
print('V2.26 large-library patch applied: 1024 metadata target, fixed 11-card render window, fixed 16-cover cache; caps changed=', replaced_caps, 'reserve=', reserve_count)
