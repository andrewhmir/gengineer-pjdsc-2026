# Hinigram firmware for the ESP32-only room build

Two ESP-IDF projects for the **original ESP32** (ESP32-WROOM / DevKitC boards):

| Project | Goes where | What it does |
|---|---|---|
| `hinigram_node` | On each chair's backrest, at chest height | Broadcasts a short ESP-NOW packet 30 times a second from `1a:00:00:00:00:<node ID>` |
| `hinigram_receiver` | In a front corner of the room, at about chest height | Prints one `CSI_DATA` line per node packet over USB serial, in the exact layout the pipeline and the board already read |

Both compiled without warnings with ESP-IDF v5.3.2 (`idf.py build`, target `esp32`) and should build with any ESP-IDF 5.1 or newer. In v1.3.3 the receiver captures the legacy long training field only (`htltf_en` and `stbc_htltf2_en` off), so every line carries the 128 values the pipeline and the board read; with them on, the nodes' HT20 packets would give 256 and the board would skip every line. That change sets two flags and was not rebuilt here. Neither project has **yet been run on hardware**: do the bring-up checks below first.

Where each board goes in the room, how to number the nodes for two receivers, and what to keep out of the links: `PLACEMENT.md`.

## Build and flash

1. Install ESP-IDF 5.1 or newer ([Espressif's guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/index.html)).
2. For each chair node:
   ```
   cd hinigram_node
   idf.py set-target esp32
   idf.py menuconfig        # Hinigram chair node -> Node ID (1, 2, 3, ...), channel, packets per second
   idf.py -p <port> flash
   ```
3. For each receiver:
   ```
   cd hinigram_receiver
   idf.py set-target esp32
   idf.py menuconfig        # Hinigram corner receiver -> receiver ID, channel, first and last node ID it logs
   idf.py -p <port> flash monitor
   ```
   Every node and receiver must use the same channel. Pick the quietest 2.4 GHz channel in the room (default 6).

Number the nodes in seat order, for example A1 = 1, A2 = 2, ... C4 = 12. Node 12 sends from `1a:00:00:00:00:0c`.

## Bring-up checks

1. One node and one receiver on a desk: the monitor shows `CSI_DATA` lines from `1a:00:00:00:00:01` about 30 times a second with `128` in the `len` column (the second number before the `"[` data; the number right before it is the first-word flag, 1), and a `HINIGRAM_RX` status line every minute with `chip=esp32` and `dropped=0`.
2. Open the board (`dashboard/Hinigram_dashboard_standalone.html`) in Chrome or Edge on the same computer, set **Serial speed** next to **Connect receiver** to the receiver's speed, choose **Connect receiver**, and pick the receiver's port. The chair appears within a few seconds and gives a reading after 30 s of quiet breathing.
3. Add nodes one at a time and watch `dropped` in the status line and the packet rate in the board's engineers' panel.
4. With the chairs empty, run the board's **Injection bench** with *Your receiver, live over USB* and the **Quick check** (2 minutes; `PLACEMENT.md`). Every chair should read *Ready*.
5. Run the board's **Check accuracy with paced breathing** with a person on each chair before trusting any reading.

## How many chairs one receiver can serve

The serial link is the first limit, not the radio. Each `CSI_DATA` line is about 470 bytes (the format sample's lines average 471, with 128 values each), so:

| Serial speed | Lines per second (with 20% headroom) | Chairs at 30 packets/s | Chairs at 20 packets/s |
|---|---|---|---|
| 921,600 baud (default) | about 155 | 5 | 7 |
| 2,000,000 baud (needs a CP2102N or CH340-class USB chip; set `CONFIG_ESP_CONSOLE_UART_BAUDRATE`) | about 340 | 11 | 17 |

For the twelve-chair layout, either give each front corner its own receiver with half the chairs (receiver 1: nodes 1 to 6, receiver 2: nodes 7 to 12, at 20 packets/s) or raise the serial speed. Lines that do not fit are dropped whole and counted in `dropped`; they never stall Wi-Fi reception. The board reads one receiver at a time, at the speed chosen next to **Connect receiver** (921,600 or 2,000,000; it remembers the choice); reading several receivers at once is planned.

## Recording to files

`tools/log_serial.py` records one CSV per receiver with a host timestamp in front of every line, which is the format the notebook and the board's **Open a CSV file** read:

```
pip install pyserial
python tools/log_serial.py COM5 COM6 --baud 921600 --out recordings
```

To score a paced-breathing check offline: `python hinigram_paced.py recordings/<file>.csv hinigram_pacer_log.json` from the bundle folder.

## What the original ESP32 cannot do

It cannot lock or report its receive gain, so the 3 to 9 dB gain steps seen in the format sample stay in the data, and the pipeline removes them packet by packet. Receivers built on an ESP32-S3, C3, C5 or C6 can use Espressif's gain compensation (`esp_csi_gain_ctrl` in [esp-csi](https://github.com/espressif/esp-csi)), which keeps more of the breathing signal.

Both projects start from Espressif's esp-csi `csi_send` and `csi_recv` examples (Apache-2.0 / CC0).
