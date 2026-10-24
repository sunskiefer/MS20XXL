// SPDX-License-Identifier: GPL-3.0-or-later
// MS20XXL -- the sound engine's building blocks, host-free. Everything here takes plain numbers and runs at 44100 Hz.
//
// Voltages: control signals are floats in "volts" as the MS-20 panel labels them (-5..+5 V, envelopes 0..+5 V, the MG
// triangle -2.5..+2.5 V, its rectangle 0..+5 V). Audio runs in the same units: an oscillator gives 5 Vpp (-2.5..+2.5 V),
// which is what the MS-20's EXT SIGNAL IN expects ("3 Vpp max" printed, a bit more in practice). Triggers are gates
// (0 = off, 1 = on); the panel's S-trig is a gate too, just inverted electrically.
//
// The filters follow the MS-20 circuit: a Sallen-Key around two one-pole stages (OTA-driven integrators), the resonance
// a positive feedback through a third one-pole of the opposite kind, with the feedback diode/transistor clipping that
// gives the MS-20 its scream (MK1: KORG35 chips, harder and louder; MK2: LM13600 OTAs, the late schematic, a touch
// softer). Zero-delay feedback, the loop solved per sample, the clipper on the feedback path.
#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>

namespace ms20 {

const float SR = 44100.0f;
const float INV_SR = 1.0f / 44100.0f;
const float PI = 3.14159265358979f;

inline float clampf(float x, float a, float b) { return x < a ? a : x > b ? b : x; }
inline float fast_tanh(float x) {   // Pade, exact enough for a clipper, cheap on armv7
  if (x < -3.0f) return -1.0f;
  if (x > 3.0f) return 1.0f;
  float x2 = x * x;
  return x * (27.0f + x2) / (27.0f + 9.0f * x2);
}
// MS-20 time pots: 0..10 -> seconds, roughly 1 ms .. 10 s (the panel legends are not in seconds)
inline float pot_time(float v) { return 0.001f * powf(10.0f, clampf(v, 0, 10) * 0.4f); }
inline float rate_for(float seconds) { return 1.0f - expf(-1.0f / (fmaxf(seconds, 0.0005f) * SR)); }
inline float midi_hz(float note) { return 440.0f * exp2f((note - 69.0f) / 12.0f); }

// ---- noise -------------------------------------------------------------------------------------------------------
struct Rng {
  uint32_t s = 0x9E3779B9u;
  inline float white() {   // -1..1
    s ^= s << 13; s ^= s >> 17; s ^= s << 5;
    return (int32_t)s * (1.0f / 2147483648.0f);
  }
};

struct Pink {   // Paul Kellet's economy pink filter
  float b0 = 0, b1 = 0, b2 = 0;
  inline float next(float w) {
    b0 = 0.99765f * b0 + w * 0.0990460f;
    b1 = 0.96300f * b1 + w * 0.2965164f;
    b2 = 0.57000f * b2 + w * 1.0526913f;
    return (b0 + b1 + b2 + w * 0.1848f) * 0.2f;
  }
};

// ---- one-pole TPT stage (Zavalishin), the building block of both filters -----------------------------------------
struct OnePole {
  float s = 0;
  inline void reset() { s = 0; }
  // alpha = g / (1 + g), g = tan(pi f / sr). lowpass out; the highpass is x - lp.
  inline float lp(float x, float alpha) {
    float v = (x - s) * alpha;
    float y = v + s;
    s = y + v;
    return y;
  }
};
inline float stage_alpha(float hz) {
  float g = tanf(PI * clampf(hz, 5.0f, 20000.0f) * INV_SR);
  return g / (1.0f + g);
}

// ---- the MS-20 lowpass ------------------------------------------------------------------------------------------
// Two cascaded one-pole stages (OTA integrators, unity buffers) with the resonance fed back around them: the late
// KLM-307 board (MK2). Vo/Vin = 1 / (s^2 + (2 - K) s + 1): Q = 1 / (2 - K), self-oscillation at K = 2, and the PEAK
// pot reaches K ~ 2.2 so it howls over the last tenth of its travel. Three series diodes (~2 V) sit in the feedback
// loop, so only the resonant corner distorts and the pass band stays clean. The early KORG35 (MK1) instead has its
// diode pair inside the gain-58 forward stage: every frequency distorts as the level grows, the resonance is
// asymmetric (stronger on the negative half) and the signal itself nudges the cutoff.
struct Ms20Lpf {
  OnePole lp1, lp2, hp;
  float alpha = 0.1f, beta = 0.9f, K = 0;
  int mk = 1;          // 0 = MK1 (KORG35), 1 = MK2 (LM13600)
  void reset() { lp1.reset(); lp2.reset(); hp.reset(); }
  // cutoff in Hz, peak 0..1, mk 0/1 -- once per control period
  void set(float hz, float peak, int mark) {
    mk = mark;
    alpha = stage_alpha(hz);
    beta = 1.0f - alpha;
    float p = clampf(peak, 0, 1);
    K = 2.2f * powf(p, 0.9f);                       // oscillation sets in near 90 % of the knob
  }
  // MK2: the three-diode string in the feedback path, ~2 V knee, gentle
  static inline float clip_fb(float v) { return fast_tanh(v * 0.5f) * 2.0f; }
  // MK1: the diode pair in the forward path, 0.5 V knee referred to the stage, biased off centre
  static inline float clip_fwd(float v) { return (fast_tanh(v * 0.6f + 0.12f) - fast_tanh(0.12f)) * 1.667f; }
  inline float tick(float x) {
    float a = alpha;
    if (mk == 0) a = clampf(alpha * (1.0f + 0.03f * x), 0.0005f, 0.98f);   // the signal moves the KORG35's cutoff
    float x1 = lp1.lp(x, a);
    // solve the loop linearly, then clip the feedback: u = x1 + K * clip(beta * (a u + S2 - sh))
    float S2 = (1.0f - a) * lp2.s;
    float lin = beta * (S2 - hp.s);
    float u = (x1 + K * lin) / (1.0f - K * beta * a);
    float fb = beta * (a * u + S2 - hp.s);
    if (mk == 1) { float fbc = clip_fb(fb); if (fbc != fb) u = x1 + K * fbc; }
    else { u = clip_fwd(x1 + K * fb); }
    float y = lp2.lp(u, a);
    hp.lp(y, a);
    return mk == 0 ? y : -y;                        // the OTA board inverts (k1 = -1)
  }
};

// ---- the MS-20 highpass -----------------------------------------------------------------------------------------
// The MS-20 feeds its highpass by lifting the first capacitor's return instead of swapping R and C: what comes out is
// a 12 dB highpass with a 6 dB band pass beside it, the band pass winning below the cutoff (Stinchcombe, Doepfer).
// That is why the MS-20 HPF thins the sound without ever quite emptying it. Same loop, same clippers as the LPF.
struct Ms20Hpf {
  OnePole hp1, hp2, lp;
  float alpha = 0.1f, K = 0;
  int mk = 1;
  void reset() { hp1.reset(); hp2.reset(); lp.reset(); }
  void set(float hz, float peak, int mark) {
    mk = mark;
    alpha = stage_alpha(hz);
    float p = clampf(peak, 0, 1);
    K = 2.2f * powf(p, 0.9f);
  }
  inline float tick(float x) {
    float a = alpha;
    if (mk == 0) a = clampf(alpha * (1.0f + 0.03f * x), 0.0005f, 0.98f);
    float x1 = x - hp1.lp(x, a);                            // HP1 out, 6 dB
    float b = 1.0f - a;
    float lin = a * (b * (-hp2.s) - lp.s) + lp.s;           // the feedback with u = 0
    float u = (x1 + K * lin) / (1.0f - K * a * b);
    float y_lin = b * (u - hp2.s);
    float fb = a * (y_lin - lp.s) + lp.s;
    if (mk == 1) { float fbc = Ms20Lpf::clip_fb(fb); if (fbc != fb) u = x1 + K * fbc; }
    else { u = Ms20Lpf::clip_fwd(x1 + K * fb); }
    float y = u - hp2.lp(u, a);
    lp.lp(y, a);
    return y + 0.45f * (x1 - y);                            // the capacitor-return injection: 6 dB band pass beside it
  }
};

// ---- oscillators ------------------------------------------------------------------------------------------------
inline float poly_blep(float t, float dt) {
  if (t < dt) { t /= dt; return t + t - t * t - 1.0f; }
  if (t > 1.0f - dt) { t = (t - 1.0f) / dt; return t * t + t + t + 1.0f; }
  return 0.0f;
}

enum { W1_TRI = 0, W1_SAW, W1_PULSE, W1_NOISE };
enum { W2_SAW = 0, W2_SQUARE, W2_PULSE, W2_RING };

struct Vco {
  float phase = 0, inc = 0;
  float drift = 0, drift_target = 0;   // slow random walk of the pitch, cents: the warmth of a free-running VCO
  int drift_count = 0;
  float tri_state = 0;                 // the triangle is an integrated blep square: band-limited, like the circuit
  Rng *rng = 0;
  void reset(float ph) { phase = ph; tri_state = 0; }
  inline void set_hz(float hz) { inc = clampf(hz * INV_SR, 0, 0.48f); }
  inline void drift_tick() {
    if (--drift_count <= 0) { drift_count = 2048 + (int)((rng->white() + 1.0f) * 2048); drift_target = rng->white() * 2.2f; }
    drift += (drift_target - drift) * 0.0005f;
  }
  inline float square(float pw) {
    float t = phase, dt = inc;
    float s = t < pw ? 1.0f : -1.0f;
    s += poly_blep(t, dt);
    float t2 = t - pw + (t < pw ? 1.0f : 0.0f);
    s -= poly_blep(t2, dt);
    return s;
  }
  inline float saw() { return 2.0f * phase - 1.0f - poly_blep(phase, inc); }
  inline float tri() {
    float sq = square(0.5f);
    float g = inc * 4.0f;                                  // integrator gain so the peak stays at +-1
    tri_state += g * sq;
    tri_state *= 0.9995f;                                  // leaky, no DC walk
    return clampf(tri_state, -1, 1);
  }
  inline void advance() { phase += inc; if (phase >= 1.0f) phase -= 1.0f; }
};

// ---- modulation generator ---------------------------------------------------------------------------------------
// One knob shapes both outputs: the triangle leans from a falling ramp through a triangle to a rising ramp, and the
// rectangle's width goes from narrow to wide (the MS-20's MG WAVE FORM pot does exactly this).
struct Mg {
  float phase = 0;
  float tri = 0, rect = 0;   // -2.5..+2.5 V and 0..+5 V
  bool wrapped = false;
  inline void tick(float hz, float shape) {   // shape 0..1
    phase += clampf(hz, 0, 2000.0f) * INV_SR;
    wrapped = false;
    if (phase >= 1.0f) { phase -= floorf(phase); wrapped = true; }
    float p = clampf(0.02f + shape * 0.96f, 0.02f, 0.98f);   // the turning point
    float t = phase < p ? phase / p : 1.0f - (phase - p) / (1.0f - p);
    tri = (t * 2.0f - 1.0f) * 2.5f;
    rect = phase < p ? 5.0f : 0.0f;
  }
  void reset() { phase = 0; }
};

// ---- envelope generator 1: delay, attack, release ---------------------------------------------------------------
// Holds at the peak while the gate is on. 0..+5 V out, REV OUT = -out.
struct Eg1 {
  enum { IDLE, DELAY, ATTACK, PEAK, RELEASE };
  int stage = IDLE;
  float out = 0, delay_left = 0;
  bool gate = false, loop = false, trig_only = false;
  float atk_rate = 0, rel_rate = 0;
  void set(float delay_s, float attack_s, float release_s) {
    delay_time = delay_s;
    atk_rate = INV_SR / fmaxf(attack_s, 0.0008f);
    rel_rate = rate_for(release_s * 0.3f);
  }
  float delay_time = 0;
  inline void gate_on() { gate = true; stage = DELAY; delay_left = delay_time; }
  inline void gate_off() { gate = false; if (!trig_only && stage != IDLE && stage != RELEASE) stage = RELEASE; }
  inline float tick() {
    switch (stage) {
      case DELAY:
        delay_left -= INV_SR;
        if (delay_left <= 0) stage = ATTACK;
        if (!gate && !trig_only) stage = RELEASE;
        break;
      case ATTACK:
        out += atk_rate;
        if (out >= 1.0f) { out = 1.0f; stage = (trig_only || loop) ? RELEASE : PEAK; }
        break;
      case PEAK:
        if (!gate) stage = RELEASE;
        break;
      case RELEASE:
        out -= out * rel_rate + 1e-6f;
        if (out <= 0) { out = 0; stage = loop && gate ? DELAY : IDLE; if (stage == DELAY) delay_left = delay_time; }
        break;
      default: break;
    }
    return out * 5.0f;
  }
};

// ---- envelope generator 2: hold, attack, decay, sustain, release -----------------------------------------------
// HOLD TIME: the sustain level stays for this long after the key is let go, then the release runs (MS-20 EG2).
// 0..+5 V, REV OUT = -out. The VCA follows it; so does the lowpass's EG2/EXT.
struct Eg2 {
  enum { IDLE, ATTACK, DECAY, SUSTAIN, HOLD, RELEASE };
  int stage = IDLE;
  float out = 0, hold_left = 0;
  bool gate = false;
  float atk_rate = 0, dec_rate = 0, rel_rate = 0, sus = 0.7f, hold_time = 0;
  void set(float hold_s, float attack_s, float decay_s, float sustain, float release_s) {
    hold_time = hold_s;
    atk_rate = INV_SR / fmaxf(attack_s, 0.0008f);
    dec_rate = rate_for(decay_s * 0.3f);
    rel_rate = rate_for(release_s * 0.3f);
    sus = clampf(sustain, 0, 1);
  }
  inline void gate_on() { gate = true; stage = ATTACK; }   // from where it is: no reset click, like the circuit
  inline void gate_off() {
    gate = false;
    if (stage == IDLE) return;
    if (hold_time > 0.002f) { stage = HOLD; hold_left = hold_time; }
    else stage = RELEASE;
  }
  inline float tick() {
    switch (stage) {
      case ATTACK:
        out += atk_rate;
        if (out >= 1.0f) { out = 1.0f; stage = DECAY; }
        break;
      case DECAY:
        out += (sus - out) * dec_rate;
        if (fabsf(out - sus) < 1e-4f) stage = SUSTAIN;
        break;
      case SUSTAIN:
        out += (sus - out) * 0.001f;
        break;
      case HOLD:
        out += (sus - out) * dec_rate;
        hold_left -= INV_SR;
        if (hold_left <= 0) stage = RELEASE;
        break;
      case RELEASE:
        out -= out * rel_rate + 1e-6f;
        if (out <= 0) { out = 0; stage = IDLE; }
        break;
      default: break;
    }
    return out * 5.0f;
  }
};

// ---- sample & hold ----------------------------------------------------------------------------------------------
struct SampleHold {
  float out = 0;
  bool last_clock = false;
  inline float tick(float in, bool clock) {
    if (clock && !last_clock) out = in;
    last_clock = clock;
    return out;
  }
};

// ---- external signal processor ----------------------------------------------------------------------------------
// SIGNAL IN -> amp (SIGNAL LEVEL) -> AMP OUT -> bandpass (LOW CUT, HIGH CUT) -> BPF OUT -> F-V converter -> CV OUT
// (CV ADJUST); BPF OUT -> envelope follower -> ENV OUT; THRESHOLD -> TRIG OUT and the PEAK lamp.
struct Esp {
  OnePole lo1, lo2, hi1, hi2;
  float a_lo = 0.01f, a_hi = 0.5f;
  float env = 0;
  float fv_period = 0, fv_count = 0, fv_hz = 0, fv_cv = 0;
  float last = 0;
  bool trig = false, peak = false;
  float amp_out = 0, bpf_out = 0, env_out = 0, cv_out = 0;
  void set(float low_cut_hz, float high_cut_hz) { a_lo = stage_alpha(low_cut_hz); a_hi = stage_alpha(high_cut_hz); }
  void reset() { lo1.reset(); lo2.reset(); hi1.reset(); hi2.reset(); env = 0; fv_count = 0; }
  inline void tick(float in, float level, float cv_adjust, float threshold, float bpf_in_patched, bool patched) {
    float g = level * level * 0.4f;                       // 0..10 -> up to 40x, the ESP amp has lots of gain
    amp_out = fast_tanh(in * g * 0.2f) * 5.0f;            // clips at 5 Vpp like the circuit's op amp
    float x = patched ? bpf_in_patched : amp_out;
    x = x - lo1.lp(x, a_lo);
    x = x - lo2.lp(x, a_lo);
    x = hi1.lp(x, a_hi);
    x = hi2.lp(x, a_hi);
    bpf_out = x;
    // envelope follower: rectify, fast attack, slower release
    float r = fabsf(x);
    env += (r - env) * (r > env ? 0.02f : 0.0008f);
    env_out = clampf(env * 2.0f, 0, 5.0f);
    // F-V: period between rising zero crossings, with a little hysteresis
    fv_count += 1.0f;
    if (last <= 0.0f && x > 0.02f && fv_count > 8.0f) {
      fv_period = fv_count;
      fv_count = 0;
      float hz = SR / fv_period;
      fv_hz += (hz - fv_hz) * 0.4f;
    }
    last = x;
    if (fv_count > SR * 0.1f) fv_hz *= 0.999f;            // no signal: fall away
    cv_out = clampf(fv_hz * 0.01f * (0.5f + cv_adjust * 0.1f), 0, 10.0f);   // Hz/V, as the VCO 1+2 CV IN expects
    float th = threshold * 0.5f;                          // 0..5 V
    if (!trig && env_out > th + 0.1f) trig = true;
    else if (trig && env_out < th - 0.1f) trig = false;
    peak = fabsf(amp_out) > 4.5f;
  }
};

// ---- the SQ-10-style sequencer ----------------------------------------------------------------------------------
// Three channels of twelve steps on one clock. Modes as on the SQ-10: parallel (all three rows step together, a
// 12-step loop) or series (rows A, B and C play one after the other through channel A, a 36-step loop), each as a
// loop or a one-shot that stops at the end until the next start. Swing delays every other step, GATE sets the
// trigger's length, PORTAMENTO slews channels A/B and C (C also per step). SLOW..FAST is 0.1 .. 60 steps a second;
// with SYNC on, a tempo division. The clock can be modulated (exponential) and replaced by an external clock.
struct Sequencer {
  static const int STEPS = 12;
  float val[3][STEPS];        // -5..+5 (the knobs)
  bool trig_on[STEPS];        // TRIGGER buttons
  bool porta_c[STEPS];        // PORTAMENTO CHANNEL C buttons
  int length = STEPS, mode = 0;   // mode: 0 12-step loop, 1 12-step once, 2 24-step loop (A then B), 3 24-step once
  float swing = 0.5f, gate_len = 0.5f, porta_ab = 0, porta_c_time = 0;
  bool running = false, ext_clock = false;
  float phase = 0;            // 0..1 through the current step
  int step = 0;               // 0..11 (parallel) or 0..35 (series)
  int lit_step = 0, lit_row = 0;   // the LED
  float out_a = 0, out_b = 0, out_c = 0;   // slewed channel outputs
  float tgt_a = 0, tgt_b = 0, tgt_c = 0;
  bool trig = false, last_ext = false, finished = false;
  float trig_time = 0;        // seconds left of the current gate
  float step_len = 0.25f;     // seconds per step (unswung)

  void init() {
    for (int c = 0; c < 3; c++) for (int s = 0; s < STEPS; s++) val[c][s] = 0;
    for (int s = 0; s < STEPS; s++) { trig_on[s] = true; porta_c[s] = false; }
  }
  void start() { running = true; finished = false; step = 0; phase = 0; fire(); }
  void stop() { running = false; trig = false; }
  void reset() { step = 0; phase = 0; finished = false; if (running) fire(); }
  void manual_step() { if (!running) { finished = false; advance(); } }   // the STEP button: one step while stopped

  int total() const { return mode >= 2 ? length * 2 : length; }
  int row(int s) const { return mode >= 2 ? s / length : 0; }
  int col(int s) const { return mode >= 2 ? s % length : s; }

  void fire() {
    int r = row(step), c = col(step);
    lit_step = c;
    lit_row = r;
    // 24-step (series): channel A plays row A then row B; B plays B then A; C runs its twelve alongside, twice
    if (mode >= 2) { tgt_a = val[r][c]; tgt_b = val[1 - r][c]; tgt_c = val[2][c]; }
    else { tgt_a = val[0][c]; tgt_b = val[1][c]; tgt_c = val[2][c]; }
    cur_porta_c = porta_c[c];
    if (trig_on[c]) { trig = true; trig_time = fmaxf(step_len * gate_len, 0.004f); }
  }
  bool cur_porta_c = false;

  void advance() {
    step++;
    if (step >= total()) {
      if (mode == 1 || mode == 3) { finished = true; running = false; trig = false; step = total() - 1; return; }
      step = 0;
    }
    fire();
  }

  // seconds per step (unswung), ext clock gate (if used), clock mod in octaves
  inline void tick(float step_seconds, bool ext_gate) {
    step_len = step_seconds;
    if (trig_time > 0) { trig_time -= INV_SR; if (trig_time <= 0) trig = false; }
    if (running && !finished) {
      if (ext_clock) {
        if (ext_gate && !last_ext) advance();
      } else {
        // swing: odd steps get longer by the swing amount, even ones shorter (50% = straight)
        float sw = (swing - 0.5f) * 2.0f;   // -1..1
        float len = step_len * ((step & 1) ? 1.0f + sw * 0.6f : 1.0f - sw * 0.6f);
        phase += INV_SR / fmaxf(len, 0.004f);
        if (phase >= 1.0f) { phase -= 1.0f; advance(); }
      }
    }
    last_ext = ext_gate;
    // portamento: exponential slew, A/B share one knob, C has its own and per-step enables
    float ra = porta_ab > 0.01f ? rate_for(pot_time(porta_ab) * 0.4f) : 1.0f;
    float rc = (porta_c_time > 0.01f && cur_porta_c) ? rate_for(pot_time(porta_c_time) * 0.4f) : 1.0f;
    out_a += (tgt_a - out_a) * ra;
    out_b += (tgt_b - out_b) * ra;
    out_c += (tgt_c - out_c) * rc;
  }
};

}  // namespace ms20
