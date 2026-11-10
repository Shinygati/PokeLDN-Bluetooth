#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
    uint8_t generation, language;
    uint16_t received;
    uint8_t fragments[10][112];
} ds_upload_t;
/* 0 = accepted, -1 = invalid, 1 = stop, 2 = start complete upload. */
int ds_receive(ds_upload_t *state, unsigned which, const uint8_t *data, size_t length);
size_t ds_image(const ds_upload_t *state, uint8_t *out, size_t capacity);
