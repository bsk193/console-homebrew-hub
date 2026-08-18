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

#define CHH_LOCAL_HOST "192.168.1.139:20181"
#define CHH_LOCAL_BASE "http://" CHH_LOCAL_HOST

static const struct {
    const char *id;
    const char *label;
    const char *url;
} CHH_LOCAL_APPS[] = {
    { "CHHU00002", "CHH UMTX (Local)",    CHH_LOCAL_BASE "/ps5/exploits/umtx/?autoload=pldmgrx.elf"    },
    { "CHHI00002", "CHH IPV6 (Local)",    CHH_LOCAL_BASE "/ps5/exploits/ipv6/?autoload=pldmgrx.elf"    },
    { "CHHS00002", "CHH Slopkit (Local)", CHH_LOCAL_BASE "/ps5/exploits/slopkit/?autoload=pldmgrx.elf" },
};
#define CHH_APP_COUNT (int)(sizeof(CHH_LOCAL_APPS) / sizeof(CHH_LOCAL_APPS[0]))

int main(void)
{
    syscall(SYS_thr_set_name, -1, "chhli.elf");
    int user_prio = 256;
    sceUserServiceInitialize(&user_prio);

    wkali_notify("Installing CHH local shortcuts...");

    int ok = 0;
    for (int i = 0; i < CHH_APP_COUNT; i++) {
        char param[512];
        snprintf(param, sizeof(param),
            "{\"titleId\":\"%s\","
            "\"applicationCategoryType\":65536,"
            "\"deeplinkUri\":\"%s\","
            "\"localizedParameters\":{\"defaultLanguage\":\"en-US\","
            "\"en-US\":{\"titleName\":\"%s\"}}}",
            CHH_LOCAL_APPS[i].id, CHH_LOCAL_APPS[i].url, CHH_LOCAL_APPS[i].label);

        wkali_log("[CHH-L] Installing %s...\n", CHH_LOCAL_APPS[i].label);
        if (wkali_install_app_with_param(CHH_LOCAL_APPS[i].id,
                (const uint8_t *)param, strlen(param)) == 0) {
            wkali_notify("%s installed!", CHH_LOCAL_APPS[i].label);
            ok++;
        } else {
            wkali_notify("%s install failed.", CHH_LOCAL_APPS[i].label);
        }
    }

    if (ok == CHH_APP_COUNT) {
        wkali_notify("CHH Local installed! Shortcuts point to " CHH_LOCAL_HOST);
    } else {
        wkali_notify("CHH Local: %d/%d shortcuts installed.", ok, CHH_APP_COUNT);
    }

    sleep(1);
    return 0;
}
