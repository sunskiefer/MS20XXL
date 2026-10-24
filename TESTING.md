# Testing MS20XXL

## Offline (every push, CI)
`bash test/run_tests.sh`: the engine under ASan/UBSan (test/engine_test.cc: navigation, Q-Links, patching by pages,
state with cables, the normalled synth's pitch at A4 (Hz/V tracking), scale, key priority, every VCO waveform, filter
closing and self-oscillation on both boards, HPF thinning, envelopes, the panel changing the sound, the SIGNAL OUT -> ESP
feedback patch, every one of the 560 cables, every control swept, the sequencer playing and stepping, one-shot stopping,
sample-accurate block sizes, CPU), the framework's host test, and the UI through the wrapper (test/ui_test.c: pop-ups,
the header buttons, patch steps as MPC drives them, presets' cables, the sequencer's RUN and lamps).

## On the device (to be done)
| # | Check | Result |
|---|---|---|
| 1 | Plugin inserts, overview shows, tiles open their pages, OVERVIEW / < / > work | |
| 2 | Knobs turn in place (filmstrips), text readable at arm's length | |
| 3 | Patch panel: tap MG TRI, inputs light; tap TOTAL; CONNECTED page; DONE; the yellow cable stays | |
| 4 | Tap a patched socket: its cable page; UNPLUG removes it | |
| 5 | Input first then output patches too; CANCEL drops a half-made patch | |
| 6 | Presets load with their cables (e.g. "Arpeggiate Up" patches three cords) | |
| 7 | Sequencer: RUN, lamps step, SEQ A -> TOTAL + SEQ TRIG -> TRIG IN plays with no key | |
| 8 | WITH TRANSPORT follows play / stop; CLOCK SYNC follows the tempo | |
| 9 | LPF PEAK at 10 self-oscillates; MK1 / MK2 differ | |
| 10 | Q-Links follow the section; the automation screen keeps working (UpdateDisplay fix) | |
| 11 | Project save / reload keeps controls and cables | |
| 12 | bench.sh PASS | |
