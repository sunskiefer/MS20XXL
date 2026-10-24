# MS20XXL inventory

Every control and jack of the instrument, generated from `tools/spec.py` (the build checks the skin against the same list). MS-20 = on the original's panel; XXL = this plugin's addition.

Left out, and why: the external audio input and PHONES (an MPC instrument plugin receives no audio and has one output), and the keyboard's own CV/trig sockets on the rear (MIDI does that job).

## Voltage Controlled Oscillators  /  Vco Mixer

| Control | Key | Range | Origin |
|---|---|---|---|
| VCO 1 Wave Form | `vco1_wave` | Triangle / Sawtooth / Pulse / White Noise | MS-20 |
| VCO 1 PW | `vco1_pw` | 0 .. 10 | MS-20 |
| VCO 1 Scale | `vco1_scale` | 32' / 16' / 8' / 4' | MS-20 |
| VCO 2 Wave Form | `vco2_wave` | Sawtooth / Square / Pulse / Ring Mod | MS-20 |
| VCO 2 Pitch | `vco2_pitch` | -5 .. 5 | MS-20 |
| VCO 2 Scale | `vco2_scale` | 16' / 8' / 4' / 2' | MS-20 |
| VCO 1 Level | `vco1_level` | 0 .. 10 | MS-20 |
| VCO 2 Level | `vco2_level` | 0 .. 10 | MS-20 |
| Portamento Time | `porta` | 0 .. 10 | MS-20 |
| Master Tune | `master_tune` | -100 .. 100 ct | MS-20 |
| Unison | `unison` | Off / 2 Voices / 4 Voices | XXL |
| Unison Detune | `unison_detune` | 0 .. 10 | XXL |

## Voltage Controlled Highpass  /  Lowpass Filter

| Control | Key | Range | Origin |
|---|---|---|---|
| HPF Cutoff Frequency | `hpf_cutoff` | 0 .. 10 | MS-20 |
| HPF Peak | `hpf_peak` | 0 .. 10 | MS-20 |
| HPF MG/T.EXT | `hpf_mg` | 0 .. 10 | MS-20 |
| HPF EG2/EXT | `hpf_eg2` | 0 .. 10 | MS-20 |
| LPF Cutoff Frequency | `lpf_cutoff` | 0 .. 10 | MS-20 |
| LPF Peak | `lpf_peak` | 0 .. 10 | MS-20 |
| LPF MG/T.EXT | `lpf_mg` | 0 .. 10 | MS-20 |
| LPF EG2/EXT | `lpf_eg2` | 0 .. 10 | MS-20 |
| Filter | `filter_mk` | MK1 / MK2 | XXL |
| Filter Drive | `filter_drive` | 0 .. 10 | XXL |

## Modulation Generator  /  Frequency Modulation

| Control | Key | Range | Origin |
|---|---|---|---|
| Freq Mod MG/T.EXT | `fm_mg` | 0 .. 10 | MS-20 |
| Freq Mod EG1/EXT | `fm_eg1` | 0 .. 10 | MS-20 |
| MG Wave Form | `mg_wave` | 0 .. 10 | MS-20 |
| MG Frequency | `mg_freq` | 0 .. 10 | MS-20 |
| MG | `mg_mode` | Free / Reset | XXL |
| MG Sync | `mg_sync` | 12 options | XXL |
| PW Mod MG/EXT | `pwm_mg` | 0 .. 10 | XXL |
| PW Mod To | `pwm_vco` | VCO 1 / VCO 2 | XXL |
| VCA Mod MG/EXT | `vca_mg` | 0 .. 10 | XXL |
| VCA Velocity | `vca_vel` | 0 .. 10 | XXL |
| LPF Velocity | `vcf_vel` | 0 .. 10 | XXL |

## Envelope Generator 1  /  Envelope Generator 2

| Control | Key | Range | Origin |
|---|---|---|---|
| EG1 Delay Time | `eg1_delay` | 0 .. 10 | MS-20 |
| EG1 Attack Time | `eg1_attack` | 0 .. 10 | MS-20 |
| EG1 Release Time | `eg1_release` | 0 .. 10 | MS-20 |
| EG1 Mode | `eg1_mode` | Normal / Trigger / Loop | XXL |
| EG2 Hold Time | `eg2_hold` | 0 .. 10 | MS-20 |
| EG2 Attack Time | `eg2_attack` | 0 .. 10 | MS-20 |
| EG2 Decay Time | `eg2_decay` | 0 .. 10 | MS-20 |
| EG2 Sustain Level | `eg2_sustain` | 0 .. 10 | MS-20 |
| EG2 Release Time | `eg2_release` | 0 .. 10 | MS-20 |
| Key Trigger | `eg_trig` | Single / Multi | XXL |

## External Signal Processor

| Control | Key | Range | Origin |
|---|---|---|---|
| Signal Level | `esp_level` | 0 .. 10 | MS-20 |
| Low Cut Freq | `esp_low` | 0 .. 10 | MS-20 |
| High Cut Freq | `esp_high` | 0 .. 10 | MS-20 |
| CV Adjust | `esp_cv` | 0 .. 10 | MS-20 |
| Threshold Level | `esp_thresh` | 0 .. 10 | MS-20 |

## Sequencer

| Control | Key | Range | Origin |
|---|---|---|---|
| Clock Speed | `seq_speed` | 0 .. 10 | XXL |
| Swing | `seq_swing` | 50 .. 75 % | XXL |
| Gate | `seq_gate` | 0 .. 10 | XXL |
| Sequence Length | `seq_length` | 1 .. 12 | XXL |
| Portamento A/B | `seq_porta_ab` | 0 .. 10 | XXL |
| Portamento C | `seq_porta_c` | 0 .. 10 | XXL |
| Clock Sync | `seq_sync` | 12 options | XXL |
| Sequence Mode | `seq_mode` | 12 Loop / 12 Once / 24 Loop / 24 Once | XXL |
| Channel A | `seq_range_a` | +/-1 V / +/-5 V | XXL |
| Channel B | `seq_range_b` | +/-1 V / +/-5 V | XXL |
| Channel C | `seq_range_c` | 0..+5 V / +/-12 st | XXL |
| Run | `seq_run` | Off / On | XXL |
| With Transport | `seq_transport` | Off / On | XXL |
| Step | `seq_step_btn` | push | XXL |
| A 1 | `seq_a1` | -5 .. 5 | XXL |
| A 2 | `seq_a2` | -5 .. 5 | XXL |
| A 3 | `seq_a3` | -5 .. 5 | XXL |
| A 4 | `seq_a4` | -5 .. 5 | XXL |
| A 5 | `seq_a5` | -5 .. 5 | XXL |
| A 6 | `seq_a6` | -5 .. 5 | XXL |
| A 7 | `seq_a7` | -5 .. 5 | XXL |
| A 8 | `seq_a8` | -5 .. 5 | XXL |
| A 9 | `seq_a9` | -5 .. 5 | XXL |
| A 10 | `seq_a10` | -5 .. 5 | XXL |
| A 11 | `seq_a11` | -5 .. 5 | XXL |
| A 12 | `seq_a12` | -5 .. 5 | XXL |
| B 1 | `seq_b1` | -5 .. 5 | XXL |
| B 2 | `seq_b2` | -5 .. 5 | XXL |
| B 3 | `seq_b3` | -5 .. 5 | XXL |
| B 4 | `seq_b4` | -5 .. 5 | XXL |
| B 5 | `seq_b5` | -5 .. 5 | XXL |
| B 6 | `seq_b6` | -5 .. 5 | XXL |
| B 7 | `seq_b7` | -5 .. 5 | XXL |
| B 8 | `seq_b8` | -5 .. 5 | XXL |
| B 9 | `seq_b9` | -5 .. 5 | XXL |
| B 10 | `seq_b10` | -5 .. 5 | XXL |
| B 11 | `seq_b11` | -5 .. 5 | XXL |
| B 12 | `seq_b12` | -5 .. 5 | XXL |
| C 1 | `seq_c1` | -5 .. 5 | XXL |
| C 2 | `seq_c2` | -5 .. 5 | XXL |
| C 3 | `seq_c3` | -5 .. 5 | XXL |
| C 4 | `seq_c4` | -5 .. 5 | XXL |
| C 5 | `seq_c5` | -5 .. 5 | XXL |
| C 6 | `seq_c6` | -5 .. 5 | XXL |
| C 7 | `seq_c7` | -5 .. 5 | XXL |
| C 8 | `seq_c8` | -5 .. 5 | XXL |
| C 9 | `seq_c9` | -5 .. 5 | XXL |
| C 10 | `seq_c10` | -5 .. 5 | XXL |
| C 11 | `seq_c11` | -5 .. 5 | XXL |
| C 12 | `seq_c12` | -5 .. 5 | XXL |
| Porta C 1 | `seq_pc1` | Off / On | XXL |
| Porta C 2 | `seq_pc2` | Off / On | XXL |
| Porta C 3 | `seq_pc3` | Off / On | XXL |
| Porta C 4 | `seq_pc4` | Off / On | XXL |
| Porta C 5 | `seq_pc5` | Off / On | XXL |
| Porta C 6 | `seq_pc6` | Off / On | XXL |
| Porta C 7 | `seq_pc7` | Off / On | XXL |
| Porta C 8 | `seq_pc8` | Off / On | XXL |
| Porta C 9 | `seq_pc9` | Off / On | XXL |
| Porta C 10 | `seq_pc10` | Off / On | XXL |
| Porta C 11 | `seq_pc11` | Off / On | XXL |
| Porta C 12 | `seq_pc12` | Off / On | XXL |
| Trigger 1 | `seq_t1` | Off / On | XXL |
| Trigger 2 | `seq_t2` | Off / On | XXL |
| Trigger 3 | `seq_t3` | Off / On | XXL |
| Trigger 4 | `seq_t4` | Off / On | XXL |
| Trigger 5 | `seq_t5` | Off / On | XXL |
| Trigger 6 | `seq_t6` | Off / On | XXL |
| Trigger 7 | `seq_t7` | Off / On | XXL |
| Trigger 8 | `seq_t8` | Off / On | XXL |
| Trigger 9 | `seq_t9` | Off / On | XXL |
| Trigger 10 | `seq_t10` | Off / On | XXL |
| Trigger 11 | `seq_t11` | Off / On | XXL |
| Trigger 12 | `seq_t12` | Off / On | XXL |

## Setup  /  Midi

| Control | Key | Range | Origin |
|---|---|---|---|
| Key Priority | `key_prio` | Low Note / High Note / Last Note | XXL |
| Pitch Bend Range | `pb_range` | 0 .. 12 st | XXL |
| Mod Wheel | `wheel_to` | Wheel Jack / MG Pitch / LPF Cutoff | XXL |
| Analog Noise | `noise_floor` | 0 .. 10 | XXL |
| VCO Drift | `drift` | 0 .. 10 | XXL |
| S&H Clock (unpatched) | `sh_clock_def` | MG Rect / KBD Trig / Seq Trig | XXL |
| S&H Input (unpatched) | `sh_in_def` | White Noise / Pink Noise / MG Tri | XXL |

## Patch Panel

| Control | Key | Range | Origin |
|---|---|---|---|
| Volume | `volume` | 0 .. 10 | MS-20 |
| Manual Control Switch | `mom_switch` | Off / On | MS-20 |

## Patch panel

Each output feeds one input, one cable per socket, as with real patch cords. An input with no cable uses its normalled source, as on the MS-20.

### Outputs

| Jack | Signal |
|---|---|
| MG TRI | Modulation generator triangle, -2.5..+2.5 V |
| MG RECT | Modulation generator rectangle, 0 / +5 V |
| EG1 OUT | Envelope generator 1, 0..+5 V |
| EG1 REV | Envelope generator 1 reversed, +5 V down to 0 |
| EG2 REV | Envelope generator 2 reversed, +5 V down to 0 |
| EG2 OUT | Envelope generator 2, 0..+5 V (XXL: the MS-20 has only REV OUT) |
| KBD CV | Keyboard CV, Hz/V: 1 V = the low C, 8 V = the high C |
| TRIG OUT | Keyboard gate, +5 V while a key is down |
| S&H OUT | Sample & hold output |
| VCA OUT | Modulation VCA output |
| PINK | Pink noise, -5..+5 V |
| WHITE | White noise, -5..+5 V |
| WHEEL | Mod wheel, 0..+5 V |
| SWITCH | Manual control switch, +5 V while on |
| SIGNAL OUT | The synth's output, before VOLUME (patch it into the ESP) |
| AMP OUT | ESP amplifier output |
| BPF OUT | ESP band pass filter output |
| F-V CV OUT | ESP frequency-to-voltage CV, Hz/V |
| ENV OUT | ESP envelope follower, 0..+5 V |
| ESP TRIG | ESP trigger, +5 V above the threshold |
| SEQ A | Sequencer channel A |
| SEQ B | Sequencer channel B |
| SEQ C | Sequencer channel C |
| SEQ TRIG | Sequencer trigger, +5 V for the gate time |
| VCO 1 OUT | VCO 1, 5 Vpp (XXL) |
| VCO 2 OUT | VCO 2, 5 Vpp (XXL) |
| VEL CV | Velocity of the last key, 0..+5 V (XXL) |
| AFTER CV | Aftertouch, 0..+5 V (XXL) |

### Inputs

| Jack | Unpatched | Destination |
|---|---|---|
| TOTAL | - | Replaces MG TRI at the three MG/T.EXT knobs: pitch (1 oct/V at 10), HPF and LPF (2 oct/V at 10) |
| FREQ | - | Replaces EG1 at the EG1/EXT frequency modulation knob, 1 oct/V at 10 |
| EXT SIGNAL IN | - | Audio into the VCO mixer, 3 Vpp max |
| HPF CUTOFF | - | Replaces EG2 at the HPF EG2/EXT knob, 2 oct/V at 10 |
| LPF CUTOFF | - | Replaces EG2 at the LPF EG2/EXT knob, 2 oct/V at 10 |
| INITIAL GAIN | - | Opens the VCA, 0..+5 V, added to EG2 |
| VCO 1+2 CV IN | keyboard | Hz/V pitch of both VCOs; the keyboard until patched |
| VCO 2 CV IN | - | Hz/V, added to VCO 2 |
| S&H CLOCK | MG RECT | Sample & hold clock (rising edge); MG RECT until patched |
| S&H IN | WHITE | Sample & hold input; white noise until patched (Setup) |
| CONTROL IN | - | Modulation VCA gain, 0..+5 V; open until patched |
| VCA IN | - | Modulation VCA input |
| EG1 TRIG IN | keyboard | Triggers EG1 alone; the keyboard until patched |
| TRIG IN | keyboard | Triggers EG1 and EG2; the keyboard until patched |
| SIGNAL IN | - | ESP input (patch SIGNAL OUT, a VCO or noise) |
| SEQ CLOCK IN | - | External sequencer clock (rising edge) replaces the internal one |
| SEQ RESET | - | A rising edge restarts the sequence at step 1 |
| SPEED x2/V | - | Clock speed modulation: each +1 V doubles it, -1 V halves it (SQ-10 x2 / /2 inputs) |
| SEQ START/STOP | - | A rising edge starts or stops the sequencer (SQ-10 EXT START/STOP) |
| PWM IN | - | Replaces MG TRI at the PW MOD MG/EXT knob (XXL) |

131 controls, 28 outputs, 20 inputs.
