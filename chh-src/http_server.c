/*
 * CHH HTTP Server — serves embedded web files from the generated file
 * registry and handles /install (installs the homescreen shortcut once
 * AppCache caching is complete, then shuts the server down).
 *
 * Based on ps5-webkit-autoloader's http_server.c by PLK.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <microhttpd.h>

#include "wkali.h"
#include "http_server.h"
#include "file_registry.h"
#include "inflate.h"
#include "app_installer.h"

#define CORS_ORIGIN "*"
#define CHH_VERSION "1.0.0"

atomic_int http_keep_running = 1;

static void add_cors_headers(struct MHD_Response *resp) {
    MHD_add_response_header(resp, "Access-Control-Allow-Origin", CORS_ORIGIN);
}

enum MHD_Result http_on_request(void *cls, struct MHD_Connection *conn,
                                const char *url, const char *method,
                                const char *version, const char *upload_data,
                                size_t *upload_data_size, void **con_cls) {
    (void)cls;
    (void)version;
    (void)upload_data;
    (void)upload_data_size;

    if (strcmp(method, "OPTIONS") == 0) {
        struct MHD_Response *resp =
            MHD_create_response_from_buffer(0, NULL, MHD_RESPMEM_PERSISTENT);
        add_cors_headers(resp);
        MHD_add_response_header(resp, "Access-Control-Allow-Methods",
                                "GET, OPTIONS");
        MHD_add_response_header(resp, "Access-Control-Allow-Headers",
                                "Content-Type");
        enum MHD_Result ret = MHD_queue_response(conn, MHD_HTTP_OK, resp);
        MHD_destroy_response(resp);
        return ret;
    }

    if (*con_cls == NULL) {
        *con_cls = (void *)1;
        return MHD_YES;
    }

    struct MHD_Response *resp = NULL;
    int http_status = MHD_HTTP_OK;

    if (strcmp(url, "/install") == 0) {
        int err = wkali_install_app_if_needed();
        if (err == 0) {
            wkali_log("[CHH] Shortcut installed. Stopping server...\n");
            resp = MHD_create_response_from_buffer(2, (void *)"OK",
                                                   MHD_RESPMEM_PERSISTENT);
            MHD_add_response_header(resp, "Content-Type", "text/plain");
            atomic_store(&http_keep_running, 0);
        } else {
            wkali_log("[CHH] Shortcut install failed (%d). Staying up.\n", err);
            const char *fail = "Install failed";
            resp = MHD_create_response_from_buffer(strlen(fail), (void *)fail,
                                                   MHD_RESPMEM_PERSISTENT);
            MHD_add_response_header(resp, "Content-Type", "text/plain");
            http_status = MHD_HTTP_INTERNAL_SERVER_ERROR;
        }
    } else if (strcmp(url, "/version") == 0) {
        resp = MHD_create_response_from_buffer(strlen(CHH_VERSION),
                                               (void *)CHH_VERSION,
                                               MHD_RESPMEM_PERSISTENT);
        MHD_add_response_header(resp, "Content-Type", "text/plain");
    } else {
        const FileEntry *entry = file_registry_find(url);
        if (entry) {
            void *payload = (void *)entry->data;
            size_t payload_size = entry->size;
            enum MHD_ResponseMemoryMode mem_mode = MHD_RESPMEM_PERSISTENT;

            if (entry->compressed) {
                unsigned char *decompressed = malloc(entry->orig_size);
                if (!decompressed) {
                    const char *oom = "503 Out of Memory\n";
                    resp = MHD_create_response_from_buffer(strlen(oom),
                        (void *)oom, MHD_RESPMEM_PERSISTENT);
                    MHD_add_response_header(resp, "Content-Type", "text/plain");
                    http_status = MHD_HTTP_SERVICE_UNAVAILABLE;
                    add_cors_headers(resp);
                    enum MHD_Result ret = MHD_queue_response(conn, http_status, resp);
                    MHD_destroy_response(resp);
                    return ret;
                }
                unsigned long destlen = entry->orig_size;
                unsigned long sourcelen = entry->size;
                int err = puff(decompressed, &destlen, entry->data, &sourcelen);
                if (err != 0) {
                    free(decompressed);
                    const char *bad = "500 Inflate Error\n";
                    resp = MHD_create_response_from_buffer(strlen(bad),
                        (void *)bad, MHD_RESPMEM_PERSISTENT);
                    MHD_add_response_header(resp, "Content-Type", "text/plain");
                    http_status = MHD_HTTP_INTERNAL_SERVER_ERROR;
                    add_cors_headers(resp);
                    enum MHD_Result ret = MHD_queue_response(conn, http_status, resp);
                    MHD_destroy_response(resp);
                    return ret;
                }
                payload = decompressed;
                payload_size = destlen;
                mem_mode = MHD_RESPMEM_MUST_FREE;
            }

            resp = MHD_create_response_from_buffer(payload_size, payload,
                                                   mem_mode);
            MHD_add_response_header(resp, "Content-Type", entry->content_type);
            if (strcmp(url, "/cache.appcache") == 0 ||
                strstr(entry->content_type, "text/html") != NULL) {
                MHD_add_response_header(resp, "Cache-Control",
                                        "no-cache, must-revalidate");
            }
        } else {
            const char *not_found = "404 Not Found\n";
            resp = MHD_create_response_from_buffer(strlen(not_found),
                (void *)not_found, MHD_RESPMEM_PERSISTENT);
            MHD_add_response_header(resp, "Content-Type", "text/plain");
            http_status = MHD_HTTP_NOT_FOUND;
        }
    }

    if (!resp)
        return MHD_NO;

    add_cors_headers(resp);
    enum MHD_Result ret = MHD_queue_response(conn, http_status, resp);
    MHD_destroy_response(resp);
    return ret;
}
