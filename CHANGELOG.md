# Changelog

## 0.1.1 (2026-10-25)
Panel layout fixes, no change to the sound or to any parameter index (one parameter, Touch Info, is added at the end).
- Patch panel: the signal-chain boxes (VCO 1 ... VCA) no longer sit on the yellow jack names, the block-diagram lines no
  longer run through the names, and TRIG OUT is no longer hidden behind the KBD box.
- Sequencer page: the clock / swing / gate and length / portamento knobs, CLOCK SYNC, MODE, the RANGE A / B / C switches
  and the RUN / TRANSPORT switches no longer print over each other or over the knobs below them; the RUN and TRANSPORT
  names sit beside their switches, the A / B / C and PORTA / TRIG row names clear the first step knob.
- The value of the control you move now shows in the top right corner of the header (name and value, e.g. "Swing  60 %");
  the value text that sat under every knob, on top of its name and scale, is gone.

## 0.1.0 (2026-10-24)
First release. Korg MS-20-style semi-modular mono synth, circuit-modelled: KLM-307 (MK2) and KORG35 (MK1) filter
boards, the capacitor-return highpass, Hz/V keyboard and VCO CV sockets, the panel's voltage laws; all 15 inputs and
20 outputs of the MS-20 patch panel in their positions, normalled as on the panel, plus XXL extras (EG2 OUT, VCO 1 / 2 /
signal outs, velocity and aftertouch CVs, PWM, unison); SQ-10-style step sequencer (3 x 12, 12 / 24 steps, loop / once,
DUTY, swing, portamento, start/stop, reset, clock in, speed CV) on the patch panel; PS3100XXL's overview tiles and
tap-tap patching; 62 factory patches with their cables (Korg's own settings examples, bass, drum, keyboard, lead, FX,
sequencer). Offline tests pass under ASan / UBSan; not yet checked on a Force.
