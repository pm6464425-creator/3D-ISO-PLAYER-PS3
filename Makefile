.SUFFIXES:

ifeq ($(strip $(PSL1GHT)),)
$(error "Please set PSL1GHT in your environment")
endif

TOPDIR ?= $(CURDIR)
export TOPDIR

include $(PSL1GHT)/ppu_rules

TARGET      := 3disoplayer
BUILD       := build
SOURCES     := source
DATA        :=
INCLUDES    := include third_party/include
TITLE       := 3D ISO PLAYER
APPID       := 3DISO001
CONTENTID   := UP0001-$(APPID)_00-0000000000000000
PKGFILES    := $(TOPDIR)/pkgfiles
ICON0       := $(TOPDIR)/pkgfiles/ICON0.PNG

CFLAGS      := -O2 -Wall -mcpu=cell $(MACHDEP) $(INCLUDE)
CXXFLAGS    := $(CFLAGS) -fno-exceptions -fno-rtti
LDFLAGS     := $(MACHDEP) -Wl,-Map,$(notdir $@).map

LIBS        := $(TOPDIR)/third_party/lib/libcobra.a \
               $(TOPDIR)/third_party/lib/libfatfs.a \
               $(TOPDIR)/third_party/lib/libntfs_ext.a \
               -lstdc++ -lz -lrsx -lgcm_sys -lio -lsysutil -lrt -llv2 -lsysmodule -lm

LIBDIRS     :=

ifneq ($(BUILD),$(notdir $(CURDIR)))

export OUTPUT   := $(CURDIR)/$(TARGET)
export VPATH    := $(foreach dir,$(SOURCES),$(CURDIR)/$(dir))
export DEPSDIR  := $(CURDIR)/$(BUILD)
export BUILDDIR := $(CURDIR)/$(BUILD)

CFILES      := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
CPPFILES    := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp)))
sFILES      := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.s)))
SFILES      := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.S)))

ifeq ($(strip $(CPPFILES)),)
export LD := $(CC)
else
export LD := $(CXX)
endif

export OFILES   := $(CPPFILES:.cpp=.o) $(CFILES:.c=.o) $(sFILES:.s=.o) $(SFILES:.S=.o)
export INCLUDE  := $(foreach dir,$(INCLUDES),-I$(CURDIR)/$(dir)) $(LIBPSL1GHT_INC) -I$(CURDIR)/$(BUILD) -I$(PORTLIBS)/include
export LIBPATHS := $(LIBPSL1GHT_LIB) -L$(PORTLIBS)/lib
export CFLAGS
export CXXFLAGS
export LDFLAGS
export LIBS

.PHONY: all pkg clean
all: $(BUILD)

$(BUILD):
	@[ -d $@ ] || mkdir -p $@
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile

pkg: $(BUILD)
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile $(OUTPUT).pkg

clean:
	@rm -rf $(BUILD) $(OUTPUT).elf $(OUTPUT).self $(OUTPUT).fake.self $(OUTPUT).pkg $(OUTPUT).gnpdrm.pkg

else

DEPENDS := $(OFILES:.o=.d)

$(OUTPUT).self: $(OUTPUT).elf
$(OUTPUT).elf: $(OFILES)

-include $(DEPENDS)

endif
