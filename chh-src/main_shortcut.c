/* chh-installer.elf — installs the CHH PS5 shortcut.
 *
 * Tiny by design: no HTTP server, no embedded files, no MHD.
 * Loaded after the first jailbreak to install the CHH shortcut.
 * Offline caching is handled by AppCache on the shortcut landing page
 * (chh.html) — subsequent uses work offline without the PC host.
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
/* Shortcut opens chh.html via custom domain (ps5.chh) — NXDOMAIN when DNS
   is not spoofed preserves AppCache; avoids conflicts with nanodns/Sony. */
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
