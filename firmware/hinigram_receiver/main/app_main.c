/*
 * Hinigram corner receiver (original ESP32, ESP-IDF 5.1 or newer)
 *
 * Mounted in a corner of the waiting area at about chest height. It captures the channel state information (CSI) of
 * every packet from the chair nodes 1a:00:00:00:00:<ID> whose ID lies in [CONFIG_HINIGRAM_NODE_FIRST,
 * CONFIG_HINIGRAM_NODE_LAST] and prints one CSI_DATA line per packet over USB serial, in the exact column layout of the
 * recordings the Hinigram pipeline was validated on (Espressif's esp-csi csi_recv format for the original ESP32).
 *
 * Differences from the esp-csi example (Apache-2.0 / CC0):
 *  - the Wi-Fi callback only copies the packet into a queue; a separate task formats and writes the lines through
 *    the UART driver, so a busy serial link drops whole lines (counted) instead of stalling Wi-Fi reception;
 *  - a HINIGRAM_RX status line at start-up and every 60 s records the chip model, revision, IDF version, channel,
 *    the node range and how many lines were logged and dropped (the pipeline and the board ignore these lines);
 *  - 20 MHz channel, any node ID in the configured range.
 * The original ESP32 cannot lock or report its receive gain, so the gain steps stay in the data; the pipeline removes
 * them packet by packet.
 */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_mac.h"
#include "esp_chip_info.h"
#include "esp_system.h"
#include "esp_idf_version.h"
#include "driver/uart.h"

#define HG_UART CONFIG_ESP_CONSOLE_UART_NUM
#define CSI_MAX_LEN 384
#define QUEUE_DEPTH 64

typedef struct {
    wifi_pkt_rx_ctrl_t rx;
    uint8_t mac[6];
    uint32_t seq;
    uint16_t len;
    uint8_t first_word_invalid;
    int8_t buf[CSI_MAX_LEN];
} csi_rec_t;

static QueueHandle_t s_queue;
static volatile uint32_t s_logged, s_dropped;
static const uint8_t s_prefix[5] = {0x1a, 0x00, 0x00, 0x00, 0x00};

static void csi_cb(void *ctx, wifi_csi_info_t *info)
{
    if (!info || !info->buf || memcmp(info->mac, s_prefix, 5) != 0) {
        return;
    }
    const uint8_t node = info->mac[5];
    if (node < CONFIG_HINIGRAM_NODE_FIRST || node > CONFIG_HINIGRAM_NODE_LAST) {
        return;
    }
    csi_rec_t rec;
    rec.rx = info->rx_ctrl;
    memcpy(rec.mac, info->mac, 6);
    rec.seq = 0;
    if (info->payload && info->payload_len >= 19) {
        memcpy(&rec.seq, info->payload + 15, sizeof(rec.seq));   /* the node's packet counter, after the ESP-NOW header */
    }
    rec.len = info->len > CSI_MAX_LEN ? CSI_MAX_LEN : info->len;
    rec.first_word_invalid = info->first_word_invalid;
    memcpy(rec.buf, info->buf, rec.len);
    if (xQueueSend(s_queue, &rec, 0) != pdTRUE) {
        s_dropped++;
    }
}

static char *put_int(char *p, int v)
{
    char tmp[12];
    int n = 0;
    unsigned u = v < 0 ? (unsigned)(-v) : (unsigned)v;
    if (v < 0) {
        *p++ = '-';
    }
    do {
        tmp[n++] = (char)('0' + u % 10);
        u /= 10;
    } while (u);
    while (n) {
        *p++ = tmp[--n];
    }
    return p;
}

static void printer_task(void *arg)
{
    static char line[2600];
    csi_rec_t rec;
    for (;;) {
        if (xQueueReceive(s_queue, &rec, portMAX_DELAY) != pdTRUE) {
            continue;
        }
        const wifi_pkt_rx_ctrl_t *r = &rec.rx;
        int n = snprintf(line, sizeof(line),
                         "CSI_DATA,%lu," MACSTR ",%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%lu,%d,%d,%d,%d,%d,\"[",
                         (unsigned long)rec.seq, MAC2STR(rec.mac), r->rssi, r->rate, r->sig_mode, r->mcs, r->cwb,
                         r->smoothing, r->not_sounding, r->aggregation, r->stbc, r->fec_coding, r->sgi, r->noise_floor,
                         r->ampdu_cnt, r->channel, r->secondary_channel, (unsigned long)r->timestamp, r->ant,
                         r->sig_len, r->sig_mode, rec.len, rec.first_word_invalid);
        if (n <= 0 || n >= (int)sizeof(line) - 8) {
            continue;
        }
        char *p = line + n;
        for (int i = 0; i < rec.len; i++) {
            if (i) {
                *p++ = ',';
            }
            p = put_int(p, rec.buf[i]);
        }
        *p++ = ']';
        *p++ = '"';
        *p++ = '\n';
        uart_write_bytes(HG_UART, line, p - line);
        s_logged++;
    }
}

static void status_line(void)
{
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    char s[256];
    int n = snprintf(s, sizeof(s),
                     "HINIGRAM_RX,receiver=%d,chip=%s,revision=%d,cores=%d,idf=%s,channel=%d,bandwidth=HT20,nodes=%d-%d,"
                     "logged=%lu,dropped=%lu\n",
                     CONFIG_HINIGRAM_RECEIVER_ID, CONFIG_IDF_TARGET, chip.revision, chip.cores, esp_get_idf_version(),
                     CONFIG_HINIGRAM_CHANNEL, CONFIG_HINIGRAM_NODE_FIRST, CONFIG_HINIGRAM_NODE_LAST,
                     (unsigned long)s_logged, (unsigned long)s_dropped);
    if (n > 0) {
        uart_write_bytes(HG_UART, s, n < (int)sizeof(s) ? n : (int)sizeof(s) - 1);
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
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_HINIGRAM_CHANNEL, WIFI_SECOND_CHAN_NONE));
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    s_queue = xQueueCreate(QUEUE_DEPTH, sizeof(csi_rec_t));
    ESP_ERROR_CHECK(s_queue ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(uart_driver_install(HG_UART, 256, 16384, 0, NULL, 0));
    const char *hdr = "type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,"
                      "noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,len,first_word,data\n";
    uart_write_bytes(HG_UART, hdr, strlen(hdr));

    wifi_init();
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));
    /* LLTF only: 64 subcarriers, 128 values per line, the layout the pipeline and the board read (len 128, as in
       esp-csi's csi_recv for the original ESP32). With HT-LTF on, the nodes' HT20 packets would give 256 values. */
    wifi_csi_config_t csi = {
        .lltf_en = true,
        .htltf_en = false,
        .stbc_htltf2_en = false,
        .ltf_merge_en = true,
        .channel_filter_en = true,
        .manu_scale = false,
        .shift = 0,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    xTaskCreatePinnedToCore(printer_task, "csi_print", 4096, NULL, 4, NULL, 1);

    status_line();
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(60000));
        status_line();
    }
}
