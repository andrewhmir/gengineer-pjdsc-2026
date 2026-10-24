/*
 * Hinigram chair node (original ESP32, ESP-IDF 5.1 or newer)
 *
 * Sits on a chair's backrest at chest height and broadcasts a short ESP-NOW packet CONFIG_HINIGRAM_SEND_HZ times a
 * second from the address 1a:00:00:00:00:<node ID>. A corner receiver turns every packet into one CSI_DATA line, so
 * the link from this node to the receiver passes through the person sitting in front of it.
 *
 * Based on Espressif's esp-csi csi_send example (Apache-2.0 / CC0). Changes: 20 MHz channel to match the recordings
 * the pipeline was validated on, a per-node address, a steady rate with a small random offset so many nodes do not
 * transmit in lockstep, and the node ID in every packet.
 */
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_now.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "esp_rom_sys.h"
#include "esp_idf_version.h"

static const char *TAG = "hinigram_node";
static uint8_t s_mac[6] = {0x1a, 0x00, 0x00, 0x00, 0x00, CONFIG_HINIGRAM_NODE_ID};
static const uint8_t s_broadcast[6] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff};

typedef struct __attribute__((packed)) {
    uint32_t seq;      /* read by the receiver as the CSI_DATA id column */
    uint8_t node;
    uint8_t version;
} hinigram_pkt_t;

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_init());
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_HINIGRAM_CHANNEL, WIFI_SECOND_CHAN_NONE));
    ESP_ERROR_CHECK(esp_wifi_set_mac(WIFI_IF_STA, s_mac));
}

static void espnow_init(void)
{
    ESP_ERROR_CHECK(esp_now_init());
    esp_now_peer_info_t peer = {
        .channel = CONFIG_HINIGRAM_CHANNEL,
        .ifidx = WIFI_IF_STA,
        .encrypt = false,
    };
    memcpy(peer.peer_addr, s_broadcast, 6);
    ESP_ERROR_CHECK(esp_now_add_peer(&peer));
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 1, 0)
    esp_now_rate_config_t rate = {
        .phymode = WIFI_PHY_MODE_HT20,
        .rate = WIFI_PHY_RATE_MCS0_LGI,
        .ersu = false,
        .dcm = false,
    };
    ESP_ERROR_CHECK(esp_now_set_peer_rate_config(peer.peer_addr, &rate));
#else
    ESP_ERROR_CHECK(esp_wifi_config_espnow_rate(WIFI_IF_STA, WIFI_PHY_RATE_MCS0_LGI));
#endif
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    wifi_init();
    espnow_init();
    ESP_LOGW(TAG, "node %d sending %d packets/s on channel %d from " MACSTR,
             CONFIG_HINIGRAM_NODE_ID, CONFIG_HINIGRAM_SEND_HZ, CONFIG_HINIGRAM_CHANNEL, MAC2STR(s_mac));

    hinigram_pkt_t pkt = {.seq = 0, .node = CONFIG_HINIGRAM_NODE_ID, .version = 1};
    const TickType_t period = pdMS_TO_TICKS(1000 / CONFIG_HINIGRAM_SEND_HZ);
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        esp_rom_delay_us(esp_random() % 2000);   /* up to 2 ms of jitter keeps neighbouring nodes out of lockstep */
        esp_err_t err = esp_now_send(s_broadcast, (const uint8_t *)&pkt, sizeof(pkt));
        if (err != ESP_OK && pkt.seq % 300 == 0) {
            ESP_LOGW(TAG, "send failed: %s", esp_err_to_name(err));
        }
        pkt.seq++;
        vTaskDelayUntil(&last, period > 0 ? period : 1);
    }
}
