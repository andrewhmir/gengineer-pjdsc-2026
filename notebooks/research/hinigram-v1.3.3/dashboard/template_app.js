(function () {
  'use strict';
  const DATA = JSON.parse(document.getElementById('hinigram-data').textContent);
  const $ = (id) => document.getElementById(id);
  const CS = getComputedStyle(document.documentElement); // live; follows theme changes
  const css = (name) => CS.getPropertyValue(name).trim();
  const reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const HAND = () => css('--hand') || 'cursive';
  const FONT = () => css('--font') || 'sans-serif';

  // ------------------------------------------------------------------ words (English / Filipino)
  const T = {
    en: {
      tagline: 'Breathing watch for the waiting area', noteMark: 'Please note',
      disclaimer: 'This is a screening aid, not a diagnosis. A nurse or doctor decides. It reads breathing movement from Wi-Fi signals; it does not use a camera.',
      srcDemo: 'Demo scenario', srcDemoSub: 'real packets, simulated breathing', srcSample: 'Format sample', srcSampleSub: 'real recording',
      srcFile: 'Open a CSV file', srcFileSub: 'from the ESP32 receiver', srcLive: 'Connect receiver', srcLiveSub: 'USB, Chrome or Edge',
      now: 'Right now', attention: 'Who needs attention', sorted: 'Each chair has its own ESP32 node. Tap a chair for details.', room: 'Where the sensors are',
      schematic: 'Plan view, not to scale. Each chair\'s node sits on its backrest, so its link to a corner receiver passes through the person sitting there.', log: 'What happened', logSub: 'Status changes and checks, newest first',
      eng: 'For engineers: sensor health', engRate: 'Packets per second (5 s window)', engRssi: 'Signal strength (dBm)',
      engSteps: 'Gain steps (% of packets)', engAct: 'Movement index (above 1 means movement)',
      foot2: 'Thresholds follow NEWS2 for adults and the WHO IMCI fast-breathing cut-offs for children under 5. They still need review by Filipino clinicians before any use with patients.',
      st: { urgent: 'Needs help now', watch: 'Watch', typical: 'No breathing concern', no_reading: 'No reliable reading', moving: 'Moving, reading paused' },
      short: { urgent: 'help now', watch: 'watch', typical: 'OK', no_reading: 'no reading', moving: 'moving' },
      act: {
        pause: 'Go to them now and check their breathing.', rateUrgent: 'Ask a nurse to check them now and take full vital signs.',
        watch: 'Recheck within 10 minutes.', childFast: 'Ask a nurse to count their breaths for a full minute and look for chest indrawing.',
        resumed: 'Please check on them.', typical: 'No action needed now.',
        no_reading: 'Ask them to sit upright and stay still, or count their breaths for 60 seconds.',
        moving: 'The reading restarts about 20 seconds after they settle.', warmup: 'Wait for the first reading.',
        lost: 'Check that the sensor has power and is on the same Wi-Fi channel.',
      },
      why: {
        pause: 'No breathing movement seen for {s} seconds.', veryfast: 'Very fast breathing: {r} per minute. The adult cut-off is 25.',
        fast: 'Fast breathing: {r} per minute (adult range 21 to 24).', veryslow: 'Very slow breathing: {r} per minute (8 or fewer).',
        slow: 'Slow breathing: {r} per minute (adult range 9 to 11).', typical: 'Breathing rate {r} per minute, in the usual adult range (12 to 20).',
        fastage: 'Fast breathing for this age: {r} per minute. The WHO cut-off is {c}.', slowage: 'Slow breathing for this age: {r} per minute.',
        typicalage: 'Breathing rate {r} per minute, usual for this age.', noread: 'The sensor cannot read breathing right now.',
        moving: 'Movement detected, so the reading is paused.', warmup: 'Starting up. The first reading needs 30 seconds of data.',
        resumed: 'Breathing came back after a pause.', weak: 'The pause check is limited at this seat because the signal is weak.',
        lost: 'No data from this sensor for {s} seconds.',
      },
      ann: { pause: 'no breathing {s} s', moving: 'moving', now: 'now', lost: 'no data' },
      seat: 'Seat {x}', perMin: 'per minute', bpmUnit: 'breaths per minute', noReadingShort: 'no reading', perMinShort: '/min',
      pauseUnit: 'without breathing movement', pauseShort: 'pause {s} s',
      conf: 'Confidence', confLv: ['Low', 'Medium', 'High'], pauseCheck: 'Pause check', pcActive: 'Active', pcLimited: 'Limited, weak signal',
      pcWait: 'Waiting for a steady reading', updated: 'Last update', secAgo: '{s} s ago', sensor: 'Sensor', none: 'None yet',
      ack: "I'm checking now", acked: 'Checked by staff at {t}', profile: 'Who is sitting here', details: 'Show details for seat {x}',
      stampBig: 'CHECKED', stampSmall: 'TININGNAN {t}',
      prof: { adult: 'Adult, 16 and older', child_1_5y: 'Child, 1 to 5 years', infant_2_12m: 'Infant, 2 to 12 months', newborn_lt2m: 'Newborn, under 2 months' },
      waveCap: 'Breathing movement, last 30 seconds', waveCapDemo: 'Breathing movement, last 30 seconds (simulated breathing on real packets)',
      trendCap: 'Breathing rate this session, on observation-chart bands', legReading: 'Hinigram reading', legTruth: 'Programmed rate (demo)',
      zone: { typical: 'usual', watch: 'watch', urgent: 'help now' }, receiver: 'receiver', sensorN: 'sensor {n}', door: 'door',
      trendAria: 'Breathing rate chart. {n} reliable readings so far{range}.', trendRange: ', from {a} to {b} per minute, latest {c}',
      tipReading: '{r} per minute', tipNone: 'No reliable reading',
      metaDemo: 'Demo room: twelve chairs in three rows, each with its own ESP32 node on the backrest and a link to a receiver in a front corner. The recording ({f}) has three real links, so each chair reuses the packets of one of them with its own simulated breathing. People in the recording move between about 1:05 and 1:50.',
      metaSample: 'Format sample. The real {d}-second recording from three ESP32 sensors ({when}). It has no breathing reference, so the honest output is mostly "No reliable reading".',
      metaFile: 'Your file {f}: {n} packets from {k} sensors over {d} seconds. Choose who is sitting at each seat in the seat details; the reading is recalculated.',
      metaLive: 'Live from the receiver: {n} packets from {k} sensors.',
      loading: 'Reading your file. This takes a few seconds per minute of recording.', progress: 'Reading your file: {a} of {b} sensors done.',
      noSerial: 'The USB connection works when this page is saved and opened as a file in Chrome or Edge on the computer plugged into the receiver. You can still open a saved CSV file here.',
      serialAsk: 'Choose the receiver port in the browser prompt.', serialOn: 'Connected. Waiting for packets ({b} baud).', serialLost: 'The receiver disconnected.',
      rxBenchEnded: 'The test has ended. The live board starts afresh, so nothing it shows comes from added breathing; readings return after about 30 s.',
      testFile: 'This file came from the injection bench: simulated breathing added to real Wi-Fi packets. It is test data, not a patient recording.',
      fileErr: 'This file has no CSI_DATA lines. Choose a log saved from the ESP32 receiver.', shortFile: 'This file is shorter than 30 seconds, so there is no breathing reading yet.',
      empty: 'No changes yet.', ackLog: 'checked by staff', play: 'Play', pause: 'Pause',
      th: ['Sensor', 'Packets/s', 'Lost', 'Longest gap', 'RSSI', 'Gain steps', 'Channel', 'Subcarriers'],
      engNote: 'Rates use the receiver clock. Gain steps are packets whose overall CSI level jumps more than 1.5 dB from the previous packet; locking the receiver gain in firmware removes them.',
      foot1: '{v}. Data shown: {src}.', srcDemoName: 'demo ({f} with simulated breathing)', srcLiveName: 'live receiver',
      counts: { urgent: 'need help now', watch: 'watch', no_reading: 'no reading', typical: 'no concern' },
      heroUrgent1: '{x} needs help now.', heroUrgentN: '{x} need help now.', heroWatch: 'Keep an eye on {x}.', heroCalm: 'No one needs help right now.',
      heroNone: 'No reliable readings right now.', heroNoRead: 'No reliable reading for {x}.', heroOk: 'No breathing concern for {x}.',
      seatOne: 'Seat {x}', seatMany: 'Seats {x}', and: 'and', seatsList: 'Seats in the waiting area',
      heroOkN: 'The other {n} seats show no breathing concern.', rowLabel: 'Row {x}', attnH: 'Needs attention', attnSub: 'Most urgent first',
      attnNone: 'No one needs attention right now.', rxN: 'receiver {n}',
      checkH: 'Check accuracy with paced breathing', checkSeat: 'Chair', checkPlan: 'Steps', checkStart: 'Start the pacer', checkStop: 'Stop',
      checkIntro: 'Hinigram runs on Wi-Fi signals alone. To check it, one person sits on one chair and breathes along with the pacer at known rates, and Hinigram\'s readings for that chair are scored against those rates. Run it with the receiver connected, or record a CSV while it runs and open both files here later.',
      planStd: 'Standard: 8, 12, 16, 20, 24 per minute, 90 s each (about 10 min)', planShort: 'Short: 10, 16, 22 per minute, 50 s each (about 3 min)',
      checkLoad: 'Load the pacer log for this file', checkSafe: 'Breathe gently, not deeply. Stop if you feel dizzy or short of breath.',
      cueIn: 'Breathe in', cueOut: 'Breathe out', cueRest: 'Breathe normally', stepRate: '{r} per minute, {s} s left in this step', stepRest: 'Rest, {s} s',
      checkNoData: 'This log was not recorded with the data now open. Open the CSV recorded during the check, then load the log again.',
      checkNoSeat: 'The chair in this log is not in the data now open.', checkUnscored: 'Nothing was scored because no receiver was connected. Save the pacer log; if a CSV was recorded during the run, open it here and load the log.', badLog: 'That file is not a Hinigram pacer log.',
      resTarget: 'Paced rate (/min)', resWin: 'Windows', resShown: 'Rate shown', resMed: 'Median reading', resOk: 'Within ±2/min', resMae: 'Mean error (/min)',
      resSummary: 'Seat {x}: {ok} of {shown} readings ({p}%) were within ±2 per minute, and a rate was shown in {c}% of {n} windows.',
      resWait: 'Scoring starts about 30 s into each step, once a whole window lies inside it.', dlResults: 'Download results (CSV)', dlLog: 'Download the pacer log', dlFailed: 'The file could not be saved here.',
      // injection bench
      srcInject: 'Injection bench', srcInjectSub: 'add known breathing, live', srcInjectName: 'injection bench ({f} with simulated breathing added live)',
      benchH: 'Injection bench', benchSub: 'Adds breathing of a known rate to Wi-Fi packets while they stream, so you can see what the board does with it. Change any chair while it runs.',
      bgLabel: 'Packets from', bgSample: 'Format sample, all of it (people move from 1:05 to 1:50)', bgQuiet: 'Format sample, quiet stretch only (1:52 to 2:53)',
      bgCsv: 'A CSV file from your receiver', bgReceiver: 'Your receiver, live over USB', chairsLabel: 'Chairs', presetLabel: 'Scenario', speedLabel: 'Speed', baudLabel: 'Serial speed',
      benchStart: 'Start', benchPause: 'Pause', benchResume: 'Resume', benchReset: 'New run', benchLoading: 'Starting...',
      presets: { mixed: 'Mixed waiting room', holds: 'Breath-hold drill (8 to 25 s)', heldout: 'Held-out scenarios (the eleven, in turn)', calm: 'Everyone breathing normally',
        none: 'Nothing added (raw packets, null test)', manual: 'Everyone at 16 per minute; you drive', setup: 'Setup check: one 4-minute routine on every chair',
        quick: 'Quick check: one 2-minute routine on every chair' },
      rxNoteAuto: 'Each node gets the scenario as soon as it is heard, timed from that moment. Use empty chairs: added breathing would mix with a real person\'s.',
      noteSetup: 'Setup check: each chair breathes 12 per minute, then 20 from 1:15, holds its breath for 18 s at 2:30 and shifts in the seat at 3:20, timed from when it starts. At 4:00 it gets a verdict{end}.',
      noteQuick: 'Quick check: each chair breathes 15 per minute, holds its breath for 18 s at 1:02 and shifts in the seat at 1:35, timed from when it starts. At 2:00 it gets a verdict{end}.',
      setupEndRx: ' and its added breathing switches off', setupEndPlay: '; the run pauses when every chair has one',
      setupH: { setup: 'Setup check', quick: 'Quick check' }, setupTh: ['Seat', 'Packets', 'Reads breathing', '18 s breath-hold', 'Shift in seat', 'Verdict'],
      setup: { left: '{t} to go', pk: '{r} a second', reads: 'rate shown {p}%, right {q}%', weak: 'weak: rate shown {p}%', wrong: 'right only {q}%', few: 'room moving: too few quiet windows', nodata: 'too few readings: is the link dropping?', drop: 'stopped for {s} s', node: 'node {n}',
        flagged: 'flagged after {s} s', missed: 'not flagged', saidOk: 'said no concern', falseAlarm: 'pause alert before the hold', moved: 'movement during it', seen: 'seen as movement', unseen: 'not seen',
        ready: 'Ready', check: 'Check', repeat: 'Repeat', hand: 'Changed by hand', summary: '{a} of {n} chairs ready.', more: ' To check: {b}. To repeat: {c}.',
        crit: 'Ready means: at least 25 packets a second on average, never stopping for more than 8 s; a rate shown in at least a third of the scored windows, and within ±2 per minute in at least 90% of those; no pause alert while the chair breathes, and the breath-hold flagged with no "no breathing concern" during it; the shift in the seat seen as movement. A change made by hand during the routine gives Changed by hand. The verdict is fixed when the routine ends. Windows in which the board saw movement are not scored. Repeat means something in the room moved during the hold, or too few quiet windows were left to score. These thresholds are suggestions for a first check, not validated ones.',
        done: 'Check finished: every chair has its verdict.' },
      tapeTag: 'TEST', tape: 'Simulated breathing added to real Wi-Fi packets. These seats are not patients.',
      tableH: 'Every chair: what was put in, and what the board shows', benchTh: ['Seat', 'Who', 'Put in', 'Board reads', 'Board says', 'Check'],
      put: { rate: '{r}/min', hold: 'held {s} s', empty: 'empty chair', off: 'nothing added' },
      mk: { ok: 'within ±2', off: 'off by {d}', flagged: 'pause flagged', missed: 'says no concern', emptyAlert: 'alert on an empty chair', offAlert: 'pause alert, no hold',
        quiet: 'no alert', waitHold: 'holding', noRate: 'no rate shown', wait: 'warming up' },
      chairSub: '{m} · replays sensor {k} of the recording', chairSubRx: '{m} · live packets from your receiver',
      follow: 'Following the scenario: {s}', takeOver: 'Take over this chair', backToScript: 'Back to the scenario', manual: 'You are controlling this chair.',
      rateL: 'Breathing rate', depthL: 'How strongly breathing moves the signal', depthHint: '5% is a person close to the link. At 1.5% v1.3.2 rarely shows a rate.',
      bandL: 'At this rate the board should say', hold: 'Hold breath', release: 'Breathe again', move: 'Shift in seat (6 s)', empty: 'Empty the chair', sit: 'Someone sits down',
      injOnPlay: 'Add breathing to this chair', injOn: 'Add breathing to this chair\'s live packets', nowLine: 'Put in now: {a}. The board shows: {b}.', rxNote: 'Breathing is added only to the chairs you switch on; the others show your receiver\'s packets unchanged. Seats appear as their nodes are heard.',
      clock: '{t} streamed', load: 'computer load {p}%', slow: 'This computer cannot keep up at this speed, so the stream runs slower.',
      noteSample: 'The recording is 2:53 long. It plays forward, then backward, and so on, so the channel never jumps where it repeats; its movement from 1:05 to 1:50 comes back on each pass. Chairs that share one of its three sensors start at different points, and the first 32 s are run straight away so readings appear at once.',
      noteQuiet: 'Only the stretch from 1:52 to 2:53, where nobody in the recording moves, played forward and backward. Chairs that share a sensor start at different points.',
      noteHeldout: 'This run: held-out scenarios {s} of 11. Each new run moves on to the next scenarios and changes which sensor gets which strength (5, 3 or 1.5%), as the notebook\'s held-out sets do.',
      noteCsv: 'Your file {f}: {n} packets from {k} sensors. Each chair replays one of its sensors, forward and backward.', noteCsvAsk: 'Choose a CSV saved from your receiver. An empty room, or people sitting still, works best.',
      scriptDesc: { rate: '{r}/min', change: '{a}/min, then {b}/min from {t}', hold: '{r}/min, holding the breath for {s} s at {t}', none: 'nothing added', empty: 'empty chair' },
      scoreH: 'How the board did', scoreRates: 'Rates: in {n} windows full of breathing the board showed a rate in {c}%, and {p}% of those were within ±2 per minute (mean error {e} per minute).',
      scoreNone: 'Rates are scored once a 30 s window is full of injected breathing.', holdsH: 'Breath-holds',
      holdTh: ['Seat', 'Held for', 'Should it alert?', 'What the board did', '"No breathing concern" during it'],
      yes: 'yes', no: 'no (shorter than {m} s)', notYet: 'not yet', flaggedAfter: 'flagged after {s} s', notFlagged: 'not flagged', moved: 'movement during it, cannot be measured',
      falseNone: 'No pause alerts when nobody held their breath.', falseSome: 'Pause alerts when nobody held their breath: {n} ({x}).', timesN: '{n} updates',
      falseEmpty: 'Pause alerts on a chair with no breathing in it (emptied, or nothing added): {n} ({x}). v1.3.2 has no presence detection (notebook Part 1, Section 6b).',
      scoreNote: 'Scored as in the notebook: 30 s windows the injected breathing fills at least 80% of; a rate is right within ±2 per minute. To check the same packets with the frozen Python v1.3.2, save the truth log and the packets and run: python dashboard/check_inject_bench.py <folder> hinigram_injected.csv hinigram_injection_log.json',
      dlTruth: 'Download the truth log (JSON)', dlCsv: 'Download the injected packets (CSV)', dlScores: 'Download the scores (CSV)', recOn: 'Packets kept for download: {mb} MB.', recFull: 'The packet recording reached 60 MB and stopped; the bench keeps running.',
      metaInject: 'Injection bench: {k} chairs. Known breathing is added to the packets of {f} while they stream. Nothing here is a patient reading.',
      metaInjectRx: 'Injection bench on your receiver: {n} packets from {k} sensors; breathing is added to the chairs you switch on.',
      legInjected: 'Breathing put in (test)', ev: { hold: 'held breath', release: 'breathing again', move: 'shifted in seat', empty: 'chair emptied', sit: 'someone sat down',
        rate: 'rate set to {r}/min', depth: 'strength set to {d}%', on: 'breathing added', off: 'breathing removed', profile: 'now: {p}', script: 'back to the scenario', take: 'taken over' },
      who: { adult: 'adult', child_1_5y: 'child 1-5', infant_2_12m: 'infant', newborn_lt2m: 'newborn' },
      csvErr: 'This file has no CSI_DATA lines, or less than 10 s of them.',
    },
    fil: {
      tagline: 'Pagbabantay ng paghinga sa waiting area', noteMark: 'Paalala',
      disclaimer: 'Paunang pagsusuri (screening) lamang ito, hindi diagnosis. Ang nurse o doktor ang magpapasya. Binabasa nito ang galaw ng paghinga mula sa Wi-Fi signal; hindi ito gumagamit ng camera.',
      srcDemo: 'Demo', srcDemoSub: 'totoong packets, simulated na paghinga', srcSample: 'Sample na recording', srcSampleSub: 'totoong recording',
      srcFile: 'Magbukas ng CSV file', srcFileSub: 'mula sa ESP32 receiver', srcLive: 'Ikonekta ang receiver', srcLiveSub: 'USB, Chrome o Edge',
      now: 'Ngayon', attention: 'Sino ang kailangang tingnan', sorted: 'May sariling ESP32 node ang bawat upuan. Pindutin ang upuan para sa detalye.', room: 'Kung nasaan ang mga sensor',
      schematic: 'Tanaw mula sa itaas, hindi eksakto ang sukat. Nasa sandalan ang node ng bawat upuan, kaya dumadaan sa taong nakaupo ang link nito papunta sa receiver sa sulok.', log: 'Mga nangyari', logSub: 'Pagbabago ng status at mga pagsusuri, pinakabago muna',
      eng: 'Para sa engineers: kalagayan ng sensors', engRate: 'Packets bawat segundo (5 s window)', engRssi: 'Lakas ng signal (dBm)',
      engSteps: 'Gain steps (% ng packets)', engAct: 'Movement index (lampas 1 ay may galaw)',
      foot2: 'Sumusunod ang mga threshold sa NEWS2 para sa adults at sa WHO IMCI para sa mga batang wala pang 5 taon. Kailangan pa itong suriin ng mga Pilipinong clinician bago gamitin sa pasyente.',
      st: { urgent: 'Kailangan ng tulong ngayon', watch: 'Bantayan', typical: 'Walang nakitang problema sa paghinga', no_reading: 'Hindi mabasa', moving: 'Gumagalaw, hinto muna ang pagbasa' },
      short: { urgent: 'tulong ngayon', watch: 'bantayan', typical: 'OK', no_reading: 'hindi mabasa', moving: 'gumagalaw' },
      act: {
        pause: 'Puntahan agad at tingnan ang paghinga nila.', rateUrgent: 'Ipatingin agad sa nurse at kunin ang buong vital signs.',
        watch: 'Suriin ulit sa loob ng 10 minuto.', childFast: 'Ipabilang sa nurse ang hinga nila sa loob ng isang buong minuto at tingnan kung may chest indrawing (paglubog ng ibabang dibdib tuwing humihinga).',
        resumed: 'Pakitingnan po sila.', typical: 'Wala pang kailangang gawin.',
        no_reading: 'Paupuin sila nang tuwid at pakiusapang huwag gumalaw, o bilangin ang hinga nila sa loob ng 60 segundo.',
        moving: 'Babalik ang pagbasa mga 20 segundo matapos silang tumigil sa paggalaw.', warmup: 'Hintayin ang unang pagbasa.',
        lost: 'Tingnan kung may kuryente ang sensor at kung nasa parehong Wi-Fi channel ito.',
      },
      why: {
        pause: 'Walang nakitang galaw ng paghinga sa loob ng {s} segundo.', veryfast: 'Napakabilis ng paghinga: {r} kada minuto. Ang cut-off para sa adult ay 25.',
        fast: 'Mabilis ang paghinga: {r} kada minuto (21 hanggang 24 sa adult).', veryslow: 'Napakabagal ng paghinga: {r} kada minuto (8 pababa).',
        slow: 'Mabagal ang paghinga: {r} kada minuto (9 hanggang 11 sa adult).', typical: 'Paghinga: {r} kada minuto, nasa karaniwang saklaw ng adult (12 hanggang 20).',
        fastage: 'Mabilis ang paghinga para sa edad: {r} kada minuto. Ang cut-off ng WHO ay {c}.', slowage: 'Mabagal ang paghinga para sa edad: {r} kada minuto.',
        typicalage: 'Paghinga: {r} kada minuto, karaniwan para sa edad.', noread: 'Hindi mabasa ng sensor ang paghinga ngayon.',
        moving: 'May galaw, kaya hinto muna ang pagbasa.', warmup: 'Nagsisimula pa lang. Kailangan ng 30 segundong datos bago ang unang pagbasa.',
        resumed: 'Bumalik ang paghinga matapos huminto.', weak: 'Limitado ang pagbantay sa paghinto sa upuang ito dahil mahina ang signal.',
        lost: 'Walang datos mula sa sensor na ito sa loob ng {s} segundo.',
      },
      ann: { pause: 'walang hinga {s} s', moving: 'gumagalaw', now: 'ngayon', lost: 'walang datos' },
      seat: 'Upuan {x}', perMin: 'kada minuto', bpmUnit: 'hinga kada minuto', noReadingShort: 'hindi mabasa', perMinShort: '/min',
      pauseUnit: 'walang galaw ng paghinga', pauseShort: 'hinto {s} s',
      conf: 'Kumpiyansa', confLv: ['Mababa', 'Katamtaman', 'Mataas'], pauseCheck: 'Bantay sa paghinto', pcActive: 'Aktibo', pcLimited: 'Limitado, mahinang signal',
      pcWait: 'Hinihintay ang tuloy-tuloy na pagbasa', updated: 'Huling update', secAgo: '{s} s na ang nakaraan', sensor: 'Sensor', none: 'Wala pa',
      ack: 'Titingnan ko na', acked: 'Tiningnan ng staff noong {t}', profile: 'Sino ang nakaupo rito', details: 'Ipakita ang detalye ng upuan {x}',
      stampBig: 'TININGNAN', stampSmall: 'CHECKED {t}',
      prof: { adult: 'Adult, 16 pataas', child_1_5y: 'Bata, 1 hanggang 5 taon', infant_2_12m: 'Sanggol, 2 hanggang 12 buwan', newborn_lt2m: 'Sanggol, wala pang 2 buwan' },
      waveCap: 'Galaw ng paghinga, huling 30 segundo', waveCapDemo: 'Galaw ng paghinga, huling 30 segundo (simulated na paghinga sa totoong packets)',
      trendCap: 'Bilis ng paghinga ngayong session, sa mga banda ng observation chart', legReading: 'Basa ng Hinigram', legTruth: 'Itinakdang bilis (demo)',
      zone: { typical: 'karaniwan', watch: 'bantayan', urgent: 'tulong ngayon' }, receiver: 'receiver', sensorN: 'sensor {n}', door: 'pinto',
      trendAria: 'Tsart ng bilis ng paghinga. {n} maaasahang pagbasa sa ngayon{range}.', trendRange: ', mula {a} hanggang {b} kada minuto, pinakahuli {c}',
      tipReading: '{r} kada minuto', tipNone: 'Walang maaasahang pagbasa',
      metaDemo: 'Demo na silid: labindalawang upuan sa tatlong hanay, bawat isa may sariling ESP32 node sa sandalan at link papunta sa receiver sa isang sulok sa harap. Tatlo lang ang totoong link sa recording ({f}), kaya ginagamit muli ng bawat upuan ang packets ng isa sa mga ito na may sariling simulated na paghinga. May mga taong gumagalaw sa recording mula mga 1:05 hanggang 1:50.',
      metaSample: 'Sample na recording. Ang totoong {d} segundong recording mula sa tatlong ESP32 sensor ({when}). Wala itong reference ng paghinga, kaya ang tapat na resulta ay halos puro "Hindi mabasa".',
      metaFile: 'Ang file mo na {f}: {n} packets mula sa {k} sensor sa loob ng {d} segundo. Piliin kung sino ang nakaupo sa bawat upuan sa detalye ng upuan; kakalkulahin ulit ang pagbasa.',
      metaLive: 'Live mula sa receiver: {n} packets mula sa {k} sensor.',
      loading: 'Binabasa ang file mo. Ilang segundo ito bawat minuto ng recording.', progress: 'Binabasa ang file mo: tapos na ang {a} sa {b} sensor.',
      noSerial: 'Gumagana ang USB connection kapag na-save ang page na ito at binuksan bilang file sa Chrome o Edge sa computer na nakakabit sa receiver. Puwede ka pa ring magbukas ng naka-save na CSV file dito.',
      serialAsk: 'Piliin ang port ng receiver sa lalabas na tanong ng browser.', serialOn: 'Nakakonekta na. Hinihintay ang packets ({b} baud).', serialLost: 'Naputol ang koneksyon sa receiver.',
      rxBenchEnded: 'Tapos na ang test. Nagsisimula ulit ang live board, kaya walang galing sa idinagdag na paghinga ang ipinapakita nito; babalik ang mga basa pagkalipas ng mga 30 s.',
      testFile: 'Galing ang file na ito sa injection bench: simulated na paghinga na idinagdag sa totoong Wi-Fi packets. Pang-test ito, hindi recording ng pasyente.',
      fileErr: 'Walang CSI_DATA na linya ang file na ito. Pumili ng log mula sa ESP32 receiver.', shortFile: 'Kulang sa 30 segundo ang file na ito, kaya wala pang pagbasa ng paghinga.',
      empty: 'Wala pang pagbabago.', ackLog: 'tiningnan ng staff', play: 'I-play', pause: 'I-pause',
      th: ['Sensor', 'Packets/s', 'Nawala', 'Pinakamahabang puwang', 'RSSI', 'Gain steps', 'Channel', 'Subcarriers'],
      engNote: 'Gamit ang orasan ng receiver. Ang gain steps ay packets na tumalon nang higit 1.5 dB ang kabuuang lakas mula sa naunang packet; nawawala ito kapag ni-lock ang gain ng receiver sa firmware.',
      foot1: '{v}. Ipinapakita: {src}.', srcDemoName: 'demo ({f} na may simulated na paghinga)', srcLiveName: 'live na receiver',
      counts: { urgent: 'kailangan ng tulong', watch: 'bantayan', no_reading: 'hindi mabasa', typical: 'walang problema' },
      heroUrgent1: '{x}: kailangan ng tulong ngayon.', heroUrgentN: '{x}: kailangan ng tulong ngayon.', heroWatch: 'Bantayan ang {x}.',
      heroCalm: 'Walang nangangailangan ng tulong ngayon.', heroNone: 'Wala pang maaasahang pagbasa ngayon.', heroNoRead: 'Hindi mabasa ang {x}.',
      heroOk: 'Walang nakitang problema sa paghinga sa {x}.', seatOne: 'Upuan {x}', seatMany: 'Upuan {x}', and: 'at', seatsList: 'Mga upuan sa waiting area',
      heroOkN: 'Walang nakitang problema sa paghinga sa {n} pang upuan.', rowLabel: 'Hanay {x}', attnH: 'Kailangang tingnan', attnSub: 'Pinakaapurahan muna',
      attnNone: 'Walang kailangang tingnan ngayon.', rxN: 'receiver {n}',
      checkH: 'Suriin ang katumpakan gamit ang ginagabayang paghinga', checkSeat: 'Upuan', checkPlan: 'Mga hakbang', checkStart: 'Simulan ang pacer', checkStop: 'Itigil',
      checkIntro: 'Wi-Fi signal lang ang ginagamit ng Hinigram. Para masuri ito, uupo ang isang tao sa isang upuan at sasabay sa pacer sa mga kilalang bilis, at ihahambing ang mga pagbasa ng Hinigram sa upuang iyon sa mga bilis na iyon. Patakbuhin ito habang nakakonekta ang receiver, o mag-record ng CSV habang tumatakbo ito at buksan dito ang dalawang file pagkatapos.',
      planStd: 'Karaniwan: 8, 12, 16, 20, 24 kada minuto, tig-90 s (mga 10 min)', planShort: 'Maikli: 10, 16, 22 kada minuto, tig-50 s (mga 3 min)',
      checkLoad: 'Buksan ang pacer log para sa file na ito', checkSafe: 'Huminga nang marahan, hindi malalim. Tumigil kung nahihilo o kinakapos ng hininga.',
      cueIn: 'Hinga papasok', cueOut: 'Hinga palabas', cueRest: 'Huminga nang normal', stepRate: '{r} kada minuto, {s} s pa sa hakbang na ito', stepRest: 'Pahinga, {s} s',
      checkNoData: 'Hindi kasabay ng datos na bukas ngayon ang log na ito. Buksan ang CSV na na-record habang tumatakbo ang pagsusuri, saka buksan muli ang log.',
      checkNoSeat: 'Wala sa datos na bukas ngayon ang upuan sa log na ito.', checkUnscored: 'Walang namarkahan dahil walang nakakonektang receiver. I-save ang pacer log; kung may CSV na na-record habang tumatakbo ito, buksan ito rito at saka buksan ang log.', badLog: 'Hindi Hinigram pacer log ang file na iyon.',
      resTarget: 'Bilis ng pacer (/min)', resWin: 'Mga window', resShown: 'May pagbasa', resMed: 'Median na pagbasa', resOk: 'Pasok sa ±2/min', resMae: 'Karaniwang mali (/min)',
      resSummary: 'Upuan {x}: {ok} sa {shown} pagbasa ({p}%) ang pasok sa ±2 kada minuto, at may pagbasa sa {c}% ng {n} window.',
      resWait: 'Nagsisimula ang pagmamarka mga 30 s sa bawat hakbang, kapag buo na ang window sa loob nito.', dlResults: 'I-download ang resulta (CSV)', dlLog: 'I-download ang pacer log', dlFailed: 'Hindi ma-save dito ang file.',
      // injection bench
      srcInject: 'Injection bench', srcInjectSub: 'magdagdag ng kilalang paghinga, live', srcInjectName: 'injection bench ({f} na may idinagdag na simulated na paghinga)',
      benchH: 'Injection bench', benchSub: 'Nagdadagdag ito ng paghingang alam ang bilis sa Wi-Fi packets habang dumadaloy ang mga ito, para makita kung ano ang gagawin ng board. Puwedeng baguhin ang kahit anong upuan habang tumatakbo.',
      bgLabel: 'Packets mula sa', bgSample: 'Sample na recording, buo (may gumagalaw mula 1:05 hanggang 1:50)', bgQuiet: 'Sample na recording, tahimik na bahagi lang (1:52 hanggang 2:53)',
      bgCsv: 'CSV file mula sa receiver mo', bgReceiver: 'Ang receiver mo, live sa USB', chairsLabel: 'Mga upuan', presetLabel: 'Senaryo', speedLabel: 'Bilis', baudLabel: 'Bilis ng serial',
      benchStart: 'Simulan', benchPause: 'I-pause', benchResume: 'Ituloy', benchReset: 'Bagong takbo', benchLoading: 'Sinisimulan...',
      presets: { mixed: 'Halo-halong waiting room', holds: 'Pagsasanay sa pagpigil ng hininga (8 hanggang 25 s)', heldout: 'Mga held-out na senaryo (ang labing-isa, sunud-sunod)', calm: 'Normal ang paghinga ng lahat',
        none: 'Walang idinagdag (hilaw na packets, null test)', manual: 'Lahat 16 kada minuto; ikaw ang magpapatakbo', setup: 'Setup check: iisang 4 minutong routine sa bawat upuan',
        quick: 'Quick check: iisang 2 minutong routine sa bawat upuan' },
      rxNoteAuto: 'Natatanggap ng bawat node ang senaryo pagkarinig dito, at doon nagsisimula ang oras nito. Gumamit ng bakanteng upuan: hahalo ang idinagdag na paghinga sa paghinga ng totoong tao.',
      noteSetup: 'Setup check: humihinga ang bawat upuan nang 12 kada minuto, tapos 20 mula 1:15, pinipigil ang hininga nang 18 s sa 2:30, at gumagalaw sa upuan sa 3:20, mula nang magsimula ito. Sa 4:00 may hatol na ito{end}.',
      noteQuick: 'Quick check: humihinga ang bawat upuan nang 15 kada minuto, pinipigil ang hininga nang 18 s sa 1:02, at gumagalaw sa upuan sa 1:35, mula nang magsimula ito. Sa 2:00 may hatol na ito{end}.',
      setupEndRx: ' at hihinto ang idinagdag na paghinga', setupEndPlay: '; hihinto ang takbo kapag may hatol na ang lahat ng upuan',
      setupH: { setup: 'Setup check', quick: 'Quick check' }, setupTh: ['Upuan', 'Packets', 'Nababasa ang paghinga', 'Pagpigil ng hininga, 18 s', 'Paggalaw sa upuan', 'Hatol'],
      setup: { left: '{t} pa', pk: '{r} kada segundo', reads: 'may bilis {p}%, tama {q}%', weak: 'mahina: may bilis {p}%', wrong: 'tama lang {q}%', few: 'may gumagalaw: kulang ang tahimik na window', nodata: 'kulang ang basa: nawawala ba ang link?', drop: 'huminto nang {s} s', node: 'node {n}',
        flagged: 'nakita pagkalipas ng {s} s', missed: 'hindi nakita', saidOk: 'sabi walang problema', falseAlarm: 'alerto ng paghinto bago pa nagpigil', moved: 'may gumalaw habang nagpipigil', seen: 'nakitang paggalaw', unseen: 'hindi nakita',
        ready: 'Handa', check: 'Suriin', repeat: 'Ulitin', hand: 'Binago nang mano-mano', summary: '{a} sa {n} upuan ang handa.', more: ' Suriin: {b}. Ulitin: {c}.',
        crit: 'Ang Handa ay: karaniwang hindi bababa sa 25 packets kada segundo, at hindi humihinto nang higit 8 s; may bilis na ipinakita sa hindi bababa sa ikatlo ng mga minarkahang window, at pasok sa ±2 kada minuto ang hindi bababa sa 90% ng mga iyon; walang alerto ng paghinto habang humihinga ang upuan, at nakita ang pagpigil ng hininga nang walang "walang problema" habang nagpipigil; nakita bilang paggalaw ang paggalaw sa upuan. Kapag may binago nang mano-mano habang tumatakbo, Binago nang mano-mano ang hatol. Naka-takda na ang hatol pagkatapos ng routine. Hindi minamarkahan ang mga window na may nakitang paggalaw ang board. Ang Ulitin ay may gumalaw sa silid habang nagpipigil, o kulang ang natirang tahimik na window na mamarkahan. Mungkahing hangganan ito para sa unang pagsusuri, hindi pa napatunayan.',
        done: 'Tapos na ang pagsusuri: may hatol na ang bawat upuan.' },
      tapeTag: 'TEST', tape: 'Simulated na paghinga na idinagdag sa totoong Wi-Fi packets. Hindi pasyente ang mga upuang ito.',
      tableH: 'Bawat upuan: ang idinagdag, at ang ipinapakita ng board', benchTh: ['Upuan', 'Sino', 'Idinagdag', 'Basa ng board', 'Sabi ng board', 'Suri'],
      put: { rate: '{r}/min', hold: 'pigil {s} s', empty: 'walang nakaupo', off: 'walang idinagdag' },
      mk: { ok: 'pasok sa ±2', off: 'mali nang {d}', flagged: 'nakita ang paghinto', missed: 'sabi walang problema', emptyAlert: 'alerto sa bakanteng upuan', offAlert: 'alerto ng paghinto, walang pagpigil',
        quiet: 'walang alerto', waitHold: 'nagpipigil', noRate: 'walang ipinakitang bilis', wait: 'nagsisimula pa' },
      chairSub: '{m} · inuulit ang sensor {k} ng recording', chairSubRx: '{m} · live na packets mula sa receiver mo',
      follow: 'Sumusunod sa senaryo: {s}', takeOver: 'Ako na ang hahawak sa upuang ito', backToScript: 'Ibalik sa senaryo', manual: 'Ikaw ang may hawak sa upuang ito.',
      rateL: 'Bilis ng paghinga', depthL: 'Gaano kalakas ginagalaw ng paghinga ang signal', depthHint: '5% ay taong malapit sa link. Sa 1.5%, bihirang magpakita ng bilis ang v1.3.2.',
      bandL: 'Sa bilis na ito, dapat sabihin ng board', hold: 'Pigilin ang hininga', release: 'Huminga ulit', move: 'Gumalaw sa upuan (6 s)', empty: 'Alisan ng nakaupo', sit: 'May umupo',
      injOnPlay: 'Dagdagan ng paghinga ang upuang ito', injOn: 'Dagdagan ng paghinga ang live na packets ng upuang ito', nowLine: 'Idinagdag ngayon: {a}. Ipinapakita ng board: {b}.', rxNote: 'Sa mga upuang binuksan mo lang nadadagdagan ng paghinga; ang iba ay ipinapakita ang packets ng receiver mo nang walang binago. Lumalabas ang mga upuan kapag narinig na ang node nila.',
      clock: '{t} na ang dumaloy', load: 'gamit ng computer {p}%', slow: 'Hindi makasabay ang computer na ito sa bilis na ito, kaya bumabagal ang daloy.',
      noteSample: 'Ang recording ay 2:53 ang haba. Tumatakbo ito pasulong, tapos paatras, at paulit-ulit, kaya hindi tumatalon ang channel kung saan ito umuulit; bumabalik sa bawat ikot ang paggalaw mula 1:05 hanggang 1:50. Magkakaiba ang simula ng mga upuang iisa ang sensor, at agad pinapatakbo ang unang 32 s para may basa agad.',
      noteQuiet: 'Ang bahaging 1:52 hanggang 2:53 lang, kung saan walang gumagalaw sa recording, pasulong at paatras. Magkakaiba ang simula ng mga upuang iisa ang sensor.',
      noteHeldout: 'Ngayong takbo: mga held-out na senaryo {s} sa 11. Sa bawat bagong takbo, lilipat sa mga susunod na senaryo at papalitan kung aling sensor ang may aling lakas (5, 3 o 1.5%), gaya ng held-out sets ng notebook.',
      noteCsv: 'Ang file mo na {f}: {n} packets mula sa {k} sensor. Inuulit ng bawat upuan ang isa sa mga sensor nito, pasulong at paatras.', noteCsvAsk: 'Pumili ng CSV mula sa receiver mo. Pinakamaganda ang bakanteng silid, o mga taong nakaupo nang hindi gumagalaw.',
      scriptDesc: { rate: '{r}/min', change: '{a}/min, tapos {b}/min mula {t}', hold: '{r}/min, pipigilin ang hininga nang {s} s sa {t}', none: 'walang idinagdag', empty: 'walang nakaupo' },
      scoreH: 'Kumusta ang board', scoreRates: 'Bilis: sa {n} window na puno ng paghinga, nagpakita ang board ng bilis sa {c}%, at {p}% sa mga iyon ang pasok sa ±2 kada minuto (karaniwang mali {e} kada minuto).',
      scoreNone: 'Mamarkahan ang bilis kapag may 30 s na window nang puno ng idinagdag na paghinga.', holdsH: 'Mga pagpigil ng hininga',
      holdTh: ['Upuan', 'Gaano katagal', 'Dapat bang mag-alerto?', 'Ginawa ng board', '"Walang problema" habang nagpipigil'],
      yes: 'oo', no: 'hindi (mas maikli sa {m} s)', notYet: 'hindi pa', flaggedAfter: 'nakita pagkalipas ng {s} s', notFlagged: 'hindi nakita', moved: 'may galaw, hindi masukat',
      falseNone: 'Walang alerto ng paghinto kapag walang nagpigil ng hininga.', falseSome: 'Mga alerto ng paghinto kahit walang nagpigil ng hininga: {n} ({x}).', timesN: '{n} update',
      falseEmpty: 'Mga alerto ng paghinto sa upuang walang humihinga (binakante, o walang idinagdag): {n} ({x}). Walang presence detection ang v1.3.2 (notebook Part 1, Section 6b).',
      scoreNote: 'Minamarkahan tulad sa notebook: mga 30 s na window na hindi bababa sa 80% ang puno ng idinagdag na paghinga; tama ang bilis kung pasok sa ±2 kada minuto. Para masuri ang parehong packets sa naka-freeze na Python v1.3.2, i-save ang truth log at ang packets at patakbuhin: python dashboard/check_inject_bench.py <folder> hinigram_injected.csv hinigram_injection_log.json',
      dlTruth: 'I-download ang truth log (JSON)', dlCsv: 'I-download ang packets na may idinagdag (CSV)', dlScores: 'I-download ang marka (CSV)', recOn: 'Packets na naka-save para i-download: {mb} MB.', recFull: 'Umabot na sa 60 MB ang naka-record na packets kaya tumigil ito; tuloy pa rin ang bench.',
      metaInject: 'Injection bench: {k} upuan. Idinadagdag ang kilalang paghinga sa packets ng {f} habang dumadaloy. Walang pasyenteng binabasa rito.',
      metaInjectRx: 'Injection bench sa receiver mo: {n} packets mula sa {k} sensor; nadadagdagan ng paghinga ang mga upuang binuksan mo.',
      legInjected: 'Idinagdag na paghinga (test)', ev: { hold: 'pinigil ang hininga', release: 'huminga ulit', move: 'gumalaw sa upuan', empty: 'nawalan ng nakaupo', sit: 'may umupo',
        rate: 'bilis ginawang {r}/min', depth: 'lakas ginawang {d}%', on: 'dinagdagan ng paghinga', off: 'inalis ang paghinga', profile: 'ngayon: {p}', script: 'ibinalik sa senaryo', take: 'hinawakan nang mano-mano' },
      who: { adult: 'adult', child_1_5y: 'bata 1-5', infant_2_12m: 'sanggol', newborn_lt2m: 'bagong silang' },
      csvErr: 'Walang CSI_DATA na linya ang file na ito, o kulang sa 10 s.',
    },
  };
  let lang = 'en';
  const other = () => (lang === 'en' ? 'fil' : 'en');
  const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => (o && o[k] !== undefined ? o[k] : ''));
  const look = (L, path) => path.split('.').reduce((a, k) => (a ? a[k] : undefined), T[L]);
  const tr = (path, o) => { const v = look(lang, path); return typeof v === 'string' ? fmt(v, o) : v; };
  const trIn = (L, path, o) => { const v = look(L, path); return typeof v === 'string' ? fmt(v, o) : v; };

  // ------------------------------------------------------------------ status icons (shape differs per state, never colour alone)
  const ICON = {
    urgent: '<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path fill-rule="evenodd" d="M11 2 L21 19.5 H1 Z M10 7.5 H12 V14 H10 Z M10 15.6 H12 V17.6 H10 Z" fill="currentColor"/></svg>',
    watch: '<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M11 1.8 L20.2 11 L11 20.2 L1.8 11 Z" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linejoin="miter"/><path d="M11 6.5 V11.5 L14 13.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    typical: '<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="9" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M6.5 11.3 L9.6 14.3 L15.6 8" fill="none" stroke="currentColor" stroke-width="2.4"/></svg>',
    no_reading: '<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><rect x="2.5" y="2.5" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 2.4"/><path d="M7 12.5 H15" stroke="currentColor" stroke-width="2.2"/></svg>',
    moving: '<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M2.5 11 H19.5 M6 7 L2.5 11 L6 15 M16 7 L19.5 11 L16 15" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>',
  };
  const SEVERITY = { urgent: 4, watch: 3, no_reading: 2, moving: 1, typical: 0 };
  const PAUSE_MIN = { adult: 10, child_1_5y: 20, infant_2_12m: 20, newborn_lt2m: 20 };
  const CUT = { newborn_lt2m: 60, infant_2_12m: 50, child_1_5y: 40 };
  const LOW = { newborn_lt2m: 25, infant_2_12m: 20, child_1_5y: 15 };
  const statusHTML = (st, alt) => '<span class="status ' + st + '">' + ICON[st] + '<span>' + esc(tr('st.' + st)) + '</span>' +
    (alt ? '<span class="alt" lang="' + other() + '">' + esc(trIn(other(), 'st.' + st)) + '</span>' : '') + '</span>';
  function stampSVG(time) {
    return '<svg class="stamp" viewBox="0 0 220 94" aria-hidden="true"><g filter="url(#ink)">' +
      '<rect x="4" y="4" width="212" height="86" fill="none" stroke="currentColor" stroke-width="4.5"/>' +
      '<rect x="12" y="12" width="196" height="70" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
      '<text x="110" y="50" text-anchor="middle" font-size="31" font-weight="800" letter-spacing="2.5" fill="currentColor">' + esc(tr('stampBig')) + '</text>' +
      '<text x="110" y="72" text-anchor="middle" font-size="14.5" font-weight="700" letter-spacing="2" fill="currentColor">' + esc(tr('stampSmall', { t: time })) + '</text>' +
      '</g></svg>';
  }

  /** A one-piece plastic chair seen from the front, the seat letter painted on its backrest. The ring is the nurse's
      marker circle around the seat that is open below; CSS shows it only on the selected row. */
  function chairSVG(letter, i) {
    return '<svg class="chair" viewBox="0 0 120 130" aria-hidden="true">' +
      '<path class="ring" d="' + wobblyEllipse(60, 66, 74, 62, (i || 0) + 2) + '"/>' +
      '<path class="rear" d="M32 86 V123 M88 86 V123 M34 66 V76 M86 66 V76"/>' +
      '<rect class="back" x="14" y="6" width="92" height="61" rx="9"/>' +
      '<text class="letter' + (String(letter).length > 1 ? ' two' : '') + '" x="60" y="' + (String(letter).length > 1 ? 50 : 53) + '" text-anchor="middle">' + esc(letter) + '</text>' +
      '<rect class="pan" x="7" y="74" width="106" height="13" rx="4"/>' +
      '<path class="legs" d="M19 88 L13 127 M101 88 L107 127"/>' +
      '</svg>';
  }

  // ------------------------------------------------------------------ state
  const state = { source: 'demo', ds: null, t: 128, playing: false, speed: 1, selected: null, acks: {}, lastKey: '', lastStruct: '',
    live: null, fileDs: null, lastAnnounced: {}, scrubbing: false, pending: null, freshStamp: null };
  let rowBuildKey = '', sheetKey = '', D = null, lastDraw = 0, mapW = 0;
  const rowEls = new Map(), seatEls = new Map();

  function startPoint(name, ds) {
    if (name === 'demo') return reduceMotion ? { t: 140, play: false } : { t: 128, play: true };
    if (name === 'sample') return { t: Math.min(ds.duration, 40), play: !reduceMotion };
    return { t: Math.max(30, ds.duration), play: false }; // a loaded file opens on its full history
  }
  /** Simulated data on screen: the injection bench, or a file saved from it. */
  const isTest = () => state.source === 'inject' || (state.source === 'file' && !!(state.ds && state.ds.test));
  const testTag = () => (isTest() ? '<b class="testtag">' + esc(tr('tapeTag')) + '</b>' : '');
  function setSource(name, ds) {
    // leaving the bench pauses a sample run and ends a receiver run (the live board then starts afresh)
    if (name !== 'inject' && bench.running && bench.kind === 'player') benchRun(false);
    if (name !== 'inject' && bench.kind === 'receiver') benchNew();
    if (name === 'live' && state.live) ds = state.live.ds;
    state.source = name;
    state.ds = ds;
    state.acks = {};
    state.lastAnnounced = {};
    ['demo', 'sample', 'file', 'live', 'inject'].forEach((k) => $('src-' + k).setAttribute('aria-pressed', String(k === name)));
    const live = name === 'live' || name === 'inject';
    $('bench').hidden = name !== 'inject'; $('tape').hidden = !isTest();
    $('btn-play').disabled = live; $('scrub').disabled = live; $('speed').disabled = live;
    $('scrub').min = '30';
    $('scrub').max = String(Math.max(30, ds.duration));
    if (!live) { const sp = startPoint(name, ds); state.t = sp.t; state.playing = sp.play; } else { state.t = ds.duration; state.playing = false; }
    state.selected = null;
    state.lastKey = ''; state.lastStruct = '';
    rowBuildKey = ''; sheetKey = '';
    syncPlay();
    renderAll(true);
  }

  // ------------------------------------------------------------------ data access
  function lastIdx(arr, t) { let lo = 0, hi = arr.length - 1, ans = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (arr[m] <= t + 1e-9) { ans = m; lo = m + 1; } else hi = m - 1; } return ans; }
  function reasonKey(r) {
    if (!r) return 'noread';
    if (r.startsWith('Possible breathing pause')) return 'pause';
    if (r.startsWith('Breathing resumed')) return 'resumed';
    if (r.startsWith('Very fast')) return 'veryfast';
    if (r.startsWith('Fast breathing for age')) return 'fastage';
    if (r.startsWith('Fast breathing')) return 'fast';
    if (r.startsWith('Very slow')) return 'veryslow';
    if (r.startsWith('Slow breathing for age')) return 'slowage';
    if (r.startsWith('Slow breathing')) return 'slow';
    if (r.startsWith('Typical breathing rate for age')) return 'typicalage';
    if (r.startsWith('Typical')) return 'typical';
    if (r.startsWith('Movement')) return 'moving';
    if (r.startsWith('Warming')) return 'warmup';
    return 'noread';
  }
  function seatState(s, t) {
    const h = s.hops;
    const i = lastIdx(h.t, t);
    if (i < 0) return { i: -1, status: 'no_reading', reason: 'Warming up', reasonKey: 'warmup', bpm: null, q: 0, rel: false, mot: false, pause: null, snr: null, ht: null, weak: false };
    const st = { i, status: h.status[i], reason: h.reason[i], reasonKey: reasonKey(h.reason[i]), bpm: h.bpm[i], q: h.q[i], rel: h.rel[i], mot: h.mot[i],
      pause: h.pause[i], snr: h.snr[i], ht: h.t[i], weak: (h.reason[i] || '').indexOf('pause check limited') >= 0 };
    if ((state.source === 'live' || state.source === 'inject') && t - h.t[i] > 8) { st.status = 'no_reading'; st.reasonKey = 'lost'; st.weak = false; st.lostFor = Math.round(t - h.t[i]); }
    return st;
  }
  function recentRate(s, t) {
    // median of the last three reliable readings, the same smoothing the status logic uses
    const h = s.hops, v = [];
    for (let j = lastIdx(h.t, t); j >= 0 && v.length < 3; j--) if (h.rel[j] && h.bpm[j] !== null) v.push(h.bpm[j]);
    if (!v.length) return null;
    v.sort((a, b) => a - b);
    const n = v.length;
    return n % 2 ? v[(n - 1) / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
  }
  function pauseSeconds(s, t) {
    // the pipeline's own estimate of how long breathing movement has been absent (v1.3.1 pause_est)
    const h = s.hops, i = lastIdx(h.t, t);
    if (i < 0) return null;
    const pmin = PAUSE_MIN[s.profile] || 10;
    const p = h.pause[i];
    return Math.round(Math.max(pmin, p !== null && p !== undefined ? p : pmin));
  }
  const showsRate = (st, r) => r !== null && st.reasonKey !== 'lost' && (st.status === 'typical' || st.status === 'watch' || (st.status === 'urgent' && st.reasonKey !== 'pause'));
  function explain(s, st, t) {
    const k = st.reasonKey;
    const r = recentRate(s, t);
    const rr = r === null ? '?' : Math.round(r);
    let why;
    if (k === 'pause') why = tr('why.pause', { s: pauseSeconds(s, t) });
    else if (k === 'lost') why = tr('why.lost', { s: st.lostFor });
    else why = tr('why.' + k, { r: rr, c: CUT[s.profile] || '' });
    if (st.weak) why += ' ' + tr('why.weak');
    let action;
    if (k === 'lost') action = tr('act.lost');
    else if (st.status === 'urgent') action = k === 'pause' ? tr('act.pause') : tr('act.rateUrgent');
    else if (st.status === 'watch') action = k === 'resumed' ? tr('act.resumed') : k === 'fastage' ? tr('act.childFast') : tr('act.watch');
    else if (st.status === 'typical') action = tr('act.typical');
    else if (st.status === 'moving') action = tr('act.moving');
    else action = k === 'warmup' ? tr('act.warmup') : tr('act.no_reading');
    const show = showsRate(st, r);
    // the big number: breaths per minute, or for a pause the seconds without breathing movement
    let num, unit, dim = false, pauseS = null;
    if (k === 'pause') { pauseS = pauseSeconds(s, t); num = pauseS + ' s'; unit = tr('pauseUnit'); }
    else if (show) { num = String(Math.round(r)); unit = null; }
    else { num = '?'; unit = tr('noReadingShort'); dim = true; }
    return { why, action, rate: r, show, num, unit, dim, pauseS };
  }
  function startMs(ds) {
    if (!ds || !ds.start) return null;
    const ms = Date.parse(String(ds.start).replace(/(\.\d{3})\d+/, '$1'));
    return Number.isFinite(ms) ? ms : null;
  }
  function clockAt(ds, t) {
    const ms = startMs(ds);
    if (ms === null) return null;
    const d = new Date(ms + t * 1000 + 8 * 3600e3); // shown in Philippine time
    const p = (x) => String(x).padStart(2, '0');
    return p(d.getUTCHours()) + ':' + p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds());
  }
  function fmtT(t) {
    t = Math.max(0, Math.floor(t));
    const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
    return (h ? h + ':' + String(m).padStart(2, '0') : String(m)) + ':' + String(s).padStart(2, '0');
  }
  function niceStep(range, n) {
    const raw = range / Math.max(1, n), p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }
  function timeStep(dur, px) {
    const steps = [15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];
    const maxTicks = Math.max(2, Math.floor(px / 72));
    for (const s of steps) if (dur / s <= maxTicks) return s;
    return 14400;
  }
  const sortedSeats = (ds, states) => ds.sensors.map((s, i) => [s, states[i]]).sort((a, b) => SEVERITY[b[1].status] - SEVERITY[a[1].status] || a[0].seat.localeCompare(b[0].seat));

  // ------------------------------------------------------------------ main render
  function renderAll(force) {
    const ds = state.ds;
    if (!ds) return;
    const t = state.t;
    const states = ds.sensors.map((s) => seatState(s, t));
    if (state.selected === null || !ds.sensors.some((s) => s.seat === state.selected)) {
      const order = sortedSeats(ds, states);
      state.selected = order.length ? order[0][0].seat : null;
    }
    $('clock').textContent = fmtT(Math.min(t, ds.duration)) + ' / ' + fmtT(ds.duration);
    if (!state.scrubbing) $('scrub').value = String(t);
    const ackKey = Object.keys(state.acks).map((k) => k + (state.acks[k].t <= t ? 1 : 0)).join('');
    const structKey = [lang, state.selected, states.map((x) => x.i + x.status + x.reasonKey).join(','), ackKey, state.source, ds.sensors.map((s) => s.profile).join(',')].join('|');
    const key = structKey + '|' + Math.floor(t);
    if (force || key !== state.lastKey) {
      const structural = force || structKey !== state.lastStruct;
      state.lastKey = key; state.lastStruct = structKey;
      renderSheet(states);
      if (structural) {
        renderCounts(states);
        renderBoard(states);
        renderMap(states, false);
        renderLog();
        renderMeta();
        fillPaceControls();
        if (!pace.run) renderPaceResults();
        if ($('eng').open) renderHealth();
        announce(states);
      }
    }
    drawCanvases(states);
  }

  function renderMeta() {
    const ds = state.ds;
    let s;
    if (state.source === 'demo') s = tr('metaDemo', { f: DATA.sources.sample.file });
    else if (state.source === 'sample') s = tr('metaSample', { d: Math.round(ds.duration), when: ds.start ? ds.start.slice(0, 10) + ', ' + ds.start.slice(11, 16) : '' });
    else if (state.source === 'file') s = tr('metaFile', { f: ds.file, n: ds.packets.toLocaleString(), k: ds.sensors.length, d: Math.round(ds.duration) });
    else if (state.source === 'inject') s = bench.kind === 'receiver' ? tr('metaInjectRx', { n: (ds.packets || 0).toLocaleString(), k: ds.sensors.length }) : tr('metaInject', { k: ds.sensors.length, f: bench.file || '' });
    else s = tr('metaLive', { n: (ds.packets || 0).toLocaleString(), k: ds.sensors.length });
    $('srcmeta').textContent = s;
    const srcName = state.source === 'demo' ? tr('srcDemoName', { f: DATA.sources.sample.file }) : state.source === 'live' ? tr('srcLiveName') :
      state.source === 'inject' ? tr('srcInjectName', { f: bench.kind === 'receiver' ? tr('srcLiveName') : bench.file || '' }) : ds.file;
    $('foot1').textContent = tr('foot1', { v: DATA.version, src: srcName });
  }

  // ---------- one plain sentence on the wall: who needs help, then everyone else
  function seatList(arr) {
    if (arr.length === 1) return tr('seatOne', { x: arr[0] });
    return tr('seatMany', { x: arr.slice(0, -1).join(', ') + ' ' + tr('and') + ' ' + arr[arr.length - 1] });
  }
  function renderCounts(states) {
    const ds = state.ds, by = { urgent: [], watch: [], no_reading: [], typical: [] };
    ds.sensors.map((s, i) => [s.seat, states[i].status]).sort((a, b) => a[0].localeCompare(b[0]))
      .forEach(([seat, st]) => by[st === 'moving' ? 'no_reading' : st].push(seat));
    let head, cls;
    if (by.urgent.length) { head = tr(by.urgent.length > 1 ? 'heroUrgentN' : 'heroUrgent1', { x: seatList(by.urgent) }); cls = 'urgent'; }
    else if (by.watch.length) { head = tr('heroWatch', { x: seatList(by.watch) }); cls = 'watch'; }
    else if (by.typical.length) { head = tr('heroCalm'); cls = 'typical'; }
    else { head = tr('heroNone'); cls = 'no_reading'; }
    const rest = [];
    if (by.urgent.length && by.watch.length) rest.push(tr('heroWatch', { x: seatList(by.watch) }));
    if (by.no_reading.length && (cls !== 'no_reading')) rest.push(tr('heroNoRead', { x: seatList(by.no_reading) }));
    if (by.typical.length && cls !== 'typical') rest.push(by.typical.length > 3 ? tr('heroOkN', { n: by.typical.length }) : tr('heroOk', { x: seatList(by.typical) }));
    const el = $('counts');
    el.className = 'hero ' + cls;
    el.innerHTML = '<p class="big" id="hero-big">' + ICON[cls] + '<span></span></p><p class="rest"></p>';
    el.querySelector('.big span').textContent = head;
    el.querySelector('.rest').textContent = rest.join(' ');
  }

  // ---------- the board: one row per seat, kept in place between updates so focus and clicks survive
  function buildRow(s) {
    const root = document.createElement('li');
    root.className = 'row';
    root.dataset.seat = s.seat;
    root.innerHTML =
      '<canvas class="strip" height="96" aria-hidden="true"></canvas>' +
      '<button type="button" class="seatbtn">' + chairSVG(s.seat, state.ds.sensors.indexOf(s)) + '</button>' +
      '<div class="rhead"><div class="stat"></div><p class="rate"><span class="num"></span><span class="unit"></span></p><p class="who">' + testTag() + '<span class="profile-t"></span><span class="sens"></span></p></div>' +
      '<div class="why"><p class="action"></p><span class="ackwrap"></span></div>';
    const c = { root, seat: root.querySelector('.seatbtn'), stat: root.querySelector('.stat'), num: root.querySelector('.num'), unit: root.querySelector('.unit'),
      prof: root.querySelector('.profile-t'), sens: root.querySelector('.sens'), strip: root.querySelector('canvas'), action: root.querySelector('.action'),
      ack: root.querySelector('.ackwrap'), lastStat: '', lastAck: '' };
    c.seat.setAttribute('aria-label', tr('details', { x: s.seat }));
    c.prof.textContent = tr('prof.' + s.profile);
    c.sens.textContent = s.label;
    c.seat.addEventListener('click', (ev) => { ev.stopPropagation(); select(s.seat); });
    root.addEventListener('click', (ev) => { if (!ev.target.closest('button')) select(s.seat); });
    return c;
  }
  function updateRow(c, s, st) {
    const ex = explain(s, st, state.t);
    const a = state.acks[s.seat];
    const acked = !!(a && a.status === st.status && a.t <= state.t);
    c.root.className = 'row ' + st.status + (acked ? ' isacked' : '') + (s.seat === state.selected ? ' selected' : '');
    c.seat.setAttribute('aria-pressed', String(s.seat === state.selected));
    if (c.lastStat !== st.status) { c.stat.innerHTML = statusHTML(st.status); c.lastStat = st.status; }
    c.num.textContent = ex.num;
    c.num.classList.toggle('dim', ex.dim);
    c.unit.textContent = ex.unit || tr('perMin');
    c.action.textContent = ex.why + ' ' + ex.action;
    const ackState = st.status === 'urgent' || st.status === 'watch' ? (acked ? 'done:' + a.label : 'ask:' + st.status) : 'none';
    if (ackState !== c.lastAck) {
      const hadFocus = c.ack.contains(document.activeElement);
      c.ack.innerHTML = '';
      if (ackState.startsWith('done')) {
        const sp = document.createElement('span'); sp.className = 'sr-only'; sp.textContent = tr('acked', { t: a.label }); c.ack.appendChild(sp);
        c.ack.insertAdjacentHTML('beforeend', stampSVG(a.label));
        if (state.freshStamp === s.seat) { const el = c.ack.querySelector('.stamp'); if (el) el.classList.add('fresh'); state.freshStamp = null; }
      } else if (ackState.startsWith('ask')) {
        const b = document.createElement('button'); b.type = 'button'; b.className = 'ack'; b.textContent = tr('ack');
        b.addEventListener('click', (ev) => { ev.stopPropagation(); acknowledge(s); });
        c.ack.appendChild(b);
      }
      if (hadFocus) c.seat.focus({ preventScroll: true });
      c.lastAck = ackState;
    }
  }
  // seat codes like A1..C4 place a chair in a row; plain letters (A, B, C) put every chair in one row
  const seatPos = (s) => { const m = /^([A-Z])(\d+)$/.exec(s.seat); return m ? { row: m[1], col: +m[2] } : { row: '', col: s.seat.charCodeAt(0) }; };
  function buildSeat(s) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'seat'; b.dataset.seat = s.seat;
    b.innerHTML = '<canvas class="mini" height="56" aria-hidden="true"></canvas>' + chairSVG(s.seat, state.ds.sensors.indexOf(s)) + '<span class="lab"></span>';
    b.addEventListener('click', () => select(s.seat));
    return { root: b, mini: b.querySelector('canvas'), lab: b.querySelector('.lab'), last: '' };
  }
  function updateSeat(c, s, st) {
    const ex = explain(s, st, state.t);
    const a = state.acks[s.seat], acked = !!(a && a.status === st.status && a.t <= state.t);
    c.root.className = 'seat ' + st.status + (acked ? ' isacked' : '') + (s.seat === state.selected ? ' selected' : '');
    c.root.setAttribute('aria-pressed', String(s.seat === state.selected));
    const key = lang + st.status + '|' + ex.num;
    if (key !== c.last) {
      c.lab.innerHTML = ICON[st.status] + '<span></span>';
      c.lab.lastChild.textContent = ex.show ? ex.num : tr('short.' + st.status);
      c.lab.classList.toggle('word', !ex.show);
      c.root.setAttribute('aria-label', tr('seat', { x: s.seat }) + ', ' + tr('st.' + st.status) + (ex.show ? ', ' + ex.num + ' ' + tr('perMin') : '') + '. ' + tr('details', { x: s.seat }));
      c.last = key;
    }
  }
  function renderBoard(states) {
    const ds = state.ds, el = $('cards');
    const bk = lang + '|' + state.source + '|' + ds.sensors.map((s) => s.seat + s.profile + s.label).join(',');
    if (bk !== rowBuildKey) {
      el.innerHTML = ''; seatEls.clear(); rowEls.clear(); $('attn').innerHTML = ''; rowBuildKey = bk;
      const rows = new Map();
      ds.sensors.slice().sort((a, b) => a.seat.localeCompare(b.seat, undefined, { numeric: true })).forEach((s) => {
        const r = seatPos(s).row;
        if (!rows.has(r)) rows.set(r, []);
        rows.get(r).push(s);
      });
      el.style.setProperty('--benches', String(Math.max(1, Math.min(3, rows.size))));
      el.setAttribute('aria-label', tr('seatsList'));
      for (const [r, list] of rows) {
        const li = document.createElement('li');
        li.className = 'bench';
        if (r) { const h = document.createElement('span'); h.className = 'benchlabel'; h.textContent = tr('rowLabel', { x: r }); li.appendChild(h); }
        const wrap = document.createElement('div');
        wrap.className = 'seats';
        wrap.style.setProperty('--k', String(Math.max(3, list.length)));
        list.forEach((s) => { const c = buildSeat(s); seatEls.set(s.seat, c); wrap.appendChild(c.root); });
        li.appendChild(wrap);
        el.appendChild(li);
      }
    }
    ds.sensors.forEach((s, i) => { const c = seatEls.get(s.seat); if (c) updateSeat(c, s, states[i]); });
    renderAttn(states);
  }
  function renderAttn(states) {
    const ds = state.ds, el = $('attn');
    const flagged = sortedSeats(ds, states).filter(([, st]) => st.status === 'urgent' || st.status === 'watch');
    let list = el.querySelector('ol');
    if (!list) {
      el.innerHTML = '<div class="head"><h2 id="attn-h"></h2><span></span></div><p class="none"></p><ol class="attnlist"></ol>';
      el.querySelector('h2').textContent = tr('attnH');
      el.querySelector('.head span').textContent = tr('attnSub');
      el.querySelector('.none').textContent = tr('attnNone');
      list = el.querySelector('ol');
    }
    el.querySelector('.none').hidden = flagged.length > 0;
    const want = flagged.map(([s, st]) => {
      let c = rowEls.get(s.seat);
      if (!c) { c = buildRow(s); rowEls.set(s.seat, c); }
      updateRow(c, s, st);
      return c.root;
    });
    for (const c of rowEls.values()) if (!want.includes(c.root) && c.root.parentNode) c.root.remove();
    const have = Array.from(list.children);
    if (have.length !== want.length || want.some((n, i) => have[i] !== n)) {
      const active = document.activeElement;
      want.forEach((n) => list.appendChild(n));
      if (active && list.contains(active) && document.activeElement !== active) active.focus({ preventScroll: true });
    }
  }
  function acknowledge(s) {
    const st = seatState(s, state.t);
    const clock = clockAt(state.ds, state.t);
    state.acks[s.seat] = { status: st.status, t: state.t, label: clock ? clock.slice(0, 5) : fmtT(state.t) };
    state.freshStamp = s.seat;
    renderAll(true);
  }
  function select(seat) {
    state.selected = seat; renderAll(true);
    if (state.source === 'inject') benchFrame(performance.now(), true); // the chair panel follows the click at once
  }

  // ---------- floor plan: one receiver on the wall; each sensor sits where its straight link to the receiver crosses one chair
  function wobblyEllipse(cx, cy, rx, ry, seed) {
    // a marker circle drawn by hand: slightly uneven, the end overshoots the start
    let d = '';
    const n = 44, start = -0.6 + seed * 0.37, sweep = Math.PI * 2 + 0.45;
    for (let k = 0; k <= n; k++) {
      const a = start + (sweep * k) / n;
      const wob = 1 + 0.035 * Math.sin(3 * a + seed) + 0.02 * Math.sin(7 * a + 2 * seed);
      const grow = 1 + 0.05 * (k / n);
      const x = cx + rx * wob * grow * Math.cos(a), y = cy + ry * wob * grow * Math.sin(a);
      d += (k ? ' L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    return d;
  }
  function renderMap(states, resized) {
    const ds = state.ds, svg = $('map');
    const cw = Math.round(svg.parentElement.clientWidth) || 600;
    const W = Math.max(320, Math.min(760, cw));
    if (resized && Math.abs(W - mapW) < 8) return;
    mapW = W;
    const seats = ds.sensors.map((s, i) => ({ s, i, p: seatPos(s) }));
    const rowKeys = Array.from(new Set(seats.map((x) => x.p.row))).sort();
    const byRow = rowKeys.map((r) => seats.filter((x) => x.p.row === r).sort((a, b) => a.p.col - b.p.col));
    const nCols = Math.max(1, ...byRow.map((r) => r.length));
    const m = 12, top = 96, rowH = W < 480 ? 92 : 104;
    const H = top + byRow.length * rowH + 30;
    const slotW = Math.min(124, (W - 2 * m - 36) / nCols);
    const cwid = Math.max(30, Math.min(56, slotW - 28)), chh = Math.round(cwid * 0.82);
    const x0 = (W - nCols * slotW) / 2;
    const recv = ds.receivers && ds.receivers.length ? ds.receivers : [{ id: 1, corner: 'front-center' }];
    const RX = {};
    recv.forEach((r) => { RX[r.id] = r.corner === 'front-left' ? [m + 24, m + 16] : r.corner === 'front-right' ? [W - m - 24, m + 16] : [W / 2, m + 8]; });
    const act = document.activeElement;
    const focusSeat = act && act.closest && act.closest('#map g.seat') ? act.getAttribute('data-seat') : null;
    const doorW = Math.min(64, W * 0.11), doorX = m + Math.min(40, W * 0.06), yb = H - m;
    let s = '<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">' +
      '<rect width="8" height="8" style="fill:var(--noread-tint)"/><path d="M0 0 V8" style="stroke:var(--pencil)" stroke-width="1.4"/></pattern>' +
      '<pattern id="tiles" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M34 0 V34 H0" fill="none" style="stroke:var(--rule-soft)" stroke-width="1" opacity="0.55"/></pattern></defs>';
    s += '<rect x="' + m + '" y="' + m + '" width="' + (W - 2 * m) + '" height="' + (H - 2 * m) + '" style="fill:url(#tiles)"/>';
    // walls, with the door in the back wall
    s += '<path d="M' + m + ' ' + m + ' H' + (W - m) + ' V' + yb + ' H' + (doorX + doorW) + ' M' + doorX + ' ' + yb + ' H' + m + ' V' + m + '" fill="none" style="stroke:var(--ink)" stroke-width="5" stroke-linecap="square"/>';
    s += '<path d="M' + doorX + ' ' + yb + ' V' + (yb - doorW) + '" style="stroke:var(--ink)" stroke-width="2"/>';
    s += '<path d="M' + doorX + ' ' + (yb - doorW) + ' A' + doorW + ' ' + doorW + ' 0 0 1 ' + (doorX + doorW) + ' ' + yb + '" fill="none" style="stroke:var(--ink-3)" stroke-width="1.2" stroke-dasharray="3 3"/>';
    s += '<text x="' + (doorX + doorW + 8) + '" y="' + (yb - 8) + '" font-size="16" style="fill:var(--ink-3);font-family:var(--hand)">' + esc(tr('door')) + '</text>';
    const pos = {};
    byRow.forEach((row, ri) => row.forEach((x, ci) => { pos[x.s.seat] = [x0 + slotW * (ci + 0.5), top + ri * rowH + rowH * 0.4]; }));
    // links first, so the chairs sit on top: from the node on the backrest to the chair's receiver
    seats.forEach((x) => {
      const c = pos[x.s.seat], r = RX[x.s.rx] || RX[recv[0].id];
      s += '<line x1="' + c[0].toFixed(1) + '" y1="' + (c[1] + chh / 2 + 10).toFixed(1) + '" x2="' + r[0] + '" y2="' + r[1] + '" style="stroke:var(--ink-3)" stroke-width="1.3" stroke-dasharray="2 5"/>';
    });
    recv.forEach((r, k) => {
      const p = RX[r.id];
      s += '<rect x="' + (p[0] - 13) + '" y="' + (p[1] - 6) + '" width="26" height="12" style="fill:var(--ink)"/>';
      s += '<path d="M' + (p[0] - 7) + ' ' + (p[1] - 6) + ' L' + (p[0] - 10) + ' ' + (p[1] - 14) + ' M' + (p[0] + 7) + ' ' + (p[1] - 6) + ' L' + (p[0] + 10) + ' ' + (p[1] - 14) + '" style="stroke:var(--ink)" stroke-width="2.4"/>';
      const right = r.corner === 'front-right';
      const label = recv.length > 1 ? tr('rxN', { n: r.id }) : tr('receiver');
      s += '<text x="' + (right ? p[0] - 20 : p[0] + 20) + '" y="' + (p[1] + 26) + '" text-anchor="' + (right ? 'end' : 'start') + '" font-size="16" style="fill:var(--ink-2);font-family:var(--hand)">' + esc(label) + '</text>';
    });
    seats.forEach((x) => {
      const sen = x.s, i = x.i, st = states[i].status, c = pos[sen.seat];
      const fill = { urgent: 'var(--urgent)', watch: 'var(--watch)', typical: 'var(--typical-tint)', no_reading: 'url(#hatch)', moving: 'url(#hatch)' }[st];
      const ink = { urgent: 'var(--urgent-ink)', watch: 'var(--watch-ink)', typical: 'var(--typical-text)', no_reading: 'var(--noread-text)', moving: 'var(--noread-text)' }[st];
      const txt = { urgent: 'var(--urgent-text)', watch: 'var(--watch-text)', typical: 'var(--typical-text)', no_reading: 'var(--noread-text)', moving: 'var(--noread-text)' }[st];
      const sel = sen.seat === state.selected;
      const x1 = c[0] - cwid / 2, y1 = c[1] - chh / 2;
      const ex = explain(sen, states[i], state.t);
      const label = ex.show ? Math.round(ex.rate) + ' ' + tr('perMinShort') : ex.pauseS !== null ? tr('pauseShort', { s: ex.pauseS }) : tr('short.' + st);
      s += '<g class="seat" data-seat="' + esc(sen.seat) + '" tabindex="0" role="button" aria-pressed="' + sel + '" aria-label="' + esc(tr('seat', { x: sen.seat }) + ', ' + tr('st.' + st) + ', ' + label) + '">';
      s += '<rect class="focusring" x="' + (x1 - 14) + '" y="' + (y1 - 12) + '" width="' + (cwid + 28) + '" height="' + (chh + 52) + '" style="fill:transparent;stroke:transparent"/>';
      if (sel) s += '<path d="' + wobblyEllipse(c[0], c[1] + 8, cwid / 2 + 20, chh / 2 + 26, i + 1) + '" fill="none" style="stroke:var(--brand)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>';
      // one-piece chair from above, facing the front wall: armrests, seat, backrest, and the ESP32 node on the backrest
      s += '<rect x="' + (x1 - 7) + '" y="' + (y1 + 6) + '" width="8" height="' + (chh - 16) + '" style="fill:var(--paper);stroke:var(--ink)" stroke-width="2"/>';
      s += '<rect x="' + (x1 + cwid - 1) + '" y="' + (y1 + 6) + '" width="8" height="' + (chh - 16) + '" style="fill:var(--paper);stroke:var(--ink)" stroke-width="2"/>';
      s += '<rect x="' + x1 + '" y="' + y1 + '" width="' + cwid + '" height="' + chh + '" rx="8" style="fill:' + fill + ';stroke:var(--ink)" stroke-width="2"/>';
      s += '<path d="M' + (x1 + 4) + ' ' + (y1 + chh - 5) + ' Q' + c[0] + ' ' + (y1 + chh + 14) + ' ' + (x1 + cwid - 4) + ' ' + (y1 + chh - 5) + '" fill="none" style="stroke:var(--ink)" stroke-width="5" stroke-linecap="round"/>';
      s += '<rect x="' + (c[0] - 4.5) + '" y="' + (y1 + chh + 5) + '" width="9" height="9" style="fill:var(--brand);stroke:var(--paper)" stroke-width="1.5"/>';
      s += '<text x="' + c[0] + '" y="' + (c[1] + 6) + '" text-anchor="middle" font-size="' + (sen.seat.length > 1 ? 15 : 20) + '" font-weight="800" style="fill:' + ink + '">' + esc(sen.seat) + '</text>';
      s += '<text x="' + c[0] + '" y="' + (y1 + chh + 32) + '" text-anchor="middle" font-size="13.5" font-weight="800" style="fill:' + txt + '">' + esc(label) + '</text>';
      s += '</g>';
    });
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('aria-label', tr('room'));
    svg.innerHTML = s;
    svg.querySelectorAll('g.seat').forEach((g) => {
      g.addEventListener('click', () => select(g.getAttribute('data-seat')));
      g.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); select(g.getAttribute('data-seat')); } });
    });
    if (focusSeat) { const g = svg.querySelector('g.seat[data-seat="' + focusSeat + '"]'); if (g) g.focus({ preventScroll: true }); }
  }

  // ---------- the sheet for the selected seat (built once per seat, updated in place)
  function buildSheet(s) {
    const el = $('detail');
    const canEdit = state.source === 'file' || state.source === 'live' || state.source === 'inject';
    const profOpts = Object.keys(T.en.prof).map((p) => '<option value="' + p + '"' + (p === s.profile ? ' selected' : '') + '>' + esc(tr('prof.' + p)) + '</option>').join('');
    el.innerHTML =
      '<div class="top"><div class="bigseat"></div><div><h3></h3><div class="stat"></div></div>' +
      '<p class="rate"><span class="num"></span><span class="unit"></span></p></div>' +
      '<p class="explain"></p>' +
      '<dl class="facts">' +
      '<div><dt></dt><dd><span class="bars"><i></i><i></i><i></i></span><span class="cv"></span></dd></div>' +
      '<div><dt></dt><dd class="pcv"></dd></div><div><dt></dt><dd class="agov"></dd></div><div><dt></dt><dd class="sensv"></dd></div></dl>' +
      '<label class="profile"><span></span><select' + (canEdit ? '' : ' disabled') + '>' + profOpts + '</select></label>' +
      '<figure><figcaption class="wavecap"></figcaption><canvas class="wave-big" height="150" aria-hidden="true"></canvas></figure>' +
      '<figure><figcaption class="trendcap"></figcaption><div class="legend"></div><canvas class="trend" height="220" role="img"></canvas></figure>';
    D = { el, big: el.querySelector('.bigseat'), h3: el.querySelector('h3'), stat: el.querySelector('.stat'), sel: el.querySelector('select'),
      num: el.querySelector('.rate .num'), unit: el.querySelector('.rate .unit'), explain: el.querySelector('.explain'), bars: el.querySelectorAll('.bars i'),
      cv: el.querySelector('.cv'), pcv: el.querySelector('.pcv'), agov: el.querySelector('.agov'), sensv: el.querySelector('.sensv'),
      wave: el.querySelector('canvas.wave-big'), trend: el.querySelector('canvas.trend'), lastStat: '' };
    D.big.textContent = s.seat;
    D.h3.innerHTML = testTag() + esc(tr('seat', { x: s.seat }));
    el.querySelector('label.profile span').textContent = tr('profile');
    const ks = el.querySelectorAll('.facts dt');
    ks[0].textContent = tr('conf'); ks[1].textContent = tr('pauseCheck'); ks[2].textContent = tr('updated'); ks[3].textContent = tr('sensor');
    D.sensv.textContent = s.label + ' (' + s.mac.slice(-5) + ')';
    el.querySelector('.wavecap').textContent = state.source === 'demo' || state.source === 'inject' ? tr('waveCapDemo') : tr('waveCap');
    el.querySelector('.trendcap').textContent = tr('trendCap');
    el.querySelector('.legend').innerHTML = '<span><i class="dot"></i></span>' + (s.truth ? '<span><i class="dash"></i></span>' : '');
    const legs = el.querySelectorAll('.legend span');
    legs[0].appendChild(document.createTextNode(tr('legReading')));
    if (legs[1]) legs[1].appendChild(document.createTextNode(tr(state.source === 'inject' ? 'legInjected' : 'legTruth')));
    D.sel.addEventListener('change', () => changeProfile(s, D.sel.value));
    attachTip(D.trend, (x) => trendTip(s, D.trend, x));
  }
  function renderSheet(states) {
    const ds = state.ds;
    const i = ds.sensors.findIndex((s) => s.seat === state.selected);
    if (i < 0) { $('detail').innerHTML = ''; D = null; sheetKey = ''; return; }
    const s = ds.sensors[i], st = states[i];
    const k = lang + '|' + state.source + '|' + s.seat + '|' + s.profile + '|' + s.mac;
    if (k !== sheetKey || !D) { buildSheet(s); sheetKey = k; }
    const ex = explain(s, st, state.t);
    if (D.lastStat !== st.status) { D.stat.innerHTML = statusHTML(st.status, true); D.big.className = 'bigseat ' + st.status; D.lastStat = st.status; }
    D.num.textContent = ex.num;
    D.num.classList.toggle('dim', ex.dim);
    D.unit.textContent = ex.unit || tr('bpmUnit');
    D.explain.textContent = ex.why + ' ' + ex.action;
    const q = st.rel ? st.q : 0;
    const lv = !ex.show ? -1 : q >= 0.75 ? 2 : q >= 0.5 ? 1 : 0;
    D.bars.forEach((b, j) => b.classList.toggle('on', j <= lv));
    D.cv.textContent = lv < 0 ? tr('none') : tr('confLv')[lv];
    D.pcv.textContent = st.snr === null || st.snr === undefined ? tr('pcWait') : st.snr >= 3 ? tr('pcActive') : tr('pcLimited');
    D.agov.textContent = st.ht === null ? tr('none') : tr('secAgo', { s: Math.max(0, Math.round(state.t - st.ht)) });
    const h = s.hops, vals = [];
    for (let j = 0; j < h.t.length && h.t[j] <= state.t; j++) if (h.rel[j] && h.bpm[j] !== null) vals.push(h.bpm[j]);
    const range = vals.length ? tr('trendRange', { a: Math.round(Math.min.apply(null, vals)), b: Math.round(Math.max.apply(null, vals)), c: Math.round(vals[vals.length - 1]) }) : '';
    D.trend.setAttribute('aria-label', tr('trendAria', { n: vals.length, range }));
  }

  // ---------- logbook
  function renderLog() {
    const ds = state.ds, el = $('log');
    const ev = [];
    ds.sensors.forEach((s) => {
      const h = s.hops;
      let prev = null;
      for (let i = 0; i < h.t.length && h.t[i] <= state.t + 1e-9; i++) {
        if (h.status[i] !== prev) { ev.push({ t: h.t[i], seat: s.seat, st: h.status[i] }); prev = h.status[i]; }
      }
    });
    Object.keys(state.acks).forEach((seat) => { if (state.acks[seat].t <= state.t) ev.push({ t: state.acks[seat].t, seat, ack: true }); });
    if (state.source === 'inject') benchLogEvents().forEach((e) => { if (e.t <= state.t + 1e-9) ev.push(e); });
    ev.sort((a, b) => b.t - a.t || (b.ack ? 1 : 0) - (a.ack ? 1 : 0));
    el.innerHTML = '';
    if (!ev.length) { const li = document.createElement('li'); li.className = 'empty'; li.textContent = tr('empty'); el.appendChild(li); return; }
    for (const e of ev.slice(0, 60)) {
      const li = document.createElement('li');
      const tm = document.createElement('time');
      const c = clockAt(ds, e.t);
      tm.textContent = c ? c.slice(0, 5) + ':' + c.slice(6, 8) : fmtT(e.t);
      const body = document.createElement('span');
      body.className = 'entry';
      const b = document.createElement('b');
      b.textContent = tr('seat', { x: e.seat });
      body.appendChild(b);
      if (e.ack) { const sn = document.createElement('span'); sn.className = 'stampnote'; sn.textContent = tr('ackLog'); body.appendChild(sn); }
      else if (e.test) { const sn = document.createElement('span'); sn.className = 'test'; sn.textContent = e.test; body.appendChild(sn); }
      else body.insertAdjacentHTML('beforeend', testTag() + statusHTML(e.st));
      li.appendChild(tm); li.appendChild(body);
      el.appendChild(li);
    }
  }

  // ---------- engineer panel
  function renderHealth() {
    const ds = state.ds, tb = $('healthtable');
    const th = tr('th');
    let h = '<thead><tr>' + th.map((x, i) => '<th' + (i > 0 && i < 6 ? ' class="num"' : '') + ' scope="col">' + esc(x) + '</th>').join('') + '</tr></thead><tbody>';
    ds.sensors.forEach((s, i) => {
      const H = s.health || {};
      const f = (v, d) => (v === undefined || v === null || Number.isNaN(v) ? '?' : Number(v).toFixed(d));
      const raw = (v) => esc(v === undefined || v === null ? '?' : v);
      h += '<tr><td><span class="key" style="background:var(--s' + ((i % 3) + 1) + ')"></span>' + esc(s.label + ' (' + s.mac.slice(-5) + ')') + '</td>' +
        '<td class="num">' + f(H.rate_hz, 1) + '</td><td class="num">' + f(H.loss_pct, 1) + '%</td><td class="num">' + f(H.max_gap_ms, 0) + ' ms</td>' +
        '<td class="num">' + f(H.rssi_mean_dbm, 0) + ' dBm</td><td class="num">' + f(H.gain_step_pct, 0) + '%</td><td>' + raw(H.channel) + '</td><td>' + raw(H.valid_subcarriers) + '</td></tr>';
    });
    tb.innerHTML = h + '</tbody>';
    $('engnote').textContent = tr('engNote');
    $('eng-legend').innerHTML = ds.sensors.map((s, i) => '<span><i class="sw" style="background:var(--s' + ((i % 3) + 1) + ')"></i>' + esc(s.label) + '</span>').join('');
  }

  // ---------- screen-reader announcements on status changes during playback or live
  function announce(states) {
    const ds = state.ds;
    const speak = state.playing || state.source === 'live' || state.source === 'inject';
    ds.sensors.forEach((s, i) => {
      const st = states[i];
      const prev = state.lastAnnounced[s.seat];
      if (speak && prev !== undefined && prev !== st.status) {
        const ex = explain(s, st, state.t);
        const msg = (isTest() ? tr('tapeTag') + ': ' : '') + tr('seat', { x: s.seat }) + ': ' + tr('st.' + st.status) + '. ' + ex.why + ' ' + ex.action;
        if (st.status === 'urgent') $('announce-urgent').textContent = msg; else $('announce').textContent = msg;
      }
      state.lastAnnounced[s.seat] = st.status;
    });
  }

  // ------------------------------------------------------------------ canvases
  function setupCanvas(c) {
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(c.getBoundingClientRect().width || c.parentElement.clientWidth || 300);
    // the designed CSS height, read once: setting c.height below rewrites the height attribute, so reading it every
    // frame doubled the canvas on every redraw on screens with more than one pixel per CSS pixel (v1.3.2 bug)
    if (c._cssH === undefined) c._cssH = parseFloat(c.getAttribute('height')) || 100;
    const h = c._cssH;
    if (c._w !== w || c._dpr !== dpr || c._h !== h) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); c.style.height = h + 'px'; c._w = w; c._h = h; c._dpr = dpr; }
    const ctx = c.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return { ctx, w, h };
  }
  function motionSpans(s, t0, t1) {
    const h = s.hops, out = [];
    for (let i = 0; i < h.t.length; i++) {
      if (!h.mot[i] || h.t[i] < t0 - 2 || h.t[i] - 2 > t1) continue;
      const a = h.t[i] - 2, b = h.t[i];
      if (out.length && a <= out[out.length - 1][1] + 0.01) out[out.length - 1][1] = b; else out.push([a, b]);
    }
    return out;
  }
  /** Strip chart: the paper (grid) moves with time, the pen stays at the right edge, nurse marks annotate it. */
  function drawStrip(c, s, st, t, span, opts) {
    if (!c) return;
    const g = setupCanvas(c), ctx = g.ctx, W = g.w, H = g.h;
    const xr = W - 7, pxps = xr / span;
    const X = (tt) => xr - (t - tt) * pxps;
    const mid = Math.round(H / 2);
    ctx.lineWidth = 1;
    if (opts.bare) {
      ctx.strokeStyle = css('--wall-guide'); ctx.setLineDash([2, 6]);
      ctx.beginPath(); ctx.moveTo(0, mid + 0.5); ctx.lineTo(W, mid + 0.5); ctx.stroke(); ctx.setLineDash([]);
    } else {
      let minorT = 0.5;
      if (minorT * pxps < 6) minorT = 1;
      const cell = minorT * pxps;
      const k0 = Math.floor((t - span - 1) / minorT), k1 = Math.floor(t / minorT);
      for (let k = k0; k <= k1; k++) {
        const x = Math.round(X(k * minorT)) + 0.5;
        if (x < 0 || x > W) continue;
        ctx.strokeStyle = css(k % 5 === 0 ? '--grid-major' : '--grid-minor');
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
      }
      const nh = Math.ceil(mid / cell);
      for (let j = -nh; j <= nh; j++) {
        const y = Math.round(mid + j * cell) + 0.5;
        if (y < 0 || y > H) continue;
        ctx.strokeStyle = css(j % 5 === 0 ? '--grid-major' : '--grid-minor');
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
      }
    }
    // pencil hatching where the sensor saw movement
    ctx.font = '700 15px ' + HAND();
    for (const [a, b] of motionSpans(s, t - span, t)) {
      const x0 = Math.max(0, X(a)), x1 = Math.min(xr, X(b));
      if (x1 - x0 < 2) continue;
      ctx.save();
      ctx.beginPath(); ctx.rect(x0, 0, x1 - x0, H); ctx.clip();
      ctx.strokeStyle = css('--pencil'); ctx.globalAlpha = 0.35; ctx.lineWidth = 1;
      for (let x = x0 - H; x < x1 + H; x += 7) { ctx.beginPath(); ctx.moveTo(x, H); ctx.lineTo(x + H, 0); ctx.stroke(); }
      ctx.restore();
      if (x1 - x0 > 44) { ctx.fillStyle = css('--noread-text'); ctx.fillText(tr('ann.moving'), x0 + 5, 16); }
    }
    // the trace
    const Wv = s.wave;
    const quiet = st.status === 'no_reading' || st.status === 'moving' || st.reasonKey === 'pause';
    const amp = (H / 2 - 9) / 2.6, gain = quiet ? 0.6 : 1;
    const Y = (v) => mid - 2.6 * Math.tanh((gain * v) / 2.6) * amp;
    let lastX = null, lastY = null;
    if (Wv && Wv.v && Wv.v.length) {
      const i0 = Math.max(0, Math.ceil((t - span - Wv.t0) * Wv.fs)), i1 = Math.min(Wv.v.length - 1, Math.floor((t - Wv.t0) * Wv.fs));
      if (i1 > i0) {
        ctx.beginPath();
        for (let i = i0; i <= i1; i++) { const x = X(Wv.t0 + i / Wv.fs), y = Y(Wv.v[i]); if (i === i0) ctx.moveTo(x, y); else ctx.lineTo(x, y); lastX = x; lastY = y; }
        ctx.strokeStyle = quiet ? css('--pencil') : css('--trace');
        ctx.lineWidth = opts.thick ? 2.4 : 2;
        ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        ctx.stroke();
      }
    }
    if (lastX !== null) {
      ctx.fillStyle = quiet ? css('--pencil') : css('--trace');
      ctx.beginPath(); ctx.arc(lastX, lastY, opts.thick ? 4 : 3.4, 0, Math.PI * 2); ctx.fill();
    }
    ctx.font = '700 14px ' + HAND(); ctx.fillStyle = css('--ink-3');
    if (!opts.mini) ctx.fillText(span + ' s', 4, H - 6);
    // nurse marks: bracket the stretch without breathing
    if (st.reasonKey === 'pause') {
      const ps = pauseSeconds(s, t) || 0;
      const x0 = Math.max(4, X(t - ps)), x1 = xr - 2, yb = 22;
      ctx.strokeStyle = css('--urgent-text'); ctx.fillStyle = css('--urgent-text'); ctx.lineWidth = 2; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(x0, yb + 7); ctx.lineTo(x0, yb); ctx.lineTo(x1, yb); ctx.lineTo(x1, yb + 7); ctx.stroke();
      if (opts.mini) return;
      const label = tr('ann.pause', { s: ps });
      ctx.font = '700 ' + (opts.thick ? 18 : 16) + 'px ' + HAND();
      const tw = ctx.measureText(label).width;
      ctx.fillText(label, Math.max(4, Math.min(x1 - tw, x0 + 4)), yb - 6);
    } else if (st.reasonKey === 'lost' && !opts.mini) {
      ctx.font = '700 16px ' + HAND(); ctx.fillStyle = css('--noread-text'); ctx.fillText(tr('ann.lost'), xr - ctx.measureText(tr('ann.lost')).width - 6, 18);
    }
  }
  function zonesFor(profile) {
    if (profile === 'adult') return [[0, 8.5, 'urgent'], [8.5, 11.5, 'watch'], [11.5, 20.5, 'typical'], [20.5, 24.5, 'watch'], [24.5, 400, 'urgent']];
    return [[0, LOW[profile], 'watch'], [LOW[profile], CUT[profile], 'typical'], [CUT[profile], 400, profile === 'newborn_lt2m' ? 'urgent' : 'watch']];
  }
  function drawHover(ctx, c, X, Tp, ph) {
    if (c._hoverT === undefined || c._hoverT === null) return;
    ctx.strokeStyle = css('--ink-2'); ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(X(c._hoverT), Tp); ctx.lineTo(X(c._hoverT), Tp + ph); ctx.stroke(); ctx.setLineDash([]);
  }
  /** Observation chart: bands like a NEWS2 chart (paper white = usual, yellow = watch, red = help now), readings as ink dots. */
  function drawObs(c, s, t) {
    if (!c) return;
    const g = setupCanvas(c), ctx = g.ctx, ds = state.ds;
    ctx.font = '700 15px ' + HAND();
    const zl = Object.values(T[lang].zone).reduce((mx, z) => Math.max(mx, ctx.measureText(z).width), 0);
    const L = 34, R = Math.ceil(zl) + 14, Tp = 22, B = 24;
    const pw = Math.max(40, g.w - L - R), ph = g.h - Tp - B;
    const dur = Math.max(ds.duration, 30);
    c._geom = { L, pw, dur };
    const h = s.hops;
    let vmax = 40;
    for (let k = 0; k < h.t.length; k++) if (h.bpm[k] !== null && h.t[k] <= t) vmax = Math.max(vmax, h.bpm[k]);
    if (s.truth) for (const v of s.truth.bpm) if (v !== null) vmax = Math.max(vmax, v);
    const ymax = Math.ceil((vmax * 1.12) / 10) * 10;
    const X = (tt) => L + (tt / dur) * pw, Y = (v) => Tp + ph - (v / ymax) * ph;
    for (const [a, b, z] of zonesFor(s.profile)) {
      if (a >= ymax) continue;
      const y0 = Y(Math.min(b, ymax)), y1 = Y(a);
      if (z !== 'typical') { ctx.fillStyle = css(z === 'urgent' ? '--urgent-tint' : '--watch-tint'); ctx.fillRect(L, y0, pw, y1 - y0); }
      if (y1 - y0 >= 16) { ctx.fillStyle = css(z === 'urgent' ? '--urgent-text' : z === 'watch' ? '--watch-text' : '--typical-text'); ctx.fillText(tr('zone.' + z), L + pw + 8, (y0 + y1) / 2 + 5); }
    }
    ctx.lineWidth = 1; ctx.font = '13px ' + FONT();
    const ystep = ymax > 60 ? 20 : 10;
    ctx.textAlign = 'right'; ctx.fillStyle = css('--ink-3');
    for (let v = 0; v <= ymax; v += ystep / 2) {
      const y = Math.round(Y(v)) + 0.5, major = v % ystep === 0;
      ctx.strokeStyle = css(major ? '--grid-major' : '--grid-minor');
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(L + pw, y); ctx.stroke();
      if (major) ctx.fillText(String(v), L - 6, y + 4);
    }
    ctx.textAlign = 'center';
    const step = timeStep(dur, pw);
    for (let tt = 0; tt <= dur + 1e-9; tt += step) {
      const x = Math.round(X(tt)) + 0.5;
      ctx.strokeStyle = css('--grid-minor'); ctx.beginPath(); ctx.moveTo(x, Tp); ctx.lineTo(x, Tp + ph); ctx.stroke();
      ctx.fillText(fmtT(tt), Math.min(Math.max(x, L + 14), L + pw - 14), g.h - 6);
    }
    ctx.textAlign = 'left';
    ctx.strokeStyle = css('--ink'); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(L, Tp + ph + 0.5); ctx.lineTo(L + pw, Tp + ph + 0.5); ctx.stroke();
    if (s.truth) {
      ctx.strokeStyle = css('--pencil'); ctx.lineWidth = 2; ctx.setLineDash([6, 5]); ctx.beginPath();
      let pen = false;
      s.truth.t.forEach((tt, k) => { const v = s.truth.bpm[k]; if (v === null || tt > t) { pen = false; return; } if (!pen) { ctx.moveTo(X(tt), Y(v)); pen = true; } else ctx.lineTo(X(tt), Y(v)); });
      ctx.stroke(); ctx.setLineDash([]);
    }
    // readings: ink dots joined like a hand-plotted chart, broken across gaps
    ctx.strokeStyle = css('--trace'); ctx.lineWidth = 1.4; ctx.beginPath();
    let prevT = null;
    for (let k = 0; k < h.t.length; k++) {
      if (h.t[k] > t || !h.rel[k] || h.bpm[k] === null) { continue; }
      const x = X(h.t[k]), y = Y(Math.min(h.bpm[k], ymax));
      if (prevT !== null && h.t[k] - prevT <= 4.1) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      prevT = h.t[k];
    }
    ctx.stroke();
    const spacing = (pw * 2) / dur, r = Math.max(2, Math.min(3.6, spacing / 2.2));
    ctx.fillStyle = css('--trace');
    for (let k = 0; k < h.t.length; k++) {
      if (h.t[k] > t || !h.rel[k] || h.bpm[k] === null) continue;
      ctx.beginPath(); ctx.arc(X(h.t[k]), Y(Math.min(h.bpm[k], ymax)), r, 0, Math.PI * 2); ctx.fill();
    }
    // "now" pencil line with a handwritten label
    const xn = X(t);
    ctx.strokeStyle = css('--ink-2'); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(xn, Tp - 2); ctx.lineTo(xn, Tp + ph); ctx.stroke();
    ctx.font = '700 15px ' + HAND(); ctx.fillStyle = css('--ink-2');
    const nl = tr('ann.now'), nw = ctx.measureText(nl).width;
    ctx.fillText(nl, Math.min(xn - nw / 2, L + pw - nw), Tp - 7);
    drawHover(ctx, c, X, Tp, ph);
  }
  function trendTip(s, c, x) {
    const G = c._geom; if (!G) return null;
    const tt = ((x - G.L) / G.pw) * G.dur;
    if (tt < 0 || tt > Math.min(G.dur, state.t) + 1) { c._hoverT = null; return null; }
    const h = s.hops, i = lastIdx(h.t, Math.min(tt, state.t));
    if (i < 0) { c._hoverT = null; return null; }
    c._hoverT = h.t[i];
    const clock = clockAt(state.ds, h.t[i]);
    const reading = h.rel[i] && h.bpm[i] !== null ? tr('tipReading', { r: Math.round(h.bpm[i]) }) : tr('tipNone');
    return '<b>' + esc(clock ? clock + ' (' + fmtT(h.t[i]) + ')' : fmtT(h.t[i])) + '</b><br>' + esc(reading) + '<br>' + esc(tr('st.' + h.status[i]));
  }
  function drawEng(id, key, t) {
    const c = $(id); if (!c) return;
    const g = setupCanvas(c), ctx = g.ctx, ds = state.ds;
    const L = 40, R = 10, Tp = 8, B = 22, pw = g.w - L - R, ph = g.h - Tp - B;
    const dur = Math.max(ds.duration, 30);
    let lo = Infinity, hi = -Infinity;
    ds.sensors.forEach((s) => s.series[key].forEach((v) => { if (v !== null) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
    if (!Number.isFinite(lo)) return;
    if (key === 'rate') { lo = 0; hi = Math.max(35, hi); }
    if (key === 'steps') { lo = 0; hi = 100; }
    if (key === 'act') { lo = 0; hi = Math.max(2, Math.min(hi, 12)); }
    const step = niceStep(hi - lo || 1, 4);
    const y0 = Math.floor(lo / step) * step, y1 = Math.max(Math.ceil(hi / step) * step, y0 + step);
    const fmtv = (v) => (step < 1 ? v.toFixed(1) : v.toFixed(0));
    c._geom = { L, pw, dur, key, fmtv };
    const X = (tt) => L + (tt / dur) * pw, Y = (v) => Tp + ph - ((v - y0) / (y1 - y0)) * ph;
    ctx.fillStyle = css('--ink-3'); ctx.font = '12px ' + FONT(); ctx.lineWidth = 1;
    ctx.textAlign = 'right';
    for (let v = y0; v <= y1 + step * 1e-6; v += step) { const y = Math.round(Y(v)) + 0.5; ctx.strokeStyle = css('--grid-major'); ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(L + pw, y); ctx.stroke(); ctx.fillText(fmtv(v), L - 6, y + 4); }
    ctx.textAlign = 'center';
    const tstep = timeStep(dur, pw);
    for (let tt = 0; tt <= dur + 1e-9; tt += tstep) ctx.fillText(fmtT(tt), Math.min(Math.max(X(tt), L + 14), L + pw - 14), g.h - 5);
    ctx.textAlign = 'left';
    if (key === 'act') { ctx.strokeStyle = css('--ink-2'); ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.moveTo(L, Y(1)); ctx.lineTo(L + pw, Y(1)); ctx.stroke(); ctx.setLineDash([]); }
    ds.sensors.forEach((s, i) => {
      const ser = s.series; ctx.strokeStyle = css('--s' + ((i % 3) + 1)); ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.beginPath();
      let pen = false;
      ser.t.forEach((tt, k) => { const v = ser[key][k]; if (v === null || tt > t) { pen = false; return; } const y = Y(Math.min(v, y1)); if (!pen) { ctx.moveTo(X(tt), y); pen = true; } else ctx.lineTo(X(tt), y); });
      ctx.stroke();
    });
    ctx.strokeStyle = css('--ink-2'); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(X(t), Tp); ctx.lineTo(X(t), Tp + ph); ctx.stroke();
    drawHover(ctx, c, X, Tp, ph);
  }
  function engTip(c, x) {
    const G = c._geom, ds = state.ds; if (!G || !ds) return null;
    const tt = ((x - G.L) / G.pw) * G.dur;
    if (tt < 0 || tt > Math.min(G.dur, state.t)) { c._hoverT = null; return null; }
    const ser0 = ds.sensors[0].series, k = lastIdx(ser0.t, tt);
    if (k < 0) { c._hoverT = null; return null; }
    c._hoverT = ser0.t[k];
    let html = '<b>' + esc(fmtT(ser0.t[k])) + '</b>';
    ds.sensors.forEach((s) => { const v = s.series[G.key][k]; html += '<br>' + esc(s.label + ': ' + (v === null || v === undefined ? '?' : G.fmtv(v))); });
    return html;
  }
  function attachTip(canvas, fn) {
    const wrap = canvas.parentElement;
    let tip = wrap.querySelector('.tip');
    if (!tip) { tip = document.createElement('div'); tip.className = 'tip'; tip.hidden = true; wrap.appendChild(tip); }
    const move = (ev) => {
      const r = canvas.getBoundingClientRect();
      const x = ev.clientX - r.left, y = ev.clientY - r.top;
      const html = fn(x);
      if (!html) { tip.hidden = true; lastDraw = 0; return; }
      tip.innerHTML = html; tip.hidden = false;
      const tw = tip.offsetWidth, thh = tip.offsetHeight;
      let left = x + 14; if (left + tw > r.width) left = x - tw - 14; if (left < 0) left = 0;
      tip.style.left = left + 'px';
      tip.style.top = Math.max(0, canvas.offsetTop + y - thh - 8) + 'px';
      lastDraw = 0;
    };
    canvas.addEventListener('pointermove', move);
    canvas.addEventListener('pointerdown', move);
    canvas.addEventListener('pointerleave', () => { tip.hidden = true; canvas._hoverT = null; lastDraw = 0; });
  }
  function drawCanvases(states) {
    const now = performance.now();
    if (now - lastDraw < 33) return;
    lastDraw = now;
    const ds = state.ds, t = state.t;
    ds.sensors.forEach((s, i) => {
      const m = seatEls.get(s.seat); if (m) drawStrip(m.mini, s, states[i], t, 12, { thick: false, bare: true, mini: true });
      const c = rowEls.get(s.seat); if (c && c.root.isConnected) drawStrip(c.strip, s, states[i], t, 20, { thick: false });
    });
    const i = ds.sensors.findIndex((s) => s.seat === state.selected);
    if (i >= 0 && D) { drawStrip(D.wave, ds.sensors[i], states[i], t, 30, { thick: true }); drawObs(D.trend, ds.sensors[i], t); }
    if ($('eng').open) { drawEng('eng-rate', 'rate', t); drawEng('eng-rssi', 'rssi', t); drawEng('eng-steps', 'steps', t); drawEng('eng-act', 'act', t); }
  }

  // ------------------------------------------------------------------ paced-breathing accuracy check
  // The reference is the pacer itself: the person breathes with it at known rates, and the chair's readings are scored
  // against those rates. Only 30 s windows that lie wholly inside a step count, so each step's first ~30 s is not scored.
  const PLANS = { standard: { rates: [8, 12, 16, 20, 24], step: 90, rest: 30 }, short: { rates: [10, 16, 22], step: 50, rest: 10 } };
  const pace = { run: null, log: null };
  function planSteps(name) {
    const p = PLANS[name], out = [];
    let t = 0;
    p.rates.forEach((r, k) => {
      out.push({ rate: r, start_s: t, end_s: t + p.step }); t += p.step;
      if (k < p.rates.length - 1) { out.push({ rest: true, start_s: t, end_s: t + p.rest }); t += p.rest; }
    });
    return out;
  }
  function fillPaceControls() {
    const ds = state.ds, sel = $('pace-seat');
    if (!ds || !sel) return;
    const keep = sel.value;
    sel.innerHTML = ds.sensors.map((x) => '<option value="' + esc(x.seat) + '">' + esc(tr('seat', { x: x.seat })) + '</option>').join('');
    if (ds.sensors.some((x) => x.seat === keep)) sel.value = keep;
    const plan = $('pace-plan');
    plan.options[0].textContent = tr('planStd'); plan.options[1].textContent = tr('planShort');
    $('pace-start').textContent = pace.run ? tr('checkStop') : tr('checkStart');
    $('pace-load').hidden = state.source !== 'file';
    sel.disabled = plan.disabled = !!pace.run;
  }
  function startPace() {
    if (pace.run) { stopPace(false); return; }
    const ds = state.ds;
    if (!ds || !ds.sensors.length) return;
    const seat = $('pace-seat').value, plan = $('pace-plan').value, x = ds.sensors.find((y) => y.seat === seat);
    pace.run = { kind: 'hinigram-paced-check', seat, mac: x ? x.mac : '', plan, steps: planSteps(plan), wall0: performance.now(),
      startedAt: new Date().toISOString(), t0: state.source === 'live' ? state.t : null, scored: state.source === 'live', lastScore: -1 };
    pace.log = null;
    $('pacer').hidden = false;
    $('pace-results').innerHTML = '';
    fillPaceControls();
  }
  function stopPace(done) {
    const r = pace.run;
    if (!r) return;
    pace.log = { kind: 'hinigram-paced-check', version: 1, seat: r.seat, mac: r.mac, plan: r.plan, startedAt: r.startedAt,
      ran_s: Math.round((performance.now() - r.wall0) / 100) / 10, complete: !!done, steps: r.steps, liveStart_t: r.t0, source: state.source };
    pace.run = null;
    $('pacer').hidden = true;
    fillPaceControls();
    renderPaceResults();
  }
  function paceFrame() {
    const r = pace.run;
    if (!r) return;
    const e = (performance.now() - r.wall0) / 1000;
    const st = r.steps.find((x) => e >= x.start_s && e < x.end_s);
    if (!st) { stopPace(true); return; }
    let k, cue;
    if (st.rest) { k = 0.45; cue = tr('cueRest'); }
    else {
      const period = 60 / st.rate, ph = ((e - st.start_s) % period) / period;   // breathe in for 40% of each cycle, out for 60%
      if (ph < 0.4) { k = (1 - Math.cos(Math.PI * ph / 0.4)) / 2; cue = tr('cueIn'); }
      else { k = 1 - (1 - Math.cos(Math.PI * (ph - 0.4) / 0.6)) / 2; cue = tr('cueOut'); }
    }
    $('pace-ring').setAttribute('r', (34 + 76 * k).toFixed(1));
    $('pace-cue').textContent = cue;
    const left = Math.max(0, Math.ceil(st.end_s - e));
    $('pace-step').textContent = st.rest ? tr('stepRest', { s: left }) : tr('stepRate', { r: st.rate, s: left });
    if (r.scored && Math.floor(e / 2) !== r.lastScore) { r.lastScore = Math.floor(e / 2); renderPaceResults(); }
  }
  function scorePace(log, t0) {
    const ds = state.ds;
    const x = ds.sensors.find((y) => log.mac && y.mac === log.mac) || ds.sensors.find((y) => y.seat === log.seat);
    if (!x) return null;
    const h = x.hops, rows = [];
    log.steps.filter((st) => !st.rest).forEach((st) => {
      const a = t0 + st.start_s + 32, b = t0 + st.end_s;
      let n = 0, shown = 0, ok = 0, err = 0;
      const vals = [];
      for (let i = 0; i < h.t.length; i++) {
        if (h.t[i] < a || h.t[i] > b || h.t[i] > state.t + 1e-6) continue;
        n++;
        if (h.rel[i] && h.bpm[i] !== null) { shown++; vals.push(h.bpm[i]); const d = Math.abs(h.bpm[i] - st.rate); err += d; if (d <= 2) ok++; }
      }
      vals.sort((p, q) => p - q);
      rows.push({ rate: st.rate, n, shown, ok, med: vals.length ? vals[vals.length >> 1] : null, mae: shown ? err / shown : null });
    });
    return { seat: x.seat, rows };
  }
  // In the claude.ai viewer a file goes through its downloads capability (the viewer confirms each save); opened as a
  // local file, the page uses a plain browser download. dl === null: no way to save here, so no save buttons.
  const inViewer = !!(window.claude && typeof window.claude.use === 'function');
  let dl = inViewer ? undefined : 'local';
  if (inViewer) window.claude.use('downloads').then((ns) => { dl = ns || null; renderPaceResults(); }, () => { dl = null; });
  function saveFile(name, text, type) {
    if (inViewer) {
      if (!dl) return;
      dl.save({ filename: name, data: text }).catch((e) => { if (!e || e.code !== 'declined') showMsg(tr('dlFailed')); });
      return;
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }
  function renderPaceResults() {
    const el = $('pace-results'), ds = state.ds;
    if (!el || !ds) return;
    let log = pace.log, t0 = null;
    if (pace.run && pace.run.scored) { log = pace.run; t0 = pace.run.t0; }
    else if (log) {
      if (log.source === 'live' && state.source === 'live' && log.liveStart_t !== null) t0 = log.liveStart_t;
      else if (state.source === 'file' && ds.start) t0 = (Date.parse(log.startedAt) - Date.parse(ds.start)) / 1000;
    }
    el.innerHTML = '';
    if (!log) return;
    const p = (t) => { const e = document.createElement('p'); e.className = 'note'; e.textContent = t; el.appendChild(e); return e; };
    const sc = t0 === null ? null : scorePace(log, t0);
    if (t0 === null) p(tr(log.source !== 'live' && state.source !== 'file' ? 'checkUnscored' : 'checkNoData'));
    else if (!sc) p(tr('checkNoSeat'));
    else {
      const tot = sc.rows.reduce((a, r) => ({ n: a.n + r.n, shown: a.shown + r.shown, ok: a.ok + r.ok }), { n: 0, shown: 0, ok: 0 });
      const fmt1 = (v) => (v === null ? '' : (Math.round(v * 10) / 10).toFixed(1));
      const pct = (a, b) => (b ? Math.round((100 * a) / b) + '%' : '');
      let html = '<div class="tablewrap"><table><thead><tr><th class="num">' + esc(tr('resTarget')) + '</th><th class="num">' + esc(tr('resWin')) + '</th><th class="num">' + esc(tr('resShown')) +
        '</th><th class="num">' + esc(tr('resMed')) + '</th><th class="num">' + esc(tr('resOk')) + '</th><th class="num">' + esc(tr('resMae')) + '</th></tr></thead><tbody>';
      sc.rows.forEach((r) => { html += '<tr><td class="num">' + r.rate + '</td><td class="num">' + r.n + '</td><td class="num">' + pct(r.shown, r.n) + '</td><td class="num">' + fmt1(r.med) +
        '</td><td class="num">' + pct(r.ok, r.shown) + '</td><td class="num">' + fmt1(r.mae) + '</td></tr>'; });
      el.insertAdjacentHTML('beforeend', html + '</tbody></table></div>');
      if (tot.n) p(tr('resSummary', { x: sc.seat, ok: tot.ok, shown: tot.shown, p: tot.shown ? Math.round((100 * tot.ok) / tot.shown) : 0, c: Math.round((100 * tot.shown) / tot.n), n: tot.n })).className = 'summary';
      else p(tr('resWait'));
      if (!pace.run && dl) {
        const d = document.createElement('div'); d.className = 'dl';
        const b1 = document.createElement('button'); b1.type = 'button'; b1.className = 'linkbtn'; b1.textContent = tr('dlResults');
        b1.addEventListener('click', () => saveFile('hinigram_paced_results.csv', 'paced_rate,windows,shown,within2,median_reading,mean_abs_error\n' +
          sc.rows.map((r) => [r.rate, r.n, r.shown, r.ok, fmt1(r.med), fmt1(r.mae)].join(',')).join('\n') + '\n', 'text/csv'));
        d.appendChild(b1); el.appendChild(d);
      }
    }
    if (!pace.run && log.kind && dl) {
      let d = el.querySelector('.dl');
      if (!d) { d = document.createElement('div'); d.className = 'dl'; el.appendChild(d); }
      const b2 = document.createElement('button'); b2.type = 'button'; b2.className = 'linkbtn'; b2.textContent = tr('dlLog');
      b2.addEventListener('click', () => saveFile('hinigram_pacer_log.json', JSON.stringify(log, null, 1), 'application/json'));
      d.appendChild(b2);
    }
  }
  function onPaceFile(ev) {
    const f = ev.target.files && ev.target.files[0];
    if (!f) return;
    f.text().then((txt) => {
      let log = null;
      try { log = JSON.parse(txt); } catch (e) { log = null; }
      if (!log || log.kind !== 'hinigram-paced-check' || !Array.isArray(log.steps)) { showMsg(tr('badLog')); return; }
      showMsg('');
      pace.log = log;
      $('check').open = true;
      renderPaceResults();
    });
    ev.target.value = '';
  }

  // ------------------------------------------------------------------ injection bench
  // The console above the room. It tells the worker what to stream and what breathing to add to each chair, keeps the
  // truth the worker reports next to each seat's readings, and scores the board against it as the notebook does.
  const INJ = window.HinigramInject, DSP = window.HinigramDSP;
  const QUIET = [112, 173.3];                                    // the format sample's longest stretch without movement
  const BUSY = [[14, 19, null], [62, 110, null], [4, 9, 2]];    // movement in the format sample (s): every sensor, or one
  const RATE_RANGE = { adult: [4, 45], child_1_5y: [8, 70], infant_2_12m: [10, 80], newborn_lt2m: [12, 90] };
  const bench = { kind: null, bg: 'sample', ds: null, running: false, speed: 1, t: 0, D: 0, a: 0, file: '', chairs: new Map(), events: [],
    load: 0, rec: null, recFull: false, csv: null, starting: false, runs: 0, lastTable: 0, lastScore: 0, score: null, tableKey: '' };
  let benchPanelKey = '';
  const emptyDs = () => ({ title: 'Bench', file: null, duration: 30, packets: 0, start: new Date().toISOString(), sensors: [] });
  const newHops = () => ({ t: [], status: [], reason: [], bpm: [], raw: [], q: [], rel: [], mot: [], pause: [], snr: [], prof: [] });
  const sampleB64 = () => { const el = document.getElementById('sample-packets'); return el ? el.textContent.trim() : ''; };

  /** Seats for n chairs, in rows of four facing two front-corner receivers (three chairs: one row, one receiver). Node IDs
   *  go through the left half of the room first, so each receiver takes one continuous range (firmware/README.md). */
  function benchLayout(n) {
    const rows = n === 12 ? ['A', 'B', 'C'] : n === 8 ? ['A', 'B'] : ['A'], cols = n === 3 ? 3 : 4;
    const out = [];
    rows.forEach((r) => { for (let c = 1; c <= cols; c++) out.push({ seat: r + c, row: r, col: c, rx: n === 3 || c <= cols / 2 ? 1 : 2 }); });
    out.filter((x) => x.rx === 1).concat(out.filter((x) => x.rx === 2)).forEach((x, i) => { x.node = i + 1; x.mac = '1a:00:00:00:00:' + (i + 1).toString(16).padStart(2, '0'); });
    return out;
  }
  // where a chair is in the recording at stream time u (forward, then backward, from its own start point)
  function srcTimeAt(c, u) { const D = bench.D, x = (((u + c.offset) % (2 * D)) + 2 * D) % (2 * D); return bench.a + (x < D ? x : 2 * D - x); }
  function quietAt(c, u0, u1) {
    if (bench.bg === 'csv') return true;                        // movement in a user's file is not known in advance
    for (let u = u0 - 22; u <= u1 + 12; u += 0.5) {             // the reading needs ~20 s without movement before a hold
      const s = srcTimeAt(c, Math.max(0, u));
      for (const [b0, b1, only] of BUSY) if ((only === null || only === c.srcIndex) && s >= b0 - 1 && s <= b1 + 1) return false;
    }
    return true;
  }
  function quietStart(c, after, len) { for (let u = after; u < after + 900; u += 1) if (quietAt(c, u, u + len)) return Math.round(u); return after; }

  // scenarios: [profile, depth, script] per seat; a script is [[t0, t1, breaths/min], ...] and 0 is a held breath
  const OPEN = 1e5;
  const MIXED = [['adult', 0.05, [[0, OPEN, 15]]], ['adult', 0.05, [[0, 90, 14], [90, OPEN, 28]]], ['child_1_5y', 0.05, [[0, OPEN, 30]]], ['adult', 0.015, [[0, OPEN, 17]]],
    ['adult', 0.05, [[0, OPEN, 22]]], ['adult', 0.04, [[0, OPEN, 13]]], ['adult', 0.05, { r: 16, hold: 17, after: 100 }], ['infant_2_12m', 0.05, [[0, OPEN, 38]]],
    ['child_1_5y', 0.05, [[0, OPEN, 46]]], ['adult', 0.035, [[0, OPEN, 16]]], ['adult', 0.05, [[0, OPEN, 7.5]]], ['adult', 0.045, [[0, OPEN, 19]]]];
  // hinigram_eval.SCENARIOS: the held-out scenarios, pauses where the recording is quiet when it plays from the start
  const HELDOUT = [['adult', [[0, OPEN, 10]]], ['adult', [[0, OPEN, 17]]], ['adult', [[0, OPEN, 23]]], ['adult', [[0, OPEN, 32]]],
    ['adult', [[0, 140, 16], [140, 152, 0], [152, OPEN, 16]]], ['adult', [[0, 40, 18], [40, 58, 0], [58, OPEN, 18]]], ['infant_2_12m', [[0, OPEN, 55]]],
    ['child_1_5y', [[0, OPEN, 34]]], ['adult', [[0, 150, 16], [150, 158, 0], [158, OPEN, 16]]], ['adult', [[0, 120, 17], [120, 134, 0], [134, OPEN, 17]]],
    ['child_1_5y', [[0, 130, 30], [130, 155, 0], [155, OPEN, 30]]]];
  const CALM = [12, 14, 16, 18, 20, 13, 15, 17, 19, 12.5, 16.5, 18.5];
  const HOLDS = [8, 12, 15, 18, 25];
  // the setup and quick checks: one routine on every chair, in seconds from the moment the chair starts; rates are scored
  // in the windows that lie wholly inside one rate (after 30 s of warm-up), the hold from its start to 8 s after its end
  const CHECK = { depth: 0.05, pk: 25, shown: 1 / 3, right: 0.9 };
  const DONE_AFTER = 2;   // s after a routine's end: its last readings are in, and the verdict is fixed
  const BY_HAND = ['take', 'script', 'profile', 'depth', 'rate', 'on', 'off', 'move', 'hold', 'release', 'empty', 'sit'];
  const ROUTINES = {
    setup: Object.assign({ script: [[0, 75, 12], [75, 150, 20], [150, 168, 0], [168, OPEN, 16]], move: 200, end: 240, rates: [[30, 75], [105, 150]], hold: [150, 168] }, CHECK),
    quick: Object.assign({ script: [[0, 62, 15], [62, 80, 0], [80, OPEN, 15]], move: 95, end: 120, rates: [[30, 62]], hold: [62, 80] }, CHECK) };
  const shiftScript = (sc, j) => sc.map(([a, b, x]) => [a + j, b >= OPEN ? OPEN : b + j, x]);
  // the held-out preset rotates over runs: each run takes the next scenarios, and the depths move on one sensor
  const heldoutIndex = (i, n, run) => (i + run * n) % HELDOUT.length;
  function presetSpec(name, i, n, c) {
    let prof = 'adult', depth = 0.05, script = null, on = true;
    if (name === 'mixed') { const m = MIXED[n === 3 ? [1, 6, 8][i] : i]; prof = m[0]; depth = m[1]; script = m[2]; }
    else if (name === 'holds') { const L = HOLDS[i % HOLDS.length]; prof = L > 20 ? 'child_1_5y' : 'adult'; script = { r: L > 20 ? 30 : 16, hold: L, after: 60 + 25 * (i % 3) }; }
    else if (name === 'heldout') { const h = HELDOUT[heldoutIndex(i, n, bench.runs)]; prof = h[0]; script = h[1]; depth = [0.05, 0.03, 0.015][(c.srcIndex + bench.runs) % 3]; }
    else if (name === 'calm') script = [[0, OPEN, CALM[i % CALM.length]]];
    else if (ROUTINES[name]) { script = ROUTINES[name].script; depth = ROUTINES[name].depth; }
    else if (name === 'none') on = false;
    if (script && !Array.isArray(script)) { const t0 = quietStart(c, script.after, script.hold); script = [[0, t0, script.r], [t0, t0 + script.hold, 0], [t0 + script.hold, OPEN, script.r]]; }
    const bpm = script ? script[0][2] : 16;
    return { profile: prof, depth, script, origScript: script, bpm, mode: 'breathing', on, manual: !script, join: 0, moves: ROUTINES[name] ? [ROUTINES[name].move] : [] };
  }
  /** A scenario for a receiver's chair: the i-th node heard, timed from the moment j (receiver clock) it starts. */
  function liveSpec(name, i, j) {
    let prof = 'adult', depth = 0.05, script = null, moves = [];
    if (ROUTINES[name]) { script = ROUTINES[name].script; depth = ROUTINES[name].depth; moves = [j + ROUTINES[name].move]; }
    else if (name === 'mixed') { const m = MIXED[i % MIXED.length]; prof = m[0]; depth = m[1]; script = m[2]; }
    else if (name === 'holds') { const L = HOLDS[i % HOLDS.length]; prof = L > 20 ? 'child_1_5y' : 'adult'; script = { r: L > 20 ? 30 : 16, hold: L, after: 60 + 25 * (i % 3) }; }
    else if (name === 'heldout') { const h = HELDOUT[i % HELDOUT.length]; prof = h[0]; script = h[1]; depth = [0.05, 0.03, 0.015][i % 3]; }
    else if (name === 'calm') script = [[0, OPEN, CALM[i % CALM.length]]];
    if (script && !Array.isArray(script)) script = [[0, script.after, script.r], [script.after, script.after + script.hold, 0], [script.after + script.hold, OPEN, script.r]];
    if (script) script = shiftScript(script, j);
    return { profile: prof, depth, script, bpm: script ? script[0][2] : 16, moves };
  }
  function scriptRateAt(c, t) {
    if (!c.script) return c.bpm;
    let r = c.script[0][2];
    for (const s of c.script) if (t >= s[0] && t < s[1]) return s[2];
    for (const s of c.script) if (s[2] > 0) r = s[2];
    return r;
  }
  /** The events a script will produce: held breaths and rate changes. */
  function scriptEvents(c, from) {
    const out = [];
    let prev = null;
    (c.script || []).forEach((s) => {
      if (s[2] === 0) { if (s[1] > from) out.push({ mac: c.mac, kind: 'hold', t0: Math.max(s[0], from), t1: s[1], scripted: true }); }
      else { if (prev !== null && prev !== s[2] && s[0] >= from) out.push({ mac: c.mac, kind: 'rate', t: s[0], r: s[2], scripted: true }); prev = s[2]; }
    });
    return out;
  }
  function describeScript(c) {
    const s = c.script, f = (v) => (Math.round(v * 10) / 10).toString();
    if (!c.on) return tr('scriptDesc.none');
    if (c.mode === 'empty') return tr('scriptDesc.empty');
    if (!s || s.length === 1) return tr('scriptDesc.rate', { r: f(scriptRateAt(c, bench.t)) });
    const h = s.find((x) => x[2] === 0);
    if (h) return tr('scriptDesc.hold', { r: f(s[0][2]), s: Math.round(h[1] - h[0]), t: fmtT(h[0]) });
    return tr('scriptDesc.change', { a: f(s[0][2]), b: f(s[1][2]), t: fmtT(s[1][0]) });
  }
  const chairParams = (c) => ({ bpm: c.bpm, depth: c.depth, mode: c.mode, on: c.on, script: c.script, scriptT0: 0 });
  function newSensor(x, c) {
    return { mac: x.mac, label: 'Node ' + x.node, seat: x.seat, row: x.row, col: x.col, rx: x.rx, profile: c.profile, health: {}, hops: newHops(),
      wave: { t0: 0, fs: 10, v: [] }, series: { t: [], rate: [], rssi: [], steps: [], act: [] }, truth: { t: [], bpm: [] } };
  }

  function benchStart() {
    const bg = $('bench-bg').value;
    if (bg === 'receiver') { benchStartReceiver(); return; }
    if (bg === 'csv' && !bench.csv) { showMsg(tr('noteCsvAsk')); $('bench-file').click(); return; }
    showMsg('');
    const n = +$('bench-n').value, preset = $('bench-preset').value;
    Object.assign(bench, { kind: 'player', bg, preset, speed: +$('bench-speed').value, t: 0, events: [], chairs: new Map(), load: 0, rec: null, recFull: false,
      score: null, starting: true, running: true, tableKey: '', setupDone: false, setupRows: null, a: bg === 'quiet' ? QUIET[0] : 0,
      D: bg === 'quiet' ? QUIET[1] - QUIET[0] : bg === 'csv' ? bench.csv.D : DATA.sources.sample.duration, file: bg === 'csv' ? bench.csv.name : DATA.sources.sample.file });
    const layout = benchLayout(n), nLinks = bg === 'csv' ? bench.csv.k : 3, bySrc = {};
    layout.forEach((x) => { x.srcIndex = (x.node - 1) % nLinks; (bySrc[x.srcIndex] = bySrc[x.srcIndex] || []).push(x); });
    // chairs that share a sensor start at different points of its forward-and-back cycle (the held-out set: all at the start)
    Object.values(bySrc).forEach((list) => list.forEach((x, j) => { x.offset = preset === 'heldout' ? 0 : (j / list.length) * 2 * bench.D; }));
    layout.forEach((x, i) => {
      const c = Object.assign({}, x, presetSpec(preset, i, n, x));
      c.profile0 = c.profile;
      bench.chairs.set(c.mac, c);
      bench.events.push(...scriptEvents(c, 0));
    });
    const ds = Object.assign(emptyDs(), { file: bench.file, sensors: layout.map((x) => newSensor(x, bench.chairs.get(x.mac))),
      receivers: n === 3 ? [{ id: 1, label: 'Receiver 1', corner: 'front-left' }] : [{ id: 1, label: 'Receiver 1', corner: 'front-left' }, { id: 2, label: 'Receiver 2', corner: 'front-right' }] });
    bench.ds = ds; bench.runs++;
    getWorker().postMessage({ type: 'inject-start', bg: bg === 'csv' ? { kind: 'csv', text: bench.csv.text, name: bench.csv.name } : { kind: 'sample', b64: sampleB64() },
      range: bg === 'quiet' ? QUIET : null, chairs: layout.map((x) => { const c = bench.chairs.get(x.mac); return { mac: c.mac, srcIndex: c.srcIndex, offset: c.offset, profile: c.profile, params: chairParams(c) }; }),
      speed: bench.speed, seed: bench.runs, run: bench.runs, record: true, preroll: 32, hostT0: Date.now() / 1000 });
    state.t = 0;
    setSource('inject', ds);
    benchControls();
  }
  function benchStartReceiver() {
    setBaud(+$('bench-baud').value);
    Object.assign(bench, { kind: 'receiver', bg: 'receiver', preset: $('bench-preset').value, joined: 0, t: 0, setupDone: false, setupRows: null,
      chairs: new Map(), events: [], running: true, starting: false, file: '', rec: null, recFull: false, score: null, tableKey: '' });
    bench.liveProfiles = state.live && state.live.ds ? Object.fromEntries(state.live.ds.sensors.map((x) => [x.mac, x.profile])) : {};
    if (state.live && state.live.connected) {
      // an open port: the bench starts its own session, so every node is heard afresh and starts its scenario from its
      // first packet, and the packets it records share the truth's clock
      state.live.ds = { title: 'Live', file: null, duration: 30, packets: 0, start: new Date().toISOString(), sensors: [] };
      liveEpoch++;
      getWorker().postMessage({ type: 'live-start', profiles: bench.liveProfiles, epoch: liveEpoch });
    }
    connectSerial({ bench: true, onOpen: (ds) => { bench.ds = ds; getWorker().postMessage({ type: 'inject-record', on: true, clear: true }); benchControls(); },
      onFail: () => { bench.kind = null; benchControls(); } });
  }
  function benchStopReceiver() {
    // the live board must never show added breathing outside the bench
    for (const c of bench.chairs.values()) if (c.on) { c.on = false; if (worker) worker.postMessage({ type: 'inject-set', mac: c.mac, params: { on: false }, tag: 'off' }); }
    if (worker) worker.postMessage({ type: 'inject-record', on: false, clear: true });
    if (bench.rxAdded && state.live) {
      // readings made from added breathing sit in the pipeline's 30 s windows and in the seats' history, so the live
      // board starts afresh (a new session in the worker, a new dataset here), keeping each seat's profile
      const profiles = Object.assign({}, bench.liveProfiles || {}, Object.fromEntries(state.live.ds.sensors.map((x) => [x.mac, x.profile])));
      for (const c of bench.chairs.values()) if (c.liveProfile) profiles[c.mac] = c.liveProfile;   // as before the bench
      state.live.ds = { title: 'Live', file: null, duration: 30, packets: 0, start: new Date().toISOString(), sensors: [] };
      liveEpoch++;
      if (worker) worker.postMessage({ type: 'live-start', profiles, epoch: liveEpoch });
      showMsg(tr('rxBenchEnded'));
    }
    bench.rxAdded = false;
  }
  function benchRun(running) {
    bench.running = running;
    if (worker && bench.kind === 'player') worker.postMessage({ type: 'inject-run', running });
    benchControls();
  }
  function benchNew() {
    if (worker && bench.kind === 'player') worker.postMessage({ type: 'inject-stop' });
    if (bench.kind === 'receiver') benchStopReceiver();
    bench.kind = null; bench.running = false; bench.starting = false;
    benchControls();
  }
  function benchFailed() { bench.kind = null; bench.starting = false; showMsg(tr('csvErr')); benchControls(); }
  function openBench() {
    showMsg('');
    setSource('inject', bench.kind && bench.ds ? bench.ds : emptyDs());
    benchControls();
  }

  /** Send a change for one chair to the worker; the worker answers with the stream time it took effect (benchEvent). */
  function benchSet(c, params, tag) {
    if (!c) return;
    c = bench.chairs.get(c.mac) || benchChair(c);
    Object.assign(c, params);
    if (bench.kind === 'receiver' && params.on) bench.rxAdded = true;
    if (worker) worker.postMessage({ type: 'inject-set', mac: c.mac, params, tag });
  }
  /** A chair being changed by hand stops following its script, at the script's current rate. */
  function takeOver(c) {
    if (!c.script) return;
    c.bpm = scriptRateAt(c, bench.t) || c.bpm || 16;
    c.manual = true; c.moves = [];
    benchSet(c, { script: null, bpm: c.bpm, mode: c.mode === 'hold' ? 'breathing' : c.mode }, 'take');
  }
  function benchChair(s) {
    // receiver mode: a chair is made when its node is first heard, with nothing added until it is switched on
    let c = bench.chairs.get(s.mac);
    if (c && !c.seat && s.seat) c.seat = s.seat;
    if (!c) { c = { mac: s.mac, seat: s.seat, profile: s.profile, profile0: s.profile, liveProfile: s.profile, bpm: 16, depth: 0.05, mode: 'breathing', on: false, manual: true, script: null, origScript: null }; bench.chairs.set(s.mac, c); }
    return c;
  }
  /** A chair's profile at stream time t: its first, then each change it was given. */
  function profileAt(c, t) {
    let p = c.profile0 || c.profile;
    for (const e of bench.events) if (e.mac === c.mac && e.kind === 'profile' && e.t <= t) p = e.p;
    return p;
  }
  /** The rate a chair breathes at now; during a scripted hold, the scenario's rate around it. */
  function breathRate(c) {
    if (!c.script) return c.bpm;
    const r = scriptRateAt(c, bench.t);
    return r > 0 ? r : (c.script.find((x) => x[2] > 0) || [0, 0, c.bpm || 16])[2];
  }
  /** Receiver: a chair is made when its node is first heard and, unless the scenario is "nothing added", starts its
   *  scenario at once, timed from that moment. */
  function joinChair(c, j) {
    if (c.joined || bench.preset === 'none') return;
    c.joined = true; bench.setupDone = false;
    const sp = liveSpec(bench.preset, bench.joined++, j);
    Object.assign(c, { origScript: sp.script, manual: !sp.script, join: j, moves: sp.moves, profile0: sp.profile });
    if (sp.profile !== c.profile) {
      benchSet(c, { profile: sp.profile }, 'profile-auto');
      const s = bench.ds && bench.ds.sensors.find((x) => x.mac === c.mac);
      if (s) s.profile = sp.profile;
    }
    benchSet(c, { on: true, bpm: sp.bpm, depth: sp.depth, mode: 'breathing', script: sp.script, scriptT0: 0 }, 'auto');
  }
  /** A node the bench has not yet started (heard before the bench began): it starts at its latest reading. */
  function benchJoin(s) { const c = benchChair(s); if (!c.joined && s.hops.t.length) joinChair(c, s.hops.t[s.hops.t.length - 1]); }
  /** Joins, shifts in the seat and ends follow the stream's messages as well as the screen, so a background tab keeps time. */
  function benchDrive() { if (bench.kind === 'receiver' && bench.ds) bench.ds.sensors.forEach(benchJoin); if (bench.kind) benchSchedule(); }
  /** Scheduled shifts in the seat, and the end of each chair's setup check (a receiver's chair then gets nothing added;
   *  a sample or CSV run pauses once every chair has its verdict). */
  function benchSchedule() {
    let all = true, any = false;
    const R = ROUTINES[bench.preset];
    for (const c of bench.chairs.values()) {
      while (c.moves && c.moves.length && bench.t >= c.moves[0]) {
        c.moves.shift();
        if (worker && c.on && c.mode === 'breathing') worker.postMessage({ type: 'inject-move', mac: c.mac, dur: 6, tag: 'auto' });
      }
      if (!R || c.join === undefined || !c.origScript) continue;
      any = true;
      if (bench.kind === 'receiver' && c.on && !c.setupOff && bench.t >= c.join + R.end) { c.setupOff = true; benchSet(c, { on: false }, 'off-auto'); }
      if (bench.t < c.join + R.end + DONE_AFTER) all = false;
    }
    if (any && all && !bench.setupDone) {
      bench.setupDone = true;
      if (bench.kind === 'player' && bench.running) benchRun(false);
      showMsg(tr('setup.done'));
    }
  }
  function openHold(mac) { return bench.events.find((e) => e.mac === mac && e.kind === 'hold' && e.t1 === null); }
  function benchEvent(m) {
    const c = bench.chairs.get(m.mac);
    if (!c || m.t === null || m.t === undefined) return;
    const t = m.t, E = bench.events;
    if (m.move) { E.push({ mac: m.mac, kind: 'move', t, dur: m.move, auto: m.tag === 'auto' }); renderAll(true); return; }
    const tag = m.tag, p = m.params || {};
    const close = () => { const h = openHold(m.mac); if (h) h.t1 = t; };
    if (tag === 'take') {
      // a scripted hold in progress ends now, and the script's later events will not happen
      for (const e of E) if (e.mac === m.mac && e.scripted && e.kind === 'hold' && e.t0 <= t && e.t1 > t) e.t1 = t;
      bench.events = E.filter((e) => !(e.mac === m.mac && e.scripted && (e.kind === 'hold' ? e.t0 > t : e.t > t)));
      bench.events.push({ mac: m.mac, kind: 'take', t });
    } else if (tag === 'script') {
      close();
      bench.events.push(...scriptEvents(c, t), { mac: m.mac, kind: 'script', t });
    } else if (tag === 'hold') { close(); E.push({ mac: m.mac, kind: 'hold', t0: t, t1: null }); }
    else if (tag === 'release') { close(); E.push({ mac: m.mac, kind: 'release', t }); }
    else if (tag === 'empty') { close(); E.push({ mac: m.mac, kind: 'empty', t }); }
    else if (tag === 'sit') E.push({ mac: m.mac, kind: 'sit', t });
    else if (tag === 'auto') E.push(...scriptEvents(c, t), { mac: m.mac, kind: 'on', t, auto: true });
    else if (tag === 'rate') E.push({ mac: m.mac, kind: 'rate', t, r: p.bpm });
    else if (tag === 'depth') E.push({ mac: m.mac, kind: 'depth', t, d: p.depth });
    else if (tag === 'on' || tag === 'off' || tag === 'off-auto') { if (tag !== 'on') close(); E.push({ mac: m.mac, kind: tag === 'on' ? 'on' : 'off', t, auto: tag === 'off-auto' }); }
    else if (tag === 'profile' || tag === 'profile-auto') E.push({ mac: m.mac, kind: 'profile', t, p: p.profile, auto: tag === 'profile-auto' });
    renderAll(true);
  }
  function benchMessage(m) {
    if (m.type === 'inject-ready') {
      bench.starting = false; bench.D = m.D; bench.a = m.a;
      m.chairs.forEach((x) => { const c = bench.chairs.get(x.mac); if (c) { c.offset = x.offset; c.srcMac = x.src; } });
      benchPanelKey = ''; benchControls();
    } else if (m.type === 'inject-tick') {
      const ds = m.src === 'bench' ? bench.ds : state.live && state.live.ds;
      if (!ds) return;
      for (const mac of Object.keys(m.truth || {})) {
        const s = ds.sensors.find((x) => x.mac === mac), c = bench.chairs.get(mac), T = m.truth[mac];
        // a receiver's node starts its scenario at its first packet, 30 s before its seat appears: keep that truth on the
        // chair and hand it to the seat when it comes
        let dst = null;
        if (s) { if (!s.truth) s.truth = (c && c.truthBuf) || { t: [], bpm: [] }; if (c) c.truthBuf = null; dst = s.truth; }
        else if (c) dst = c.truthBuf = c.truthBuf || { t: [], bpm: [] };
        if (!dst) continue;
        for (let i = 0; i < T.t.length; i++) { dst.t.push(T.t[i]); dst.bpm.push(T.bpm[i]); }
        if (c && T.t.length) c.truthT = T.t[T.t.length - 1];
      }
      if (m.src === 'bench' && ds === bench.ds) {
        bench.t = m.t; bench.load = m.load || 0;
        ds.duration = Math.max(ds.duration, m.t);
        if (state.source === 'inject' && state.ds === ds && (state.t < m.t - 1 || state.t > m.t + 0.6)) state.t = m.t;
        $('scrub').max = String(Math.max(30, ds.duration));
      }
      if (m.src === 'receiver' && bench.kind === 'receiver' && Number.isFinite(m.t)) bench.t = Math.max(bench.t, m.t);
      if (m.rec) bench.rec = m.rec;
    } else if (m.type === 'inject-event') benchEvent(m);
    else if (m.type === 'inject-csv') saveFile('hinigram_injected.csv', m.text, 'text/csv');
    else if (m.type === 'inject-recfull') bench.recFull = true;
    else if (m.type === 'inject-heard' && bench.kind === 'receiver') {
      for (const nd of m.nodes) {
        let c = bench.chairs.get(nd.mac);
        if (!c) {
          const p = (bench.liveProfiles || {})[nd.mac] || 'adult';
          c = { mac: nd.mac, seat: liveSeats.get(nd.mac) || null, profile: p, profile0: p, liveProfile: p, bpm: 16, depth: 0.05, mode: 'breathing', on: false, manual: true, script: null, origScript: null };
          bench.chairs.set(nd.mac, c);
        }
        joinChair(c, nd.t);
      }
    }
  }
  /** Bench events as logbook entries (TEST notes next to the status changes). */
  function benchLogEvents() {
    const ds = state.ds, out = [];
    if (!ds) return out;
    const seatOf = (mac) => { const s = ds.sensors.find((x) => x.mac === mac); return s ? s.seat : null; };
    for (const e of bench.events) {
      const seat = seatOf(e.mac);
      if (!seat) continue;
      if (e.kind === 'hold') {
        out.push({ t: e.t0, seat, test: tr('ev.hold') });
        if (e.t1 !== null && e.t1 < OPEN / 2) out.push({ t: e.t1, seat, test: tr('ev.release') });
      } else if (e.kind !== 'release') out.push({ t: e.t, seat, test: tr('ev.' + e.kind, { r: e.r, d: e.d !== undefined ? Math.round(e.d * 1000) / 10 : '', p: e.p ? tr('prof.' + e.p) : '' }) });
    }
    return out;
  }

  // ---------- scoring: windows full of breathing (as in the notebook), breath-holds, and alerts nobody caused
  function benchScore() {
    const ds = state.ds, t = state.t;
    let n = 0, shown = 0, ok = 0, err = 0;
    const perSeat = [], falseAlerts = [];
    ds.sensors.forEach((s) => {
      const c = bench.chairs.get(s.mac);
      if (!c || !s.truth) return;
      const h = s.hops;
      if (!c.sc || c.sc.k > h.t.length || c.sc.hops !== h) c.sc = { k: 0, hops: h, n: 0, shown: 0, ok: 0, err: 0, alerts: [] };
      const sc = c.sc, tMax = Math.min(t, c.truthT === undefined ? -1 : c.truthT);
      for (; sc.k < h.t.length && h.t[sc.k] <= tMax; sc.k++) {
        const k = sc.k, w = INJ.windowTruth(s.truth, h.t[k], 30);
        if (w.full) { sc.n++; if (h.rel[k] && h.bpm[k] !== null) { sc.shown++; const d = Math.abs(h.bpm[k] - w.bpm); sc.err += d; if (d <= 2) sc.ok++; } }
        if (h.status[k] === 'urgent' && reasonKey(h.reason[k]) === 'pause') sc.alerts.push(h.t[k]);
      }
      n += sc.n; shown += sc.shown; ok += sc.ok; err += sc.err;
      const profs = [c.profile0 || s.profile, ...bench.events.filter((e) => e.mac === s.mac && e.kind === 'profile' && e.t <= t).map((e) => e.p)].filter((p, j, a) => !j || p !== a[j - 1]);
      perSeat.push({ seat: s.seat, profile: profs.join(' > '), n: sc.n, shown: sc.shown, ok: sc.ok, mae: sc.shown ? sc.err / sc.shown : null });
      // pause alerts are explained by a hold that began before them and ended less than 30 s earlier
      const holds = bench.events.filter((e) => e.mac === s.mac && e.kind === 'hold' && e.t0 <= t);
      // and counted apart when nobody was breathing in the chair (emptied, or nothing added: the injected truth is empty)
      let episodes = 0, emptyEp = 0, last = -1e9;
      for (const a of sc.alerts) {
        if (a - last > 4.1 && !holds.some((e) => a >= e.t0 && a <= (e.t1 === null ? t : Math.min(e.t1, t)) + 30)) {
          const j = lastIdx(s.truth.t, a);
          if (j >= 0 && s.truth.bpm[j] === null) emptyEp++; else episodes++;
        }
        last = a;
      }
      if (episodes) falseAlerts.push({ seat: s.seat, n: episodes, empty: false });
      if (emptyEp) falseAlerts.push({ seat: s.seat, n: emptyEp, empty: true });
    });
    const holds = [];
    bench.events.filter((e) => e.kind === 'hold' && e.t0 <= t).forEach((e) => {
      const s = ds.sensors.find((x) => x.mac === e.mac);
      if (!s) return;
      const c = bench.chairs.get(e.mac);
      const h = s.hops, pmin = PAUSE_MIN[c ? profileAt(c, e.t0) : s.profile] || 10, end = e.t1 === null ? t : Math.min(e.t1, t), done = e.t1 !== null && e.t1 <= t;
      const planned = e.t1 === null ? null : e.t1 - e.t0;
      let flagged = null, moved = false, saidOk = 0;
      for (let k = 0; k < h.t.length && h.t[k] <= t; k++) {
        const tk = h.t[k];
        if (flagged === null && tk >= e.t0 && tk <= end + 8 && h.status[k] === 'urgent' && reasonKey(h.reason[k]) === 'pause') flagged = tk - e.t0;
        if (h.mot[k] && tk >= e.t0 - 2 && tk <= end) moved = true;
        if (tk >= e.t0 + pmin && tk <= end && h.status[k] === 'typical') saidOk++;
      }
      const should = planned !== null ? planned >= pmin : end - e.t0 >= pmin ? true : null;
      holds.push({ seat: s.seat, len: end - e.t0, planned, done, pmin, should, flagged, moved, saidOk });
    });
    return { n, shown, ok, mae: shown ? err / shown : null, perSeat, holds, falseAlerts };
  }

  // ---------- console rendering
  function benchControls() {
    const sel = $('bench-preset');
    if (!sel) return;
    const keep = sel.value || 'mixed';
    sel.innerHTML = ['quick', 'setup', 'mixed', 'holds', 'heldout', 'calm', 'none', 'manual'].map((k) => '<option value="' + k + '">' + esc(tr('presets.' + k)) + '</option>').join('');
    sel.value = keep;
    const active = !!bench.kind, bg = $('bench-bg').value;
    ['bench-bg', 'bench-n', 'bench-preset', 'bench-baud'].forEach((id) => { $(id).disabled = active; });
    $('bench-n').disabled = active || bg === 'receiver';   // a receiver's chairs are its nodes
    if (state.live && state.live.connected) $('bench-baud').disabled = true;
    $('bench-speed').disabled = bg === 'receiver' || bench.kind === 'receiver';
    $('bench-baud-l').hidden = bg !== 'receiver';
    const go = $('bench-go');
    go.textContent = bench.starting ? tr('benchLoading') : !active ? tr('benchStart') : bench.kind === 'receiver' ? tr('benchReset') : bench.running ? tr('benchPause') : tr('benchResume');
    go.disabled = bench.starting;
    $('bench-reset').hidden = !active || bench.kind === 'receiver';
    const preset = $('bench-preset').value;
    const note = bg === 'receiver' ? tr(preset === 'none' ? 'rxNote' : 'rxNoteAuto') : bg === 'csv' ? (bench.csv ? tr('noteCsv', { f: bench.csv.name, n: bench.csv.n.toLocaleString(), k: bench.csv.k }) : tr('noteCsvAsk')) : tr(bg === 'quiet' ? 'noteQuiet' : 'noteSample');
    const run = active ? bench.runs - 1 : bench.runs, n = +$('bench-n').value;
    const held = bg !== 'receiver' && $('bench-preset').value === 'heldout'
      ? ' ' + tr('noteHeldout', { s: [...new Set(Array.from({ length: n }, (_, i) => heldoutIndex(i, n, run) + 1))].join(', ') }) : '';
    const setupNote = ROUTINES[preset] ? ' ' + tr(preset === 'quick' ? 'noteQuick' : 'noteSetup', { end: tr(bg === 'receiver' ? 'setupEndRx' : 'setupEndPlay') }) : '';
    $('bench-note').textContent = note + held + setupNote;
    $('bench-grid').hidden = !active; $('bench-score').hidden = !active;
    benchPanelKey = ''; bench.tableKey = '';
  }
  function benchFrame(now, force) {
    if (state.source !== 'inject' || !state.ds) return;
    if (!force && now - bench.lastTable < 400) return;
    bench.lastTable = now;
    benchDrive();
    const clock = $('bench-clock'), load = $('bench-load');
    if (bench.kind === 'player') {
      clock.textContent = tr('clock', { t: fmtT(bench.t) });
      const p = Math.round(100 * bench.load);
      load.textContent = bench.load > 0.92 ? tr('slow') : bench.load > 0 ? tr('load', { p }) : '';
      load.classList.toggle('slow', bench.load > 0.92);
    } else { clock.textContent = ''; load.textContent = ''; }
    if (!bench.kind) return;
    renderBenchTable();
    renderChairPanel();
    if (force || now - bench.lastScore > 1000) { bench.lastScore = now; bench.score = benchScore(); renderBenchScore(); }
  }
  function putIn(s, c) {
    if (!c.on) return tr('put.off');
    if (c.mode === 'empty') return tr('put.empty');
    const h = openHold(s.mac) || bench.events.find((e) => e.mac === s.mac && e.kind === 'hold' && e.t0 <= state.t && e.t1 > state.t);
    if (h) return tr('put.hold', { s: Math.max(0, Math.round(state.t - h.t0)) });
    // the rate set now (the scenario's or the knob's); the check compares the board with the 30 s it scores
    return tr('put.rate', { r: Math.round(breathRate(c) * 10) / 10 });
  }
  function benchCheck(s, c, st, ex) {
    const t = state.t;
    const h = openHold(s.mac) || bench.events.find((e) => e.mac === s.mac && e.kind === 'hold' && e.t0 <= t && e.t1 > t);
    const pmin = PAUSE_MIN[h ? profileAt(c, h.t0) : s.profile] || 10;
    const alert = st.status === 'urgent' && st.reasonKey === 'pause';
    if (st.i < 0) return ['na', tr('mk.wait')];
    if (!c.on || c.mode === 'empty') return alert ? ['bad', tr(c.on ? 'mk.emptyAlert' : 'mk.offAlert')] : ['ok', tr('mk.quiet')];
    if (h) {
      if (alert) return ['ok', tr('mk.flagged')];
      if (t - h.t0 >= pmin && st.status === 'typical') return ['bad', tr('mk.missed')];
      return ['na', tr('mk.waitHold')];
    }
    const w = s.truth && st.ht !== null ? INJ.windowTruth(s.truth, st.ht, 30) : null;
    if (!ex.show) return ['na', tr('mk.noRate')];
    if (!w || !w.full) return ['na', '–'];
    if (Math.abs(w.bpm - breathRate(c)) > 2) return ['na', '–']; // the scored 30 s still spans a change of rate
    const d = Math.abs(ex.rate - w.bpm);
    return d <= 2 ? ['ok', tr('mk.ok')] : ['bad', tr('mk.off', { d: Math.round(d) })];
  }
  function renderBenchTable() {
    const ds = state.ds, tb = $('bench-table');
    const seats = ds.sensors.slice().sort((a, b) => a.seat.localeCompare(b.seat, undefined, { numeric: true }));
    const key = lang + '|' + seats.map((s) => s.seat).join(',');
    if (key !== bench.tableKey) {
      bench.tableKey = key;
      tb.innerHTML = '<thead><tr>' + tr('benchTh').map((x) => '<th scope="col">' + esc(x) + '</th>').join('') + '</tr></thead><tbody>' +
        seats.map((s) => '<tr data-seat="' + esc(s.seat) + '"><td class="seatc"></td><td class="who"></td><td class="put"></td><td class="reads"></td><td class="says"></td><td class="chk"></td></tr>').join('') + '</tbody>';
      tb.querySelectorAll('tbody tr').forEach((tr_) => tr_.addEventListener('click', () => select(tr_.dataset.seat)));
    }
    seats.forEach((s) => {
      const row = tb.querySelector('tr[data-seat="' + s.seat + '"]');
      if (!row) return;
      const c = bench.chairs.get(s.mac) || benchChair(s), st = seatState(s, state.t), ex = explain(s, st, state.t), ck = benchCheck(s, c, st, ex);
      row.classList.toggle('sel', s.seat === state.selected);
      row.children[0].textContent = s.seat;
      row.children[1].textContent = tr('who.' + s.profile);
      row.children[2].textContent = putIn(s, c);
      row.children[3].textContent = ex.show ? tr('put.rate', { r: Math.round(ex.rate) }) : ex.pauseS !== null ? tr('pauseShort', { s: ex.pauseS }) : '–';
      const sk = st.status + lang;
      if (row._sk !== sk) { row.children[4].innerHTML = statusHTML(st.status); row._sk = sk; }
      const mk = (ck[0] === 'ok' ? '✓\u00a0' : ck[0] === 'bad' ? '✗\u00a0' : '') + ck[1]; // the mark stays with its first word when the cell wraps
      if (row._mk !== mk) { row.children[5].innerHTML = '<span class="mk ' + ck[0] + '">' + esc(mk) + '</span>'; row._mk = mk; }
    });
  }
  function renderChairPanel() {
    const ds = state.ds, el = $('chairctl');
    const s = ds.sensors.find((x) => x.seat === state.selected);
    if (!s) { el.innerHTML = ''; benchPanelKey = ''; return; }
    const c = bench.chairs.get(s.mac) || benchChair(s);
    const key = [lang, s.mac, s.profile, c.mode, c.on, !!c.script, bench.kind].join('|');
    if (key !== benchPanelKey) {
      benchPanelKey = key;
      const rr = RATE_RANGE[s.profile] || RATE_RANGE.adult;
      const profOpts = Object.keys(T.en.prof).map((p) => '<option value="' + p + '"' + (p === s.profile ? ' selected' : '') + '>' + esc(tr('prof.' + p)) + '</option>').join('');
      const sub = bench.kind === 'receiver' ? tr('chairSubRx', { m: s.mac }) : tr('chairSub', { m: s.mac, k: (c.srcIndex || 0) + 1 });
      const knob = (id, label, min, max, step, hint) => '<div class="knob" id="' + id + '"><div class="lbl"><span>' + esc(label) + '</span><span class="val"></span></div>' +
        '<div class="row"><button type="button" class="step" data-d="-1" aria-label="−">−</button><input type="range" min="' + min + '" max="' + max + '" step="' + step + '" aria-label="' + esc(label) + '">' +
        '<button type="button" class="step" data-d="1" aria-label="+">+</button></div>' + (hint ? '<p class="hint">' + esc(hint) + '</p>' : '') + '</div>';
      el.innerHTML = '<h3>' + esc(tr('seat', { x: s.seat })) + '<small>' + esc(sub) + '</small></h3>' +
        (c.script ? '<p class="follow"><span class="fs"></span><button type="button" class="linkbtn" data-act="take">' + esc(tr('takeOver')) + '</button></p>'
          : c.origScript ? '<p class="follow"><span>' + esc(tr('manual')) + '</span><button type="button" class="linkbtn" data-act="script">' + esc(tr('backToScript')) + '</button></p>' : '') +
        '<label class="toggle"><input type="checkbox"' + (c.on ? ' checked' : '') + ' data-act="on"><span>' + esc(tr(bench.kind === 'receiver' ? 'injOn' : 'injOnPlay')) + '</span></label>' +
        '<label class="row2"><span>' + esc(tr('profile')) + '</span><select data-act="profile">' + profOpts + '</select></label>' +
        knob('k-rate', tr('rateL'), rr[0], rr[1], 0.5) + '<p class="knob band"></p>' +
        knob('k-depth', tr('depthL'), 0.5, 8, 0.5, tr('depthHint')) +
        '<div class="acts"><button type="button" class="ack" data-act="hold"></button><button type="button" class="ack" data-act="move">' + esc(tr('move')) + '</button>' +
        '<button type="button" class="ack" data-act="empty"></button></div><p class="now"></p>';
      const rate = el.querySelector('#k-rate input'), depth = el.querySelector('#k-depth input');
      rate.value = String(breathRate(c)); depth.value = String(Math.round(c.depth * 1000) / 10);
      // nothing is added to a chair that is off, so its knobs wait until it is switched on
      if (!c.on) el.querySelectorAll('.knob input, .knob .step').forEach((x) => { x.disabled = true; });
      const sendRate = () => { takeOver(c); benchSet(c, { bpm: +rate.value }, 'rate'); };
      const sendDepth = () => benchSet(c, { depth: +depth.value / 100 }, 'depth');
      c._rateDraft = undefined;
      rate.addEventListener('input', () => { c._rateDraft = +rate.value; renderChairValues(s, c); });
      rate.addEventListener('change', () => { c._rateDraft = undefined; sendRate(); });
      // a drag released where it started (or cancelled) fires no change: drop the draft so the knob follows the scenario again
      ['pointerup', 'pointercancel', 'blur'].forEach((evn) => rate.addEventListener(evn, () => setTimeout(() => {
        if (c._rateDraft !== undefined) { c._rateDraft = undefined; renderChairValues(s, c); }
      }, 60)));
      depth.addEventListener('input', () => renderChairValues(s, c, +depth.value));
      depth.addEventListener('change', sendDepth);
      el.querySelectorAll('#k-rate .step').forEach((b) => b.addEventListener('click', () => { c._rateDraft = undefined; rate.value = String(breathRate(c) + +b.dataset.d); sendRate(); renderChairValues(s, c); }));
      el.querySelectorAll('#k-depth .step').forEach((b) => b.addEventListener('click', () => { depth.value = String(+depth.value + 0.5 * +b.dataset.d); sendDepth(); renderChairValues(s, c); }));
      el.querySelector('select[data-act="profile"]').addEventListener('change', (ev) => changeProfile(s, ev.target.value));
      el.querySelectorAll('[data-act]').forEach((b) => {
        const act = b.dataset.act;
        if (act === 'profile') return;
        b.addEventListener(act === 'on' ? 'change' : 'click', () => {
          if (act === 'take') takeOver(c);
          else if (act === 'script') { c.manual = false; benchSet(c, { script: c.origScript, mode: 'breathing', bpm: c.origScript[0][2] }, 'script'); }
          else if (act === 'hold') {
            const scriptedHold = c.mode !== 'hold' && !!c.script && scriptRateAt(c, bench.t) === 0;
            takeOver(c);   // ends a scripted hold in progress
            if (!scriptedHold) benchSet(c, { mode: c.mode === 'hold' ? 'breathing' : 'hold' }, c.mode === 'hold' ? 'release' : 'hold');
          }
          else if (act === 'empty') { takeOver(c); benchSet(c, { mode: c.mode === 'empty' ? 'breathing' : 'empty' }, c.mode === 'empty' ? 'sit' : 'empty'); }
          else if (act === 'move') { if (worker) worker.postMessage({ type: 'inject-move', mac: c.mac, dur: 6 }); }
          else if (act === 'on') { const on = b.checked; if (!on) takeOver(c); benchSet(c, Object.assign({ on }, on ? { bpm: c.bpm, depth: c.depth, mode: c.mode } : {}), on ? 'on' : 'off'); }
          benchPanelKey = ''; renderChairPanel();
        });
      });
    }
    renderChairValues(s, c);
  }
  function renderChairValues(s, c, depthDraft) {
    const el = $('chairctl');
    const r = c._rateDraft !== undefined ? c._rateDraft : breathRate(c);
    const rv = el.querySelector('#k-rate .val'), dv = el.querySelector('#k-depth .val');
    if (!rv) return;
    // the slider follows the scenario's rate, except while it is being dragged
    const rin = el.querySelector('#k-rate input');
    if (c._rateDraft === undefined && +rin.value !== r) rin.value = String(r);
    rv.textContent = tr('put.rate', { r: Math.round(r * 10) / 10 });
    dv.textContent = (depthDraft !== undefined ? depthDraft : Math.round(c.depth * 1000) / 10) + '%';
    const band = DSP.classifyRate(r, s.profile)[0];
    const bandEl = el.querySelector('.band');
    const bk = lang + band;
    if (bandEl._k !== bk) { bandEl.innerHTML = '<span>' + esc(tr('bandL')) + '</span> ' + statusHTML(band); bandEl._k = bk; }
    const fs = el.querySelector('.follow .fs');
    if (fs) fs.textContent = tr('follow', { s: describeScript(c) });
    const holdB = el.querySelector('[data-act="hold"]'), emptyB = el.querySelector('[data-act="empty"]');
    const h = openHold(s.mac) || bench.events.find((e) => e.mac === s.mac && e.kind === 'hold' && e.t0 <= state.t && e.t1 > state.t);
    const holding = c.mode === 'hold' || (!!h && c.on && c.mode !== 'empty');
    holdB.textContent = holding ? tr('release') + ' · ' + tr('put.hold', { s: h ? Math.max(0, Math.round(state.t - h.t0)) : 0 }) : tr('hold');
    holdB.setAttribute('aria-pressed', String(holding));
    holdB.disabled = c.mode === 'empty' || !c.on;
    emptyB.textContent = c.mode === 'empty' ? tr('sit') : tr('empty');
    emptyB.setAttribute('aria-pressed', String(c.mode === 'empty'));
    emptyB.disabled = !c.on;
    const st = seatState(s, state.t), ex = explain(s, st, state.t);
    const board = (ex.show ? tr('put.rate', { r: Math.round(ex.rate) }) + ', ' : '') + tr('st.' + st.status).toLowerCase();
    el.querySelector('.now').innerHTML = esc(tr('nowLine', { a: '\u0000', b: '\u0001' })).replace('\u0000', '<b>' + esc(putIn(s, c)) + '</b>').replace('\u0001', '<b>' + esc(board) + '</b>');
  }
  function renderBenchScore() {
    const el = $('bench-score'), S = bench.score;
    if (!S) return;
    const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
    let h = '<h3 id="score-h">' + esc(tr('scoreH')) + '</h3>';
    if (ROUTINES[bench.preset]) h += setupHTML();
    h += S.n ? '<p class="summary">' + esc(tr('scoreRates', { n: S.n, c: pct(S.shown, S.n), p: pct(S.ok, S.shown), e: S.mae === null ? '–' : S.mae.toFixed(1) })) + '</p>'
      : '<p class="note">' + esc(tr('scoreNone')) + '</p>';
    if (S.holds.length) {
      const th = tr('holdTh');
      h += '<h3>' + esc(tr('holdsH')) + '</h3><div class="tablewrap"><table><thead><tr>' + th.map((x, i) => '<th scope="col"' + (i === 1 || i === 4 ? ' class="num"' : '') + '>' + esc(x) + '</th>').join('') + '</tr></thead><tbody>';
      S.holds.forEach((x) => {
        const should = x.should === null ? tr('notYet') : x.should ? tr('yes') : tr('no', { m: x.pmin });
        let did, cls;
        if (x.flagged !== null) { did = tr('flaggedAfter', { s: Math.round(x.flagged) }); cls = x.should === false ? 'bad' : 'ok'; }
        else if (x.moved) { did = tr('moved'); cls = 'na'; }
        else if (!x.done) { did = '…'; cls = 'na'; }
        else { did = tr('notFlagged'); cls = x.should ? 'bad' : 'ok'; }
        const mark = cls === 'ok' ? '✓ ' : cls === 'bad' ? '✗ ' : '';
        h += '<tr><td>' + esc(x.seat) + '</td><td class="num">' + Math.round(x.planned !== null && x.done ? x.planned : x.len) + ' s</td><td>' + esc(should) + '</td><td><span class="mk ' + cls + '">' + esc(mark + did) +
          '</span></td><td class="num">' + (x.saidOk ? '<span class="mk bad">' + esc(tr('timesN', { n: x.saidOk })) + '</span>' : '0') + '</td></tr>';
      });
      h += '</tbody></table></div>';
    }
    const fa = (empty) => S.falseAlerts.filter((x) => x.empty === empty), sum = (L) => L.reduce((a, x) => a + x.n, 0), list = (L) => L.map((x) => x.seat + ' ×' + x.n).join(', ');
    h += '<p class="note">' + esc(fa(false).length ? tr('falseSome', { n: sum(fa(false)), x: list(fa(false)) }) : tr('falseNone')) + '</p>';
    if (fa(true).length) h += '<p class="note">' + esc(tr('falseEmpty', { n: sum(fa(true)), x: list(fa(true)) })) + '</p>';
    if (bench.rec && bench.rec.on) h += '<p class="note">' + esc(bench.recFull ? tr('recFull') : tr('recOn', { mb: (bench.rec.bytes / 1e6).toFixed(1) })) + '</p>';
    h += '<p class="note">' + esc(tr('scoreNote')) + '</p>';
    el.innerHTML = h;
    if (dl) {
      const d = document.createElement('div'); d.className = 'dl';
      const btn = (label, fn) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'linkbtn'; b.textContent = label; b.addEventListener('click', fn); d.appendChild(b); };
      btn(tr('dlTruth'), () => saveFile('hinigram_injection_log.json', JSON.stringify(benchLog()), 'application/json'));
      if (bench.rec && bench.rec.lines) btn(tr('dlCsv'), () => worker && worker.postMessage({ type: 'inject-export', marker: testMarker() }));
      btn(tr('dlScores'), () => saveFile('hinigram_injection_scores.csv', benchScoresCsv(), 'text/csv'));
      el.appendChild(d);
    }
  }
  /** Whether the board flagged movement in the w seconds up to update k. */
  function movedIn(h, k, w) { for (let i = k; i >= 0 && h.t[i] > h.t[k] - w; i--) if (h.mot[i]) return true; return false; }
  /** The setup check's verdict for one chair, from the board's own updates during the routine. */
  function setupVerdict(s, c) {
    if (c.final) return c.final;   // fixed when the routine ended: later events do not change it
    const R = ROUTINES[bench.preset], j = c.join, end = j + R.end, x = bench.t - j, h = s.hops, S = s.series;
    const r = { seat: s.seat, mac: s.mac, node: parseInt(s.mac.slice(-2), 16), left: Math.max(0, end + DONE_AFTER - bench.t) };
    // a change by hand during the routine (its own start, shifts in the seat and end are not changes by hand)
    r.hand = bench.events.some((e) => { const et = e.t !== undefined ? e.t : e.t0; return e.mac === c.mac && BY_HAND.includes(e.kind) && !e.auto && !e.scripted && et > j && et <= end; });
    // packets over the routine: the mean rate, and the longest stretch without an update (a silent node has none)
    let sum = 0, cnt = 0;
    for (let k = 0; k < S.t.length; k++) if (S.t[k] >= j && S.t[k] <= end && Number.isFinite(S.rate[k])) { sum += S.rate[k]; cnt++; }
    r.pk = cnt ? sum / cnt : null;
    let n = 0, shown = 0, ok = 0, moveW = 0, flagged = null, moved = false, saidOk = 0, seen = false, falsePause = false, prevPause = false, gap = 0, last = j + 30;
    for (let k = 0; k < h.t.length && h.t[k] <= Math.min(bench.t, end); k++) {
      const u = h.t[k] - j, pause = h.status[k] === 'urgent' && reasonKey(h.reason[k]) === 'pause';
      if (h.t[k] >= j + 30) { gap = Math.max(gap, h.t[k] - last); last = h.t[k]; }
      if (s.truth && R.rates.some(([a, b]) => u >= a && u < b)) {
        if (movedIn(h, k, 30)) moveW++;   // a window the board saw movement in is not held against the link
        else {
          const w = INJ.windowTruth(s.truth, h.t[k], 30);
          if (w.full) { n++; if (h.rel[k] && h.bpm[k] !== null) { shown++; if (Math.abs(h.bpm[k] - w.bpm) <= 2) ok++; } }
        }
      }
      if (pause && u >= 30 && u < R.hold[0]) falsePause = true;   // the chair breathes all along before the hold
      if (flagged === null && pause && !prevPause && u >= R.hold[0] && u <= R.hold[1] + 8) flagged = u - R.hold[0];   // an alert that starts in the hold
      if (u >= R.hold[0] - 2 && u <= R.hold[1] && h.mot[k]) moved = true;
      if (u >= R.hold[0] + 10 && u <= R.hold[1] && h.status[k] === 'typical') saidOk++;
      if (u >= R.move && u <= R.move + 14 && h.mot[k]) seen = true;
      prevPause = pause;
    }
    if (x >= R.end) gap = Math.max(gap, end - last);
    Object.assign(r, { n, shown, ok, moveW, saidOk, flagged, gap: Math.round(gap), p: n ? Math.round((100 * shown) / n) : 0, q: shown ? Math.round((100 * ok) / shown) : 0 });
    r.drop = gap > 8;
    r.reads = x < R.rates[R.rates.length - 1][1] ? null : n >= 8 ? (shown / n < R.shown ? 'weak' : ok / shown < R.right ? 'wrong' : 'ok') : moveW >= 4 ? 'few' : 'nodata';
    r.hold = falsePause ? 'falseAlarm' : saidOk ? 'saidOk' : flagged !== null ? 'flagged' : x < R.hold[1] + 8 ? null : moved ? 'moved' : 'missed';
    r.move = x < R.move + 14 ? null : seen ? 'seen' : 'unseen';
    const bad = r.drop || (x >= R.end && (r.pk === null || r.pk < R.pk)) || ['weak', 'wrong', 'nodata'].includes(r.reads) || ['falseAlarm', 'saidOk', 'missed'].includes(r.hold) || r.move === 'unseen';
    r.verdict = x < R.end + DONE_AFTER ? null : r.hand ? 'hand' : bad ? 'check' : r.reads === 'few' || r.hold === 'moved' ? 'repeat' : 'ready';
    if (r.verdict) c.final = r;
    return r;
  }
  function setupHTML() {
    const rows = state.ds.sensors.map((s) => { const c = bench.chairs.get(s.mac); return c && c.join !== undefined && c.origScript ? setupVerdict(s, c) : null; })
      .filter(Boolean).sort((a, b) => a.seat.localeCompare(b.seat, undefined, { numeric: true }));
    bench.setupRows = rows;
    if (!rows.length) return '';
    const mk = (cls, text) => '<span class="mk ' + cls + '">' + esc((cls === 'ok' ? '✓\u00a0' : cls === 'bad' ? '✗\u00a0' : '') + text) + '</span>';
    const seats = (v) => rows.filter((x) => x.verdict === v).map((x) => x.seat).join(', ') || '–';
    const R = ROUTINES[bench.preset];
    let h = '<h3>' + esc(tr('setupH.' + bench.preset)) + '</h3>';
    if (rows.some((x) => x.verdict)) {
      const notReady = rows.some((x) => x.verdict === 'check' || x.verdict === 'repeat');
      h += '<p class="summary">' + esc(tr('setup.summary', { a: rows.filter((x) => x.verdict === 'ready').length, n: rows.length }) + (notReady ? tr('setup.more', { b: seats('check'), c: seats('repeat') }) : '')) + '</p>';
    }
    h += '<div class="tablewrap"><table class="setup"><thead><tr>' + tr('setupTh').map((x) => '<th scope="col">' + esc(x) + '</th>').join('') + '</tr></thead><tbody>';
    rows.forEach((r) => {
      const pk = r.drop ? mk('bad', tr('setup.drop', { s: r.gap })) : r.pk === null ? mk('na', '–') : mk(r.pk >= R.pk ? 'ok' : 'bad', tr('setup.pk', { r: Math.round(r.pk * 10) / 10 }));
      const reads = r.reads === null ? mk('na', '…') : r.reads === 'ok' ? mk('ok', tr('setup.reads', { p: r.p, q: r.q })) : r.reads === 'few' ? mk('na', tr('setup.few'))
        : r.reads === 'nodata' ? mk('bad', tr('setup.nodata')) : r.reads === 'weak' ? mk('bad', tr('setup.weak', { p: r.p })) : mk('bad', tr('setup.wrong', { q: r.q }));
      const hold = r.hold === null ? mk('na', '…') : r.hold === 'flagged' ? mk('ok', tr('setup.flagged', { s: Math.round(r.flagged) })) : r.hold === 'moved' ? mk('na', tr('setup.moved')) : mk('bad', tr('setup.' + r.hold));
      const mv = r.move === null ? mk('na', '…') : r.move === 'seen' ? mk('ok', tr('setup.seen')) : mk('bad', tr('setup.unseen'));
      const v = r.verdict === null ? mk('na', tr('setup.left', { t: fmtT(r.left) })) : mk(r.verdict === 'ready' ? 'ok' : r.verdict === 'check' ? 'bad' : 'na', tr('setup.' + r.verdict));
      h += '<tr><td>' + esc(r.seat + ' · ' + tr('setup.node', { n: r.node })) + '</td><td>' + pk + '</td><td>' + reads + '</td><td>' + hold + '</td><td>' + mv + '</td><td>' + v + '</td></tr>';
    });
    return h + '</tbody></table></div><p class="note">' + esc(tr('setup.crit')) + '</p>';
  }
  /** The truth log: what was put into each chair and what the board did, in the layout check_inject_bench.py reads. */
  function benchLog() {
    const ds = state.ds, r3 = (v) => (v === null || v === undefined ? null : Math.round(v * 1000) / 1000);
    return { kind: 'hinigram-injection-log', version: 1, board: DATA.version, background: bench.kind === 'receiver' ? 'live receiver' : bench.file, bg: bench.bg,
      range: bench.bg === 'quiet' ? QUIET : null, preset: bench.preset || null, savedAt: new Date().toISOString(), run_s: r3(state.t),
      check: ROUTINES[bench.preset] ? { routine: bench.preset, chairs: bench.setupRows || [] } : null,
      chairs: ds.sensors.map((s) => {
        const c = bench.chairs.get(s.mac) || {};
        const prof = (k) => (s.hops.prof && s.hops.prof[k]) || s.profile;
        return { seat: s.seat, mac: s.mac, node: c.node || null, profile: s.profile, profile_start: c.profile0 || s.profile,
          empty: !(s.truth && s.truth.bpm.some((v) => v > 0)), depth: c.depth, on: c.on !== false, src: c.srcMac || null, offset_s: r3(c.offset), join_s: r3(c.join),
          script: c.origScript || null, events: bench.events.filter((e) => e.mac === s.mac).map((e) => Object.assign({}, e, { mac: undefined })),
          truth: s.truth || { t: [], bpm: [] },
          js: s.hops.t.map((t, k) => ({ t: r3(t), status: s.hops.status[k], reason: s.hops.reason[k], bpm: r3(s.hops.bpm[k]), reliable: !!s.hops.rel[k], motion: !!s.hops.mot[k], profile: prof(k) })) };
      }) };
  }
  function benchScoresCsv() {
    const S = bench.score || benchScore(), f = (v) => (v === null || v === undefined ? '' : (Math.round(v * 100) / 100).toString());
    let out = 'seat,profile,windows_full_of_breathing,rate_shown,within_2,mean_abs_error\n' + S.perSeat.map((x) => [x.seat, x.profile, x.n, x.shown, x.ok, f(x.mae)].join(',')).join('\n') + '\n';
    out += '\nseat,hold_s,should_alert,flagged_after_s,movement_during,no_concern_updates_during\n' +
      S.holds.map((x) => [x.seat, f(x.planned !== null && x.done ? x.planned : x.len), x.should === null ? '' : x.should ? 'yes' : 'no', f(x.flagged), x.moved ? 'yes' : 'no', x.saidOk].join(',')).join('\n') + '\n';
    if (ROUTINES[bench.preset] && bench.setupRows) {
      out += '\nseat,node_mac,packets_per_s,longest_gap_s,windows_scored,windows_with_movement,rate_shown,within_2,reads_breathing,breath_hold,hold_flagged_after_s,no_concern_updates_during_hold,shift_in_seat,changed_by_hand,verdict\n' +
        bench.setupRows.map((x) => [x.seat, x.mac, f(x.pk), x.gap, x.n, x.moveW, x.shown, x.ok, x.reads || '', x.hold || '', f(x.flagged), x.saidOk, x.move || '', x.hand ? 'yes' : 'no', x.verdict || 'running'].join(',')).join('\n') + '\n';
    }
    out += '\nseat,pause_alert_episodes_without_a_hold,nobody_breathing_in_chair\n' + S.falseAlerts.map((x) => [x.seat, x.n, x.empty ? 'yes' : 'no'].join(',')).join('\n') + '\n';
    return out;
  }
  function benchWire() {
    $('bench-go').addEventListener('click', () => {
      if (!bench.kind) benchStart();
      else if (bench.kind === 'receiver') benchNew();
      else benchRun(!bench.running);
    });
    $('bench-reset').addEventListener('click', benchNew);
    $('bench-bg').addEventListener('change', () => {
      if ($('bench-bg').value === 'csv' && !bench.csv) $('bench-file').click();
      if ($('bench-bg').value === 'receiver') $('bench-preset').value = 'quick';   // the receiver's usual job: check the room
      benchControls();
    });
    ['bench-preset', 'bench-n'].forEach((id) => $(id).addEventListener('change', benchControls));
    $('bench-speed').addEventListener('change', () => { bench.speed = +$('bench-speed').value; if (worker && bench.kind === 'player') worker.postMessage({ type: 'inject-speed', speed: bench.speed }); });
    $('bench-baud').addEventListener('change', () => setBaud(+$('bench-baud').value));
    $('bench-file').addEventListener('change', (ev) => {
      const f = ev.target.files && ev.target.files[0];
      if (!f) return;
      f.text().then((text) => {
        // count packets, sensors and duration on the receiver clock, so chairs can be spread over the recording
        const macs = new Map();
        let n = 0;
        for (const ln of text.split(/\r?\n/)) {
          const r = DSP.parseLine(ln);
          if (!r || r.len !== 128) continue;
          n++;
          const m = macs.get(r.mac) || { first: r.ts_us, last: r.ts_us, add: 0, prev: r.ts_us };
          if (r.ts_us - m.prev < -2147483648) m.add += 4294967296;
          m.prev = r.ts_us; m.last = r.ts_us + m.add; macs.set(r.mac, m);
        }
        const D = Math.min(...Array.from(macs.values()).map((m) => (m.last - m.first) / 1e6));
        if (!n || !(D > 10)) { bench.csv = null; showMsg(tr('csvErr')); benchControls(); return; }
        bench.csv = { text, name: f.name, n, k: macs.size, D };
        showMsg(''); $('bench-bg').value = 'csv'; benchControls();
      });
      ev.target.value = '';
    });
  }

  // ------------------------------------------------------------------ playback loop
  let prevFrame = performance.now();
  function frame(now) {
    const dt = Math.min(0.25, Math.max(0, (now - prevFrame) / 1000));
    prevFrame = now;
    const ds = state.ds;
    if (ds && state.playing && state.source !== 'live') {
      state.t += dt * state.speed;
      if (state.t >= ds.duration) { state.t = ds.duration; state.playing = false; syncPlay(); }
    } else if (ds && state.source === 'live' && state.live && state.live.connected && ds.sensors.length) {
      state.t += dt; // wall time keeps moving so a silent sensor shows up as lost
    } else if (ds && state.source === 'inject') {
      if (bench.kind === 'player' && bench.running) state.t = Math.min(state.t + dt * bench.speed, bench.t + 0.3 * bench.speed);
      else if (bench.kind === 'receiver' && state.live && state.live.connected && ds.sensors.length) state.t += dt;
    }
    if (state.source === 'inject') benchFrame(now);
    if (ds) renderAll(false);
    paceFrame();
    requestAnimationFrame(frame);
  }
  function syncPlay() {
    $('ico-play').hidden = state.playing; $('ico-pause').hidden = !state.playing;
    $('btn-play').setAttribute('aria-label', state.playing ? tr('pause') : tr('play'));
  }

  // ------------------------------------------------------------------ language
  function applyLang() {
    document.documentElement.lang = lang === 'en' ? 'en' : 'fil';
    document.querySelectorAll('[data-i18n]').forEach((el) => { const v = T[lang][el.dataset.i18n]; if (typeof v === 'string') el.textContent = v; });
    $('lang-en').setAttribute('aria-pressed', String(lang === 'en'));
    $('lang-fil').setAttribute('aria-pressed', String(lang === 'fil'));
    syncPlay();
    renderAll(true);
    benchControls(); benchPanelKey = ''; benchFrame(0, true);
  }

  // ------------------------------------------------------------------ worker: file analysis and live stream
  let worker = null;
  function getWorker() {
    if (worker) return worker;
    const src = document.getElementById('dsp-src').textContent + '\n' + document.getElementById('inject-src').textContent + '\n' + document.getElementById('worker-src').textContent;
    worker = new Worker(URL.createObjectURL(new Blob([src], { type: 'text/javascript' })));
    worker.onmessage = onWorker;
    worker.onerror = () => showMsg(tr('fileErr'));
    return worker;
  }
  function showMsg(text) { const m = $('msg'); if (!text) { m.hidden = true; m.textContent = ''; return; } m.textContent = text; m.hidden = false; }
  let lastFile = null;
  // first line of the bench's packet download; the pipelines read only CSI_DATA lines, so they skip it
  const TEST_MARK = /^\uFEFF?# hinigram-injection-bench/;
  const testMarker = () => ('# hinigram-injection-bench v1: simulated breathing added to real Wi-Fi packets; test data, not a patient recording; ' + DATA.version +
    '; preset ' + (bench.kind === 'receiver' ? 'receiver' : bench.preset || '') + '; background ' + (bench.kind === 'receiver' ? 'live receiver' : bench.file || '')).replace(/CSI_DATA|[\r\n]/g, ' ');
  function analyzeFile(text, name, profiles) {
    showMsg(tr('loading'));
    lastFile = { text, name, profiles: profiles || {} };
    getWorker().postMessage({ type: 'analyze', text, name, profiles: lastFile.profiles });
  }
  function onWorker(ev) {
    const m = ev.data;
    if (m.run !== undefined && (m.run !== bench.runs || !bench.kind)) return; // from an earlier or a stopped bench run
    if (m.epoch !== undefined && m.epoch !== liveEpoch) return;                // from an earlier receiver session
    if (m.type === 'progress') showMsg(m.done < m.total ? tr('progress', { a: m.done, b: m.total }) : tr('loading'));
    else if (m.type === 'result') {
      m.data.test = !!(lastFile && TEST_MARK.test(lastFile.text.slice(0, 200)));
      showMsg(m.data.short ? tr('shortFile') : m.data.test ? tr('testFile') : '');
      state.fileDs = m.data;
      const pend = state.pending; state.pending = null;
      setSource('file', m.data);
      if (pend) { state.t = Math.min(pend.t, m.data.duration); state.selected = pend.seat; renderAll(true); }
    } else if (m.type === 'error') { if (m.during === 'inject-start') benchFailed(); else showMsg(tr('fileErr')); }
    else if (m.type === 'live') liveUpdate(m.updates, m.packets, m.src);
    else if (m.type && m.type.indexOf('inject-') === 0) benchMessage(m);
    if (bench.kind && (m.type === 'live' || m.type === 'inject-tick')) benchDrive();
  }
  function changeProfile(s, profile) {
    if (state.source === 'file' && lastFile) {
      const p = Object.assign({}, lastFile.profiles); p[s.mac] = profile;
      state.pending = { t: state.t, seat: s.seat };
      analyzeFile(lastFile.text, lastFile.name, p);
    } else if (state.source === 'inject' && worker) {
      // the pipeline starts afresh for the new profile; earlier updates stay, scored with the profile they were made with
      benchSet(s, { profile }, 'profile');
      s.profile = profile;
      renderAll(true);
    } else if (state.source === 'live' && worker) {
      worker.postMessage({ type: 'live-profile', mac: s.mac, profile });
      s.profile = profile;
      const h = s.hops; Object.keys(h).forEach((k) => { h[k] = []; });
      renderAll(true);
    }
  }
  function liveUpdate(updates, packets, src) {
    const ds = src === 'bench' ? bench.ds : state.live && state.live.ds;
    if (!ds) return;
    ds.packets = packets;
    for (const u of updates) {
      let s = ds.sensors.find((x) => x.mac === u.mac);
      if (!s) {
        if (src === 'bench') continue; // a bench run has a fixed set of chairs
        if (!liveSeats.has(u.mac)) liveSeats.set(u.mac, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[liveSeats.size] || String(liveSeats.size + 1));
        s = { mac: u.mac, label: u.label, seat: liveSeats.get(u.mac), profile: u.profile, health: {},
          hops: newHops(),
          wave: { t0: 0, fs: 10, v: [] }, series: { t: [], rate: [], rssi: [], steps: [], act: [] } };
        ds.sensors.push(s);
      }
      if (u.profile !== s.profile) continue; // stale update from before a profile change
      const h = s.hops;
      h.t.push(u.t); h.status.push(u.status); h.reason.push(u.reason); h.bpm.push(u.bpm); h.raw.push(u.raw);
      h.q.push(u.quality); h.rel.push(!!u.reliable); h.mot.push(!!u.motion); h.pause.push(u.pause); h.snr.push(u.snr); if (h.prof) h.prof.push(u.profile);
      s.wave = { t0: u.t - u.wave.length / 10, fs: 10, v: u.wave };
      s.series.t.push(u.t); s.series.rate.push(u.rate); s.series.rssi.push(u.rssi); s.series.steps.push(u.steps); s.series.act.push(u.activity);
      s.health = { rate_hz: u.rate, loss_pct: u.lossPct, max_gap_ms: null, rssi_mean_dbm: u.rssi, gain_step_pct: u.steps, channel: u.channel, valid_subcarriers: u.nsc };
      ds.duration = Math.max(ds.duration, u.t);
    }
    if ((state.source !== 'live' && state.source !== 'inject') || ds !== state.ds) return;
    if (src !== 'bench') state.t = Math.max(state.t, ds.duration);
    $('scrub').max = String(Math.max(30, ds.duration));
  }
  // the receiver's serial speed: one choice for "Connect receiver" and the bench, remembered in this browser
  let liveEpoch = 0;   // the receiver session the page is showing
  const liveSeats = new Map();   // node -> seat letter, kept when the live board starts afresh, so a seat keeps its letter
  let baud = 921600;
  try { if (+localStorage.getItem('hinigram-baud') === 2000000) baud = 2000000; } catch (e) { /* storage blocked */ }
  function setBaud(b) {
    if (state.live && state.live.connected) b = baud; // an open port keeps its speed; both selects show it
    baud = b === 2000000 ? 2000000 : 921600;
    $('live-baud').value = $('bench-baud').value = String(baud);
    try { localStorage.setItem('hinigram-baud', String(baud)); } catch (e) { /* storage blocked */ }
  }
  async function connectSerial(opts) {
    opts = opts || {};
    const as = opts.bench ? 'inject' : 'live';
    if (state.live && state.live.connected) { if (opts.bench) opts.onOpen(state.live.ds); setSource(as, state.live.ds); return; }
    if (!('serial' in navigator)) { showMsg(tr('noSerial')); if (opts.onFail) opts.onFail(); return; }
    let port;
    try {
      showMsg(tr('serialAsk'));
      port = await navigator.serial.requestPort();
      await port.open({ baudRate: baud });
    } catch (e) { showMsg(tr('noSerial')); if (opts.onFail) opts.onFail(); return; }
    showMsg(tr('serialOn', { b: baud }));
    const ds = { title: 'Live', file: null, duration: 30, packets: 0, start: new Date().toISOString(), sensors: [] };
    state.live = { port, ds, connected: true };
    $('live-baud').disabled = true;
    const w = getWorker();
    liveEpoch++;
    w.postMessage({ type: 'live-start', profiles: {}, epoch: liveEpoch });
    if (opts.bench) opts.onOpen(ds);
    setSource(as, ds);
    try {
      const reader = port.readable.pipeThrough(new TextDecoderStream()).getReader();
      let buf = '', batch = [], lastSend = performance.now();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += value;
        const lines = buf.split(/\r?\n/);
        buf = lines.pop() || '';
        for (const ln of lines) if (ln.indexOf('CSI_DATA') >= 0) batch.push(ln);
        if (batch.length && performance.now() - lastSend > 250) {
          w.postMessage({ type: 'live-lines', lines: batch }); batch = []; lastSend = performance.now();
          if ($('msg').textContent === tr('serialOn', { b: baud })) showMsg('');
        }
      }
    } catch (e) { /* cable pulled or port closed */ }
    state.live.connected = false;
    $('live-baud').disabled = false;
    showMsg(tr('serialLost'));
  }

  // ------------------------------------------------------------------ wiring
  $('lang-en').addEventListener('click', () => { lang = 'en'; applyLang(); });
  $('lang-fil').addEventListener('click', () => { lang = 'fil'; applyLang(); });
  $('src-demo').addEventListener('click', () => { showMsg(''); setSource('demo', DATA.sources.demo); });
  $('src-sample').addEventListener('click', () => { showMsg(''); setSource('sample', DATA.sources.sample); });
  $('src-file').addEventListener('click', () => $('file-input').click());
  $('pace-start').addEventListener('click', startPace);
  $('pace-load').addEventListener('click', () => $('pace-input').click());
  $('pace-input').addEventListener('change', onPaceFile);
  $('src-live').addEventListener('click', () => connectSerial());
  setBaud(baud);
  $('live-baud').addEventListener('change', () => setBaud(+$('live-baud').value));
  $('src-inject').addEventListener('click', openBench);
  benchWire();
  $('file-input').addEventListener('change', (ev) => {
    const f = ev.target.files && ev.target.files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => analyzeFile(String(r.result), f.name, {});
    r.onerror = () => showMsg(tr('fileErr'));
    r.readAsText(f);
    ev.target.value = '';
  });
  $('btn-play').addEventListener('click', () => {
    if (!state.ds) return;
    if (!state.playing && state.t >= state.ds.duration - 0.01) state.t = 30;
    state.playing = !state.playing; syncPlay();
  });
  const scrub = $('scrub');
  scrub.addEventListener('input', () => { state.scrubbing = true; state.t = parseFloat(scrub.value); renderAll(false); });
  scrub.addEventListener('change', () => { state.scrubbing = false; });
  scrub.addEventListener('pointerup', () => { state.scrubbing = false; });
  $('speed').addEventListener('change', () => { state.speed = parseFloat($('speed').value); });
  $('eng').addEventListener('toggle', () => {
    if (!$('eng').open || !state.ds) return;
    renderHealth(); lastDraw = 0;
    drawCanvases(state.ds.sensors.map((s) => seatState(s, state.t)));
  });
  ['eng-rate', 'eng-rssi', 'eng-steps', 'eng-act'].forEach((id) => attachTip($(id), (x) => engTip($(id), x)));
  let rsT = null;
  const onResize = () => { lastDraw = 0; clearTimeout(rsT); rsT = setTimeout(() => { if (state.ds) renderMap(state.ds.sensors.map((s) => seatState(s, state.t)), true); }, 120); };
  window.addEventListener('resize', onResize);
  if (window.ResizeObserver) new ResizeObserver(onResize).observe(document.querySelector('.plan'));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { lastDraw = 0; mapW = 0; if (state.ds) renderAll(true); });

  setSource('demo', DATA.sources.demo);
  applyLang();
  requestAnimationFrame(frame);
})();
