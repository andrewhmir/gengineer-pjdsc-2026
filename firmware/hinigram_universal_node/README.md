# Hinigram universal node

One transmitter firmware for any number of chair nodes, for the original ESP32 (ESP-IDF 5.1 or newer).
The version is in [`version.txt`](version.txt) and is printed at start-up.

Each board keeps its node ID (1 to 254) in its NVS flash, so every transmitter runs the same image and
sends from `1a:00:00:00:00:<ID in hex>`. Set or change the ID over USB serial at 115,200 baud, without
writing the firmware again:

```text
hinigram id 7       store ID 7 and restart with it
hinigram info       print the start-up lines again
```

The Hinigram live console's Boards panel does this for you: it writes the firmware, then gives the board the
next free ID. A board with no stored ID takes one from its chip address and says so at start-up.

At start-up the node prints two lines (log level WARN):

```text
W (550) hinigram_node: node 7 sending 30 packets/s on channel 6 from 1a:00:00:00:00:07
W (551) hinigram_node: universal v1.0.0, chip d0:ef:76:56:e8:68, id stored, IDF v5.3.2
```

Channel and packet rate are build settings (`idf.py menuconfig`, *Hinigram universal node*); every node and
the receiver must use the same channel.

It pairs with [`../hinigram_receiver`](../hinigram_receiver), which accepts nodes 1 to 254 by default. The
team's `csi_rx` accepts only nodes 1 to 3.

Based on the v1.3.3 bundle's `hinigram_node`, itself based on Espressif's esp-csi `csi_send` example
(Apache-2.0 / CC0). The radio settings, timing and packet are unchanged; only where the ID comes from is new.

## Versions

| Version | Change |
|---|---|
| 1.0.0 | First version: the ID from NVS, the `hinigram id` and `hinigram info` commands, the version and chip address at start-up. |
| 1.1.0 | Set the staged transmit address before `esp_wifi_start()`, the state `esp_wifi_set_mac()` is documented for; the radio settings, packet and start-up lines are unchanged. |
