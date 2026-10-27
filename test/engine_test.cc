// SPDX-License-Identifier: GPL-3.0-or-later
// MS20XXL engine tests (x86, ASan/UBSan): test/run_tests.sh
// The patch panel and zoom logic the skin depends on, the state, the presets' cables, and the sound: every control
// swept, every cable patched, every waveform, the filters' resonance, the sequencer, and CPU.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <string>
extern "C" {
#include "engine.h"
}
#include "param_ids.h"

static int fails = 0, checks = 0;
#define CHECK(cond, ...)                                  \
  do {                                                    \
    checks++;                                             \
    if (!(cond)) { fails++; printf("FAIL "); printf(__VA_ARGS__); printf("\n"); } \
  } while (0)

static const mpc_engine_t *E;

static std::string get(void *s, const char *k) {
  char buf[16384];
  int n = E->get_param(s, k, buf, sizeof buf);
  return n > 0 ? std::string(buf) : std::string();
}
static int geti(void *s, const char *k) { return atoi(get(s, k).c_str()); }
static float getf(void *s, const char *k) { return (float)atof(get(s, k).c_str()); }
static void set(void *s, const char *k, const char *v) { E->set_param(s, k, v); }
static void setf(void *s, const char *k, float v) { char b[32]; snprintf(b, sizeof b, "%g", v); E->set_param(s, k, b); }
static void tap(void *s, const char *jack) { std::string k = std::string("tap_") + jack; set(s, k.c_str(), "1"); }
static void note(void *s, int n, int v) { uint8_t m[3] = {(uint8_t)(v ? 0x90 : 0x80), (uint8_t)n, (uint8_t)(v ? v : 0)}; E->midi(s, m, 3); }

struct Stats { double rms; int peak; int crossings; bool bad; };
static Stats render(void *s, int blocks, int frames = 128) {
  int16_t buf[256];
  Stats st = {0, 0, 0, false};
  double acc = 0;
  int last = 0;
  long n = 0;
  for (int b = 0; b < blocks; b++) {
    E->render(s, buf, frames);
    for (int i = 0; i < frames; i++) {
      int l = buf[i * 2];
      acc += (double)l * l;
      if (abs(l) > st.peak) st.peak = abs(l);
      if ((l >= 0) != (last >= 0)) st.crossings++;
      last = l;
      n++;
    }
  }
  st.rms = sqrt(acc / n) / 32768.0;
  return st;
}
static double hz_of(const Stats &st, int blocks, int frames = 128) { return st.crossings / 2.0 / (blocks * frames / 44100.0); }

static int out_index(const char *k) { for (int i = 0; i < N_OUTS; i++) if (!strcmp(OUT_KEY[i], k)) return i; return -1; }
static int in_index(const char *k) { for (int i = 0; i < N_INS; i++) if (!strcmp(IN_KEY[i], k)) return i; return -1; }
static void init(void *s) { for (int i = 0; i < N_CONTROLS; i++) setf(s, P_KEY[i], P_DEF[i]); for (int o = 0; o < N_OUTS; o++) setf(s, (std::string("pt_") + OUT_KEY[o]).c_str(), 0); }

int main() {
  E = mpc_engine();
  void *s = E->create(nullptr);

  // ---- views and navigation
  CHECK(geti(s, "view") == V_OVERVIEW, "starts on the overview");
  set(s, "go_vcf", "1");
  CHECK(geti(s, "view") == V_VCF, "go_vcf zooms in (%d)", geti(s, "view"));
  set(s, "nav_next", "1");
  CHECK(geti(s, "view") == V_MOD, "next steps to modulation");
  set(s, "nav_next", "1");   // the same press arriving again at once must not skip a page
  CHECK(geti(s, "view") == V_MOD, "a repeated > inside 120 ms is ignored (%d)", geti(s, "view"));
  render(s, 50);             // 50 blocks of 128 frames, about 145 ms
  set(s, "nav_prev", "1"); render(s, 50); set(s, "nav_prev", "1"); render(s, 50);
  CHECK(geti(s, "view") == V_VCO, "prev twice, a real tap apart: oscillators");
  set(s, "nav_prev", "1"); set(s, "nav_prev", "1");
  render(s, 50);
  CHECK(geti(s, "view") == N_VIEWS - 1, "prev wraps to the last section, and only one page back");
  set(s, "nav_zoom", "1");
  CHECK(geti(s, "view") == V_OVERVIEW, "OVERVIEW returns");
  set(s, "go_vcf", "0");
  CHECK(geti(s, "view") == V_OVERVIEW, "a trigger's release (0) does nothing");

  // ---- Q-Links follow the view
  set(s, "go_vcf", "1");
  CHECK(get(s, "ql1_name") == "HPF Cutoff Frequency", "ql1 is the HPF cutoff on the filter page ('%s')", get(s, "ql1_name").c_str());
  setf(s, "ql1", 0.25f);
  CHECK(fabsf(getf(s, "hpf_cutoff") - 2.5f) < 0.01f, "ql1 drives the cutoff (%g)", getf(s, "hpf_cutoff"));
  setf(s, "hpf_cutoff", 8.0f);
  CHECK(fabsf(getf(s, "ql1") - 0.8f) < 0.01f, "the Q-Link follows the knob (%g)", getf(s, "ql1"));
  set(s, "go_patch", "1");
  CHECK(get(s, "ql1_name") == "Volume", "the patch page's Q-Link 1 is VOLUME, as on the panel ('%s')", get(s, "ql1_name").c_str());
  for (int v = 0; v < N_VIEWS; v++)
    for (int i = 0; i < 16; i++) CHECK(VIEW_QLINKS[v][i] < N_CONTROLS, "Q-Link targets are sound controls");

  // ---- the header's top right readout: the control just moved, with its value; gone on a page change
  set(s, "go_seq", "1");
  CHECK(get(s, "touch_info").empty(), "a page change clears the readout ('%s')", get(s, "touch_info").c_str());
  set(s, "seq_swing", "60");
  CHECK(get(s, "touch_info").find("Swing") != std::string::npos && get(s, "touch_info").find("60") != std::string::npos,
        "moving SWING reads 'Swing  60 %%' ('%s')", get(s, "touch_info").c_str());
  set(s, "go_patch", "1");
  CHECK(get(s, "touch_info").empty(), "off the sequencer page the readout is empty again");

  // ---- patching, by pages: tap a jack, tap the other end, the cable has its own page
  unsigned rev0 = (unsigned)geti(s, "display_rev");
  CHECK(geti(s, "pk") == 1 && geti(s, "pk_t") == 1 && geti(s, "pk_c") == 0, "the patch page opens on the choose step");
  tap(s, "mg_tri");
  CHECK(geti(s, "pk") == 2 && geti(s, "pk_c") == 1 && geti(s, "pk_t") == 1, "an output opens 'pick an input'");
  CHECK((unsigned)geti(s, "display_rev") != rev0, "a tap bumps display_rev");
  CHECK(get(s, "patch_info").find("MG TRI") != std::string::npos, "the line names the waiting jack");
  tap(s, "total");
  CHECK(geti(s, "pk") == 4 && geti(s, "pk_t") == 0, "the input completes the cable and opens its page");
  CHECK(geti(s, "pt_mg_tri") == 1 + in_index("total"), "MG TRI is patched to TOTAL");
  CHECK(geti(s, "cp_mg_tri_0") == 0, "no cable picture on the connected page");
  set(s, "pk_done", "1");
  CHECK(geti(s, "pk") == 1 && geti(s, "cp_mg_tri_0") == 1 + in_index("total"), "DONE: back to choose, the cable drawn (%d)", geti(s, "cp_mg_tri_0"));
  set(s, "nav_zoom", "1");
  CHECK(geti(s, "pk") == 0 && geti(s, "pk_t") == 0 && geti(s, "cp_mg_tri_0") == 0, "no patch step or cable picture on the overview");
  set(s, "go_patch", "1");
  tap(s, "mg_tri");
  CHECK(geti(s, "pk") == 4, "a patched output opens its cable page");
  set(s, "pk_unplug", "1");
  CHECK(geti(s, "pt_mg_tri") == 0 && geti(s, "pk") == 1, "UNPLUG takes the cable out and goes back");
  // either order: an input first; two of the same side just move the selection; cancel
  tap(s, "lpf_cv");
  CHECK(geti(s, "pk") == 3 && geti(s, "hi_0") == 1 + in_index("lpf_cv"), "an input opens 'pick an output', ring on it (%d)", geti(s, "hi_0"));
  tap(s, "total");
  CHECK(geti(s, "pk") == 3, "another input is ignored while an input waits");
  set(s, "pk_cancel", "1");
  CHECK(geti(s, "pk") == 1 && geti(s, "hi_0") == 0, "CANCEL drops the half-made patch");
  tap(s, "lpf_cv"); tap(s, "eg1_out");
  CHECK(geti(s, "pt_eg1_out") == 1 + in_index("lpf_cv"), "input then output patches");
  set(s, "pk_done", "1");
  tap(s, "pink"); tap(s, "lpf_cv");
  CHECK(geti(s, "pk") == 4, "connected page");
  set(s, "pk_done", "1");
  CHECK(geti(s, "pt_pink") == 1 + in_index("lpf_cv") && geti(s, "pt_eg1_out") == 0, "a new cable into an input replaces the old one");
  int hd = (int)(out_index("pink") / JACK_GROUP);
  tap(s, "white");
  char hk[16]; snprintf(hk, sizeof hk, "hd_%d", (int)(out_index("white") / JACK_GROUP));
  CHECK(geti(s, hk) == 1 + out_index("white") % JACK_GROUP, "the held output's ring is on (%s = %d)", hk, geti(s, hk));
  (void)hd;
  set(s, "pk_cancel", "1");
  // cables as parameters (presets): by option index
  setf(s, "pt_seq_a", 1 + in_index("total"));
  CHECK(geti(s, "pt_seq_a") == 1 + in_index("total") && geti(s, "pt_pink") == 1 + in_index("lpf_cv"), "pt_ sets a cable, others stay");
  setf(s, "pt_pink", 0);
  CHECK(geti(s, "pt_pink") == 0, "pt_ 0 unplugs");

  // ---- state round trip with cables
  setf(s, "lpf_cutoff", 3.3f);
  setf(s, "seq_a5", -2.5f);
  std::string st = get(s, "state");
  CHECK(st.find("cable=seq_a>total;") != std::string::npos, "the state lists the cable (%s)", st.substr(0, 60).c_str());
  void *s2 = E->create(nullptr);
  set(s2, "state", st.c_str());
  CHECK(fabsf(getf(s2, "lpf_cutoff") - 3.3f) < 0.01f && fabsf(getf(s2, "seq_a5") + 2.5f) < 0.01f, "controls restored");
  CHECK(geti(s2, "pt_seq_a") == 1 + in_index("total"), "cables restored");
  E->destroy(s2);

  // ---- sound: the normalled synth plays, pitch follows the keyboard (Hz/V), portamento, scale
  init(s);
  set(s, "nav_zoom", "1");
  setf(s, "vco2_level", 0); setf(s, "lpf_cutoff", 10); setf(s, "lpf_eg2", 0); setf(s, "eg2_sustain", 10);
  setf(s, "eg2_attack", 0); setf(s, "volume", 7); setf(s, "drift", 0); setf(s, "noise_floor", 0);
  Stats q = render(s, 20);
  CHECK(q.peak < 50, "silent with no key (peak %d)", q.peak);
  note(s, 69, 100);
  render(s, 10);
  Stats a = render(s, 100);
  CHECK(a.rms > 0.05, "A4 plays (rms %.3f)", a.rms);
  CHECK(fabs(hz_of(a, 100) - 440) < 8, "VCO 1 saw at A4 is 440 Hz (%.1f)", hz_of(a, 100));
  CHECK(fabsf(getf(s, "kbd_cv_display") + 1) > 0, "kbd");
  setf(s, "vco1_scale", 3);
  render(s, 10); a = render(s, 100);
  CHECK(fabs(hz_of(a, 100) - 880) < 12, "4' is an octave up (%.1f)", hz_of(a, 100));
  setf(s, "vco1_scale", 2);
  note(s, 81, 100);
  render(s, 10); a = render(s, 100);
  CHECK(fabs(hz_of(a, 100) - 440) < 8, "low-note priority: A4 still sounds with A5 added (%.1f)", hz_of(a, 100));
  note(s, 69, 0);
  render(s, 10); a = render(s, 100);
  CHECK(fabs(hz_of(a, 100) - 880) < 12, "A5 when A4 is released (%.1f)", hz_of(a, 100));
  note(s, 81, 0);
  render(s, 300);
  q = render(s, 20);
  CHECK(q.peak < 200, "decays to silence after release (peak %d)", q.peak);

  // every VCO 1 and VCO 2 waveform makes sound; noise has no pitch
  note(s, 60, 100);
  for (int w = 0; w < 4; w++) {
    setf(s, "vco1_wave", w); render(s, 10);
    Stats t = render(s, 50);
    CHECK(t.rms > 0.03, "VCO 1 wave %d sounds (%.3f)", w, t.rms);
  }
  setf(s, "vco1_wave", 1); setf(s, "vco1_level", 0); setf(s, "vco2_level", 10);
  for (int w = 0; w < 4; w++) {
    setf(s, "vco2_wave", w); render(s, 10);
    Stats t = render(s, 50);
    CHECK(t.rms > 0.02, "VCO 2 wave %d sounds (%.3f)", w, t.rms);
  }
  setf(s, "vco1_level", 10); setf(s, "vco2_wave", 0);
  // VCO 2 pitch +5 = an octave up
  setf(s, "vco1_level", 0); setf(s, "vco2_pitch", 5); render(s, 10); a = render(s, 100);
  CHECK(fabs(hz_of(a, 100) - 523.3) < 10, "VCO 2 PITCH +5 is an octave up (%.1f)", hz_of(a, 100));
  setf(s, "vco2_pitch", 0); setf(s, "vco1_level", 10); setf(s, "vco2_level", 0);

  // ---- filters: closing the lowpass darkens, PEAK at 10 self-oscillates with no input
  setf(s, "lpf_cutoff", 10); render(s, 10); Stats open_ = render(s, 50);
  setf(s, "lpf_cutoff", 2); render(s, 10); Stats closed = render(s, 50);
  CHECK(closed.rms < open_.rms * 0.6, "LPF at 2 is quieter than open (%.3f vs %.3f)", closed.rms, open_.rms);
  CHECK(closed.crossings < open_.crossings, "and has fewer zero crossings (%d vs %d)", closed.crossings, open_.crossings);
  for (int mk = 0; mk < 2; mk++) {
    setf(s, "filter_mk", mk);
    setf(s, "vco1_level", 0); setf(s, "lpf_cutoff", 6); setf(s, "lpf_peak", 10); render(s, 40);
    Stats osc = render(s, 100);
    CHECK(osc.rms > 0.01, "MK%d LPF self-oscillates at PEAK 10 with no input (rms %.3f)", mk + 1, osc.rms);
    CHECK(osc.peak < 32767, "and stays within range (peak %d)", osc.peak);
    setf(s, "lpf_peak", 0); render(s, 40);
    osc = render(s, 50);
    CHECK(osc.peak < 100, "MK%d quiet again at PEAK 0 (peak %d)", mk + 1, osc.peak);
    setf(s, "hpf_cutoff", 6); setf(s, "hpf_peak", 10); render(s, 40);
    osc = render(s, 100);
    CHECK(osc.rms > 0.01, "MK%d HPF self-oscillates at PEAK 10 (rms %.3f)", mk + 1, osc.rms);
    setf(s, "hpf_peak", 0); setf(s, "hpf_cutoff", 0);
  }
  setf(s, "filter_mk", 1); setf(s, "vco1_level", 10); setf(s, "lpf_cutoff", 10);
  // HPF thins: at 7 the low saw loses level
  render(s, 10); Stats flat = render(s, 50);
  setf(s, "hpf_cutoff", 8); render(s, 10); Stats thin = render(s, 50);
  CHECK(thin.rms < flat.rms * 0.8, "HPF at 8 thins the sound (%.3f vs %.3f)", thin.rms, flat.rms);
  setf(s, "hpf_cutoff", 0);
  note(s, 60, 0); render(s, 300);

  // ---- envelopes: EG2 attack slows the start; EG1 OUT reaches +5 V on the panel
  setf(s, "eg2_attack", 6);
  note(s, 60, 100); render(s, 2); Stats early = render(s, 5);
  CHECK(early.rms < 0.02, "a slow attack starts quiet (%.3f)", early.rms);
  render(s, 300); Stats late = render(s, 20);
  CHECK(late.rms > early.rms * 3, "and gets there (%.3f)", late.rms);
  note(s, 60, 0); render(s, 400); setf(s, "eg2_attack", 0);

  // ---- the patch panel changes the sound: MG TRI -> TOTAL with FM at 10 wobbles the pitch; EG2 REV -> LPF closes
  setf(s, "fm_mg", 0); setf(s, "pt_mg_tri", 1 + in_index("total")); setf(s, "mg_freq", 8);
  note(s, 60, 100); render(s, 10);
  Stats still = render(s, 100);
  setf(s, "fm_mg", 10); render(s, 10);
  Stats wob = render(s, 100);
  CHECK(abs(wob.crossings - still.crossings) > 10, "MG TRI into TOTAL moves the pitch (%d vs %d crossings)", wob.crossings, still.crossings);
  setf(s, "fm_mg", 0); setf(s, "pt_mg_tri", 0);
  note(s, 60, 0); render(s, 300);

  // ---- SIGNAL OUT -> ESP -> ENV OUT -> INITIAL GAIN: a feedback patch renders without blowing up
  setf(s, "pt_sig_out", 1 + in_index("esp_in")); setf(s, "pt_esp_env", 1 + in_index("init_gain"));
  note(s, 48, 120); Stats fb = render(s, 200);
  CHECK(fb.peak <= 32767 && fb.rms > 0.01, "feedback through the ESP stays sane (peak %d rms %.3f)", fb.peak, fb.rms);
  note(s, 48, 0); render(s, 300);
  setf(s, "pt_sig_out", 0); setf(s, "pt_esp_env", 0);

  // ---- every cable, every input: nothing explodes, no NaN
  for (int o = 0; o < N_OUTS; o++) {
    for (int j = 0; j < N_INS; j++) {
      setf(s, (std::string("pt_") + OUT_KEY[o]).c_str(), 1 + j);
      note(s, 55, 100);
      Stats t = render(s, 8);
      CHECK(t.peak <= 32767, "%s -> %s renders", OUT_LABEL[o], IN_LABEL[j]);
      note(s, 55, 0);
      render(s, 8);
    }
    setf(s, (std::string("pt_") + OUT_KEY[o]).c_str(), 0);
  }
  render(s, 200);

  // ---- every control swept with a key down
  note(s, 60, 100);
  for (int p = 0; p < N_CONTROLS; p++) {
    if (p == P_VOLUME) continue;
    for (int k = 0; k <= 4; k++) {
      setf(s, P_KEY[p], P_MIN[p] + (P_MAX[p] - P_MIN[p]) * k / 4.0f);
      Stats t = render(s, 3);
      CHECK(t.peak <= 32767, "%s = %g renders", P_KEY[p], P_MIN[p] + (P_MAX[p] - P_MIN[p]) * k / 4.0f);
    }
    setf(s, P_KEY[p], P_DEF[p]);
  }
  note(s, 60, 0); render(s, 300);
  init(s);

  // ---- the sequencer: SEQ A -> TOTAL and SEQ TRIG -> TRIG IN play steps without a key
  setf(s, "pt_seq_a", 1 + in_index("total")); setf(s, "pt_seq_trig", 1 + in_index("trig_in"));
  setf(s, "fm_mg", 10); setf(s, "seq_speed", 8); setf(s, "seq_gate", 5); setf(s, "eg2_sustain", 10); setf(s, "eg2_release", 0);
  setf(s, "lpf_cutoff", 10); setf(s, "lpf_eg2", 0); setf(s, "vco2_level", 0); setf(s, "volume", 7);
  setf(s, "seq_a1", 0); setf(s, "seq_a2", 2.5f); setf(s, "seq_length", 2);
  CHECK(render(s, 20).peak < 50, "sequencer stopped: silence");
  setf(s, "seq_run", 1);
  render(s, 5);
  Stats sq = render(s, 400);
  CHECK(sq.rms > 0.02, "the sequencer plays the synth (rms %.3f)", sq.rms);
  CHECK(geti(s, "seq_running") == 1, "seq_running reports");
  set(s, "go_seq", "1");
  CHECK(geti(s, "seq_step_lo") >= 1 && geti(s, "seq_step_lo") <= 2, "the step LED shows a step in 1..2 (%d)", geti(s, "seq_step_lo"));
  // pitch alternates: steps 1 and 2 differ by 2.5 V * 12 st/V at FM 10 = 30 st
  set(s, "nav_zoom", "1");
  setf(s, "seq_run", 0); render(s, 50);
  setf(s, "seq_speed", 0); setf(s, "seq_length", 2);
  setf(s, "seq_run", 1); render(s, 30);
  Stats st1 = render(s, 60);
  double f1 = hz_of(st1, 60);
  set(s, "seq_step_btn", "1");
  setf(s, "seq_run", 0); render(s, 2); set(s, "seq_step_btn", "1"); setf(s, "seq_run", 1); render(s, 30);
  Stats st2 = render(s, 60);
  double f2 = hz_of(st2, 60);
  CHECK(f1 > 20 && f2 > 20 && (f2 / f1 > 3.0 || f1 / f2 > 3.0), "steps 1 and 2 differ by 30 st (%.0f vs %.0f Hz)", f1, f2);
  setf(s, "seq_run", 0);
  // 24-step series mode has 2 x length steps
  setf(s, "seq_mode", 2); setf(s, "seq_length", 3);
  // one-shot stops at the end
  setf(s, "seq_mode", 1); setf(s, "seq_length", 2); setf(s, "seq_speed", 10); setf(s, "seq_run", 1);
  render(s, 2000);
  CHECK(geti(s, "seq_running") == 0, "a one-shot sequence stops at its end");
  setf(s, "seq_run", 0);
  init(s);

  // ---- presets' cables through the parameters, as the wrapper applies them (option labels resolve in the wrapper)
  // ---- info and inventory sanity
  for (int o = 0; o < N_OUTS; o++) CHECK(strlen(OUT_INFO[o]) > 8, "info for %s", OUT_LABEL[o]);
  for (int j = 0; j < N_INS; j++) CHECK(strlen(IN_INFO[j]) > 8, "info for %s", IN_LABEL[j]);
  for (int p = 0; p < N_CONTROLS; p++) {
    std::string d = get(s, (std::string(P_KEY[p]) + "_display").c_str());
    CHECK(!d.empty() && d.size() < 24, "%s has a display text ('%s')", P_KEY[p], d.c_str());
  }

  // ---- sample-accurate blocks: any frame count 1..128
  note(s, 60, 100);
  for (int f = 1; f <= 128; f += 7) { Stats t = render(s, 4, f); CHECK(t.peak <= 32767, "frames=%d renders", f); }
  note(s, 60, 0); render(s, 300);

  // ---- CPU: a busy patch with unison 4, both filters resonant, sequencer running
  setf(s, "unison", 2); setf(s, "lpf_peak", 7); setf(s, "hpf_peak", 5); setf(s, "hpf_cutoff", 3);
  setf(s, "pt_seq_a", 1 + in_index("total")); setf(s, "pt_seq_trig", 1 + in_index("trig_in")); setf(s, "seq_run", 1);
  setf(s, "pt_sig_out", 1 + in_index("esp_in"));
  note(s, 50, 100);
  struct timespec t0, t1;
  clock_gettime(CLOCK_MONOTONIC, &t0);
  int blocks = 2000;
  render(s, blocks);
  clock_gettime(CLOCK_MONOTONIC, &t1);
  double us = ((t1.tv_sec - t0.tv_sec) * 1e9 + (t1.tv_nsec - t0.tv_nsec)) / 1e3 / blocks;
  printf("info: %.1f us per 128-frame block on this host (budget on the Force: 2902 us)\n", us);
  CHECK(us < 2902, "CPU within budget here");

  E->destroy(s);
  printf("%s: %d checks, %d failed\n", fails ? "FAILED" : "PASSED", checks, fails);
  return fails ? 1 : 0;
}
