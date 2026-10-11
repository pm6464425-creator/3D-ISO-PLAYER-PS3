# Componentes de terceros

Este proyecto usa durante la compilación componentes públicos de IRISMAN:

- `libcobra.a` y `cobra.h` para las operaciones Cobra.
- `libntfs_ext.a`, `libfatfs.a` y `ntfs.h` para acceso NTFS.
- `raw_iso.sprx`, reconstruido desde el array `rawseciso/bin2c/rawseciso.c`, para montar una ISO ubicada físicamente en un dispositivo NTFS mediante sectores.

IRISMAN y sus componentes derivados se distribuyen bajo licencias GPL compatibles. El código de este repositorio se publica bajo GPL-3.0 para mantener compatibilidad de redistribución.

PSL1GHT/PS3DEV se utiliza únicamente como toolchain de compilación.
