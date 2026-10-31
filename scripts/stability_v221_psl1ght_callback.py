from pathlib import Path
import re
import sys

# FLOW MOVIE V2.21 - PSL1GHT callback fix
# V2.20 is intentionally NOT part of this build. This patch is applied on top
# of V2.19. It does not proactively reserve FIFO space or call the callback.
# Instead it fixes PSL1GHT's rsxContextCallback wrapper in the toolchain so a
# natural segment crossing is visible to GCC and context->current is reloaded.

main = Path('source/main.cpp')
s = main.read_text()
s = s.replace('flow_log("SESSION_START","FLOW MOVIE V2.19 STABILITY FIX");',
              'flow_log("SESSION_START","FLOW MOVIE V2.21 PSL1GHT CALLBACK FIX");', 1)
if 'FLOW MOVIE V2.21 PSL1GHT CALLBACK FIX' not in s:
    raise SystemExit('V2.19 session marker not found in main.cpp')
main.write_text(s)

if len(sys.argv) != 2:
    raise SystemExit('usage: stability_v221_psl1ght_callback.py <rsx_function_macros.h>')

hdr = Path(sys.argv[1])
if not hdr.exists():
    raise SystemExit(f'PSL1GHT header not found: {hdr}')
r = hdr.read_text()

# Match the old PSL1GHT wrapper exactly from the function declaration through
# the closing brace immediately before RSX_FUNC_INTERNAL. This old wrapper uses
# inline asm and does not tell GCC that memory/context state can change.
pattern = re.compile(
    r's32 __attribute__\(\(noinline\)\) rsxContextCallback\(gcmContextData \*context,u32 count\)\s*\{.*?\n\s*\}\s*\n\s*#define RSX_FUNC_INTERNAL',
    re.S,
)
replacement = '''s32 __attribute__((noinline)) rsxContextCallback(gcmContextData *context,u32 count)\n\t{\n\t\t/* V2.21: use a real C call so GCC sees context memory may change. */\n\t\ts32 result = context->callback(context,count);\n\t\t__asm__ __volatile__("" ::: "memory");\n\t\treturn result;\n\t}\n\t\n\t#define RSX_FUNC_INTERNAL'''

r2, n = pattern.subn(replacement, r, count=1)
if n != 1:
    raise SystemExit(f'expected one rsxContextCallback wrapper, replaced {n}')
if 'context->callback(context,count)' not in r2:
    raise SystemExit('direct callback replacement missing')
if 'V2.21: use a real C call' not in r2:
    raise SystemExit('V2.21 callback marker missing')

hdr.write_text(r2)
print('FLOW MOVIE V2.21: patched PSL1GHT rsxContextCallback; no proactive FIFO reserve')
