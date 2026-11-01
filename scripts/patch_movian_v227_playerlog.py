from pathlib import Path

p=Path('/tmp/movian-next/src/arch/ps3/ps3_main.c')
s=p.read_text()

if '#include <stdarg.h>' not in s:
    s=s.replace('#include <stdio.h>\n', '#include <stdio.h>\n#include <stdarg.h>\n', 1)

anchor='static uint64_t ticks_per_us;\n'
helper=r'''

#define FLOW_PLAYER_LOG_PATH "/dev_hdd0/game/3DISO0001/USRDIR/FLOW_PLAYER.LOG"

static void
flow_player_log(const char *tag, const char *fmt, ...)
{
  FILE *fp = fopen(FLOW_PLAYER_LOG_PATH, "a");
  if(fp == NULL)
    return;

  struct timeval tv;
  gettimeofday(&tv, NULL);
  fprintf(fp, "[%lld.%03lld] %s", (long long)tv.tv_sec,
          (long long)(tv.tv_usec / 1000), tag ? tag : "PLAYER");
  if(fmt != NULL && *fmt) {
    fprintf(fp, " | ");
    va_list ap;
    va_start(ap, fmt);
    vfprintf(fp, fmt, ap);
    va_end(ap);
  }
  fputc('\n', fp);
  fflush(fp);
  fclose(fp);
}
'''
if 'FLOW_PLAYER_LOG_PATH' not in s:
    if anchor not in s:
        raise SystemExit('ticks_per_us anchor not found')
    s=s.replace(anchor, anchor+helper, 1)

old='''static void\nps3_early_init(int argc, char **argv)\n{\n  char buf[PATH_MAX], *x;'''
new='''static void\nps3_early_init(int argc, char **argv)\n{\n  char buf[PATH_MAX], *x;\n\n  flow_player_log("PLAYER_START", "argc=%d argv0=%s argv1=%s",\n                  argc,\n                  (argc > 0 && argv && argv[0]) ? argv[0] : "<null>",\n                  (argc > 1 && argv && argv[1]) ? argv[1] : "<null>");'''
if old not in s:
    raise SystemExit('ps3_early_init anchor not found')
s=s.replace(old,new,1)

old='''  netInitialize();\n  netCtlInit();'''
new='''  netInitialize();\n  netCtlInit();\n  flow_player_log("NET_INIT_DONE", "network initialized");'''
if old not in s:
    raise SystemExit('net init anchor not found')
s=s.replace(old,new,1)

old='''  gconf.cache_path = strdup(buf);\n  SysLoadModule(SYSMODULE_RTC);'''
new='''  gconf.cache_path = strdup(buf);\n  flow_player_log("PATHS_READY", "binary=%s dirname=%s persistent=%s cache=%s",\n                  gconf.binary ? gconf.binary : "<null>",\n                  gconf.dirname ? gconf.dirname : "<null>",\n                  gconf.persistent_path ? gconf.persistent_path : "<null>",\n                  gconf.cache_path ? gconf.cache_path : "<null>");\n  SysLoadModule(SYSMODULE_RTC);'''
if old not in s:
    raise SystemExit('path setup anchor not found')
s=s.replace(old,new,1)

old='''void\ntrace_arch(int level, const char *prefix, const char *str)\n{\n  printf("[%s] %s\\n", prefix, str);\n  fflush(stdout);\n}'''
new='''void\ntrace_arch(int level, const char *prefix, const char *str)\n{\n  printf("[%s] %s\\n", prefix, str);\n  fflush(stdout);\n  flow_player_log("TRACE", "[%s] %s", prefix ? prefix : "?", str ? str : "");\n}'''
if old not in s:
    raise SystemExit('trace_arch anchor not found')
s=s.replace(old,new,1)

old='''    thread_dump();\n\n    exit(0);'''
new='''    flow_player_log("CRASH_EVENT", "exec catcher received event source=%llu data1=%llu data2=%llu data3=%llu",\n                    (unsigned long long)event.source,\n                    (unsigned long long)event.data1,\n                    (unsigned long long)event.data2,\n                    (unsigned long long)event.data3);\n    thread_dump();\n\n    exit(0);'''
if old not in s:
    raise SystemExit('exec catcher anchor not found')
s=s.replace(old,new,1)

old='static int no_sfo_overwrite;'
new='static int no_sfo_overwrite = 1;'
if old not in s:
    raise SystemExit('no_sfo_overwrite anchor not found')
s=s.replace(old,new,1)

old='''  main_init();\n\n  sysprop = prop_create(prop_get_global(), "system");'''
new='''  flow_player_log("MAIN_INIT_BEGIN", "initial URL follows child argv contract");\n  main_init();\n  flow_player_log("MAIN_INIT_END", "core initialized");\n\n  sysprop = prop_create(prop_get_global(), "system");'''
if old not in s:
    raise SystemExit('main_init anchor not found')
s=s.replace(old,new,1)

old='''  extern void glw_ps3_start(void);\n  glw_ps3_start();\n\n  main_fini();'''
new='''  extern void glw_ps3_start(void);\n  flow_player_log("GLW_START", "entering Movian UI/player loop");\n  glw_ps3_start();\n  flow_player_log("GLW_RETURNED", "UI/player loop returned");\n\n  main_fini();'''
if old not in s:
    raise SystemExit('glw start anchor not found')
s=s.replace(old,new,1)

p.write_text(s)
print('Patched Movian Next: FLOW_PLAYER.LOG + crash markers + no SFO/icon overwrite')
