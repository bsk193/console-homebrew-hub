#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <microhttpd.h>

#include "app_installer.h"
#include "notification.h"
#include "wkali.h"
#include "chh_file_registry.h"
#include "chh_proxy_paths.h"

/* Defined in app_installer_chh_patch.c (appended to app_installer.c) */
int wkali_install_app_with_param(const char *title_id,
    const uint8_t *param_json, size_t param_json_size);

/* Raw DEFLATE decompressor from inflate.c in autoloader-x */
extern int puff(unsigned char *dest, unsigned long *destlen,
                const unsigned char *source, unsigned long *srclen);

extern int sceUserServiceInitialize(void *);

#define CHH_PORT         20181
#define CHH_PC_PORT      6969
#define CHH_SHORTCUT_ID  "CHHM00001"
#define CHH_SHORTCUT_URL "http://127.0.0.1:20181/ps5/?autoload=pldmgrx.elf"
#define CHH_LABEL        "CHH"

static volatile int g_install_done = 0;

/* PC's IP address, read from /etc/resolv.conf at startup.
   Large exploit core files and pldmgrx.elf are not embedded in this ELF —
   they are proxied from the PC during AppCache installation. */
static char g_pc_ip[INET_ADDRSTRLEN] = "";

/* Which exploit triggered the install flow (set from ?exploit=X query param).
   Used to build a per-exploit AppCache manifest so only ~25 files are
   downloaded instead of all 105, preventing background memory pressure. */
static char g_exploit[32] = "";

/* ── PC IP detection ──────────────────────────────────────────────────────── */

static void detect_pc_ip(void)
{
    static const char *paths[] = {
        "/etc/resolv.conf",
        "/system/etc/resolv.conf",
        "/system/priv/etc/resolv.conf",
        NULL
    };
    for (int i = 0; paths[i]; i++) {
        FILE *f = fopen(paths[i], "r");
        if (!f) continue;
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            if (sscanf(line, "nameserver %45s", g_pc_ip) == 1 && g_pc_ip[0])
                break;
        }
        fclose(f);
        if (g_pc_ip[0]) {
            wkali_log("[CHH] PC IP: %s (resolv.conf)\n", g_pc_ip);
            return;
        }
    }
    wkali_log("[CHH] WARNING: could not detect PC IP — large files will 404\n");
}

/* ── Minimal memmem (avoids libc dependency) ─────────────────────────────── */

static void *chh_memmem(const void *hay, size_t hlen,
                         const void *ndl, size_t nlen)
{
    if (nlen == 0) return (void *)hay;
    if (hlen < nlen) return NULL;
    const char *h = (const char *)hay;
    const char *n = (const char *)ndl;
    for (size_t i = 0; i <= hlen - nlen; i++) {
        if (h[i] == n[0] && memcmp(h + i, n, nlen) == 0)
            return (void *)(h + i);
    }
    return NULL;
}

/* ── HTTP proxy to PC:6969 ───────────────────────────────────────────────── */

static enum MHD_Result proxy_file(struct MHD_Connection *conn, const char *path)
{
    static const char err_no_pc[] = "PC not detected";
    static const char err_connect[] = "Could not connect to PC";

    if (!g_pc_ip[0]) {
        struct MHD_Response *r = MHD_create_response_from_buffer(
            sizeof(err_no_pc) - 1, (void *)err_no_pc, MHD_RESPMEM_PERSISTENT);
        enum MHD_Result res = MHD_queue_response(conn, MHD_HTTP_BAD_GATEWAY, r);
        MHD_destroy_response(r);
        return res;
    }

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return MHD_NO;

    /* 10-second timeout so a missing PC doesn't hang the MHD thread */
    struct timeval tv = {10, 0};
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    sa.sin_port   = htons(CHH_PC_PORT);
    if (inet_pton(AF_INET, g_pc_ip, &sa.sin_addr) <= 0) {
        close(sock); return MHD_NO;
    }

    if (connect(sock, (struct sockaddr *)&sa, sizeof(sa)) != 0) {
        close(sock);
        wkali_log("[CHH] proxy: connect to %s:%d failed\n", g_pc_ip, CHH_PC_PORT);
        struct MHD_Response *r = MHD_create_response_from_buffer(
            sizeof(err_connect) - 1, (void *)err_connect, MHD_RESPMEM_PERSISTENT);
        enum MHD_Result res = MHD_queue_response(conn, MHD_HTTP_BAD_GATEWAY, r);
        MHD_destroy_response(r);
        return res;
    }

    /* Send HTTP/1.0 GET — server closes connection after response */
    char req[1024];
    int rlen = snprintf(req, sizeof(req),
        "GET %s HTTP/1.0\r\nHost: %s:%d\r\nConnection: close\r\n\r\n",
        path, g_pc_ip, CHH_PC_PORT);
    if (write(sock, req, (size_t)rlen) != rlen) {
        close(sock); return MHD_NO;
    }

    /* Read entire response into a growing buffer */
    size_t cap = 65536, used = 0;
    char *rbuf = malloc(cap);
    if (!rbuf) { close(sock); return MHD_NO; }

    ssize_t n;
    while ((n = read(sock, rbuf + used, cap - used)) > 0) {
        used += (size_t)n;
        if (used >= cap - 4096) {
            size_t newcap = cap * 2;
            char *tmp = realloc(rbuf, newcap);
            if (!tmp) { free(rbuf); close(sock); return MHD_NO; }
            rbuf = tmp;
            cap  = newcap;
        }
    }
    close(sock);

    /* Locate end of HTTP headers */
    char *body = (char *)chh_memmem(rbuf, used, "\r\n\r\n", 4);
    if (!body) { free(rbuf); return MHD_NO; }
    body += 4;

    /* Parse HTTP status code */
    unsigned int status_code = MHD_HTTP_OK;
    sscanf(rbuf, "HTTP/1.%*u %u", &status_code);

    /* Extract Content-Type header (case-insensitive prefix scan) */
    char ct[256] = "application/octet-stream";
    size_t hdr_len = (size_t)(body - rbuf);
    const char *ct_hdr = (const char *)chh_memmem(rbuf, hdr_len,
                                                    "\r\nContent-Type:", 15);
    if (!ct_hdr) ct_hdr = (const char *)chh_memmem(rbuf, hdr_len,
                                                     "\r\ncontent-type:", 15);
    if (ct_hdr) {
        ct_hdr += 15;
        while (*ct_hdr == ' ') ct_hdr++;
        size_t ci = 0;
        while (ci < sizeof(ct) - 1 && *ct_hdr && *ct_hdr != '\r' && *ct_hdr != '\n')
            ct[ci++] = *ct_hdr++;
        ct[ci] = '\0';
    }

    /* Copy body out (rbuf must be freed; body_copy passed to MHD_RESPMEM_MUST_FREE) */
    size_t body_len = used - (size_t)(body - rbuf);
    char *body_copy = malloc(body_len ? body_len : 1);
    if (!body_copy) { free(rbuf); return MHD_NO; }
    if (body_len) memcpy(body_copy, body, body_len);
    free(rbuf);

    struct MHD_Response *resp = MHD_create_response_from_buffer(
        body_len, body_copy, MHD_RESPMEM_MUST_FREE);
    if (!resp) { free(body_copy); return MHD_NO; }
    MHD_add_response_header(resp, "Content-Type", ct);
    MHD_add_response_header(resp, "Cache-Control", "no-cache");
    enum MHD_Result r = MHD_queue_response(conn, (unsigned int)status_code, resp);
    MHD_destroy_response(resp);
    return r;
}

/* ── Dynamic AppCache manifest ───────────────────────────────────────────── */

static enum MHD_Result serve_dynamic_manifest(struct MHD_Connection *conn)
{
    /* Choose per-exploit proxy path list; fall back to slopkit if unknown */
    const char * const *proxy_paths;
    if (strcmp(g_exploit, "umtx") == 0)
        proxy_paths = CHH_PROXY_UMTX;
    else if (strcmp(g_exploit, "ipv6") == 0)
        proxy_paths = CHH_PROXY_IPV6;
    else
        proxy_paths = CHH_PROXY_SLOPKIT;

    /* Estimate manifest size: header + one line per embedded file + proxy files */
    size_t cap = 4096 + CHH_FILE_COUNT * 80;
    for (const char * const *p = proxy_paths; *p; p++)
        cap += strlen(*p) + 2;
    char *buf = malloc(cap);
    if (!buf) return MHD_NO;

    size_t n = 0;
    n += (size_t)snprintf(buf + n, cap - n,
        "CACHE MANIFEST\n"
        "# CHH v1 exploit=%s\n"
        "\nCACHE:\n",
        g_exploit);

    /* Embedded files (served directly from the ELF, no PC needed) */
    for (size_t i = 0; i < CHH_FILE_COUNT; i++)
        n += (size_t)snprintf(buf + n, cap - n, "%s\n", CHH_FILES[i].path);

    /* Exploit-specific proxy files (fetched from PC:6969 by the ELF) */
    for (const char * const *p = proxy_paths; *p; p++)
        n += (size_t)snprintf(buf + n, cap - n, "%s\n", *p);

    n += (size_t)snprintf(buf + n, cap - n, "\nNETWORK:\n*\n");

    struct MHD_Response *resp = MHD_create_response_from_buffer(
        n, buf, MHD_RESPMEM_MUST_FREE);
    if (!resp) { free(buf); return MHD_NO; }
    MHD_add_response_header(resp, "Content-Type", "text/cache-manifest");
    MHD_add_response_header(resp, "Cache-Control", "no-store");
    enum MHD_Result r = MHD_queue_response(conn, MHD_HTTP_OK, resp);
    MHD_destroy_response(resp);
    return r;
}

/* ── Embedded file serving ───────────────────────────────────────────────── */

static enum MHD_Result serve_file(struct MHD_Connection *conn, const ChhFile *f)
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
    enum MHD_Result r = MHD_queue_response(conn, MHD_HTTP_OK, resp);
    MHD_destroy_response(resp);
    return r;
}

static enum MHD_Result request_cb(void *cls, struct MHD_Connection *conn,
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
        enum MHD_Result r = MHD_queue_response(conn, MHD_HTTP_OK, resp);
        MHD_destroy_response(resp);
        return r;
    }

    /* Strip query string for registry lookup; extract exploit= param if present */
    char path[512];
    strncpy(path, url, sizeof(path) - 1);
    path[sizeof(path) - 1] = '\0';
    char *q = strchr(path, '?');
    if (q) *q = '\0';

    /* When the installer page is requested with ?exploit=X, record which exploit
       triggered this install so we can serve a per-exploit AppCache manifest. */
    if (strcmp(path, "/installer/index.html") == 0) {
        const char *ex = MHD_lookup_connection_value(conn, MHD_GET_ARGUMENT_KIND, "exploit");
        if (ex && (strcmp(ex, "slopkit") == 0 ||
                   strcmp(ex, "umtx")    == 0 ||
                   strcmp(ex, "ipv6")    == 0)) {
            strncpy(g_exploit, ex, sizeof(g_exploit) - 1);
            g_exploit[sizeof(g_exploit) - 1] = '\0';
            wkali_log("[CHH] install mode: exploit=%s\n", g_exploit);
        }
    }

    /* Dynamic AppCache manifest — generated per exploit to limit download size */
    if (strcmp(path, "/installer/cache.appcache") == 0)
        return serve_dynamic_manifest(conn);

    /* Exact path match in embedded registry */
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

    /* Not in embedded registry: proxy to PC (for exploit cores, pldmgrx.elf, etc.) */
    return proxy_file(conn, path);
}

int main(void)
{
    syscall(SYS_thr_set_name, -1, "chhi.elf");
    int user_prio = 256;
    sceUserServiceInitialize(&user_prio);

    /* Detect the PC's IP so we can proxy large files during AppCache install */
    detect_pc_ip();

    wkali_notify("CHH: Caching exploit for offline use...");

    /* Bind to loopback only — AppCache fetches from 127.0.0.1:20181 */
    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family      = AF_INET;
    sa.sin_port        = htons(CHH_PORT);
    sa.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    struct MHD_Daemon *mhd = MHD_start_daemon(
        MHD_USE_THREAD_PER_CONNECTION,
        CHH_PORT, NULL, NULL, request_cb, NULL,
        MHD_OPTION_SOCK_ADDR, (struct sockaddr *)&sa,
        MHD_OPTION_END);

    if (!mhd) {
        wkali_notify("CHH: Failed to start HTTP server.");
        return 1;
    }

    wkali_log("[CHH] Serving %zu embedded files on 127.0.0.1:%d\n",
              CHH_FILE_COUNT, CHH_PORT);
    wkali_log("[CHH] Large files proxied from PC %s:%d\n",
              g_pc_ip[0] ? g_pc_ip : "(unknown)", CHH_PC_PORT);
    wkali_log("[CHH] Waiting for browser AppCache to finish...\n");

    /* The exploit page JS (warmShortcutCache) navigates the browser to
       http://127.0.0.1:20181/installer/index.html which triggers AppCache
       download of all files (embedded ones served locally, large ones proxied
       from the PC).  When done, that page calls /install. */
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
