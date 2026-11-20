/* ESP-IDF source-only example: hashes a declared DEMO payload, DOES NOT sign.
 * Firmware compilation and physical-hardware tests are pending.
 */
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "mbedtls/sha256.h"

static const char *TAG = "INNOVULIS";

void app_main(void) {
    const char *payload = "{\"action\":\"READ_METER\",\"unit\":\"DEMO_UNITS\",\"value\":250}";
    unsigned char digest[32];
    int ret = mbedtls_sha256((const unsigned char *)payload, strlen(payload), digest, 0);
    if (ret != 0) {
        ESP_LOGE(TAG, "SHA256 calculation failed: %d", ret);
        return;
    }
    char hex[65];
    for (size_t i = 0; i < 32; ++i) {
        (void)snprintf(hex + 2 * i, sizeof(hex) - 2 * i, "%02x", digest[i]);
    }
    hex[64] = '\0';
    ESP_LOGI(TAG, "SYNTHETIC_PAYLOAD_SHA256=%s", hex);
    ESP_LOGI(TAG, "UPTIME_US=%" PRId64, esp_timer_get_time());
    ESP_LOGW(TAG, "UNSIGNED_DEVELOPMENT_ONLY: No SE050/HSM attestation or ESP-NOW transport");
}
