#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#include "app_installer.h"
#include "notification.h"
#include "wkali.h"

extern int sceUserServiceInitialize(void *);

#define CHH_BASE "https://bsk193.github.io/console-homebrew-hub"

static const struct {
    const char *id;
    const char *label;
    const char *url;
} CHH_APPS[] = {
    { "CHHU00001", "CHH UMTX",    CHH_BASE "/ps5/exploits/umtx/?autoload=pldmgrx.elf"    },
    { "CHHI00001", "CHH IPV6",    CHH_BASE "/ps5/exploits/ipv6/?autoload=pldmgrx.elf"    },
    { "CHHS00001", "CHH Slopkit", CHH_BASE "/ps5/exploits/slopkit/?autoload=pldmgrx.elf" },
};
#define CHH_APP_COUNT (int)(sizeof(CHH_APPS) / sizeof(CHH_APPS[0]))

int main(void)
{
    syscall(SYS_thr_set_name, -1, "chhi.elf");
    int user_prio = 256;
    sceUserServiceInitialize(&user_prio);

    wkali_notify("Installing CHH shortcuts...");

    int ok = 0;
    for (int i = 0; i < CHH_APP_COUNT; i++) {
        char param[512];
        snprintf(param, sizeof(param),
            "{\"titleId\":\"%s\","
            "\"applicationCategoryType\":65536,"
            "\"deeplinkUri\":\"%s\","
            "\"localizedParameters\":{\"defaultLanguage\":\"en-US\","
            "\"en-US\":{\"titleName\":\"%s\"}}}",
            CHH_APPS[i].id, CHH_APPS[i].url, CHH_APPS[i].label);

        wkali_log("[CHH] Installing %s...\n", CHH_APPS[i].label);
        if (wkali_install_app_with_param(CHH_APPS[i].id,
                (const uint8_t *)param, strlen(param)) == 0) {
            wkali_notify("%s installed!", CHH_APPS[i].label);
            ok++;
        } else {
            wkali_notify("%s install failed.", CHH_APPS[i].label);
        }
    }

    if (ok == CHH_APP_COUNT) {
        wkali_notify("CHH installed! Reboot once, then use shortcuts.");
    } else {
        wkali_notify("CHH: %d/%d shortcuts installed.", ok, CHH_APP_COUNT);
    }

    sleep(1);
    return 0;
}
