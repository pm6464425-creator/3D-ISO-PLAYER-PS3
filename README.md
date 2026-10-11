# 3D ISO PLAYER PS3

Homebrew para PlayStation 3 con **CFW Cobra** orientado a reproducir copias personales de Blu-ray 3D en formato ISO desde discos USB NTFS.

## Objetivo

- Interfaz en español.
- Sin dependencia de webMAN.
- Detectar automáticamente USB 000-007.
- Montar particiones NTFS en modo lectura.
- Buscar `BDISO/*.iso`.
- Mostrar cada película mediante diálogo nativo de PS3 y permitir elegirla.
- Montar la ISO como Blu-ray usando Cobra + rawseciso.
- Intentar lanzar directamente `/dev_flash/bdplayer/bdp_BDMV.self` después del montaje.

## Estado

El proyecto se compila automáticamente con GitHub Actions usando el toolchain PS3DEV. El montaje NTFS reutiliza interfaces públicas compatibles con `libntfs_ext` y `libcobra` de IRISMAN. El `raw_iso.sprx` se genera en tiempo de compilación desde el array binario publicado por IRISMAN.

> Se requiere prueba en una PS3 física con CFW Cobra. El lanzamiento directo del reproductor Blu-ray depende del firmware y puede necesitar ajuste si Sony cambia el comportamiento del SELF.

## Uso previsto

En el disco NTFS:

```text
BDISO/
  Avatar 3D.iso
  Cars 3D.iso
  Titanic 3D.iso
```

Instala el PKG, conecta el disco y abre **3D ISO PLAYER**.

## Licencia

GPL-3.0. Se reutilizan interfaces/código compatible GPL procedente de IRISMAN/libntfs; consulta `LICENSE` y `THIRD_PARTY.md`.
