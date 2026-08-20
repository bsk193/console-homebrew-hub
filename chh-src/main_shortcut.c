/* LEGACY — replaced by main.c (which includes an HTTP server for AppCache).
 *
 * This file is kept for reference only. The build now uses main.c which
 * starts a local MHD server, caches web content via AppCache, and installs
 * the shortcut after caching completes — matching ps5-webkit-autoloader's
 * architecture. See main.c and http_server.c.
 */

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#include "app_installer.h"
#include "notification.h"
#include "wkali.h"

int wkali_install_app_with_param(const char *title_id,
    const uint8_t *param_json, size_t param_json_size);

extern int sceUserServiceInitialize(void *);

#define CHH_SHORTCUT_ID  "CHHM00001"
/* LEGACY: see param.json for the new shortcut URL (http://127.0.0.1:18280/...) */
#define CHH_SHORTCUT_URL "http://ps5.chh:6969/ps5/chh.html"
#define CHH_LABEL        "CHH"

int main(void)
{
    syscall(SYS_thr_set_name, -1, "chh-sc.elf");
    int prio = 256;
    sceUserServiceInitialize(&prio);

    char param[512];
    snprintf(param, sizeof(param),
        "{\"titleId\":\"%s\","
        "\"applicationCategoryType\":65536,"
        "\"deeplinkUri\":\"%s\","
        "\"localizedParameters\":{\"defaultLanguage\":\"en-US\","
        "\"en-US\":{\"titleName\":\"%s\"}}}",
        CHH_SHORTCUT_ID, CHH_SHORTCUT_URL, CHH_LABEL);

    if (wkali_install_app_with_param(CHH_SHORTCUT_ID,
            (const uint8_t *)param, strlen(param)) == 0)
        wkali_notify("CHH shortcut installed!");
    else
        wkali_notify("CHH shortcut install failed.");

    sleep(1);
    return 0;
}
