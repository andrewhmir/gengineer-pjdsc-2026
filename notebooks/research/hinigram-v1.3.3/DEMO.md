# Demo runbook: three watched seats

For showing Hinigram with what the team has: three ESP32 transmitters (chair nodes) and one ESP32 receiver. One node
watches one chair, so the demo shows three watched seats, not a whole room (why: "Questions" below).

## What to bring

* 3 chair nodes and 1 receiver, flashed (`firmware/README.md`): nodes with IDs 1, 2 and 3; the receiver with first node
  1, last node 3; all on the same channel.
* 4 USB power sources for the nodes and a USB cable from the receiver to the laptop.
* A laptop with Chrome or Edge and this bundle unzipped on it.
* 3 chairs, and tape or cable ties to fix the nodes to the backrests.

## Before the demo (about an hour)

1. **Place the boards** as in `firmware/PLACEMENT.md`, section "Three transmitters, one receiver": receiver in a corner
   at chest height, chairs fanned out 2 to 4 m away and facing it, each node on the back of its chair at mid-chest height.
2. **Bring-up:** `idf.py monitor` on the receiver shows `CSI_DATA` lines from all three nodes, `128` in the `len`
   column, and `dropped=0`. Close the monitor afterwards: only one program can use the port.
3. **Quick check (2 minutes):** open `dashboard/Hinigram_dashboard_standalone.html` by double-clicking it, choose
   **Injection bench**, then *Your receiver, live over USB*, press **Start** and pick the port. Keep the chairs empty and
   people still. At 2:00 every chair should read *Ready*. *Repeat*: someone moved, so run it again. *Check*: follow the
   table in `PLACEMENT.md`. Press **Download the scores (CSV)** to keep the result.
4. **One person per chair:** run **Check accuracy with paced breathing** with the *Short* plan (about 3 minutes per
   chair): the teammate breathes with the on-screen pacer and the board scores itself against it.
5. **Record a backup:** `python firmware/tools/log_serial.py COM5 --out recordings` (your port; Linux: `/dev/ttyUSB0`)
   for 5 minutes with teammates sitting, breathing normally, one holding their breath for 15 to 20 s. If the radio
   misbehaves on the day, this file drives the same board.

## The five-minute script

| Time | Show | Say |
|---|---|---|
| 0:00 | The board, **Connect receiver**, three seats | Between triage and the doctor, nobody watches the waiting room. Wi-Fi between a node on the chair and a receiver in the corner changes as the chest moves; no camera, no wearable. |
| 0:45 | A teammate sits in seat A and breathes normally | After 30 s of quiet breathing the seat shows a rate and a state (NEWS2 bands for adults, IMCI for children). |
| 1:30 | The teammate breathes out and holds still for 15 s | *Needs help now: possible breathing pause* comes about 10 to 12 s after the breath stops (adult minimum 10 s). |
| 2:15 | The Quick check verdict table from the setup | The bench adds breathing of a known rate to the live packets and checks the board against it, so we know each seat works before trusting it. |
| 2:45 | The notebook (`Hinigram_v1_3_3_complete.ipynb`) | Data science: every pipeline version frozen with a hash and tested once on held-out data it never saw; a learned model (ResoNet) against the rules; the fallback rule: more correct readings (30.6% to 37.4% of windows), but more false reassurance during pauses (6 to 8 of 162 pause windows against 2), so the board does not use it. |
| 4:15 | The limits | One person per link; an empty chair can raise a pause alert; not yet tested against a reference sensor on patients. A screening aid: a nurse decides. |

## If something fails

| Problem | Fix |
|---|---|
| The board cannot find the receiver | Chrome or Edge, page opened as a file (not from a web page), no other program on the port, **Serial speed** matching the firmware (921,600 by default) |
| Readings jump or never appear | Keep people out of the lines between chairs and receiver; check `dropped` and the packet rate in the engineers' panel |
| The radio does not work at all | **Injection bench** with *A CSV file from your receiver* (the backup recording) and the Quick check, or *Format sample, quiet stretch only*: the same pipeline, offline |
| No laptop with USB | The board's **Demo scenario**: a twelve-chair room built from real packets with simulated breathing |

## Questions you may get

* **Why not one receiver for the whole room?** A link that crosses several people sums their breathing. Telling people
  apart by breathing rate needs their rates at least about 2 a minute apart in a 30 s window; with resting adults
  between 12 and 20 a minute, two people collide about 44% of the time and three about 87% (rates spread evenly).
  Harmonics (12 a minute also shows at 24) and movement make it worse, and a stopped breath can hide behind the others'.
  The original ESP32 has one antenna and 20 MHz of bandwidth, so it cannot locate people either. One node per seat is
  the reliable route (about USD 5 per seat).
* **How do you know it is accurate?** Semi-synthetic held-out tests (known breathing added to real packets), the bench,
  the paced-breathing check on people, and real breathing from the HKU dataset with a respiration belt
  (`training/Hinigram_training.ipynb`, Section 9): every rate v1.3.2 showed on steady breathing was within 2/min of the
  belt, and the empty office gave no rate and no alert. Another radio and one office, so not yet an ESP32 result.
* **Privacy?** No camera and no microphone: Wi-Fi channel measurements only, processed on the laptop.
