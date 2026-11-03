from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

# V2.26 LARGE_LIBRARY_100PLUS
# Keep render cost independent from total library size:
# - metadata library can hold up to 1024 entries
# - reserve vector capacity up-front to avoid repeated reallocations during scan
# - cover rendering stays limited to the existing 11-card window (selected +/-5)
# - cover cache stays fixed at 16 slots; no per-library-size texture allocation

if '#define MAX_LIBRARY_ITEMS 1024' not in s:
    anchor = '#define MAX_SECTIONS'
    if anchor not in s:
        raise SystemExit('MAX_SECTIONS anchor not found')
    s = s.replace(anchor,
                  '/* V2.26 LARGE_LIBRARY_100PLUS: metadata may scale, GPU work may not. */\n#define MAX_LIBRARY_ITEMS 1024\n' + anchor,
                  1)

# The original scanner stopped at 512. Raise only the metadata/list cap.
# Do not increase the visible cover window or texture-cache size.
s, replaced_caps = re.subn(r'fresh\.size\(\)\s*>=\s*512',
                           'fresh.size() >= MAX_LIBRARY_ITEMS', s)
if replaced_caps == 0 and 'fresh.size() >= MAX_LIBRARY_ITEMS' not in s:
    raise SystemExit('movie scan cap anchor not found')

# Avoid vector growth/copy churn when hundreds of movies are discovered.
if 'fresh.reserve(MAX_LIBRARY_ITEMS);' not in s:
    needle = '    std::vector<Movie> fresh;\n'
    if needle not in s:
        raise SystemExit('fresh vector anchor not found')
    s = s.replace(needle,
                  needle + '    fresh.reserve(MAX_LIBRARY_ITEMS);\n',
                  1)

# Hard safety checks: a large library must never expand the per-frame GPU workload.
required = [
    '#define MAX_LIBRARY_ITEMS 1024',
    'fresh.reserve(MAX_LIBRARY_ITEMS);',
    'fresh.size() >= MAX_LIBRARY_ITEMS',
    '#define COVER_CACHE_SLOTS 16',
    'FlowDrawItem items[11];',
    'for(int idx=base-5;idx<=base+5;idx++)',
    'CoverBitmap *c=find_cached_cover(m);',
    'cover_prefetch_idle();',
]
for marker in required:
    if marker not in s:
        raise SystemExit('large-library invariant missing: ' + marker)

# Keep prefetch neighborhood bounded. 13 nearby candidates fit comfortably in
# the 16-slot LRU cache and remain independent from total library size.
if 'static const int off[13]={0,1,-1,2,-2,3,-3,4,-4,5,-5,6,-6};' not in s:
    raise SystemExit('bounded 13-cover prefetch neighborhood missing')

p.write_text(s)
print('V2.26 large-library patch applied: 1024 metadata entries, fixed 11-card render window, fixed 16-cover cache')
