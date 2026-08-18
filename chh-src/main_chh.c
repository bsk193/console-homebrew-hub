#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#include "app_installer.h"
#include "notification.h"
#include "wkali.h"

/* CHH extension — defined in app_installer_chh_patch.c appended to app_installer.c */
int wkali_install_app_with_param(const char *title_id,
    const uint8_t *param_json, size_t param_json_size);

extern int sceUserServiceInitialize(void *);

#define CHH_BASE "https://bsk193.github.io/console-homebrew-hub"

int main(void)
{
    syscall(SYS_thr_set_name, -1, "chhi.elf");
    int user_prio = 256;
    sceUserServiceInitialize(&user_prio);

    wkali_notify("Installing CHH shortcut...");

    /* Single shortcut — firmware-detection hub auto-routes to the right exploit */
    const char *id    = "CHHM00001";
    const char *label = "CHH";
    const char *url   = CHH_BASE "/ps5/?autoload=pldmgrx.elf";

    char param[512];
    snprintf(param, sizeof(param),
        "{\"titleId\":\"%s\","
        "\"applicationCategoryType\":65536,"
        "\"deeplinkUri\":\"%s\","
        "\"localizedParameters\":{\"defaultLanguage\":\"en-US\","
        "\"en-US\":{\"titleName\":\"%s\"}}}",
        id, url, label);

    wkali_log("[CHH] Installing %s shortcut...\n", label);
    if (wkali_install_app_with_param(id, (const uint8_t *)param, strlen(param)) == 0) {
        wkali_notify("CHH installed! Reboot once, then use the shortcut.");
    } else {
        wkali_notify("CHH install failed.");
    }

    sleep(1);
    return 0;
}
