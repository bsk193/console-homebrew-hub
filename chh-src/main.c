/*
 * chh-installer.elf — Console Homebrew Hub PS5 installer.
 *
 * Architecture copied from ps5-webkit-autoloader by PLK:
 *   1. Install the homescreen shortcut
 *   2. Start a temporary HTTP server on the PS5 (libmicrohttpd)
 *   3. Open the PS5 browser to cache all web content via AppCache
 *   4. Exit — subsequent launches work offline from AppCache
 *
 * The shortcut points to http://127.0.0.1:<port>/ps5/chh.html.
 * 127.0.0.1 always resolves (no NXDOMAIN), so AppCache can serve
 * cached pages even when no server is running.
 */

#include <microhttpd.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/sysctl.h>
#include <unistd.h>

#include "wkali.h"
#include "http_server.h"
#include "ps5_launcher.h"

#define CHH_PORT        18280
#define CHH_THREAD_NAME "chh-inst.elf"
#define CHH_TIMEOUT_SEC 120

static pid_t find_pid(const char *name) {
    int mib[4] = {1, 14, 8, 0};
    pid_t mypid = getpid();
    pid_t pid = -1;
    size_t buf_size;
    uint8_t *buf;

    if (sysctl(mib, 4, 0, &buf_size, 0, 0))
        return -1;
    if (!(buf = malloc(buf_size)))
        return -1;
    if (sysctl(mib, 4, buf, &buf_size, 0, 0)) {
        free(buf);
        return -1;
    }

    for (uint8_t *ptr = buf; ptr < (buf + buf_size);) {
        int ki_structsize = *(int *)ptr;
        pid_t ki_pid = *(pid_t *)&ptr[72];
        char *ki_tdname = (char *)&ptr[447];
        ptr += ki_structsize;
        if (!strcmp(name, ki_tdname) && ki_pid != mypid)
            pid = ki_pid;
    }

    free(buf);
    return pid;
}

extern int sceNetCtlInit();
extern int sceUserServiceInitialize(void *);

int main(void) {
    struct MHD_Daemon *daemon;
    pid_t pid;

    syscall(SYS_thr_set_name, -1, CHH_THREAD_NAME);

    while ((pid = find_pid(CHH_THREAD_NAME)) > 0) {
        if (kill(pid, SIGKILL))
            return EXIT_FAILURE;
        sleep(1);
    }

    wkali_log("[CHH] Console Homebrew Hub installer starting...\n");

    int err;
    if ((err = sceNetCtlInit()) != 0)
        wkali_log("[CHH] sceNetCtlInit: 0x%08X\n", err);

    int user_prio = 256;
    if ((err = sceUserServiceInitialize(&user_prio)) != 0)
        wkali_log("[CHH] sceUserServiceInitialize: 0x%08X\n", err);

    signal(SIGPIPE, SIG_IGN);
    signal(SIGHUP, SIG_IGN);
    signal(SIGTERM, SIG_IGN);

    err = wkali_install_app_if_needed();
    if (err == 0)
        wkali_log("[CHH] Shortcut installed.\n");
    else
        wkali_log("[CHH] Shortcut install returned: %d\n", err);

    wkali_notify("CHH shortcut installed!");

    daemon = MHD_start_daemon(
        MHD_USE_INTERNAL_POLLING_THREAD | MHD_USE_DEBUG,
        CHH_PORT, NULL, NULL, &http_on_request, NULL,
        MHD_OPTION_THREAD_POOL_SIZE, (unsigned int)8,
        MHD_OPTION_END);

    if (!daemon) {
        wkali_log("[CHH] Failed to start HTTP server!\n");
        wkali_notify("CHH: HTTP server failed — offline caching skipped");
        return 0;
    }

    wkali_log("[CHH] Server running on port %d. Waiting before browser...\n",
              CHH_PORT);
    sleep(2);

    char browser_url[128];
    snprintf(browser_url, sizeof(browser_url),
             "http://127.0.0.1:%d/ps5/chh.html", CHH_PORT);
    wkali_log("[CHH] Opening browser: %s\n", browser_url);
    ps5_launch_browser(browser_url);

    int remaining = CHH_TIMEOUT_SEC;
    while (atomic_load(&http_keep_running) && remaining > 0) {
        sleep(1);
        remaining--;
    }

    if (remaining <= 0) {
        wkali_log("[CHH] Timeout waiting for cache. Shutting down.\n");
        wkali_notify("CHH: Cache timeout — shortcut works with PC connected");
    } else {
        wkali_log("[CHH] Caching complete.\n");
        wkali_notify("CHH: Offline cache ready!");
    }

    wkali_log_wakeup();
    usleep(500000);

    if (daemon)
        MHD_stop_daemon(daemon);

    sleep(1);
    return 0;
}
