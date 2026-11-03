from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

# V2.26 LARGE_LIBRARY_100PLUS
# This runs on the base scanner BEFORE the V2.26 UI/coverflow patch chain.
# Only metadata/list capacity changes here. GPU/render behavior is untouched.

if '#define MAX_LIBRARY_ITEMS 1024' not in s:
    anchor = '#define MAX_SECTIONS'
    if anchor not in s:
        raise SystemExit('MAX_SECTIONS anchor not found')
    s = s.replace(anchor,
                  '/* V2.26 LARGE_LIBRARY_100PLUS: metadata may scale, GPU work may not. */\n#define MAX_LIBRARY_ITEMS 1024\n' + anchor,
                  1)

# Replace scanner numeric caps with the common 1024-item metadata cap.
s, changed = re.subn(r'fresh\.size\(\)\s*>=\s*[0-9]+',
                     'fresh.size() >= MAX_LIBRARY_ITEMS', s)

# Reserve once to avoid repeated vector growth while scanning hundreds of titles.
if 'fresh.reserve(MAX_LIBRARY_ITEMS);' not in s:
    needle = '    std::vector<Movie> fresh;\n'
    if needle not in s:
        raise SystemExit('fresh vector anchor not found')
    s = s.replace(needle,
                  needle + '    fresh.reserve(MAX_LIBRARY_ITEMS);\n',
                  1)

# Idempotent validation. If already patched, changed may be zero.
required = [
    '#define MAX_LIBRARY_ITEMS 1024',
    'fresh.reserve(MAX_LIBRARY_ITEMS);',
]
for marker in required:
    if marker not in s:
        raise SystemExit('missing large-library marker: ' + marker)

# If this scanner has an explicit cap, it must now use MAX_LIBRARY_ITEMS.
if re.search(r'fresh\.size\(\)\s*>=\s*[0-9]+', s):
    raise SystemExit('numeric movie-list cap remained')

p.write_text(s)
print('V2.26 base scanner prepared for 100+ titles; numeric caps changed=', changed)
