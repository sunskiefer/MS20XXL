// SPDX-License-Identifier: GPL-3.0-or-later
// MS20XXL -- a Korg MS-20-style semi-modular monophonic synthesizer for MPC OS (mpc-vst-plugins engine), with an
// SQ-10-style step sequencer. Own DSP (src/ms20_dsp.h), written from the MS-20's circuit and panel; no Korg code.
//
//   VCO 1 + VCO 2 (+ EXT SIGNAL IN) -> VCO MIXER -> HPF -> LPF -> VCA -> VOLUME -> out
//
// Modulation runs as the MS-20's patch panel: every output (MG, EG1, EG2, keyboard, S&H, noise, ESP, sequencer ...)
// is computed each sample into out_v[]; an input reads the output a cable brings to it, or its normalled source when
// unpatched, exactly as the panel's hidden wiring does. One cable per output and per input.
//
// The UI side lives here too: the zoom 'view', the jack taps, which cable picture each output shows, and 16 Q-Link
// knobs that follow the section on screen (see get/set of "ql<n>").
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <new>

extern "C" {
#include "engine.h"
}
#include "param_ids.h"
#include "denormals.h"
#include "limiter.h"
#include "ms20_dsp.h"

namespace {

using namespace ms20;

const int MAX_VOICES = 4;        // unison stack; the MS-20 is one voice
const int CTRL_EVERY = 8;        // pitch and filter coefficients are recomputed every 8 samples
const float HZ_PER_VOLT = 65.406f;  // the panel's Hz/V sockets: 1 V = the keyboard's low C (C2), 8 V = its high C

struct Voice {
  Vco v1, v2;
  Ms20Hpf hpf;
  Ms20Lpf lpf;
  float detune = 0;   // cents, unison spread
  float pan = 0.5f;
  void reset(Rng *r) { v1.rng = v2.rng = r; v1.reset((r->white() + 1.0f) * 0.5f); v2.reset((r->white() + 1.0f) * 0.5f);
                       hpf.reset(); lpf.reset(); }
};

struct Synth {
  float pv[P_COUNT];                // parameter values (native units; options = index)
  int view = 0, held = -1, held_in = -1;
  int pk = 0;                       // the patch step: 0 off the page, 1 choose, 2 output waits, 3 input waits, 4 connected
  int pair_o = -1, pair_j = -1;     // the cable the connected page shows
  int dest[N_OUTS];                 // output -> input it is patched to, -1 = none
  int src[N_INS];                   // input -> output feeding it, -1 = none (derived from dest)
  unsigned rev = 1;                 // display_rev
  char info[128];
  char touch[96];                   // the header's top-right readout: the control just moved and its value
  bool pop_open[N_POPS] = {};

  // patch panel values, this sample
  float out_v[N_OUTS];

  // MIDI / keyboard
  bool key_held[128];
  int keys_down = 0;
  int key_order[128];               // the keys down, in the order pressed (for last-note priority)
  int cur_note = -1;                // the key the VCOs follow
  float vel = 0.8f, after = 0, pb = 0, mw = 0;
  bool kbd_gate = false, kbd_trig_edge = false;
  float kbd_semi = 69.0f, kbd_target = 69.0f;   // keyboard pitch, slewed by PORTAMENTO (in semitones)
  float bpm = 120.0f;
  bool transport = false;

  // modules
  Rng rng;
  Pink pink;
  Mg mg;
  Eg1 eg1;
  Eg2 eg2;
  SampleHold sh;
  Esp esp;
  Sequencer seq;
  Voice voices[MAX_VOICES];
  int nvoices = 1;
  bool gate_in_last = false, eg1_in_last = false, seq_reset_last = false, seq_ss_last = false;
  int ctrl_count = 0;
  float white = 0, pinkv = 0;

  // output
  plateau::Limiter lim;
  float dc_l = 0, dc_r = 0, dcx_l = 0, dcx_r = 0;
  float s_vol = 0;
  float sig_out = 0;                // last sample's output in volts (SIGNAL OUT jack, one sample late)
  bool esp_peak_lamp = false;
  int seq_lamp = 0;

  void init() {
    for (int i = 0; i < P_COUNT; i++) pv[i] = P_DEF[i];
    for (int i = 0; i < N_OUTS; i++) { dest[i] = -1; out_v[i] = 0; }
    for (int i = 0; i < N_INS; i++) src[i] = -1;
    memset(key_held, 0, sizeof key_held);
    for (int i = 0; i < MAX_VOICES; i++) voices[i].reset(&rng);
    seq.init();
    lim.Init();
    snprintf(info, sizeof info, "Tap a jack. Then tap the other end of the cable.");
    apply_all();
  }

  // ---- parameters ------------------------------------------------------------------------------------------------
  inline float P(int i) const { return pv[i]; }
  inline int Pi(int i) const { return (int)lroundf(pv[i]); }
  bool on(int i) const { return Pi(i) != 0; }

  void apply_all() {
    for (int s = 0; s < 12; s++) {
      seq.val[0][s] = pv[P_SEQ_A1 + s];
      seq.val[1][s] = pv[P_SEQ_B1 + s];
      seq.val[2][s] = pv[P_SEQ_C1 + s];
      seq.porta_c[s] = on(P_SEQ_PC1 + s);
      seq.trig_on[s] = on(P_SEQ_T1 + s);
    }
    seq.length = (int)clampf(pv[P_SEQ_LENGTH], 1, 12);
    seq.mode = Pi(P_SEQ_MODE);
    seq.swing = pv[P_SEQ_SWING] * 0.01f;
    seq.gate_len = pv[P_SEQ_GATE] * 0.1f;
    seq.porta_ab = pv[P_SEQ_PORTA_AB];
    seq.porta_c_time = pv[P_SEQ_PORTA_C];
    int nv = Pi(P_UNISON) == 0 ? 1 : Pi(P_UNISON) == 1 ? 2 : 4;
    if (nv != nvoices) { nvoices = nv; for (int i = 0; i < MAX_VOICES; i++) voices[i].reset(&rng); }
    static const float SPREAD2[2] = {-1, 1}, SPREAD4[4] = {-1, -0.33f, 0.33f, 1};
    for (int i = 0; i < nvoices; i++) {
      float sp = nvoices == 1 ? 0 : nvoices == 2 ? SPREAD2[i] : SPREAD4[i];
      voices[i].detune = sp * pv[P_UNISON_DETUNE] * 3.0f;        // up to +-30 cents
      voices[i].pan = 0.5f + sp * 0.35f;
    }
  }

  void recompute_src() {
    for (int i = 0; i < N_INS; i++) src[i] = -1;
    for (int o = 0; o < N_OUTS; o++)
      if (dest[o] >= 0) src[dest[o]] = o;
  }

  void bump() { rev++; }

  // ---- keyboard ---------------------------------------------------------------------------------------------------
  int priority_note() const {
    if (keys_down == 0) return -1;
    int prio = Pi(P_KEY_PRIO);
    if (prio == 2) return key_order[keys_down - 1];
    int best = -1;
    for (int n = 0; n < 128; n++)
      if (key_held[n]) { if (best < 0 || (prio == 0 ? n < best : n > best)) best = n; }
    return best;
  }

  void follow_keys(bool new_press) {
    int n = priority_note();
    bool multi = Pi(P_EG_TRIG) == 1;
    if (n >= 0) {
      bool changed = n != cur_note;
      cur_note = n;
      kbd_target = (float)n;
      if (!kbd_gate) { kbd_gate = true; kbd_trig_edge = true; }
      else if (multi && new_press && changed) kbd_trig_edge = true;   // multi trigger: every new key retriggers
    } else {
      kbd_gate = false;
    }
  }

  void note_on(int note, int velocity) {
    if (!key_held[note]) {
      key_held[note] = true;
      key_order[keys_down++] = note;
    }
    vel = velocity / 127.0f;
    follow_keys(true);
    if (keys_down == 1 && pv[P_PORTA] < 0.05f) kbd_semi = kbd_target;   // no slew at all with the pot at 0
  }

  void note_off(int note) {
    if (!key_held[note]) return;
    key_held[note] = false;
    int k = 0;
    for (int i = 0; i < keys_down; i++) if (key_order[i] != note) key_order[k++] = key_order[i];
    keys_down = k;
    follow_keys(false);
  }

  void all_off() {
    memset(key_held, 0, sizeof key_held);
    keys_down = 0;
    kbd_gate = false;
  }

  void midi(const uint8_t *m, int len) {
    if (len < 1) return;
    int st = m[0] & 0xF0;
    int d1 = len > 1 ? m[1] & 127 : 0, d2 = len > 2 ? m[2] & 127 : 0;
    if (st == 0x90 && d2 > 0) note_on(d1, d2);
    else if (st == 0x80 || (st == 0x90 && d2 == 0)) note_off(d1);
    else if (st == 0xE0) pb = clampf(((d2 << 7 | d1) - 8192) / 8192.0f, -1, 1);
    else if (st == 0xD0) after = d1 / 127.0f;
    else if (st == 0xA0) after = d2 / 127.0f;
    else if (st == 0xB0) {
      if (d1 == 1) mw = d2 / 127.0f;
      if (d1 == 120 || d1 == 123) all_off();
    }
  }

  // ---- the patch panel -------------------------------------------------------------------------------------------
  inline bool patched(int j) const { return src[j] >= 0; }
  inline float in(int j, float dflt) const { return src[j] >= 0 ? out_v[src[j]] : dflt; }
  inline bool gate_at(int j, bool dflt) const { return src[j] >= 0 ? out_v[src[j]] > 2.5f : dflt; }

  float sync_hz(int sync_param, float free_hz) const {
    int s = Pi(sync_param);
    if (s <= 0) return free_hz;
    return bpm / 60.0f / DIV_BEATS[s - 1];
  }

  // control-rate values (every block)
  float mg_hz = 1, step_seconds = 0.25f, kbd_slew = 1.0f;
  float hpf_base = 0, lpf_base = 8, vca_mod_depth = 0;
  int mk = 1, w1 = 1, w2 = 0;

  void begin_block() {
    mg_hz = sync_hz(P_MG_SYNC, 0.1f * exp2f(pv[P_MG_FREQ] * 0.7644f));   // 0.1 .. 20 Hz
    eg1.set(pot_time(pv[P_EG1_DELAY]) * (pv[P_EG1_DELAY] < 0.05f ? 0.0f : 1.0f), pot_time(pv[P_EG1_ATTACK]),
            pot_time(pv[P_EG1_RELEASE]));
    eg1.loop = Pi(P_EG1_MODE) == 2;
    eg1.trig_only = Pi(P_EG1_MODE) == 1;
    eg2.set(pv[P_EG2_HOLD] < 0.05f ? 0.0f : pot_time(pv[P_EG2_HOLD]) * 2.0f, pot_time(pv[P_EG2_ATTACK]),   // HOLD 0 .. 20 s
            pot_time(pv[P_EG2_DECAY]), pv[P_EG2_SUSTAIN] * 0.1f, pot_time(pv[P_EG2_RELEASE]));
    esp.set(50.0f * exp2f(pv[P_ESP_LOW] * 0.5644f), 100.0f * exp2f(pv[P_ESP_HIGH] * 0.5644f));   // 50 Hz-2.5 kHz, 100 Hz-5 kHz
    kbd_slew = pv[P_PORTA] < 0.05f ? 1.0f : rate_for(pot_time(pv[P_PORTA]) * 0.5f);
    int s = Pi(P_SEQ_SYNC);
    step_seconds = s <= 0 ? 1.0f / (0.1f * exp2f(pv[P_SEQ_SPEED] * 0.92f)) : DIV_BEATS[s - 1] * 60.0f / bpm;
    seq.ext_clock = patched(I_SEQ_CLOCK);
    mk = Pi(P_FILTER_MK);
    w1 = Pi(P_VCO1_WAVE);
    w2 = Pi(P_VCO2_WAVE);
    vca_mod_depth = pv[P_VCA_MG] * 0.1f;
  }

  // all modulation for one sample
  void modulation() {
    float *o = out_v;
    // noise, performance
    white = rng.white();
    pinkv = clampf(pink.next(white) * 3.0f, -1, 1);
    o[O_WHITE] = white * 5.0f;
    o[O_PINK] = pinkv * 5.0f;
    int wt = Pi(P_WHEEL_TO);
    o[O_WHEEL] = wt == 0 ? mw * 5.0f : 0.0f;
    o[O_MOM] = on(P_MOM_SWITCH) ? 5.0f : 0.0f;
    o[O_VEL] = vel * 5.0f;
    o[O_AFTER] = after * 5.0f;
    // keyboard: pitch with portamento, gate
    kbd_semi += (kbd_target - kbd_semi) * kbd_slew;
    float kbd_hz = midi_hz(kbd_semi + pb * pv[P_PB_RANGE]);
    o[O_KBD_CV] = kbd_hz / HZ_PER_VOLT;
    o[O_KBD_TRIG] = kbd_gate ? 5.0f : 0.0f;
    // modulation generator
    mg.tick(mg_hz, pv[P_MG_WAVE] * 0.1f);
    o[O_MG_TRI] = mg.tri;
    o[O_MG_RECT] = mg.rect;
    // sequencer (its trigger can feed TRIG IN, its channels TOTAL / VCO CV)
    bool sreset = gate_at(I_SEQ_RESET, false);
    if (sreset && !seq_reset_last) seq.reset();
    seq_reset_last = sreset;
    bool ss = gate_at(I_SEQ_SS, false);
    if (ss && !seq_ss_last) { pv[P_SEQ_RUN] = on(P_SEQ_RUN) ? 0.0f : 1.0f; bump(); }   // START/STOP jack toggles RUN
    seq_ss_last = ss;
    bool want_run = on(P_SEQ_RUN) || (on(P_SEQ_TRANSPORT) && transport);
    if (want_run && !seq.running && !seq.finished) seq.start();
    if (want_run && seq.finished && !seq.running && on(P_SEQ_RUN) == false) {}   // one-shot done: waits for a new start
    if (!want_run && seq.running) seq.stop();
    if (!want_run) seq.finished = false;
    float smod = patched(I_SEQ_MOD) ? exp2f(clampf(in(I_SEQ_MOD, 0), -5, 5)) : 1.0f;
    seq.tick(step_seconds / smod, gate_at(I_SEQ_CLOCK, false));
    o[O_SEQ_A] = Pi(P_SEQ_RANGE_A) == 0 ? seq.out_a * 0.2f : seq.out_a;
    o[O_SEQ_B] = Pi(P_SEQ_RANGE_B) == 0 ? seq.out_b * 0.2f : seq.out_b;
    o[O_SEQ_C] = Pi(P_SEQ_RANGE_C) == 0 ? (seq.out_c + 5.0f) * 0.5f : seq.out_c * 0.2f;   // 0..+5 V, or +-1 V (12 st)
    o[O_SEQ_TRIG] = seq.trig ? 5.0f : 0.0f;
    // triggers: TRIG IN drives both envelopes (the keyboard until patched), EG1 TRIG IN drives EG1 alone
    bool gate = gate_at(I_TRIG_IN, kbd_gate);
    bool eg1_gate = patched(I_EG1_TRIG) ? gate_at(I_EG1_TRIG, false) : gate;
    bool retrig = !patched(I_TRIG_IN) && kbd_trig_edge;
    kbd_trig_edge = false;
    if (gate && (!gate_in_last || retrig)) eg2.gate_on();
    if (!gate && gate_in_last) eg2.gate_off();
    bool eg1_retrig = !patched(I_EG1_TRIG) && retrig;
    if (eg1_gate && (!eg1_in_last || eg1_retrig)) eg1.gate_on();
    if (!eg1_gate && eg1_in_last) eg1.gate_off();
    gate_in_last = gate;
    eg1_in_last = eg1_gate;
    float e1 = eg1.tick(), e2 = eg2.tick();
    o[O_EG1_OUT] = e1;
    o[O_EG1_REV] = 5.0f - e1;     // REV OUT: +5 V at rest, down to 0 V at the peak
    o[O_EG2_OUT] = e2;
    o[O_EG2_REV] = 5.0f - e2;
    // sample & hold: clock (MG RECT, the keyboard or the sequencer until patched), input (noise until patched)
    bool clk;
    if (patched(I_SH_CLOCK)) clk = gate_at(I_SH_CLOCK, false);
    else { int d = Pi(P_SH_CLOCK_DEF); clk = d == 0 ? mg.rect > 2.5f : d == 1 ? kbd_gate : seq.trig; }
    float shin;
    if (patched(I_SH_IN)) shin = in(I_SH_IN, 0);
    else { int d = Pi(P_SH_IN_DEF); shin = d == 0 ? o[O_WHITE] : d == 1 ? o[O_PINK] : mg.tri; }
    o[O_SH_OUT] = sh.tick(shin, clk);
    // modulation VCA: open until a control voltage is patched
    float g = patched(I_VCA_CTL) ? clampf(in(I_VCA_CTL, 5) * 0.2f, 0, 1) : 1.0f;
    o[O_VCA_OUT] = in(I_VCA_IN, 0) * g;
    // ESP
    esp.tick(in(I_ESP_IN, 0), pv[P_ESP_LEVEL], pv[P_ESP_CV], pv[P_ESP_THRESH], 0, false);
    o[O_ESP_AMP] = esp.amp_out;
    o[O_ESP_BPF] = esp.bpf_out;
    o[O_ESP_CV] = esp.cv_out;
    o[O_ESP_ENV] = esp.env_out;
    o[O_ESP_TRIG] = esp.trig ? 5.0f : 0.0f;
    o[O_SIG_OUT] = sig_out;
  }

  // ---- render --------------------------------------------------------------------------------------------------------
  float v_hz1[MAX_VOICES], v_hz2[MAX_VOICES], v_pw1 = 0.5f, v_pw2 = 0.1f;
  float render_l[128], render_r[128];

  void render(int16_t *out, int frames) {
    ScopedDenormalDisable dg;
    begin_block();
    float tgt_vol = powf(pv[P_VOLUME] * 0.1f, 1.6f) * 1.6f;   // VOLUME 7 ~ -7 dBFS peaks, 10 a touch under full scale
    float noise_amt = pv[P_NOISE_FLOOR] * 0.1f * 0.0012f;
    float drive = 1.0f + pv[P_FILTER_DRIVE] * 0.12f;
    float inv_nv = nvoices == 1 ? 1.0f : nvoices == 2 ? 0.75f : 0.55f;
    static const float OCT1[4] = {-24, -12, 0, 12}, OCT2[4] = {-12, 0, 12, 24};
    float mt = pv[P_MASTER_TUNE] * 0.01f;
    float drift_amt = pv[P_DRIFT] * 0.1f;
    for (int n = 0; n < frames; n++) {
      modulation();
      const float *o = out_v;
      bool control = (ctrl_count++ % CTRL_EVERY) == 0;
      if (control) {
        // frequency modulation: MG/T.EXT (TOTAL replaces the MG), EG1/EXT (FREQ replaces EG1); 1 V/oct at 10
        float fm = (patched(I_TOTAL) ? in(I_TOTAL, 0) : mg.tri) * pv[P_FM_MG] * 1.2f;
        fm += (patched(I_FREQ) ? in(I_FREQ, 0) : o[O_EG1_OUT]) * pv[P_FM_EG1] * 1.2f;
        if (Pi(P_WHEEL_TO) == 1) fm += mg.tri * mw * 2.4f;
        // pitch: Hz/V from VCO 1+2 CV IN (the keyboard until patched), VCO 2 CV IN added to VCO 2
        float base_hz = patched(I_VCO12_CV) ? fmaxf(in(I_VCO12_CV, 0), 0.0f) * HZ_PER_VOLT : midi_hz(kbd_semi + pb * pv[P_PB_RANGE]);
        float hz2_add = patched(I_VCO2_CV) ? in(I_VCO2_CV, 0) * HZ_PER_VOLT : 0.0f;
        float semi1 = OCT1[Pi(P_VCO1_SCALE) & 3] + mt + fm;
        float semi2 = OCT2[Pi(P_VCO2_SCALE) & 3] + pv[P_VCO2_PITCH] * 2.4f + mt + fm;   // PITCH -5..+5 = +-1 octave
        for (int i = 0; i < nvoices; i++) {
          Voice &v = voices[i];
          v.v1.drift_tick(); v.v2.drift_tick();
          float d1 = (v.v1.drift * drift_amt + v.detune) * 0.01f, d2 = (v.v2.drift * drift_amt - v.detune) * 0.01f;
          v_hz1[i] = base_hz * exp2f((semi1 + d1) / 12.0f);
          v_hz2[i] = base_hz * exp2f((semi2 + d2) / 12.0f) + hz2_add;
          v.v1.set_hz(v_hz1[i]);
          v.v2.set_hz(fmaxf(v_hz2[i], 0.0f));
        }
        // pulse width: the PW pot, modulated by the MG (PWM IN replaces it) on the chosen VCO
        float pwm = (patched(I_PWM_IN) ? in(I_PWM_IN, 0) : mg.tri) * 0.2f * pv[P_PWM_MG] * 0.1f;
        float pw1 = 0.5f - pv[P_VCO1_PW] * 0.047f;            // the PW pot: 1:1 at 0, the narrowest pulse at 10
        v_pw1 = clampf(pw1 + (Pi(P_PWM_VCO) == 0 ? pwm * 0.45f : 0.0f), 0.04f, 0.96f);
        v_pw2 = clampf(0.15f + (Pi(P_PWM_VCO) == 1 ? pwm * 0.3f : 0.0f), 0.04f, 0.96f);
        // filters: cutoff pots 50 Hz .. 15 kHz; MG/T.EXT and EG2/EXT at 2 oct/V with the knob at 10 (the panel's law)
        float mg_src = patched(I_TOTAL) ? in(I_TOTAL, 0) : mg.tri;
        float h_oct = pv[P_HPF_CUTOFF] * 0.823f + mg_src * pv[P_HPF_MG] * 0.2f +
                      (patched(I_HPF_CV) ? in(I_HPF_CV, 0) : o[O_EG2_OUT]) * pv[P_HPF_EG2] * 0.2f;
        float l_oct = pv[P_LPF_CUTOFF] * 0.823f + mg_src * pv[P_LPF_MG] * 0.2f +
                      (patched(I_LPF_CV) ? in(I_LPF_CV, 0) : o[O_EG2_OUT]) * pv[P_LPF_EG2] * 0.2f +
                      (vel - 0.6f) * pv[P_VCF_VEL] * 0.4f;
        if (Pi(P_WHEEL_TO) == 2) l_oct += mw * 3.0f;
        float hp_hz = 50.0f * exp2f(clampf(h_oct, -2, 9.0f)), lp_hz = 50.0f * exp2f(clampf(l_oct, -2, 8.6f));
        for (int i = 0; i < nvoices; i++) {
          voices[i].hpf.set(hp_hz, pv[P_HPF_PEAK] * 0.1f, mk);
          voices[i].lpf.set(lp_hz, pv[P_LPF_PEAK] * 0.1f, mk);
        }
      }
      // the VCA: EG2 (0..5 V) + INITIAL GAIN, exponential-ish, tremolo by the MG, velocity
      float vca_cv = clampf(o[O_EG2_OUT] + in(I_INIT_GAIN, 0), 0, 5.0f) * 0.2f;
      float vca = vca_cv * vca_cv * (1.0f - pv[P_VCA_VEL] * 0.1f * (1.0f - vel));
      if (vca_mod_depth > 0.001f) vca *= 1.0f - vca_mod_depth * (0.5f - mg.tri * 0.2f);
      float ext = in(I_EXT_IN, 0);
      float L = 0, R = 0, v1_out = 0, v2_out = 0;
      for (int i = 0; i < nvoices; i++) {
        Voice &v = voices[i];
        float s1, s2;
        switch (w1) {
          case W1_TRI: s1 = v.v1.tri(); break;
          case W1_SAW: s1 = v.v1.saw(); break;
          case W1_PULSE: s1 = v.v1.square(v_pw1); break;
          default: s1 = white; break;
        }
        float sq2 = v.v2.square(0.5f);
        switch (w2) {
          case W2_SAW: s2 = v.v2.saw(); break;
          case W2_SQUARE: s2 = sq2; break;
          case W2_PULSE: s2 = v.v2.square(v_pw2); break;
          default: s2 = s1 * sq2; break;                      // ring mod: VCO 1 chopped by VCO 2
        }
        v.v1.advance();
        v.v2.advance();
        s1 *= 2.5f; s2 *= 2.5f;                                 // 5 Vpp
        if (i == 0) { v1_out = s1; v2_out = s2; }
        float mix = (s1 * pv[P_VCO1_LEVEL] + s2 * pv[P_VCO2_LEVEL]) * 0.1f + ext;
        mix = mix * drive + white * 3e-5f;                      // thermal noise: what a resonating filter grows from
        float y = v.hpf.tick(mix);
        y = v.lpf.tick(y);
        y *= inv_nv;
        L += y * (1.0f - v.pan);
        R += y * v.pan;
      }
      if (nvoices == 1) { R = L; L = L; }
      else { L *= 1.4f; R *= 1.4f; }
      L *= vca; R *= vca;
      sig_out = (L + R) * 0.5f;                                 // to the SIGNAL OUT jack next sample, in volts
      s_vol += (tgt_vol - s_vol) * 0.002f;
      float outl = L * 0.2f * s_vol + white * noise_amt, outr = R * 0.2f * s_vol + white * noise_amt;
      // DC blocker
      float yl = outl - dcx_l + 0.9995f * dc_l, yr = outr - dcx_r + 0.9995f * dc_r;
      dcx_l = outl; dcx_r = outr; dc_l = yl; dc_r = yr;
      render_l[n] = yl;
      render_r[n] = yr;
      // the XXL audio jacks
      out_v[O_VCO1_OUT] = v1_out;
      out_v[O_VCO2_OUT] = v2_out;
    }
    lim.Process(render_l, render_r, frames, 0.0f, -0.3f, 80.0f, SR);
    for (int n = 0; n < frames; n++) {
      float a = render_l[n] * 32767.0f, b = render_r[n] * 32767.0f;
      out[n * 2] = (int16_t)(a > 32767.0f ? 32767 : a < -32768.0f ? -32768 : lrintf(a));
      out[n * 2 + 1] = (int16_t)(b > 32767.0f ? 32767 : b < -32768.0f ? -32768 : lrintf(b));
    }
    // lamps (polled by the screen)
    bool pk_lamp = esp.peak;
    int lamp = seq.running ? seq.lit_step + 1 : 0;
    if (pk_lamp != esp_peak_lamp || lamp != seq_lamp) { esp_peak_lamp = pk_lamp; seq_lamp = lamp; }
  }

  // ---- UI: views, jacks, Q-Links -----------------------------------------------------------------------------------------
  void set_view(int v) {
    if (v < 0 || v >= N_VIEWS || v == view) return;
    view = v;
    close_pops();
    touch[0] = 0;
    held = held_in = -1;
    pk = v == V_PATCH ? 1 : 0;
    if (pk) snprintf(info, sizeof info, "Tap a jack. Then tap the other end of the cable.");
    bump();
  }

  bool close_pops() {
    bool any = false;
    for (int i = 0; i < N_POPS; i++) if (pop_open[i]) { pop_open[i] = false; any = true; }
    return any;
  }

  void set_pop(int i, bool open) {
    if (open) close_pops();
    pop_open[i] = open;
    bump();
  }

  bool connect(int o, int j) {
    for (int k = 0; k < N_OUTS; k++) if (dest[k] == j) dest[k] = -1;   // one cable per input
    dest[o] = j;                                                       // one cable per output
    recompute_src();
    return true;
  }

  void unplug(int o) { if (o >= 0 && o < N_OUTS) { dest[o] = -1; recompute_src(); } }

  void show_pair(int o, int j) {
    pair_o = o; pair_j = j; pk = 4; held = held_in = -1;
    snprintf(info, sizeof info, "%s  ->  %s", OUT_LABEL[o], IN_LABEL[j]);
    bump();
  }

  void cancel_pick() {
    held = held_in = -1; pk = view == V_PATCH ? 1 : 0;
    snprintf(info, sizeof info, "Tap a jack. Then tap the other end of the cable.");
    bump();
  }

  void unplug_pair() {
    if (pk == 4 && pair_o >= 0 && dest[pair_o] == pair_j) {
      unplug(pair_o);
      snprintf(info, sizeof info, "%s unplugged", OUT_LABEL[pair_o]);
      pair_o = pair_j = -1; held = held_in = -1; pk = 1; bump();
    } else cancel_pick();
  }

  void done_pick() { cancel_pick(); }

  // Patching by pages: tap a jack; the page then asks for the other end (the same side dimmed and ignored); connecting
  // opens the page that shows the cable. A tapped jack that is already patched opens that cable's page (UNPLUG is there).
  void pick(int jack) {
    if (view != V_PATCH || pk < 1 || pk > 3) return;
    bool is_out = jack < N_OUTS;
    int o = is_out ? jack : -1, j = is_out ? -1 : jack - N_OUTS;
    if (pk == 1) {
      if (is_out) {
        if (dest[o] >= 0) { show_pair(o, dest[o]); return; }
        held = o; pk = 2;
        snprintf(info, sizeof info, "%s: now tap an input  (%s)", OUT_LABEL[o], OUT_INFO[o]);
      } else {
        if (src[j] >= 0) { show_pair(src[j], j); return; }
        held_in = j; pk = 3;
        snprintf(info, sizeof info, "%s: now tap an output  (%s)", IN_LABEL[j], IN_INFO[j]);
      }
    } else if (pk == 2) {                           // an output waits for an input
      if (is_out) { if (o == held) cancel_pick(); return; }
      int oo = held;
      connect(oo, j);
      show_pair(oo, j);
      return;
    } else {                                        // an input waits for an output
      if (!is_out) { if (j == held_in) cancel_pick(); return; }
      int jj = held_in;
      connect(o, jj);
      show_pair(o, jj);
      return;
    }
    bump();
  }

  // the cable / ring picture switches: each at most JACK_GROUP + 1 positions (see tools/spec.py)
  int vis_value(int k) const {
    if (VIS_KIND[k] == 2) {                        // ring: the output waiting for its input
      if (view != V_PATCH || held < 0 || held / JACK_GROUP != VIS_GROUP[k]) return 0;
      return 1 + held % JACK_GROUP;
    }
    if (VIS_KIND[k] == 3) {                        // ring: the input waiting for its output
      if (view != V_PATCH || held_in < 0 || held_in / JACK_GROUP != VIS_GROUP[k]) return 0;
      return 1 + held_in % JACK_GROUP;
    }
    if (view != V_PATCH || pk == 4) return 0;      // the panel's cables; the connected page has its own
    int o = VIS_OUT[k], d = dest[o];
    if (d < 0) return 0;
    return d / JACK_GROUP == VIS_GROUP[k] ? 1 + d % JACK_GROUP : 0;
  }

  int ql_target(int i) const { return VIEW_QLINKS[view][i]; }

  // ---- value text ------------------------------------------------------------------------------------------------------
  void display(int p, char *buf, int n) const {
    if (P_NOPTS[p]) { snprintf(buf, n, "%s", P_OPT[p][(int)clampf(pv[p], 0, P_NOPTS[p] - 1)]); return; }
    float v = pv[p];
    const char *u = P_UNIT[p];
    if (p >= P_SEQ_C1 && p < P_SEQ_C1 + 12) {   // channel C: 0..+5 V, or semitones
      if (Pi(P_SEQ_RANGE_C) == 0) snprintf(buf, n, "%.2f V", (v + 5.0f) * 0.5f);
      else snprintf(buf, n, "%+.1f st", v * 2.4f);
      return;
    }
    if (p >= P_SEQ_A1 && p < P_SEQ_A1 + 24) {
      int r = p < P_SEQ_B1 ? P_SEQ_RANGE_A : P_SEQ_RANGE_B;
      snprintf(buf, n, "%+.2f V", Pi(r) == 0 ? v * 0.2f : v);
      return;
    }
    if (P_INT[p]) snprintf(buf, n, "%s%d%s%s", (p == P_MASTER_TUNE) ? (v > 0.5f ? "+" : "") : "", (int)lroundf(v),
                           *u ? " " : "", u);
    else if (p == P_VCO2_PITCH) snprintf(buf, n, "%+.1f st", v * 2.4f);
    else snprintf(buf, n, "%.1f%s%s", v, *u ? " " : "", u);
  }

  // the control just moved, named with its value, for the top right corner (on the patch page it uses the page's own line)
  void note_touch(int p) {
    char val[48];
    display(p, val, sizeof val);
    if (view == V_PATCH) {
      if (pk == 0 || pk == 1) snprintf(info, sizeof info, "%s  %s", P_NAME[p], val);
    } else {
      snprintf(touch, sizeof touch, "%s  %s", P_NAME[p], val);
    }
    bump();
  }

  // ---- state ---------------------------------------------------------------------------------------------------------------
  int save(char *buf, int n) const {
    int len = snprintf(buf, n, "ms20xxl 1;");
    for (int i = 0; i < N_CONTROLS && len < n; i++) len += snprintf(buf + len, n - len, "%s=%g;", P_KEY[i], pv[i]);
    if (len < n) len += snprintf(buf + len, n - len, "view=%d;", view);
    for (int o = 0; o < N_OUTS && len < n; o++)
      if (dest[o] >= 0) len += snprintf(buf + len, n - len, "cable=%s>%s;", OUT_KEY[o], IN_KEY[dest[o]]);
    return len < n ? len : -1;
  }
};

int find_key(const char *k) {
  static int table[2048];
  static bool built = false;
  auto h = [](const char *s) { uint32_t x = 2166136261u; while (*s) x = (x ^ (unsigned char)*s++) * 16777619u; return x; };
  if (!built) {
    for (int i = 0; i < 2048; i++) table[i] = -1;
    for (int i = 0; i < P_COUNT; i++) {
      uint32_t s = h(P_KEY[i]) & 2047;
      while (table[s] >= 0) s = (s + 1) & 2047;
      table[s] = i;
    }
    built = true;
  }
  uint32_t s = h(k) & 2047;
  while (table[s] >= 0) {
    if (!strcmp(P_KEY[table[s]], k)) return table[s];
    s = (s + 1) & 2047;
  }
  return -1;
}

int find_in(const char *a, const char *const *keys, int n) {
  for (int i = 0; i < n; i++) if (!strcmp(a, keys[i])) return i;
  return -1;
}

void set_control(Synth *s, int p, float v);

void load_state(Synth *s, const char *st) {
  if (strncmp(st, "ms20xxl", 7)) return;
  for (int o = 0; o < N_OUTS; o++) s->dest[o] = -1;
  const char *q = strchr(st, ';');
  while (q && *++q) {
    const char *e = strchr(q, ';');
    if (!e) break;
    char item[96];
    int len = (int)(e - q) < 95 ? (int)(e - q) : 95;
    memcpy(item, q, len);
    item[len] = 0;
    char *eq = strchr(item, '=');
    if (eq) {
      *eq = 0;
      const char *val = eq + 1;
      if (!strcmp(item, "view")) s->view = (int)clampf((float)atoi(val), 0, N_VIEWS - 1);
      else if (!strcmp(item, "cable")) {
        char a[48];
        snprintf(a, sizeof a, "%s", val);
        char *gt = strchr(a, '>');
        if (gt) {
          *gt = 0;
          int o = find_in(a, OUT_KEY, N_OUTS), j = find_in(gt + 1, IN_KEY, N_INS);
          if (o >= 0 && j >= 0) {
            for (int k = 0; k < N_OUTS; k++) if (s->dest[k] == j) s->dest[k] = -1;
            s->dest[o] = j;
          }
        }
      } else {
        int p = find_key(item);
        if (p >= 0 && p < N_CONTROLS) set_control(s, p, (float)atof(val));
      }
    }
    q = e;
  }
  s->held = -1;
  s->held_in = -1;
  s->recompute_src();
  s->apply_all();
  s->bump();
}

void set_control(Synth *s, int p, float v) {
  v = clampf(v, P_MIN[p], P_MAX[p]);
  if (P_NOPTS[p] || P_INT[p]) v = roundf(v);
  bool moved = s->pv[p] != v;
  s->pv[p] = v;
  if ((p >= P_SEQ_SPEED && p <= P_SEQ_T12) || p == P_UNISON || p == P_UNISON_DETUNE) s->apply_all();
  if (p == P_SEQ_RUN && moved && v > 0.5f) s->seq.finished = false;
  if (p == P_SEQ_STEP_BTN && v > 0.5f) { s->seq.manual_step(); s->pv[p] = 0; }
  if (p == P_MG_MODE && moved && v > 0.5f) s->mg.reset();
  for (int i = 0; i < N_POPS; i++)          // a pick from a pop-up list closes it
    if (POP_ENUM[i] == p && moved && s->pop_open[i]) { s->pop_open[i] = false; s->bump(); }
}

// ---- mpc_engine glue ------------------------------------------------------------------------------------------------
void *create(const char *) {
  void *mem = calloc(1, sizeof(Synth));
  if (!mem) return nullptr;
  Synth *s = new (mem) Synth();
  s->init();
  return s;
}

void destroy(void *inst) {
  Synth *s = (Synth *)inst;
  s->~Synth();
  free(s);
}

void midi(void *inst, const uint8_t *m, int len) { ((Synth *)inst)->midi(m, len); }

void set_param(void *inst, const char *key, const char *val) {
  Synth *s = (Synth *)inst;
  float v = (float)atof(val);
  if (!strcmp(key, "state")) { load_state(s, val); return; }
  if (!strcmp(key, "lfo_bpm")) { if (v > 1) s->bpm = v; return; }
  if (!strcmp(key, "transport")) {
    bool play = v > 0.5f;
    if (play && !s->transport && s->on(P_SEQ_TRANSPORT)) { s->seq.finished = false; s->seq.step = 0; s->seq.phase = 0; }
    s->transport = play;
    if (play) s->mg.reset();
    return;
  }
  int p = find_key(key);
  if (p < 0) return;
  if (p < N_CONTROLS) {
    float before = s->pv[p];
    set_control(s, p, v);
    if (s->pv[p] != before && p != P_SEQ_STEP_BTN) s->note_touch(p);
    s->bump();                              // the Q-Link knob mirroring it moves too
    return;
  }
  if (p == P_VIEW) { s->set_view((int)lroundf(v)); return; }
  if (p == P_IN_SEC) return;                // follows the view
  if (p == P_PK || p == P_PK_T || p == P_PK_C) return;   // follow the patch step
  if (p == P_ESP_PEAK || p == P_SEQ_STEP_LO || p == P_SEQ_STEP_HI || p == P_SEQ_RUNNING) return;   // lamps
  if (p >= P_PT_MG_TRI && p < P_PT_MG_TRI + N_OUTS) {   // a cable as a parameter (presets, automation)
    int o = p - P_PT_MG_TRI, j = (int)lroundf(v) - 1;
    if (j < 0 || j >= N_INS) s->unplug(o);
    else if (s->dest[o] != j) s->connect(o, j);
    s->bump();
    return;
  }
  if (p > P_IN_SEC && p <= P_IN_SEC + N_POPS) { s->set_pop(p - P_IN_SEC - 1, v > 0.5f); return; }
  if (v < 0.5f) {
    if (p >= P_QL1 && p <= P_QL16) {} else return;   // triggers fire on 1 only
  }
  if (p == P_NAV_ZOOM) { s->set_view(V_OVERVIEW); return; }
  if (p == P_NAV_PREV || p == P_NAV_NEXT) {
    int v2 = s->view <= 0 ? 1 : s->view + (p == P_NAV_NEXT ? 1 : -1);
    if (v2 < 1) v2 = N_VIEWS - 1;
    if (v2 >= N_VIEWS) v2 = 1;
    s->set_view(v2);
    return;
  }
  if (p >= P_GO_VCO && p < P_GO_VCO + (N_VIEWS - 1)) { s->set_view(1 + p - P_GO_VCO); return; }
  if (p >= P_TAP_MG_TRI && p < P_TAP_MG_TRI + N_OUTS + N_INS) { s->pick(p - P_TAP_MG_TRI); return; }
  if (p == P_PK_CANCEL) { s->cancel_pick(); return; }
  if (p == P_PK_UNPLUG) { s->unplug_pair(); return; }
  if (p == P_PK_DONE) { s->done_pick(); return; }
  if (p >= P_QL1 && p <= P_QL16) {
    int t = s->ql_target(p - P_QL1);
    if (t < 0) return;
    float x = clampf(v, 0, 1);
    float before = s->pv[t];
    set_control(s, t, P_MIN[t] + x * (P_MAX[t] - P_MIN[t]));
    if (s->pv[t] != before) s->note_touch(t);
    s->bump();
    return;
  }
}

int get_param(void *inst, const char *key, char *buf, int n) {
  Synth *s = (Synth *)inst;
  if (!strcmp(key, "display_rev")) return snprintf(buf, n, "%u", s->rev);
  if (!strcmp(key, "state")) return s->save(buf, n);
  size_t kl = strlen(key);
  char base[64];
  int suffix = 0;   // 1 = _display, 2 = _name
  if (kl > 8 && !strcmp(key + kl - 8, "_display")) { suffix = 1; kl -= 8; }
  else if (kl > 5 && !strcmp(key + kl - 5, "_name")) { suffix = 2; kl -= 5; }
  if (kl >= sizeof base) return 0;
  memcpy(base, key, kl);
  base[kl] = 0;
  int p = find_key(base);
  if (p < 0) return 0;
  if (p >= P_QL1 && p <= P_QL16) {
    int t = s->ql_target(p - P_QL1);
    if (suffix == 2) return snprintf(buf, n, "%s", t >= 0 ? P_NAME[t] : "-");
    if (suffix == 1) { if (t < 0) return snprintf(buf, n, " "); s->display(t, buf, n); return (int)strlen(buf); }
    if (t < 0) return snprintf(buf, n, "0");
    float span = P_MAX[t] - P_MIN[t];
    return snprintf(buf, n, "%g", span > 0 ? (s->pv[t] - P_MIN[t]) / span : 0.0f);
  }
  if (suffix == 2) return 0;
  if (suffix == 1) {
    if (p >= N_CONTROLS) return 0;
    s->display(p, buf, n);
    return (int)strlen(buf);
  }
  if (p < N_CONTROLS) {
    if (P_NOPTS[p]) return snprintf(buf, n, "%d", (int)s->pv[p]);
    return snprintf(buf, n, "%g", s->pv[p]);
  }
  if (p == P_VIEW) return snprintf(buf, n, "%d", s->view);
  if (p == P_IN_SEC) return snprintf(buf, n, "%d", s->view > 0 ? 1 : 0);
  if (p == P_PK) return snprintf(buf, n, "%d", s->view == V_PATCH ? s->pk : 0);
  if (p == P_PK_T) return snprintf(buf, n, "%d", s->view == V_PATCH && s->pk >= 1 && s->pk <= 3 ? 1 : 0);
  if (p == P_PK_C) return snprintf(buf, n, "%d", s->view == V_PATCH && (s->pk == 2 || s->pk == 3) ? 1 : 0);
  if (p >= P_VIS_FIRST && p < P_VIS_FIRST + N_VIS) return snprintf(buf, n, "%d", s->vis_value(p - P_VIS_FIRST));
  if (p > P_IN_SEC && p <= P_IN_SEC + N_POPS) return snprintf(buf, n, "%d", s->pop_open[p - P_IN_SEC - 1] ? 1 : 0);
  if (p >= P_PT_MG_TRI && p < P_PT_MG_TRI + N_OUTS) return snprintf(buf, n, "%d", s->dest[p - P_PT_MG_TRI] + 1);
  if (p == P_PATCH_INFO) return snprintf(buf, n, "%s", s->info);
  if (p == P_TOUCH_INFO) return snprintf(buf, n, "%s", s->touch);
  if (p == P_ESP_PEAK) return snprintf(buf, n, "%d", s->esp_peak_lamp && s->view == V_ESP ? 1 : 0);
  if (p == P_SEQ_STEP_LO) return snprintf(buf, n, "%d", s->view == V_SEQ && s->seq_lamp >= 1 && s->seq_lamp <= 6 ? s->seq_lamp : 0);
  if (p == P_SEQ_STEP_HI) return snprintf(buf, n, "%d", s->view == V_SEQ && s->seq_lamp >= 7 ? s->seq_lamp - 6 : 0);
  if (p == P_SEQ_RUNNING) return snprintf(buf, n, "%d", s->seq.running ? 1 : 0);
  return snprintf(buf, n, "0");   // triggers and navigation read back as 0
}

void render(void *inst, int16_t *out, int frames) { ((Synth *)inst)->render(out, frames); }

const mpc_engine_t API = {create, destroy, midi, set_param, get_param, render, nullptr, nullptr};

}  // namespace

extern "C" const mpc_engine_t *mpc_engine(void) { return &API; }
