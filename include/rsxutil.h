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

#endif
