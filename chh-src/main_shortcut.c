/* chh-shortcut.elf — installs the CHH PS5 shortcut.
 *
 * This ELF is tiny by design: no HTTP server, no embedded files, no MHD.
 * It is the autoload target in install mode so that the exploit core only needs
 * to hold a ~100-200 KB ArrayBuffer (vs 2-5 MB for chh-installer.elf), which
 * prevents OOM during the kernel exploit phase.
 *
 * Offline caching is handled by AppCache on the shortcut landing page
 * (chh.html).  After the shortcut is installed once (while the PC host is
 * running), subsequent uses work fully offline.
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
/* Shortcut opens chh.html which has AppCache manifest for offline caching. */
#define CHH_SHORTCUT_URL "https://manuals.playstation.net/ps5/chh.html"
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
