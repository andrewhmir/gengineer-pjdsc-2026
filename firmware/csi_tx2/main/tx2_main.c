#include <unistd.h>
#include "nvs_flash.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_mac.h"

// defining channel and firmware info
#define CONFIG_LESS_INTERFERENCE_CHANNEL   6      //channel defined here
#define CONFIG_WIFI_BANDWIDTH           WIFI_BW20  //channel bandwidth: 40 MHz
#define CONFIG_ESP_NOW_PHYMODE          WIFI_PHY_MODE_HT20  //format: 802.11n at 40 MHz
#define CONFIG_ESP_NOW_RATE             WIFI_PHY_RATE_MCS0_LGI //data rate: MCS0
#define CONFIG_SEND_FREQUENCY               30

// custom MAC adress
static const uint8_t CONFIG_CSI_SEND_MAC[] = {0x1a, 0x00, 0x00, 0x00, 0x00, 0x02};
static const char *TAG = "csi_tx2";

static void wifi_init()
{
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_init());

    //loads and starts wifi driver
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA)); //station mode, will act as client
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM)); //settings in ram only

    // Initiates the WiFi, must start before channel is set
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_STA, CONFIG_WIFI_BANDWIDTH));
    ESP_ERROR_CHECK(esp_wifi_start());

    //power save off
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    // sets the wifi channel
    if (CONFIG_WIFI_BANDWIDTH == WIFI_BW20) {
        ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_LESS_INTERFERENCE_CHANNEL, WIFI_SECOND_CHAN_NONE));
    } else {
        ESP_ERROR_CHECK(esp_wifi_set_channel(CONFIG_LESS_INTERFERENCE_CHANNEL, WIFI_SECOND_CHAN_BELOW));
    }

    // asigns custom mac adress for transmission
    ESP_ERROR_CHECK(esp_wifi_set_mac(WIFI_IF_STA, CONFIG_CSI_SEND_MAC));
}

static void wifi_esp_now_init(esp_now_peer_info_t peer)
{
    ESP_ERROR_CHECK(esp_now_init()); //start ESP NOW
    ESP_ERROR_CHECK(esp_now_set_pmk((uint8_t *)"pmk1234567890123")); //encryption master key, we are transmitting non-encrypted tho
    ESP_ERROR_CHECK(esp_now_add_peer(&peer)); //registers the rx
    esp_now_rate_config_t rate_config = { //forces our transmission settings (modulation, data rate, etc.)
        .phymode = CONFIG_ESP_NOW_PHYMODE,
        .rate = CONFIG_ESP_NOW_RATE,
        .ersu = false,
        .dcm = false
    };
    ESP_ERROR_CHECK(esp_now_set_peer_rate_config(peer.peer_addr, &rate_config)); //802.11n, 40 MHz, MCS0
}

void app_main()
{
    // standard nvs initialization
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

    //logging
    ESP_LOGI(TAG, "================ CSI SEND ================");
    ESP_LOGI(TAG, "wifi_channel: %d, send_frequency: %d, mac: " MACSTR,
             CONFIG_LESS_INTERFERENCE_CHANNEL, CONFIG_SEND_FREQUENCY, MAC2STR(CONFIG_CSI_SEND_MAC));

    // frame counter, sleeps between frame
    for (uint32_t count = 0; ; ++count) {
        esp_err_t ret = esp_now_send(peer.peer_addr, (const uint8_t *)&count, sizeof(count));
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "free_heap: %ld <%s> ESP-NOW send error", esp_get_free_heap_size(), esp_err_to_name(ret));
        }

        usleep(1000 * 1000 / CONFIG_SEND_FREQUENCY);
    }
}
