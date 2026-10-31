from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.11
# Visual sizing measured from the user's reference video.
# Keep V2.10 SAFE movement/render path, restore the remastered Blu-ray frame
# using the efficient border-only sampler from V2.7, and use true case ratio.

old_geom='''        const float sel_h=sh*0.50f;\n        const float nb_h=sh*0.32f;\n        const float aspect=0.68f;'''
new_geom='''        /* V2.11: compact proportions matched to the reference video.\n           The case master is 640x822, so keep its real 0.779 aspect. */\n        const float sel_h=sh*0.39f;\n        const float nb_h=sh*0.25f;\n        const float aspect=640.0f/822.0f;'''
if old_geom not in s:
    raise SystemExit('geometry anchor not found')
s=s.replace(old_geom,new_geom,1)

old_case='''    /* V2.8 HARD PERF: lightweight case outline.  The previous PNG frame still\n       required thousands of alpha blends per visible cover every frame. */\n    u32 edge = selected ? 0xFF5FCFFF : 0xFF24465A;\n    int bw = selected ? 3 : 2;\n    fill_rect(x,y,w,bw,edge);\n    fill_rect(x,y+h-bw,w,bw,edge);\n    fill_rect(x,y,bw,h,edge);\n    fill_rect(x+w-bw,y,bw,h,edge);'''

new_case='''    /* V2.11: restore the real remastered Blu-ray case without the expensive\n       transparent center.  Only the visible top/side/bottom bands are sampled,\n       preserving the rounded corners and Blu-ray header from CASE_FRAME.PNG. */\n    if(g_case_frame.rgba) {\n        int fw=g_case_frame.w, fh=g_case_frame.h;\n        int top_src=fh*88/822; if(top_src<1) top_src=1;\n        int bot_y=fh*790/822; if(bot_y<0) bot_y=0;\n        int side_y=fh*64/822;\n        int side_h=fh*748/822; if(side_y+side_h>fh) side_h=fh-side_y;\n        int edge=fw*18/640; if(edge<2) edge=2;\n\n        int top_dst=h*88/822; if(top_dst<2) top_dst=2;\n        int bot_dst_y=h*790/822;\n        int side_dst_y=h*64/822;\n        int side_dst_h=h*748/822;\n        int edge_dst=w*18/640; if(edge_dst<2) edge_dst=2;\n\n        draw_rgba_region_scaled(x,y,w,top_dst,&g_case_frame,0,0,fw,top_src);\n        draw_rgba_region_scaled(x,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,0,side_y,edge,side_h);\n        draw_rgba_region_scaled(x+w-edge_dst,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,fw-edge,side_y,edge,side_h);\n        draw_rgba_region_scaled(x,y+bot_dst_y,w,h-bot_dst_y,&g_case_frame,0,bot_y,fw,fh-bot_y);\n    }'''
if old_case not in s:
    raise SystemExit('simple case anchor not found')
s=s.replace(old_case,new_case,1)

# Slightly tighten spacing to match the reference coverflow composition.
old_spacing='''        const float x1=sel_w*0.5f+nb_w*0.30f+nb_w*0.5f;\n        const float pitch=nb_w*1.12f;'''
new_spacing='''        const float x1=sel_w*0.5f+nb_w*0.24f+nb_w*0.5f;\n        const float pitch=nb_w*1.06f;'''
if old_spacing not in s:
    raise SystemExit('spacing anchor not found')
s=s.replace(old_spacing,new_spacing,1)

p.write_text(s)
print('FLOW MOVIE V2.11: compact reference sizing + efficient real Blu-ray frame restored')
