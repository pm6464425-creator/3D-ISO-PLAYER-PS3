/*
 * Compatibilidad mínima: algunas versiones de libcobra.a publicadas con
 * IRISMAN no exportan is_cobra_based(), aunque cobra.h lo declare.
 * El montaje real sigue validándose por el resultado de cobra_load_vsh_plugin().
 */
int is_cobra_based(void)
{
    return 1;
}
