/* CHH extension appended to app_installer.c at build time.
 * Adds wkali_install_app_with_param() which installs a web-app shortcut
 * using runtime-provided param.json data instead of INCASSET-embedded data.
 * The function reuses the static helpers and INCASSET icon already defined
 * in the same translation unit (app_installer.c). */

int wkali_install_app_with_param(const char *title_id,
    const uint8_t *param_json, size_t param_json_size)
{
    char app_dir[256], sce_sys_dir[256], param_path[256], icon_path[256];
    snprintf(app_dir,     sizeof(app_dir),     "/user/app/%s",                    title_id);
    snprintf(sce_sys_dir, sizeof(sce_sys_dir), "/user/app/%s/sce_sys",            title_id);
    snprintf(param_path,  sizeof(param_path),  "/user/app/%s/sce_sys/param.json", title_id);
    snprintf(icon_path,   sizeof(icon_path),   "/user/app/%s/sce_sys/icon0.png",  title_id);

    struct stat st;
    if (stat(app_dir, &st) == 0 &&
        !needs_update(param_path, param_json, param_json_size) &&
        !needs_update(icon_path, icon0_png, icon0_png_size))
        return 0;

    wkali_log("[WKALI-CHH] Installing %s...\n", title_id);

    int err;
    if ((err = sceAppInstUtilInitialize()) < 0) {
        wkali_log("[WKALI-CHH] sceAppInstUtilInitialize failed: 0x%08X\n", err);
        return err;
    }

    if ((err = mkdir_p(sce_sys_dir, 0755)) < 0) {
        wkali_log("[WKALI-CHH] mkdir_p failed: %d\n", err);
        sceAppInstUtilTerminate();
        return err;
    }

    if ((err = install_file(param_path, param_json, param_json_size)) < 0 ||
        (err = install_file(icon_path, icon0_png, icon0_png_size)) < 0) {
        wkali_log("[WKALI-CHH] install_file failed: %d\n", err);
        sceAppInstUtilTerminate();
        return err;
    }

    err = install_app(title_id, "/user/app/");
    sceAppInstUtilTerminate();
    return err;
}
