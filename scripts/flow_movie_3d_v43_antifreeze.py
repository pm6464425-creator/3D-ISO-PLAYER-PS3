from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def replace_function(signature, new_text, label):
    global s
    start = s.find(signature)
    if start < 0:
        raise SystemExit(f'{label} signature not found')
    brace = s.find('{', start)
    if brace < 0:
        raise SystemExit(f'{label} opening brace not found')
    depth = 0
    end = -1
    for i in range(brace, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise SystemExit(f'{label} closing brace not found')
    s = s[:start] + new_text + s[end:]


# Remember whether each movie has already had its sidecar cover paths probed.
old_movie = '''    std::string source;\n    std::string cover;\n    int usb_id;'''
new_movie = '''    std::string source;\n    std::string cover;\n    bool cover_checked;\n    int usb_id;'''
if old_movie not in s:
    raise SystemExit('Movie cover field anchor not found')
s = s.replace(old_movie, new_movie, 1)

# All freshly scanned entries start with lazy cover discovery disabled/unresolved.
s = s.replace('''                m.ntfs = false;\n                fresh.push_back(m);''',
              '''                m.ntfs = false;\n                m.cover_checked = false;\n                fresh.push_back(m);''')
s = s.replace('''                m.ntfs = true;\n                fresh.push_back(m);''',
              '''                m.ntfs = true;\n                m.cover_checked = false;\n                fresh.push_back(m);''')

# Do NOT probe every possible JPG/PNG path for the whole library during a scan.
# That was up to 12 NTFS stat calls per movie and could stall the UI for seconds.
replace_function('static void resolve_cover_paths()', r'''static void resolve_cover_paths()
{
    for(size_t i=0;i<g_movies.size();++i) {
        g_movies[i].cover.clear();
        g_movies[i].cover_checked=false;
    }
}''', 'resolve_cover_paths')

# Lower pathological image limits. Movie posters do not need multi-megapixel
# source images on a 720p/1080p PS3 UI and huge PNG/JPEG files can stall the PPU.
s = s.replace('st.st_size > 16*1024*1024', 'st.st_size > 8*1024*1024')
s = s.replace('(uint64_t)pw*(uint64_t)ph>12000000ULL', '(uint64_t)pw*(uint64_t)ph>6000000ULL')

anchor = 'static unsigned int g_cover_stamp = 1;\n'
extra = r'''
static bool g_cover_allow_io = false;
static int g_cover_prefetch_step = 0;
static int g_cover_prefetch_selected = -1;
'''
if anchor not in s:
    raise SystemExit('cover globals anchor not found')
s = s.replace(anchor, anchor + extra, 1)

# The final V4 renderer stores texture memory permanently and only changes LRU
# metadata. Cover discovery/decode is now allowed only from the one-item prefetch
# budget, never opportunistically for all visible cards in draw_poster().
replace_function('static CoverBitmap *get_movie_cover(const Movie &m)', r'''static CoverBitmap *get_movie_cover(Movie &m)
{
    if(!m.cover_checked) {
        if(!g_cover_allow_io) return NULL;
        m.cover = find_movie_cover(m);
        m.cover_checked = true;
        if(m.cover.empty()) return NULL;
    }
    if(m.cover.empty()) return NULL;

    for(int i=0;i<COVER_CACHE_SLOTS;i++) {
        if(g_cover_cache[i].rgba && g_cover_cache[i].path==m.cover) {
            g_cover_cache[i].stamp=++g_cover_stamp;
            return &g_cover_cache[i];
        }
    }
    if(!g_cover_allow_io) return NULL;

    int slot=-1;
    unsigned oldest=0xFFFFFFFFu;
    for(int i=0;i<COVER_CACHE_SLOTS;i++) {
        if(g_cover_cache[i].path.empty()) { slot=i; break; }
        if(g_cover_cache[i].stamp<oldest) { oldest=g_cover_cache[i].stamp; slot=i; }
    }
    if(slot<0) return NULL;

    size_t sz=0;
    unsigned char *file=read_file_bytes(m,m.cover,&sz);
    if(!file) return NULL;

    int pw=0,ph=0,pc=0;
    if(!stbi_info_from_memory(file,(int)sz,&pw,&ph,&pc) || pw<=0 || ph<=0 ||
       pw>4096 || ph>4096 || (uint64_t)pw*(uint64_t)ph>6000000ULL) {
        free(file);
        return NULL;
    }

    int iw=0,ih=0,comp=0;
    unsigned char *decoded=stbi_load_from_memory(file,(int)sz,&iw,&ih,&comp,4);
    free(file);
    if(!decoded) return NULL;

    int cw=0,ch=0;
    unsigned char *scaled=scale_rgba(decoded,iw,ih,&cw,&ch);
    stbi_image_free(decoded);
    if(!scaled) return NULL;

    const size_t cap=(size_t)320*480*4;
    if(!g_cover_cache[slot].rgba) {
        g_cover_cache[slot].rgba=(unsigned char*)tiny3d_AllocTexture((u32)cap);
        if(!g_cover_cache[slot].rgba) { free(scaled); return NULL; }
    }

    u32 *dst=(u32*)g_cover_cache[slot].rgba;
    size_t count=(size_t)cw*ch;
    for(size_t i=0;i<count;i++) {
        const unsigned char *sp=scaled+i*4;
        dst[i]=((u32)sp[3]<<24)|((u32)sp[0]<<16)|((u32)sp[1]<<8)|sp[2];
    }
    free(scaled);

    g_cover_cache[slot].w=cw;
    g_cover_cache[slot].h=ch;
    g_cover_cache[slot].path=m.cover;
    g_cover_cache[slot].stamp=++g_cover_stamp;
    return &g_cover_cache[slot];
}''', 'get_movie_cover')

# draw_poster receives a mutable library item so lazy cover state can be cached.
s = s.replace('static void draw_poster(int x, int y, int w, int h, const Movie &m, bool selected)',
              'static void draw_poster(int x, int y, int w, int h, Movie &m, bool selected)', 1)

# Load exactly one center-near cover per frame. This keeps input and animation
# responsive even with slow NTFS media or large cover files.
insert_anchor = 'static void render_ui()\n{\n'
helper = r'''static void flow_prefetch_one_cover()
{
    if(g_movies.empty() || g_selected<0 || g_selected>=(int)g_movies.size()) return;
    if(g_cover_prefetch_selected != g_selected) {
        g_cover_prefetch_selected = g_selected;
        g_cover_prefetch_step = 0;
    }

    static const int offsets[9] = {0,1,-1,2,-2,3,-3,4,-4};
    for(int tries=0; tries<9; ++tries) {
        int off = offsets[g_cover_prefetch_step % 9];
        g_cover_prefetch_step = (g_cover_prefetch_step + 1) % 9;
        int idx = g_selected + off;
        if(idx<0 || idx>=(int)g_movies.size()) continue;

        Movie &m = g_movies[idx];
        bool needs_work = !m.cover_checked;
        if(!needs_work && !m.cover.empty()) {
            bool cached=false;
            for(int i=0;i<COVER_CACHE_SLOTS;i++) {
                if(g_cover_cache[i].rgba && g_cover_cache[i].path==m.cover) { cached=true; break; }
            }
            needs_work = !cached;
        }
        if(!needs_work) continue;

        g_cover_allow_io=true;
        (void)get_movie_cover(m);
        g_cover_allow_io=false;
        return;
    }
}

'''
if insert_anchor not in s:
    raise SystemExit('render_ui anchor not found')
s = s.replace(insert_anchor, helper + insert_anchor, 1)

# The V4.2 frame starts with flow_begin_frame(); perform only one bounded cover
# operation before drawing. draw_poster itself is now I/O-free.
needle = '''    flow_update();\n    draw_background();'''
repl = '''    flow_update();\n    flow_prefetch_one_cover();\n    draw_background();'''
if needle not in s:
    raise SystemExit('render prefetch insertion anchor not found')
s = s.replace(needle, repl, 1)

# Switching tabs or rescanning should restart center-first prefetch ordering.
s = s.replace('g_selected=0; rebuild_movies();', 'g_selected=0; g_cover_prefetch_selected=-1; rebuild_movies();')
s = s.replace('if(tri && !p_tri) refresh_usb_state(true);', 'if(tri && !p_tri) { g_cover_prefetch_selected=-1; refresh_usb_state(true); }')

p.write_text(s)
print('FLOW MOVIE 3D V4.3 anti-freeze applied: lazy cover discovery, one decode per frame, bounded poster size')
