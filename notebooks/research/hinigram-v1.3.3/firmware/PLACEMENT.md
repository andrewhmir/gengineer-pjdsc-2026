# Where the ESP32 boards go

How to place the chair nodes and the corner receivers in the waiting room. The layout itself (a node on every backrest
at chest height, receivers in the front corners) comes from the notebook (Part 1, Section 6) and `firmware/README.md`.
The distances, heights and mounting details marked *suggested* are starting points to tune with the paced-breathing
check; none of them has been measured on hardware yet.

## The one rule

The straight line from a chair's node to its receiver must pass through that person's chest. Breathing changes a Wi-Fi
link most where the link crosses the chest, so each person sits **between** their node (behind them) and the receiver
(in front of them).

```
SIDE VIEW (one chair)

  front wall                                            chair
  +--+                                                  | [N]  node on the BACK face of the backrest,
  |RX| <=========== link through the chest ======  (person) |      centred, at mid-chest height
  +--+   receiver at about the same height              |
                                                      ==+== seat
  ------------------------------------ floor ---------------------------------
```

## Three transmitters, one receiver: three watched chairs

The smallest room that works: one receiver in a front corner and three chairs, each with its own node. Use them as
*watched seats* for the people triage judges most at risk. One link reads one person: a link that crosses several
people mixes their breathing, and a pause in one of them can then hide behind the others' breathing (notebook Part 1,
Section 7). So three nodes watch three chairs, not the whole room.

```
PLAN VIEW (everyone in a watched chair faces the receiver's corner)

 [RX]=================================  front wall
  ||\  `.
  || \   `.
  ||  \    `.
  || (A)    `.          A: about 2 m from RX
  ||  N       (B)       B: about 3 m
  ||           N   .    C: about 4 m
  ||               (C)  N: the node on the back of each chair
  ||                N
  side wall
```

| | |
|---|---|
| Receiver | In the corner at about 0.8 to 1.0 m (*suggested*), antenna end facing the room; USB to the laptop running the board. Menuconfig: first node 1, last node 3 |
| Chairs | Each on its own straight line to the receiver, the lines fanned out (*suggested:* at least 20 degrees apart, chairs 2 to 4 m away) so nobody sits on another chair's line. Each chair faces the corner |
| Nodes | IDs 1, 2 and 3, on the back of each backrest at mid-chest height (below). Same channel as the receiver |
| Clear lines | No aisle, other seat or metal between a watched chair and the receiver. Other waiting-room seats go behind or beside the fan, not inside it |
| Serial speed | 921,600 baud is enough for three chairs (it carries about five) |

Then: the **Quick check** on the empty chairs (below), and the paced-breathing check with a person in each chair.

## Chair nodes

| | |
|---|---|
| Where | On the backrest, at chest height (`firmware/README.md`). *Suggested:* on the back face of the backrest, centred left to right, so the person never leans on it or touches it |
| Height | Mid-chest of a seated adult. *Suggested:* about 25 to 35 cm above the seat, which is about 70 to 85 cm above the floor on a standard chair, near the top of the backrest |
| Fixing | *Suggested:* a small plastic box, fixed firmly with cable ties or hook-and-loop tape. A node that moves makes its own "breathing" |
| Antenna | *Suggested:* the end of the module with the zig-zag antenna trace up or towards the receiver, uncovered, and not against a metal frame |
| Power | Not specified in the bundle. *Suggested:* a mains USB charger (5 V, 1 A or more) with the cable down a chair leg and taped. Some power banks switch themselves off at the node's low current |
| Identity | Node ID set in `idf.py menuconfig`; the node sends from `1a:00:00:00:00:<ID in hex>`. Settings are fixed at build time, so changing an ID means re-flashing |

The node's firmware drives no LED. Its only self-report is one boot line on its own serial console (and occasional
`send failed` warnings), so check an installed node through the receiver or the board.

## Receivers

| | |
|---|---|
| Where | In the front corners, on the wall the people face, at about chest height (`firmware/README.md`). *Suggested:* about the same height as the nodes, 0.8 to 1.0 m, so each link runs roughly level through a chest |
| Fixing | *Suggested:* on a wall or post, not on metal shelving, antenna end clear and facing the room |
| Cable | A USB cable to the computer running the board or `tools/log_serial.py`; the receiver sends its data over USB serial. *Suggested:* plain USB 2.0 cables up to about 5 m, an active extension beyond |
| Status | The `HINIGRAM_RX` line on the serial port, at start-up and every minute: `receiver=`, `channel=`, `nodes=`, `logged=`, `dropped=`. Its `chip=` field repeats the build target (always esp32); it does not detect the chip |

## Which chairs each receiver serves

A receiver accepts one continuous range of node IDs (`NODE_FIRST` to `NODE_LAST`). Number the nodes so each corner
receiver takes the half of the room nearest to it; then links stay short and do not cross the room:

```
PLAN VIEW (12 chairs, everyone facing the front wall)

   [RX1] <------------------ front wall ------------------> [RX2]
    A1 (1)   A2 (2)                         A3 (7)   A4 (8)      row A
    B1 (3)   B2 (4)                         B3 (9)   B4 (10)     row B
    C1 (5)   C2 (6)                         C3 (11)  C4 (12)     row C
   RX1: nodes 1-6                          RX2: nodes 7-12
                         walkway / door at the back
```

This is the left/right split the board's demo room draws, and the injection bench numbers its chairs the same way. The
README's example numbering (A1 = 1 ... C4 = 12) also works, but with 1-6 and 7-12 it splits the room front and back.

## How many chairs one receiver can carry

The USB serial link fills first: each `CSI_DATA` line is about 470 bytes, for the 128-value lines the receiver sends (`firmware/README.md`).

| Serial speed | Chairs at 30 packets/s | Chairs at 20 packets/s |
|---|---|---|
| 921,600 baud (default) | 5 | 7 |
| 2,000,000 baud (needs a CP2102N or CH340-class USB chip) | 11 | 17 |

*Suggested:* 2,000,000 baud, two receivers with six chairs each, nodes at 30 packets/s. The pipeline was validated at
about 28.5 packets/s; 20 packets/s has not been tested. Set `CONFIG_ESP_CONSOLE_UART_BAUDRATE` in the receiver's
menuconfig, run `log_serial.py` with `--baud 2000000`, and choose 2,000,000 under **Serial speed** next to the board's
**Connect receiver** (the injection bench uses the same setting). Lines that do not fit are dropped whole and counted in `dropped`; they also show in the board's "Lost" column.

## What to keep out of the links

* **Metal** between a node and its receiver, or near either antenna: chair frames, filing cabinets, televisions.
* **Things that move:** fans, curtains, a door's swing, and above all a walkway between the front row and the front wall.
  Anyone walking there disturbs every link and the board shows *moving*. Put the aisle at the back or the sides.
* **Neighbours:** a person beside a link also changes it. Links from the outer chairs that run past the next seat pick
  up that neighbour's breathing. The injection bench showed the consequence: an empty chair whose link picked up periodic
  movement from elsewhere gave *needs help now* when that movement stopped (notebook Part 1, Section 6b). Space the
  seats a little, or angle each chair slightly towards its receiver.
* **Back rows:** their links pass near the people in front, so they will give *no reliable reading* more often.

## First test: one chair

1. One chair 2 to 3 m in front of the receiver, facing it, its node on the backrest, the receiver at chest height.
2. In `idf.py monitor` on the receiver: `CSI_DATA` lines about 30 times a second, `128` in the `len` column, and `dropped=0`.
3. Open the board in Chrome or Edge, set **Serial speed** to the receiver's, **Connect receiver**, sit still, and run
   **Check accuracy with paced breathing**.
4. Move the node up or down a few centimetres and repeat. At channel 6 the Fresnel zones are about 6 cm apart, and
   accuracy is best mid-zone (Yang et al. 2018: 0.6 breaths/min error mid-zone against 3.1 at a zone boundary).
5. Watch signal strength in the engineers' panel; the format sample's three links averaged -34 to -45 dBm (5th to 95th
   percentile -59 to -18). A chair much weaker than the rest needs its receiver closer.

**Check the whole chain before anyone sits down (2 minutes).** With the chairs empty, choose **Injection bench**, then
*Your receiver, live over USB* (the scenario switches to **Quick check**), press **Start** and pick the port. Every node
gets the same routine as soon as it is heard: breathing at 15 a minute, an 18 s breath-hold at 1:02, a shift in the
seat at 1:35, timed from the node's first packet. At 2:00 each chair has a verdict, fixed from then on (the table also
names each chair's node, so you can find it):

| Verdict | Means | Do |
|---|---|---|
| Ready | Packets arrive, the rate is read and right, the hold raises *needs help now*, the shift is seen as movement | Go on to the paced-breathing check |
| Repeat | Something in the room moved during the test | Keep people away from the lines and run it again |
| Check | Too few packets or a node that stopped sending, a rate shown too seldom or wrongly, a pause alert while the chair was breathing, a missed hold, or a missed shift (the cell says which) | Packets: power and cable of that node, receiver closer, or fewer nodes. Rate, hold or false alert: move the node a few cm up or down, or turn the chair to face the receiver, then repeat |
| Changed by hand | Someone changed that chair's settings during the routine | Run it again without touching it |

The **Setup check** does the same in 4 minutes with two rates (12, then 20 a minute). Both use suggested thresholds,
listed under the verdict table; they are a first check, not a validation.

## Tests before trusting the layout

| Question | How |
|---|---|
| Chairs per receiver | Add nodes one at a time; watch `dropped` and the packet rate |
| Back rows | Record with people moving in the front rows; count *no reliable reading* in the back rows |
| Node height | Move the node between heights and compare with a respiration belt or the pacer |
| Neighbours | Two people side by side, one holding their breath |
| Empty chairs | Record with chairs empty next to occupied ones; count any pause alerts |

## Not covered yet

Children (a lower chest, and often held by a caregiver, which puts two breathers in one link), validated distances and
heights, enclosures for a clinical area, and electrical safety of bare development boards. The firmware compiles with
ESP-IDF 5.3.2 but has not yet run on hardware; do the bring-up checks in `firmware/README.md` first.
