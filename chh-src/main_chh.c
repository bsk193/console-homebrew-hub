#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <microhttpd.h>

#include "app_installer.h"
#include "notification.h"
#include "wkali.h"
#include "chh_file_registry.h"

/* Defined in app_installer_chh_patch.c (appended to app_installer.c) */
int wkali_install_app_with_param(const char *title_id,
    const uint8_t *param_json, size_t param_json_size);

/* Raw DEFLATE decompressor from inflate.c in autoloader-x */
extern int puff(unsigned char *dest, unsigned long *destlen,
                const unsigned char *source, unsigned long *srclen);

extern int sceUserServiceInitialize(void *);

#define CHH_PORT         20181
#define CHH_SHORTCUT_ID  "CHHM00001"
#define CHH_SHORTCUT_URL "http://127.0.0.1:20181/ps5/?autoload=pldmgrx.elf"
#define CHH_LABEL        "CHH"

static volatile int g_install_done = 0;

static MHD_Result serve_file(struct MHD_Connection *conn, const ChhFile *f)
{
    unsigned long dlen = f->original_size;
    unsigned long slen = f->compressed_size;
    uint8_t *buf = malloc(dlen);
    if (!buf)
        return MHD_NO;

    if (puff(buf, &dlen, f->data, &slen) != 0) {
        free(buf);
        return MHD_NO;
    }

    struct MHD_Response *resp = MHD_create_response_from_buffer(
        dlen, buf, MHD_RESPMEM_MUST_FREE);
    if (!resp) {
        free(buf);
        return MHD_NO;
    }
    MHD_add_response_header(resp, "Content-Type", f->content_type);
    MHD_add_response_header(resp, "Cache-Control", "no-cache");
    MHD_Result r = MHD_queue_response(conn, MHD_HTTP_OK, resp);
    MHD_destroy_response(resp);
    return r;
}

static MHD_Result request_cb(void *cls, struct MHD_Connection *conn,
    const char *url, const char *method,
    const char *version, const char *upload_data,
    size_t *upload_data_size, void **con_cls)
{
    (void)cls; (void)version; (void)upload_data;
    (void)upload_data_size; (void)con_cls;

    if (strcmp(method, "GET") != 0 && strcmp(method, "HEAD") != 0)
        return MHD_NO;

    /* /install: AppCache has finished downloading everything */
    if (strcmp(url, "/install") == 0) {
        g_install_done = 1;
        static const char ok[] = "OK";
        struct MHD_Response *resp = MHD_create_response_from_buffer(
            2, (void *)ok, MHD_RESPMEM_PERSISTENT);
        MHD_Result r = MHD_queue_response(conn, MHD_HTTP_OK, resp);
        MHD_destroy_response(resp);
        return r;
    }

    /* Strip query string for registry lookup */
    char path[512];
    strncpy(path, url, sizeof(path) - 1);
    path[sizeof(path) - 1] = '\0';
    char *q = strchr(path, '?');
    if (q) *q = '\0';

    /* Exact path match */
    for (size_t i = 0; i < CHH_FILE_COUNT; i++) {
        if (strcmp(CHH_FILES[i].path, path) == 0)
            return serve_file(conn, &CHH_FILES[i]);
    }

    /* Directory index fallback: /foo/ -> /foo/index.html */
    size_t plen = strlen(path);
    if (plen > 0 && path[plen - 1] == '/') {
        char idx[520];
        snprintf(idx, sizeof(idx), "%sindex.html", path);
        for (size_t i = 0; i < CHH_FILE_COUNT; i++) {
            if (strcmp(CHH_FILES[i].path, idx) == 0)
                return serve_file(conn, &CHH_FILES[i]);
        }
    }

    static const char nf[] = "Not Found";
    struct MHD_Response *resp = MHD_create_response_from_buffer(
        9, (void *)nf, MHD_RESPMEM_PERSISTENT);
    MHD_Result r = MHD_queue_response(conn, MHD_HTTP_NOT_FOUND, resp);
    MHD_destroy_response(resp);
    return r;
}

int main(void)
{
    syscall(SYS_thr_set_name, -1, "chhi.elf");
    int user_prio = 256;
    sceUserServiceInitialize(&user_prio);

    wkali_notify("CHH: Caching exploit for offline use...");

    /* Bind to loopback only — AppCache fetches from 127.0.0.1:20181 */
    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family      = AF_INET;
    sa.sin_port        = htons(CHH_PORT);
    sa.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    struct MHD_Daemon *mhd = MHD_start_daemon(
        MHD_USE_THREAD_PER_CONNECTION | MHD_USE_IPv4,
        CHH_PORT, NULL, NULL, request_cb, NULL,
        MHD_OPTION_SOCK_ADDR, (struct sockaddr *)&sa,
        MHD_OPTION_END);

    if (!mhd) {
        wkali_notify("CHH: Failed to start HTTP server.");
        return 1;
    }

    wkali_log("[CHH] Serving %zu files on 127.0.0.1:%d\n", CHH_FILE_COUNT, CHH_PORT);
    wkali_log("[CHH] Waiting for browser AppCache to finish...\n");

    /* The exploit page JS (warmShortcutCache) navigates the browser to
       http://127.0.0.1:20181/installer/index.html which triggers AppCache
       download of all embedded files.  When done, that page calls /install. */
    while (!g_install_done)
        usleep(200000);

    wkali_log("[CHH] AppCache done — installing shortcut\n");

    char param[512];
    snprintf(param, sizeof(param),
        "{\"titleId\":\"%s\","
        "\"applicationCategoryType\":65536,"
        "\"deeplinkUri\":\"%s\","
        "\"localizedParameters\":{\"defaultLanguage\":\"en-US\","
        "\"en-US\":{\"titleName\":\"%s\"}}}",
        CHH_SHORTCUT_ID, CHH_SHORTCUT_URL, CHH_LABEL);

    if (wkali_install_app_with_param(CHH_SHORTCUT_ID,
            (const uint8_t *)param, strlen(param)) == 0) {
        wkali_notify("CHH ready! Shortcut works offline — no PC needed.");
    } else {
        wkali_notify("CHH shortcut install failed.");
    }

    sleep(2);
    MHD_stop_daemon(mhd);
    return 0;
}
