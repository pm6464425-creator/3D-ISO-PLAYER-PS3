from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 MOTION NO-FENCE
# While the coverflow is moving, all CPU drawing happens first, then real
# covers are queued to RSX as the last poster operation of the frame. There is
# deliberately NO waitFinish()/rsx_cover_sync() on the moving path.

if 'V2.26 MOTION NO-FENCE' not in s:
    s=s.replace('    (void)allow_cover_load;\n    CoverBitmap *c=find_cached_cover(m);\n',
'''    CoverBitmap *c=find_cached_cover(m);\n''',1)

    old='''    if(phase==0) {\n        /* Draw every CPU-only underlay before any RSX cover commands are queued. */\n        int shad=(w>220)?7:4;\n        fill_rect(x+shad,y+shad,w,h,0x44000000);\n        if(!c) draw_generic_cover(ax,ay,aw,ah,m,selected);\n        return;\n    }\n'''
    new='''    if(phase==0) {\n        /* V2.26 MOTION NO-FENCE: all CPU work is completed before moving\n           covers are queued to RSX. The lightweight motion frame occupies\n           only pixels OUTSIDE the artwork rectangle, so the later GPU copy\n           cannot overwrite it and no GPU fence is needed. */\n        int shad=(w>220)?7:4;\n        fill_rect(x+shad,y+shad,w,h,0x44000000);\n        if(!c) {\n            draw_generic_cover(ax,ay,aw,ah,m,selected);\n        } else if(!allow_cover_load) {\n            int top_h=ay-y; if(top_h<2) top_h=2;\n            int left_w=ax-x; if(left_w<2) left_w=2;\n            int right_x=ar;\n            int right_w=(x+w)-right_x; if(right_w<2) right_w=2;\n            int bot_y=ab;\n            int bot_h=(y+h)-bot_y; if(bot_h<2) bot_h=2;\n            fill_rect(x,y,w,top_h,0xFF176EA8);\n            fill_rect(x,y,left_w,h,0xFF26343E);\n            fill_rect(right_x,y,right_w,h,0xFF26343E);\n            fill_rect(x,bot_y,w,bot_h,0xFF202A31);\n            if(selected) {\n                int glow_w=w*58/100; if(glow_w<12) glow_w=12;\n                int gx=x+(w-glow_w)/2;\n                fill_rect(gx,y+h+2,glow_w,2,0xB85FD7FF);\n            }\n        }\n        return;\n    }\n'''
    if old not in s:
        raise SystemExit('draw_poster phase0 anchor missing')
    s=s.replace(old,new,1)

    old='''        /* Phase 0: all CPU underlays first. */\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating,0);\n        }\n        /* Phase 1: queue every real cover to RSX, far-to-near. No per-cover fence. */\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating,1);\n        }\n        /* Exactly one GPU fence, and only when at least one RSX cover was queued. */\n        rsx_cover_sync();\n        /* Phase 2: restore the exact original case-frame bands and selected glow. */\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating,2);\n        }\n'''
    new='''        /* Phase 0: every CPU poster underlay first. */\n        for(int i=0;i<nitems;i++) {\n            bool active=fabsf(items[i].d)<0.34f;\n            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,!flow_animating,0);\n        }\n\n        if(!flow_animating) {\n            /* At rest we keep the exact high-quality case overlay. A fence here\n               is harmless because there is no coverflow animation to stall. */\n            for(int i=0;i<nitems;i++) {\n                bool active=fabsf(items[i].d)<0.34f;\n                draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,true,1);\n            }\n            rsx_cover_sync();\n            for(int i=0;i<nitems;i++) {\n                bool active=fabsf(items[i].d)<0.34f;\n                draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,true,2);\n            }\n        }\n'''
    if old not in s:
        raise SystemExit('cover phase block anchor missing')
    s=s.replace(old,new,1)

    old='''        for(int i=0;i<shown;i++) {\n            int idx=start+i;\n            draw_circle(dot_x+i*dot_gap,dot_y,idx==g_selected?3:2,idx==g_selected?0xFF70C8FF:0xFF4A5863);\n        }\n    }\n\n    int footer_h='''
    new='''        for(int i=0;i<shown;i++) {\n            int idx=start+i;\n            draw_circle(dot_x+i*dot_gap,dot_y,idx==g_selected?3:2,idx==g_selected?0xFF70C8FF:0xFF4A5863);\n        }\n\n        if(flow_animating) {\n            /* V2.26 MOTION NO-FENCE: queue real covers only after every CPU\n               element in the movie area has been written. Do NOT call\n               rsx_cover_sync() here. flip() flushes these transfer commands\n               before the VSync flip, preserving command order without a\n               second 15-16 ms CPU-side wait. */\n            for(int i=0;i<nitems;i++) {\n                bool active=fabsf(items[i].d)<0.34f;\n                draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active,false,1);\n            }\n        }\n    }\n\n    int footer_h='''
    if old not in s:
        raise SystemExit('deferred moving cover anchor missing')
    s=s.replace(old,new,1)

    # Strong generated-source invariants.
    if 'if(flow_animating) {' not in s or 'V2.26 MOTION NO-FENCE' not in s:
        raise SystemExit('motion no-fence markers missing')

p.write_text(s)
print('V2.26 motion no-fence patch applied: moving real covers use RSX with zero explicit per-frame fence')
