# Changelog: Hinigram universal firmware

One version number covers the pair that is released together: this transmitter and the receiver
[`../hinigram_receiver`](../hinigram_receiver). Every change to either one's code gets a new version and an entry
here, newest first, under a heading `## <version> (<date>)`.

- **1.0 to 1.1, 1.2, ...** for a change that still works alongside boards running an earlier 1.x.
- **1.x to 2.0** for a change that does not, such as a new packet layout, channel width or address scheme, so that
  every board has to be written again.

GitHub builds each version and publishes it as the release `universal-v<version>`, with this section as its notes.
The release fails if the code changed while [`version.txt`](version.txt) did not, so a published version never
changes.

## 1.1 (2026-10-24)

- The transmitter prints a `HINIGRAM_TX` line at start-up and in answer to `hinigram info`: its version, ID, whether
  the ID is stored, its address and chip address, the ESP-IDF version, the build time, and its radio settings
  (channel, bandwidth, PHY rate, packets a second, the most random offset, packet layout). The console's Boards panel
  shows these for each board and compares them with any version it could write.
- The radio settings are one string in the image, which the release workflow reads to record each version's
  settings in its `build-info.json`.
- Nothing the board sends has changed: same radio settings, timing and packet as 1.0. The receiver is unchanged.

## 1.0 (2026-10-24)

- First version: one transmitter image for any number of chair nodes. The node ID (1 to 254) is kept in the board's
  NVS flash, not in the build, and is set or changed over USB serial with `hinigram id N` without writing the
  firmware again. `hinigram info` prints the start-up lines again.
- The start-up lines give the firmware version, the chip address, whether the ID is stored, and the ESP-IDF version.
  A board with no stored ID takes one from its chip address and says so.
- Radio settings, timing and packet are those of the v1.3.3 bundle's `hinigram_node`: 20 MHz on channel 6, MCS0,
  30 packets a second from `1a:00:00:00:00:<ID>`, with up to 2 ms of random offset.
- Receiver: the v1.3.3 bundle's `hinigram_receiver`, unchanged. It logs nodes 1 to 254 at 921,600 baud and reports
  how many lines it logged and dropped every 60 s.
