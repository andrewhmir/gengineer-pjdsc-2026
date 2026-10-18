#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "nvs_flash.h"
#include "rom/ets_sys.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_now.h"

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_mac.h"

// defining channel and firmware info
#define CONFIG_LESS_INTERFERENCE_CHANNEL   6      //channel defined here
#define CONFIG_WIFI_BANDWIDTH           WIFI_BW20  //channel bandwidth: 40 MHz
#define CONFIG_ESP_NOW_PHYMODE          WIFI_PHY_MODE_HT20  //format: 802.11n at 40 MHz
#define CONFIG_ESP_NOW_RATE             WIFI_PHY_RATE_MCS0_LGI //data rate: MCS0
#define CONFIG_FORCE_GAIN                   0

// callback dependency
#define CSI_MAX_LEN 384

typedef struct {
    wifi_pkt_rx_ctrl_t rx_ctrl;
    uint8_t  mac[6];
    uint32_t id;
    int      len;
    int      first_word_invalid;
    int8_t   buf[CSI_MAX_LEN];
} csi_item_t;

static QueueHandle_t s_csi_q;
static volatile uint32_t s_dropped = 0;

// 3 Tx acceptance
static const uint8_t TX_MAC_PREFIX[5] = {0x1a, 0x00, 0x00, 0x00, 0x00};

static bool is_tx_mac(const uint8_t *mac)
{
    return memcmp(mac, TX_MAC_PREFIX, 5) == 0 && mac[5] >= 1 && mac[5] <= 3;
}


static const char *TAG = "csi_rx";

static void wifi_init()
{
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_init());

    // initiates wifi driver
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA)); //station mode, will not connect to any wifi
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM)); // settings stored in ram only

    // starts wifi
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, CONFIG_WIFI_BANDWIDTH));
    ESP_ERROR_CHECK(esp_wifi_start());

    // power save off
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    // sets wifi channel based on bandwidth
    if (CONFIG_WIFI_BANDWIDTH == WIFI_BW20) {
        ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_LESS_INTERFERENCE_CHANNEL, WIFI_SECOND_CHAN_NONE));
    } else {
        ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_LESS_INTERFERENCE_CHANNEL, WIFI_SECOND_CHAN_BELOW));
    }

}

static void wifi_esp_now_init(esp_now_peer_info_t peer)
{
    ESP_ERROR_CHECK(esp_now_init());
    ESP_ERROR_CHECK(esp_now_set_pmk((uint8_t *)"pmk1234567890123"));
    esp_now_rate_config_t rate_config = {
        .phymode = CONFIG_ESP_NOW_PHYMODE,
        .rate = CONFIG_ESP_NOW_RATE,
        .ersu = false,
        .dcm = false
    };
    ESP_ERROR_CHECK(esp_now_add_peer(&peer));
    ESP_ERROR_CHECK(esp_now_set_peer_rate_config(peer.peer_addr, &rate_config));

}

// callback
static void wifi_csi_rx_cb(void *ctx, wifi_csi_info_t *info)
{
    if (!info || !info->buf) return;
    if (!is_tx_mac(info->mac)) {
    return;
    }
    if (info->len > CSI_MAX_LEN) return;            // safety

    csi_item_t item;                                 // copy, then hand off
    item.rx_ctrl = info->rx_ctrl;
    memcpy(item.mac, info->mac, 6);
    item.id = *(uint32_t *)(info->payload + 15);
    item.len = info->len;
    item.first_word_invalid = info->first_word_invalid;
    memcpy(item.buf, info->buf, info->len);

    if (xQueueSend(s_csi_q, &item, 0) != pdTRUE) {   // never block here
        s_dropped++;
    }
}

static void csi_print_task(void *arg)
{
    csi_item_t it;
    bool header = false;
    while (1) {
        if (xQueueReceive(s_csi_q, &it, portMAX_DELAY) != pdTRUE) continue;
        const wifi_pkt_rx_ctrl_t *r = &it.rx_ctrl;

        if (!header) {
            header = true;
            ets_printf("type,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_format,len,first_word,data\n");
        }
        ets_printf("CSI_DATA,%d," MACSTR ",%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
                   (int)it.id, MAC2STR(it.mac), r->rssi, r->rate, r->sig_mode,
                   r->mcs, r->cwb, r->smoothing, r->not_sounding,
                   r->aggregation, r->stbc, r->fec_coding, r->sgi,
                   r->noise_floor, r->ampdu_cnt, r->channel, r->secondary_channel,
                   (int)r->timestamp, r->ant, r->sig_len, r->sig_mode);
        ets_printf(",%d,%d,\"[%d", it.len, it.first_word_invalid, it.buf[0]);
        for (int i = 1; i < it.len; i++) ets_printf(",%d", it.buf[i]);
        ets_printf("]\"\n");

        if (s_dropped && (it.id % 100 == 0)) {
            ets_printf("# dropped=%u\n", (unsigned)s_dropped);
        }
    }
}


static void wifi_csi_init()
{
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true)); //receiver everything, filter later with tx mac add

    /**< default config */

    wifi_csi_config_t csi_config = {
        .lltf_en           = true,
        .htltf_en          = false,
        .stbc_htltf2_en    = false,
        .ltf_merge_en      = false,
        .channel_filter_en = true,
        .manu_scale        = false,
        .shift             = false,
    };


    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_rx_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
}

void app_main()
{
    // nvs initializattion
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // wifi initialization
    wifi_init();

    // esp now initialization
    esp_now_peer_info_t peer = {
        .channel   = CONFIG_LESS_INTERFERENCE_CHANNEL,
        .ifidx     = WIFI_IF_STA,
        .encrypt   = false,
        .peer_addr = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
    };

    wifi_esp_now_init(peer);

    s_csi_q = xQueueCreate(20, sizeof(csi_item_t));
    xTaskCreate(csi_print_task, "csi_print", 4096, NULL, 5, NULL);
    wifi_csi_init();
}
