"""MS20XXL: the one source of truth for every control, jack, view and position.

Everything else is generated from this file:
  tools/gen_params.py  -> params.json, src/param_ids.h, layout.conf, docs/INVENTORY.md, presets.json
  tools/post_skin.py   -> panel art, knob strips, jacks, cables, overview (reads the built skin + this file)

MPC stores automation and saved values by parameter INDEX, so once a version ships, the parameter list below is
append-only: never reorder, rename a key or remove a parameter.

Coordinates are skin pixels: the plugin page is 1280 x 628 (layout.conf adds 86 to y, the Force Shadow offset).

Inventory sources: the Korg MS-20 panel and its patch sheet (every knob, switch and jack of the original, in the
original's positions), the MS-20 owner's manual (ranges, normalled connections) and, for the sequencer, the Korg SQ-10.
XXL extras are marked: the step sequencer, VCO 1 / VCO 2 / signal outputs on the patch panel, EG2 OUT (the MS-20 only
has its REV OUT), velocity and aftertouch CVs, PWM, unison, a MK1 / MK2 filter switch.
"""

# ---------------------------------------------------------------------------------------------- shared option lists
OFF_ON = ["Off", "On"]
DIVS = ["1/1", "1/2", "1/4", "1/8", "1/16", "1/32", "1/4 T", "1/8 T", "1/16 T", "1/8 .", "1/16 ."]
DIV_BEATS = [4, 2, 1, 0.5, 0.25, 0.125, 2 / 3.0, 1 / 3.0, 1 / 6.0, 0.75, 0.375]
SYNC = ["Free"] + DIVS

# ---------------------------------------------------------------------------------------------------------- views
# (key, title on the zoomed page, title on the overview tile)
VIEWS = [
    ("overview", "MS20XXL", ""),
    ("vco", "VOLTAGE CONTROLLED OSCILLATORS  /  VCO MIXER", "OSCILLATORS"),
    ("vcf", "VOLTAGE CONTROLLED HIGHPASS  /  LOWPASS FILTER", "FILTERS"),
    ("mod", "MODULATION GENERATOR  /  FREQUENCY MODULATION", "MODULATION"),
    ("env", "ENVELOPE GENERATOR 1  /  ENVELOPE GENERATOR 2", "ENVELOPES"),
    ("esp", "EXTERNAL SIGNAL PROCESSOR", "ESP"),
    ("seq", "SEQUENCER", "SEQUENCER"),
    ("setup", "SETUP  /  MIDI", "SETUP"),
    ("patch", "PATCH PANEL", "PATCH PANEL"),
]
VIEW_KEYS = [v[0] for v in VIEWS]
# Overview tiles (x, y, w, h) on the 1280 x 628 page: the signal path along the top row, modulation, sequencer and
# setup below, the patch panel large at the bottom.
TILES = {}
_TW, _TH, _GAP = 250, 123, 6
for _i, _k in enumerate(["vco", "vcf", "mod", "env", "esp"]):
    TILES[_k] = (5 + _i * (_TW + _GAP), 74, _TW, _TH)
for _i, _k in enumerate(["seq", "setup"]):
    TILES[_k] = (5 + _i * (_TW + _GAP), 74 + _TH + _GAP, _TW, _TH)
TILES["patch"] = (5, 74 + 2 * (_TH + _GAP), 556, 273)   # the patch panel, big: its cables are the point

# --------------------------------------------------------------------------------------------------- the controls
# Each control: dict(key, name, kind, ...). kind: knob (min, max, default, r), toggle (default), enum (options,
# default, widget: enum_h / popup, sw, sh, rows), button (momentary). view + cx, cy place it on its zoomed page.
BIG, SMALL, STEP = 58, 46, 27          # knob radii; STEP: the sequencer's 36 step knobs


def K(key, name, lo, hi, de, view, cx, cy, r=SMALL, unit="", intd=False, ms20=True):
    return dict(key=key, name=name, kind="knob", min=lo, max=hi, default=de, view=view, cx=cx, cy=cy, r=r,
                unit=unit, int=intd, ms20=ms20)


def T(key, name, de, view, cx, cy, options=OFF_ON, ms20=True):
    return dict(key=key, name=name, kind="toggle", options=options, default=de, view=view, cx=cx, cy=cy, ms20=ms20)


def E(key, name, options, de, view, cx, cy, widget="enum_h", sw=150, sh=56, rows=1, w=240, h=56, ms20=True):
    return dict(key=key, name=name, kind="enum", options=options, default=de, view=view, cx=cx, cy=cy,
                widget=widget, sw=sw, sh=sh, rows=rows, w=w, h=h, ms20=ms20)


def B(key, name, view, cx, cy, ms20=True):
    return dict(key=key, name=name, kind="button", view=view, cx=cx, cy=cy, ms20=ms20)


R1, R2 = 215, 455   # the two rows of knobs on a zoomed page (below the 70 px header)

# the sequencer page: a left strip of its settings, then 12 columns of step knobs A, B, C and two rows of buttons
SEQ_X0, SEQ_DX = 520, 64   # 520: the A/B/C and PORTA/TRIG names (at SEQ_X0 - 52) clear the frame and the first knob
SEQ_ROWS = {"a": 184, "b": 280, "c": 376}
SEQ_PORTA_Y, SEQ_TRIG_Y = 459, 552
SEQ_LEFT = [85, 220, 355]

CONTROLS = [
    # parameter 0 first: MPC's host toggles parameter 0 on insert and on every STOP, and the wrapper holds its writes
    # (mpc-vst-plugins NOTES 2026-10-10), so it is the plain VOLUME knob, as on the MS-20's own panel
    K("volume", "Volume", 0, 10, 7, "patch", 1150, 178, r=BIG),
    # ---- VOLTAGE CONTROLLED OSCILLATOR 1
    E("vco1_wave", "VCO 1 Wave Form", ["Triangle", "Sawtooth", "Pulse", "White Noise"], 1, "vco", 160, R1 - 10,
      sw=112, sh=58, rows=2),
    K("vco1_pw", "VCO 1 PW", 0, 10, 0, "vco", 375, R1),
    E("vco1_scale", "VCO 1 Scale", ["32'", "16'", "8'", "4'"], 2, "vco", 160, R2, sw=66, sh=58),
    # ---- VOLTAGE CONTROLLED OSCILLATOR 2
    E("vco2_wave", "VCO 2 Wave Form", ["Sawtooth", "Square", "Pulse", "Ring Mod"], 0, "vco", 610, R1 - 10,
      sw=112, sh=58, rows=2),
    K("vco2_pitch", "VCO 2 Pitch", -5, 5, 0, "vco", 820, R1),
    E("vco2_scale", "VCO 2 Scale", ["16'", "8'", "4'", "2'"], 1, "vco", 600, R2, sw=66, sh=58),
    # ---- VCO MIXER, portamento, master tune
    K("vco1_level", "VCO 1 Level", 0, 10, 10, "vco", 1000, R1, r=BIG),
    K("vco2_level", "VCO 2 Level", 0, 10, 0, "vco", 1180, R1, r=BIG),
    K("porta", "Portamento Time", 0, 10, 0, "vco", 385, R2),
    K("master_tune", "Master Tune", -100, 100, 0, "vco", 830, R2, unit="ct"),
    E("unison", "Unison", ["Off", "2 Voices", "4 Voices"], 0, "vco", 1085, R2 - 60, sw=95, sh=52, ms20=False),
    K("unison_detune", "Unison Detune", 0, 10, 2, "vco", 1085, R2 + 72, r=36, ms20=False),
    # ---- VOLTAGE CONTROLLED HIGHPASS FILTER
    K("hpf_cutoff", "HPF Cutoff Frequency", 0, 10, 0, "vcf", 200, R1, r=BIG),
    K("hpf_peak", "HPF Peak", 0, 10, 0, "vcf", 420, R1, r=BIG),
    K("hpf_mg", "HPF MG/T.EXT", 0, 10, 0, "vcf", 200, R2),
    K("hpf_eg2", "HPF EG2/EXT", 0, 10, 0, "vcf", 420, R2),
    # ---- VOLTAGE CONTROLLED LOWPASS FILTER
    K("lpf_cutoff", "LPF Cutoff Frequency", 0, 10, 8, "vcf", 760, R1, r=BIG),
    K("lpf_peak", "LPF Peak", 0, 10, 0, "vcf", 980, R1, r=BIG),
    K("lpf_mg", "LPF MG/T.EXT", 0, 10, 0, "vcf", 760, R2),
    K("lpf_eg2", "LPF EG2/EXT", 0, 10, 4, "vcf", 980, R2),
    E("filter_mk", "Filter", ["MK1", "MK2"], 1, "vcf", 1170, R1, sw=90, sh=58, ms20=False),
    K("filter_drive", "Filter Drive", 0, 10, 3, "vcf", 1170, R2, r=36, ms20=False),
    # ---- FREQUENCY MODULATION, MODULATION GENERATOR, PW and VCA modulation
    K("fm_mg", "Freq Mod MG/T.EXT", 0, 10, 0, "mod", 150, R1),
    K("fm_eg1", "Freq Mod EG1/EXT", 0, 10, 0, "mod", 330, R1),
    K("mg_wave", "MG Wave Form", 0, 10, 5, "mod", 580, R1, r=BIG),
    K("mg_freq", "MG Frequency", 0, 10, 4, "mod", 800, R1, r=BIG),
    E("mg_mode", "MG", ["Free", "Reset"], 0, "mod", 1020, R1, sw=100, sh=58, ms20=False),
    E("mg_sync", "MG Sync", SYNC, 0, "mod", 1020, R1 + 90, widget="popup", w=220, h=52, ms20=False),
    K("pwm_mg", "PW Mod MG/EXT", 0, 10, 0, "mod", 150, R2, ms20=False),
    E("pwm_vco", "PW Mod To", ["VCO 1", "VCO 2"], 0, "mod", 330, R2, sw=100, sh=58, ms20=False),
    K("vca_mg", "VCA Mod MG/EXT", 0, 10, 0, "mod", 580, R2, ms20=False),
    K("vca_vel", "VCA Velocity", 0, 10, 0, "mod", 800, R2, ms20=False),
    K("vcf_vel", "LPF Velocity", 0, 10, 0, "mod", 1020, R2, ms20=False),
    # ---- ENVELOPE GENERATOR 1
    K("eg1_delay", "EG1 Delay Time", 0, 10, 0, "env", 160, R1),
    K("eg1_attack", "EG1 Attack Time", 0, 10, 3, "env", 330, R1),
    K("eg1_release", "EG1 Release Time", 0, 10, 3, "env", 500, R1),
    E("eg1_mode", "EG1 Mode", ["Normal", "Trigger", "Loop"], 0, "env", 330, R2, sw=110, sh=58, ms20=False),
    # ---- ENVELOPE GENERATOR 2
    K("eg2_hold", "EG2 Hold Time", 0, 10, 0, "env", 720, R1),
    K("eg2_attack", "EG2 Attack Time", 0, 10, 0, "env", 890, R1),
    K("eg2_decay", "EG2 Decay Time", 0, 10, 4, "env", 1060, R1),
    K("eg2_sustain", "EG2 Sustain Level", 0, 10, 7, "env", 890, R2, r=BIG),
    K("eg2_release", "EG2 Release Time", 0, 10, 3, "env", 1060, R2),
    E("eg_trig", "Key Trigger", ["Single", "Multi"], 0, "env", 720, R2, sw=100, sh=58, ms20=False),
    # ---- EXTERNAL SIGNAL PROCESSOR
    K("esp_level", "Signal Level", 0, 10, 5, "esp", 180, 300, r=BIG),
    K("esp_low", "Low Cut Freq", 0, 10, 2, "esp", 410, 300, r=BIG),
    K("esp_high", "High Cut Freq", 0, 10, 8, "esp", 640, 300, r=BIG),
    K("esp_cv", "CV Adjust", 0, 10, 5, "esp", 870, 300, r=BIG),
    K("esp_thresh", "Threshold Level", 0, 10, 5, "esp", 1100, 300, r=BIG),
    # ---- SEQUENCER (SQ-10-style, XXL)
    K("seq_speed", "Clock Speed", 0, 10, 4, "seq", SEQ_LEFT[0], 168, r=40, ms20=False),
    K("seq_swing", "Swing", 50, 75, 50, "seq", SEQ_LEFT[1], 168, r=40, unit="%", intd=True, ms20=False),
    K("seq_gate", "Gate", 0, 10, 5, "seq", SEQ_LEFT[2], 168, r=40, ms20=False),
    K("seq_length", "Sequence Length", 1, 12, 12, "seq", SEQ_LEFT[0], 316, r=36, intd=True, ms20=False),
    K("seq_porta_ab", "Portamento A/B", 0, 10, 0, "seq", SEQ_LEFT[1], 316, r=36, ms20=False),
    K("seq_porta_c", "Portamento C", 0, 10, 0, "seq", SEQ_LEFT[2], 316, r=36, ms20=False),
    E("seq_sync", "Clock Sync", SYNC, 0, "seq", 120, 452, widget="popup", w=190, h=44, ms20=False),
    E("seq_mode", "Sequence Mode", ["12 Loop", "12 Once", "24 Loop", "24 Once"], 0, "seq", 325, 445, sw=100, sh=32,   # rows=2: cy is the first row
      rows=2, ms20=False),
    E("seq_range_a", "Channel A", ["+/-1 V", "+/-5 V"], 0, "seq", SEQ_LEFT[0], 548, sw=62, sh=40, ms20=False),
    E("seq_range_b", "Channel B", ["+/-1 V", "+/-5 V"], 0, "seq", SEQ_LEFT[1] + 5, 548, sw=62, sh=40, ms20=False),
    E("seq_range_c", "Channel C", ["0..+5 V", "+/-12 st"], 0, "seq", SEQ_LEFT[2] + 10, 548, sw=62, sh=40, ms20=False),
    T("seq_run", "Run", 0, "seq", 62, 598, ms20=False),
    T("seq_transport", "With Transport", 0, "seq", 235, 598, ms20=False),
    B("seq_step_btn", "Step", "seq", 570, 598, ms20=False),
    *[K("seq_a%d" % (i + 1), "A %d" % (i + 1), -5, 5, 0, "seq", SEQ_X0 + i * SEQ_DX, SEQ_ROWS["a"], r=STEP, ms20=False)
      for i in range(12)],
    *[K("seq_b%d" % (i + 1), "B %d" % (i + 1), -5, 5, 0, "seq", SEQ_X0 + i * SEQ_DX, SEQ_ROWS["b"], r=STEP, ms20=False)
      for i in range(12)],
    *[K("seq_c%d" % (i + 1), "C %d" % (i + 1), -5, 5, 0, "seq", SEQ_X0 + i * SEQ_DX, SEQ_ROWS["c"], r=STEP, ms20=False)
      for i in range(12)],
    *[T("seq_pc%d" % (i + 1), "Porta C %d" % (i + 1), 0, "seq", SEQ_X0 + i * SEQ_DX, SEQ_PORTA_Y, ms20=False)
      for i in range(12)],
    *[T("seq_t%d" % (i + 1), "Trigger %d" % (i + 1), 1, "seq", SEQ_X0 + i * SEQ_DX, SEQ_TRIG_Y, ms20=False)
      for i in range(12)],
    # ---- SETUP / MIDI (XXL)
    E("key_prio", "Key Priority", ["Low Note", "High Note", "Last Note"], 0, "setup", 230, R1, sw=120, sh=58, ms20=False),
    K("pb_range", "Pitch Bend Range", 0, 12, 2, "setup", 520, R1, unit="st", intd=True, ms20=False),
    E("wheel_to", "Mod Wheel", ["Wheel Jack", "MG Pitch", "LPF Cutoff"], 0, "setup", 800, R1, sw=120, sh=58, ms20=False),
    K("noise_floor", "Analog Noise", 0, 10, 2, "setup", 1080, R1, r=36, ms20=False),
    K("drift", "VCO Drift", 0, 10, 3, "setup", 230, R2, r=36, ms20=False),
    E("sh_clock_def", "S&H Clock (unpatched)", ["MG Rect", "KBD Trig", "Seq Trig"], 0, "setup", 470, R2, sw=100, sh=58,
      ms20=False),
    E("sh_in_def", "S&H Input (unpatched)", ["White Noise", "Pink Noise", "MG Tri"], 0, "setup", 820, R2, sw=100, sh=58,
      ms20=False),
    T("mom_switch", "Manual Control Switch", 0, "patch", 1096, 396, ms20=True),
]
CTRL = {c["key"]: c for c in CONTROLS}

# ------------------------------------------------------------------------------------------------------ the jacks
# Every jack carries a voltage, as on the MS-20: any output can go into any input (a gate is 0 / +5 V, so a trigger
# input fires on anything that rises past +2.5 V, and an envelope or gate makes a fine CV). One cable per output and
# per input, like a physical mono patch cord. An input left unpatched uses its normalled source, as on the panel.
# (key, label, info)
OUTS = [
    ("mg_tri", "MG TRI", "Modulation generator triangle, -2.5..+2.5 V"),
    ("mg_rect", "MG RECT", "Modulation generator rectangle, 0 / +5 V"),
    ("eg1_out", "EG1 OUT", "Envelope generator 1, 0..+5 V"),
    ("eg1_rev", "EG1 REV", "Envelope generator 1 reversed, +5 V down to 0"),
    ("eg2_rev", "EG2 REV", "Envelope generator 2 reversed, +5 V down to 0"),
    ("eg2_out", "EG2 OUT", "Envelope generator 2, 0..+5 V (XXL: the MS-20 has only REV OUT)"),
    ("kbd_cv", "KBD CV", "Keyboard CV, Hz/V: 1 V = the low C, 8 V = the high C"),
    ("kbd_trig", "TRIG OUT", "Keyboard gate, +5 V while a key is down"),
    ("sh_out", "S&H OUT", "Sample & hold output"),
    ("vca_out", "VCA OUT", "Modulation VCA output"),
    ("pink", "PINK", "Pink noise, -5..+5 V"),
    ("white", "WHITE", "White noise, -5..+5 V"),
    ("wheel", "WHEEL", "Mod wheel, 0..+5 V"),
    ("mom", "SWITCH", "Manual control switch, +5 V while on"),
    ("sig_out", "SIGNAL OUT", "The synth's output, before VOLUME (patch it into the ESP)"),
    ("esp_amp", "AMP OUT", "ESP amplifier output"),
    ("esp_bpf", "BPF OUT", "ESP band pass filter output"),
    ("esp_cv", "F-V CV OUT", "ESP frequency-to-voltage CV, Hz/V"),
    ("esp_env", "ENV OUT", "ESP envelope follower, 0..+5 V"),
    ("esp_trig", "ESP TRIG", "ESP trigger, +5 V above the threshold"),
    ("seq_a", "SEQ A", "Sequencer channel A"),
    ("seq_b", "SEQ B", "Sequencer channel B"),
    ("seq_c", "SEQ C", "Sequencer channel C"),
    ("seq_trig", "SEQ TRIG", "Sequencer trigger, +5 V for the gate time"),
    ("vco1_out", "VCO 1 OUT", "VCO 1, 5 Vpp (XXL)"),
    ("vco2_out", "VCO 2 OUT", "VCO 2, 5 Vpp (XXL)"),
    ("vel", "VEL CV", "Velocity of the last key, 0..+5 V (XXL)"),
    ("after", "AFTER CV", "Aftertouch, 0..+5 V (XXL)"),
]
# (key, label, default source, info)   default: an output key, "kbd" (the keyboard), "mg_rect" ... or None
INS = [
    ("total", "TOTAL", None, "Replaces MG TRI at the three MG/T.EXT knobs: pitch (1 oct/V at 10), HPF and LPF (2 oct/V at 10)"),
    ("freq", "FREQ", None, "Replaces EG1 at the EG1/EXT frequency modulation knob, 1 oct/V at 10"),
    ("ext_in", "EXT SIGNAL IN", None, "Audio into the VCO mixer, 3 Vpp max"),
    ("hpf_cv", "HPF CUTOFF", None, "Replaces EG2 at the HPF EG2/EXT knob, 2 oct/V at 10"),
    ("lpf_cv", "LPF CUTOFF", None, "Replaces EG2 at the LPF EG2/EXT knob, 2 oct/V at 10"),
    ("init_gain", "INITIAL GAIN", None, "Opens the VCA, 0..+5 V, added to EG2"),
    ("vco12_cv", "VCO 1+2 CV IN", "kbd", "Hz/V pitch of both VCOs; the keyboard until patched"),
    ("vco2_cv", "VCO 2 CV IN", None, "Hz/V, added to VCO 2"),
    ("sh_clock", "S&H CLOCK", "mg_rect", "Sample & hold clock (rising edge); MG RECT until patched"),
    ("sh_in", "S&H IN", "white", "Sample & hold input; white noise until patched (Setup)"),
    ("vca_ctl", "CONTROL IN", None, "Modulation VCA gain, 0..+5 V; open until patched"),
    ("vca_in", "VCA IN", None, "Modulation VCA input"),
    ("eg1_trig", "EG1 TRIG IN", "kbd", "Triggers EG1 alone; the keyboard until patched"),
    ("trig_in", "TRIG IN", "kbd", "Triggers EG1 and EG2; the keyboard until patched"),
    ("esp_in", "SIGNAL IN", None, "ESP input (patch SIGNAL OUT, a VCO or noise)"),
    ("seq_clock", "SEQ CLOCK IN", None, "External sequencer clock (rising edge) replaces the internal one"),
    ("seq_reset", "SEQ RESET", None, "A rising edge restarts the sequence at step 1"),
    ("seq_mod", "SPEED x2/V", None, "Clock speed modulation: each +1 V doubles it, -1 V halves it (SQ-10 x2 / /2 inputs)"),
    ("seq_ss", "SEQ START/STOP", None, "A rising edge starts or stops the sequencer (SQ-10 EXT START/STOP)"),
    ("pwm_in", "PWM IN", None, "Replaces MG TRI at the PW MOD MG/EXT knob (XXL)"),
]
OUT_KEYS = [o[0] for o in OUTS]
IN_KEYS = [i[0] for i in INS]

# Patch panel: where each jack sits, in the positions of the MS-20's patch sheet (12 columns, rows of the signal
# path, modulation, keyboard, the S&H / VCA / noise row, the ESP row, then the XXL row of the sequencer and extras).
COLS = [60 + i * 108 for i in range(11)]
ROWS = [150, 232, 314, 396, 492, 586]
JACKS = {
    "total": (COLS[0], ROWS[0]), "freq": (COLS[1], ROWS[0]), "ext_in": (COLS[2], ROWS[0]),
    "hpf_cv": (COLS[3], ROWS[0]), "lpf_cv": (COLS[4], ROWS[0]), "init_gain": (COLS[5], ROWS[0]),
    "sig_out": (COLS[8], ROWS[0]),
    "mg_tri": (COLS[0], ROWS[1]), "mg_rect": (COLS[1], ROWS[1]), "eg1_out": (COLS[2], ROWS[1]),
    "eg2_rev": (COLS[5], ROWS[1]), "vco12_cv": (COLS[7], ROWS[1]), "kbd_cv": (COLS[8], ROWS[1]),
    "sh_clock": (COLS[0], ROWS[2]), "eg1_rev": (COLS[2], ROWS[2]), "vca_ctl": (COLS[3], ROWS[2]),
    "eg1_trig": (COLS[4], ROWS[2]), "eg2_out": (COLS[5], ROWS[2]), "vco2_cv": (COLS[6], ROWS[2]),
    "trig_in": (COLS[7], ROWS[2]), "kbd_trig": (COLS[8], ROWS[2]),
    "sh_in": (COLS[0], ROWS[3]), "sh_out": (COLS[1], ROWS[3]), "vca_in": (COLS[2], ROWS[3]),
    "vca_out": (COLS[3], ROWS[3]), "pink": (COLS[4], ROWS[3]), "white": (COLS[5], ROWS[3]),
    "wheel": (COLS[6], ROWS[3]), "mom": (COLS[8], ROWS[3]),
    "esp_in": (COLS[0], ROWS[4]), "esp_amp": (COLS[1], ROWS[4]), "esp_bpf": (COLS[2], ROWS[4]),
    "esp_cv": (COLS[3], ROWS[4]), "esp_env": (COLS[4], ROWS[4]), "esp_trig": (COLS[5], ROWS[4]),
    "vco1_out": (COLS[7], ROWS[4]), "vco2_out": (COLS[8], ROWS[4]), "vel": (COLS[9], ROWS[4]),
    "after": (COLS[10], ROWS[4]),
    "seq_a": (COLS[0], ROWS[5]), "seq_b": (COLS[1], ROWS[5]), "seq_c": (COLS[2], ROWS[5]),
    "seq_trig": (COLS[3], ROWS[5]), "seq_clock": (COLS[4], ROWS[5]), "seq_reset": (COLS[5], ROWS[5]),
    "seq_mod": (COLS[6], ROWS[5]), "seq_ss": (COLS[7], ROWS[5]), "pwm_in": (COLS[9], ROWS[5]),
}
assert set(JACKS) == set(OUT_KEYS) | set(IN_KEYS), "every jack placed once"
assert len(set(JACKS.values())) == len(JACKS), "no two jacks on one spot"
JACK_R = 21                  # socket radius on the patch panel
CABLE_TILE = 128             # cable pictures are cut on this grid (post_skin.tile_pieces): memory vs component count
CABLE_COLOURS = [(236, 214, 38), (226, 186, 32), (241, 226, 70), (209, 170, 30), (248, 235, 110), (219, 196, 40),
                 (233, 205, 50), (203, 178, 44)]   # the MS-20's yellow patch cords, a few shades so they tell apart

# Header on every zoomed page: back to the overview, previous / next section.
NAV = [("nav_zoom", "OVERVIEW", 90, 38), ("nav_prev", "<", 240, 38), ("nav_next", ">", 350, 38)]

# Cable and ring pictures are switched by parameters of at most JACK_GROUP + 1 positions (PS3100XXL 0.1.4: on the
# Force nothing above 11 positions has been seen working on an IndexedEnabling picture). Each output's cable is split
# over small parameters: the inputs in groups of JACK_GROUP, one parameter per group ("-" or which input of the group).
JACK_GROUP = 9


def groups(items):
    return [items[i:i + JACK_GROUP] for i in range(0, len(items), JACK_GROUP)]


def cable_groups():
    return list(enumerate(groups(INS)))


def cable_param(out, j):
    """(param key, option index, option count) showing out's cable to input j on the patch panel."""
    t = INS.index(j)
    g = t // JACK_GROUP
    n = len(groups(INS)[g])
    return "cp_%s_%d" % (out[0], g), 1 + t % JACK_GROUP, n + 1


def held_in_param(j):
    ii = INS.index(j)
    g = ii // JACK_GROUP
    return "hi_%d" % g, 1 + ii % JACK_GROUP, len(groups(INS)[g]) + 1


def held_param(out):
    oi = OUTS.index(out)
    g = oi // JACK_GROUP
    return "hd_%d" % g, 1 + oi % JACK_GROUP, len(groups(OUTS)[g]) + 1


# Patching by steps (PS3100XXL 0.1.5, the method that works on the Force): the sockets on the patch panel are the touch
# zones; tapping one opens the step that asks for the other end (the sockets that cannot take it dimmed and ignored);
# the cable is shown on its own page with DONE / UNPLUG / CANCEL.
PICK_W, PICK_H = 100, 78     # a jack's touch zone: the sockets are 108 apart across and 82 down


def pick_box(key):
    x, y = JACKS[key]
    return (x - PICK_W // 2, y - PICK_H // 2 + 2, PICK_W, PICK_H)


PICK_ORDER = OUT_KEYS + IN_KEYS

# the steps (the 'pk' parameter): 0 off the patch page, 1 choose any jack, 2 an output waits for an input,
# 3 an input waits for an output, 4 connected (the cable page)
PK_STEPS = ["Off", "Choose", "Pick input", "Pick output", "Connected"]
PK_CANCEL = (1190, 38)
PK_DONE = (420, 548, 260, 70)
PK_UNPLUG = (860, 548, 260, 70)

# the overview's Q-Links: the main sound controls
OVERVIEW_QLINKS = ["lpf_cutoff", "lpf_peak", "hpf_cutoff", "hpf_peak", "vco1_level", "vco2_level", "vco2_pitch", "volume",
                   "lpf_eg2", "fm_mg", "mg_freq", "mg_wave", "eg2_attack", "eg2_decay", "eg2_sustain", "eg2_release"]
SEQ_QLINKS = ["seq_speed", "seq_swing", "seq_gate", "seq_length"] + ["seq_a%d" % (i + 1) for i in range(12)]
assert all(k in [c["key"] for c in CONTROLS] for k in SEQ_QLINKS + OVERVIEW_QLINKS)
