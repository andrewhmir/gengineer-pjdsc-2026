/*
 * Hinigram universal node (original ESP32, ESP-IDF 5.1 or newer)
 *
 * One firmware for every transmitter. The node ID (1 to 254) is kept in the board's NVS flash instead of being
 * compiled in, so the same image serves any number of chair nodes: the console's Boards panel writes it, then gives
 * the board the next free ID over USB serial, and an ID can be changed later without writing the firmware again.
 * Console commands, one per line at 115,200 baud:
 *
 *     hinigram id <1..254>    store the ID and restart with it
 *     hinigram info           print the start-up lines again
 *
 * Without a stored ID the node takes one from its chip address, so two unconfigured boards rarely clash, and says so.
 *
 * At start-up, and in answer to "hinigram info", it prints one HINIGRAM_TX line for the console: version, ID, whether
 * the ID is stored, addresses, ESP-IDF version, build time and the radio settings, for example
 *
 *     HINIGRAM_TX,version=1.2.0,id=7,id_stored=1,mac=1a:00:00:00:00:07,chip=d0:ef:76:56:e8:68,idf=v5.3.2,
 *     built=Oct 24 2026 18:02:11,channel=6,bandwidth=HT20,phy=MCS0_LGI,send_hz=30,jitter_us=2000,packet=1
 *
 * (one line). The radio settings are one string in the image, s_params, which the release workflow also reads from
 * the built image to record what each version sends.
 *
 * Otherwise as the v1.3.3 bundle's hinigram_node, itself based on Espressif's esp-csi csi_send example (Apache-2.0 /
 * CC0): 20 MHz channel, MCS0, CONFIG_HINIGRAM_SEND_HZ packets a second from 1a:00:00:00:00:<ID>, a steady rate with up
 * to 2 ms of random offset so nodes do not transmit in lockstep, and the packet counter where receivers read it.
 */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_now.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "esp_rom_sys.h"
#include "esp_system.h"
#include "esp_app_desc.h"
#include "esp_idf_version.h"
#include "driver/uart.h"

#define HG_STR_(x) #x
#define HG_STR(x) HG_STR_(x)
#define HG_JITTER_US 2000      /* the most random offset before each packet */
#define HG_PACKET_VERSION 1    /* the layout of hinigram_pkt_t */

/* The radio settings this image sends with. bandwidth and phy name the values wifi_init and espnow_init set. */
static const char s_params[] = "channel=" HG_STR(CONFIG_HINIGRAM_CHANNEL) ",bandwidth=HT20,phy=MCS0_LGI,send_hz="
                               HG_STR(CONFIG_HINIGRAM_SEND_HZ) ",jitter_us=" HG_STR(HG_JITTER_US)
                               ",packet=" HG_STR(HG_PACKET_VERSION);

static const char *TAG = "hinigram_node";
static const uint8_t s_broadcast[6] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
static uint8_t s_mac[6] = {0x1a, 0x00, 0x00, 0x00, 0x00, 0x00};
static uint8_t s_chip_mac[6];
static uint8_t s_id;
static bool s_id_stored;

typedef struct __attribute__((packed)) {
    uint32_t seq;      /* read by the receiver as the CSI_DATA id column */
    uint8_t node;
    uint8_t version;
} hinigram_pkt_t;

/* The stored ID, or one taken from the chip address when none is stored. */
static void load_id(void)
{
    nvs_handle_t h;
    uint8_t id = 0;
    if (nvs_open("hinigram", NVS_READONLY, &h) == ESP_OK) {
        if (nvs_get_u8(h, "node_id", &id) != ESP_OK) {
            id = 0;
        }
        nvs_close(h);
    }
    s_id_stored = id >= 1 && id <= 254;
    s_id = s_id_stored ? id : (uint8_t)(1 + (((s_chip_mac[4] << 8) | s_chip_mac[5]) % 254));
    s_mac[5] = s_id;
}

static esp_err_t store_id(int id)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open("hinigram", NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_set_u8(h, "node_id", (uint8_t)id);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err;
}

/*
 * The lines the console's Identify reads: the node line every Hinigram node prints, this firmware's own, and the
 * HINIGRAM_TX line with everything in one place.
 */
static void announce(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    ESP_LOGW(TAG, "node %d sending %d packets/s on channel %d from " MACSTR,
             s_id, CONFIG_HINIGRAM_SEND_HZ, CONFIG_HINIGRAM_CHANNEL, MAC2STR(s_mac));
    ESP_LOGW(TAG, "universal v%s, chip " MACSTR ", id %s, IDF %s", app->version, MAC2STR(s_chip_mac),
             s_id_stored ? "stored" : "from the chip address (set one with: hinigram id N)", esp_get_idf_version());
    printf("HINIGRAM_TX,version=%s,id=%d,id_stored=%d,mac=" MACSTR ",chip=" MACSTR ",idf=%s,built=%s %s,%s\n",
           app->version, s_id, s_id_stored ? 1 : 0, MAC2STR(s_mac), MAC2STR(s_chip_mac), esp_get_idf_version(),
           app->date, app->time, s_params);
    fflush(stdout);
}

/* Reads "hinigram id N" and "hinigram info" from the USB serial console. */
static void console_task(void *arg)
{
    char line[64];
    size_t n = 0;
    for (;;) {
        uint8_t c;
        if (uart_read_bytes(UART_NUM_0, &c, 1, portMAX_DELAY) != 1) {
            continue;
        }
        if (c != '\r' && c != '\n') {
            if (n < sizeof(line) - 1) {
                line[n++] = (char)c;
            }
            continue;
        }
        line[n] = 0;
        n = 0;
        int id;
        if (sscanf(line, " hinigram id %d", &id) == 1) {
            if (id < 1 || id > 254) {
                ESP_LOGW(TAG, "id %d refused: use 1 to 254", id);
            } else if (store_id(id) == ESP_OK) {
                ESP_LOGW(TAG, "id set to %d; restarting", id);
                vTaskDelay(pdMS_TO_TICKS(100));
                esp_restart();
            } else {
                ESP_LOGW(TAG, "id %d could not be stored", id);
            }
        } else if (strstr(line, "hinigram info")) {
            announce();
        }
    }
}

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_init());
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    /* The node's address is set while the interface is still disabled: esp_wifi_set_mac() is documented for that
       state, and the "from 1a:00:00:00:00:<ID>" start-up line is what the console matches a board on. */
    ESP_ERROR_CHECK(esp_wifi_set_mac(WIFI_IF_STA, s_mac));
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_HINIGRAM_CHANNEL, WIFI_SECOND_CHAN_NONE));
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
    ESP_ERROR_CHECK(esp_read_mac(s_chip_mac, ESP_MAC_WIFI_STA)); /* the chip's own address, before it is replaced */
    load_id();
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0));
    xTaskCreate(console_task, "hinigram_console", 3072, NULL, 3, NULL);
    wifi_init();
    espnow_init();
    announce();

    hinigram_pkt_t pkt = {.seq = 0, .node = s_id, .version = HG_PACKET_VERSION};
    const TickType_t period = pdMS_TO_TICKS(1000 / CONFIG_HINIGRAM_SEND_HZ);
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        esp_rom_delay_us(esp_random() % HG_JITTER_US);   /* random offset keeps neighbouring nodes out of lockstep */
        esp_err_t err = esp_now_send(s_broadcast, (const uint8_t *)&pkt, sizeof(pkt));
        if (err != ESP_OK && pkt.seq % 300 == 0) {
            ESP_LOGW(TAG, "send failed: %s", esp_err_to_name(err));
        }
        pkt.seq++;
        vTaskDelayUntil(&last, period > 0 ? period : 1);
    }
}
