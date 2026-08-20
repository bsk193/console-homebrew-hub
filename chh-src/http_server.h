#pragma once

#include <microhttpd.h>
#include <stdatomic.h>

extern atomic_int http_keep_running;

enum MHD_Result http_on_request(void *cls, struct MHD_Connection *conn,
                                const char *url, const char *method,
                                const char *version, const char *upload_data,
                                size_t *upload_data_size, void **con_cls);
