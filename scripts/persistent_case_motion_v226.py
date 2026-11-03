from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# V2.26 PERSISTENT CASE DURING MOTION
# The master CASE_FRAME.PNG is fully transparent inside the artwork window
# (x=10..629, y=70..805 in the 640x822 source). Therefore the complete case
# bands can be drawn on CPU BEFORE the RSX artwork transfer with no pixel race:
# the later cover only writes into the transparent artwork window.
# This keeps the exact Blu-ray frame visible while moving, with zero RSX fence.

if 'V2.26 PERSISTENT CASE DURING MOTION' not in s:
    old='''        } else if(!allow_cover_load) {\n            int top_h=ay-y; if(top_h<2) top_h=2;\n            int left_w=ax-x; if(left_w<2) left_w=2;\n            int right_x=ar;\n            int right_w=(x+w)-right_x; if(right_w<2) right_w=2;\n            int bot_y=ab;\n            int bot_h=(y+h)-bot_y; if(bot_h<2) bot_h=2;\n            fill_rect(x,y,w,top_h,0xFF176EA8);\n            fill_rect(x,y,left_w,h,0xFF26343E);\n            fill_rect(right_x,y,right_w,h,0xFF26343E);\n            fill_rect(x,bot_y,w,bot_h,0xFF202A31);\n            if(selected) {\n                int glow_w=w*58/100; if(glow_w<12) glow_w=12;\n                int gx=x+(w-glow_w)/2;\n                fill_rect(gx,y+h+2,glow_w,2,0xB85FD7FF);\n            }\n        }\n'''
    new='''        } else if(!allow_cover_load) {\n            /* V2.26 PERSISTENT CASE DURING MOTION:\n               draw the exact remastered Blu-ray frame BEFORE the RSX cover.\n               CASE_FRAME is transparent in the artwork window, so the later\n               GPU transfer cannot erase any visible frame pixel. */\n            if(g_case_frame.rgba) {\n                int fw=g_case_frame.w, fh=g_case_frame.h;\n                int top_src=fh*88/822; if(top_src<1) top_src=1;\n                int bot_y=fh*790/822; if(bot_y<0) bot_y=0;\n                int side_y=fh*64/822;\n                int side_h=fh*748/822; if(side_y+side_h>fh) side_h=fh-side_y;\n                int edge=fw*18/640; if(edge<2) edge=2;\n\n                int top_dst=h*88/822; if(top_dst<2) top_dst=2;\n                int bot_dst_y=h*790/822;\n                int side_dst_y=h*64/822;\n                int side_dst_h=h*748/822;\n                int edge_dst=w*18/640; if(edge_dst<2) edge_dst=2;\n\n                draw_rgba_region_scaled(x,y,w,top_dst,&g_case_frame,0,0,fw,top_src);\n                draw_rgba_region_scaled(x,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,0,side_y,edge,side_h);\n                draw_rgba_region_scaled(x+w-edge_dst,y+side_dst_y,edge_dst,side_dst_h,&g_case_frame,fw-edge,side_y,edge,side_h);\n                draw_rgba_region_scaled(x,y+bot_dst_y,w,h-bot_dst_y,&g_case_frame,0,bot_y,fw,fh-bot_y);\n            }\n            if(selected) {\n                int glow_w=w*58/100; if(glow_w<12) glow_w=12;\n                int gx=x+(w-glow_w)/2;\n                fill_rect(gx,y+h+2,glow_w,2,0xB85FD7FF);\n            }\n        }\n'''
    if old not in s:
        raise SystemExit('motion lightweight case block not found')
    s=s.replace(old,new,1)

# Safety invariants: keep the no-fence and realtime fixes untouched.
required=[
    'V2.26 PERSISTENT CASE DURING MOTION',
    'V2.26 MOTION NO-FENCE',
    'V2.26 REALTIME MOTION PERF',
    'draw_rgba_region_scaled(x,y,w,top_dst,&g_case_frame,0,0,fw,top_src);',
    'if(flow_animating)',
]
for marker in required:
    if marker not in s:
        raise SystemExit('persistent-case invariant missing: '+marker)

p.write_text(s)
print('V2.26 persistent case applied: exact Blu-ray frame stays visible during motion, zero extra RSX fence')
