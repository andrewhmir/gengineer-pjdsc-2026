# Hinigram receiver

The corner receiver from the Hinigram v1.3.3 bundle, copied so it is under version control next to
[`../hinigram_universal_node`](../hinigram_universal_node). For the original ESP32, ESP-IDF 5.1 or newer.

One fix on top of the bundle copy (universal 1.2.0): the CSI column the header labels `rx_state` carries
`rx_ctrl.rx_state`; the bundle's copy repeated `sig_mode` there. The line layout is otherwise unchanged, and the
pipeline does not use that column.

It prints one `CSI_DATA` line per packet from nodes `1a:00:00:00:00:<ID>` with an ID between
`CONFIG_HINIGRAM_NODE_FIRST` and `CONFIG_HINIGRAM_NODE_LAST` (1 to 254 by default, so any universal node),
at 921,600 baud, plus a `HINIGRAM_RX` status line at start-up and every 60 s with how many lines it logged
and dropped. The design notes are at the top of [`main/app_main.c`](main/app_main.c).

How many transmitters one receiver can carry is set by the serial link: each node at 30 packets a second
sends about 18 KB/s of `CSI_DATA` text, and 921,600 baud carries about 92 KB/s, so about five nodes. For
more, raise the console speed to 2,000,000 baud (USB chips that support it, such as the CH340), lower the
packet rate, or split the nodes over several receivers with `CONFIG_HINIGRAM_NODE_FIRST` and `_LAST`.
