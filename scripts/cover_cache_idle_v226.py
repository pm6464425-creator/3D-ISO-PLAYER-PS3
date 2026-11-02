from pathlib import Path
import re

p = Path('source/main.cpp')
s = p.read_text()

# V2.26 cover I/O isolation fix:
# - never perform NTFS stat/read/JPEG decode from draw_poster/render path
# - resolve cover filenames lazily only after coverflow has been idle
# - load one cover at a time after a short idle guard
# - keep a slightly wider resident neighborhood to reduce re-decode churn

if 'bool cover_checked;' not in s:
    s = s.replace('    std::string cover;\n    int usb_id;',
                  '    std::string cover;\n    bool cover_checked;\n    int usb_id;', 1)

s = s.replace('#define COVER_CACHE_SLOTS 10', '#define COVER_CACHE_SLOTS 16', 1)

s = s.replace('                m.ntfs = false;\n                fresh.push_back(m);',
              '                m.ntfs = false;\n                m.cover_checked = false;\n                fresh.push_back(m);', 1)
s = s.replace('                m.ntfs = true;\n                fresh.push_back(m);',
              '                m.ntfs = true;\n                m.cover_checked = false;\n                fresh.push_back(m);', 1)

needle = '''static void resolve_cover_paths()\n{\n    for(size_t i=0;i<g_movies.size();++i) g_movies[i].cover = find_movie_cover(g_movies[i]);\n}\n'''
if needle not in s:
    raise SystemExit('resolve_cover_paths block not found')
replacement = needle + '''\nstatic void ensure_movie_cover_path(Movie &m)\n{\n    if(m.cover_checked) return;\n    m.cover = find_movie_cover(m);\n    m.cover_checked = true;\n}\n'''
s = s.replace(needle, replacement, 1)

s = s.replace('    cover_cache_clear();\n    resolve_cover_paths();\n    g_selected = 0;',
              '    cover_cache_clear();\n    /* Cover paths are resolved lazily while the coverflow is idle. */\n    g_selected = 0;', 1)

pat = re.compile(r'''static void cover_prefetch_idle\(\)\n\{.*?\n\}\n\nstatic void release_port''', re.S)
m = pat.search(s)
if not m:
    raise SystemExit('cover_prefetch_idle block not found')
new_prefetch = r'''static void cover_prefetch_idle()
{
    static unsigned int idle_tick=0;
    static int phase=0;
    static int last_selected=-1;

    if(g_movies.empty()) {
        idle_tick=0;
        phase=0;
        last_selected=-1;
        return;
    }

    /* Absolutely no NTFS stat/read/JPEG work while a cover is moving. */
    if(fabsf(g_flow_pos-(float)g_selected)>0.010f || fabsf(g_flow_vel)>0.010f) {
        idle_tick=0;
        last_selected=g_selected;
        return;
    }

    if(last_selected!=g_selected) {
        last_selected=g_selected;
        idle_tick=0;
        phase=0;
    }

    /* Give input/animation ~0.20 s of quiet time before any blocking I/O. */
    if(++idle_tick < 12u) return;
    idle_tick=0;

    static const int off[13]={0,1,-1,2,-2,3,-3,4,-4,5,-5,6,-6};
    for(int n=0;n<13;n++) {
        int k=(phase+n)%13;
        int idx=g_selected+off[k];
        if(idx<0 || idx>=(int)g_movies.size()) continue;

        Movie &cm=g_movies[idx];
        ensure_movie_cover_path(cm);
        if(cm.cover.empty()) continue;
        if(find_cached_cover(cm)) continue;

        /* One cover per idle slice. The render path itself never decodes. */
        get_movie_cover(cm);
        phase=(k+1)%13;
        return;
    }
    phase=(phase+1)%13;
}

static void release_port'''
s = s[:m.start()] + new_prefetch + s[m.end():]

old = '    CoverBitmap *c=allow_cover_load?get_movie_cover(m):find_cached_cover(m);'
if old not in s:
    raise SystemExit('draw_poster cover-load line not found')
s = s.replace(old,
              '    (void)allow_cover_load;\n    CoverBitmap *c=find_cached_cover(m);', 1)

markers = [
    'bool cover_checked;',
    '#define COVER_CACHE_SLOTS 16',
    'ensure_movie_cover_path',
    'Give input/animation ~0.20 s of quiet time',
    'CoverBitmap *c=find_cached_cover(m);',
    'Cover paths are resolved lazily while the coverflow is idle.',
]
for marker in markers:
    if marker not in s:
        raise SystemExit('missing marker: '+marker)

rebuild = s[s.find('static void rebuild_movies()'):s.find('static bool refresh_usb_state')]
if 'resolve_cover_paths();' in rebuild:
    raise SystemExit('eager resolve_cover_paths still present in rebuild_movies')

p.write_text(s)
print('V2.26 cover idle-cache fix applied: render-only cached covers + lazy idle NTFS/JPEG work')
