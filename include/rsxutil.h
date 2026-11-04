#ifndef __RSXUTIL_H__
#define __RSXUTIL_H__

#include <ppu-types.h>
#include <rsx/rsx.h>

#define HOST_SIZE (32*1024*1024)
#define CB_SIZE   (1024*1024)

extern gcmContextData *context;
void init_screen(void *host_addr,u32 size);
void flip(void);
void waitflip(void);
void setRenderTarget(u32 index);
u32* get_back_buffer(void);
u32 get_screen_width(void);
u32 get_screen_height(void);


/* Declarations used by the verified V2.26 GPU cover/background runtime. */
int rsx_upload_hq_background(const u32 *pixels,u32 width,u32 height);
void rsx_free_hq_background(void);
void rsx_draw_hq_background(u32 fallback_color);
void rsx_cover_free(int slot);
void rsx_cover_free_all(void);
int rsx_cover_upload(int slot,const u32 *pixels,u32 width,u32 height);
int rsx_cover_draw(int slot,int x,int y,int w,int h);
void rsx_cover_sync(void);
void rsx_flip_last_complete(void);

#endif
