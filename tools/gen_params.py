#!/usr/bin/env python3
"""Writes everything that follows from tools/spec.py:

    python3 tools/gen_params.py

  params.json        the VST parameter list for mpc-vst-plugins' gen_vst.py (index = order, append-only once shipped)
  src/param_ids.h    P_<KEY> indices and the jack tables for the engine
  layout.conf        the skin layout (one tab; every section is a when=view:<x> mode panel)
  docs/INVENTORY.md  the full control and jack list, checked against the build
  presets.json       the factory patches, cables included (tools/presets.py)
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec  # noqa: E402
import presets as PRESETS  # noqa: E402

Y0 = 86   # Force Shadow y of the plugin page's top


# ------------------------------------------------------------------------------------------------ parameters
def param_of(c):
    if c["kind"] == "knob":
        p = {"key": c["key"], "name": c["name"], "min": float(c["min"]), "max": float(c["max"]),
             "default": float(c["default"]), "dynamic_display": True}
        if c.get("int"):
            p["display"] = "int"
        if c.get("unit"):
            p["unit"] = c["unit"]
        return p
    if c["kind"] in ("toggle", "enum"):
        return {"key": c["key"], "name": c["name"], "options": c["options"], "default": c["default"]}
    if c["kind"] == "button":
        return {"key": c["key"], "name": c["name"], "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True,
                "type": "trigger"}
    raise ValueError(c)


def trigger(key, name):
    return {"key": key, "name": name, "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True, "type": "trigger"}


def build_params():
    P = [param_of(c) for c in spec.CONTROLS]
    P.append({"key": "view", "name": "View", "options": ["Overview"] + [v[2].title() for v in spec.VIEWS[1:]], "default": 0})
    # the section switches: the 16 Q-Links' names follow the section, so these ask MPC to redraw (mpc-vst-plugins #486)
    P += [dict(trigger(k, lbl), refresh_display=True) for k, lbl, _, _ in spec.NAV]
    P += [dict(trigger("go_" + v[0], "Go " + v[2].title()), refresh_display=True) for v in spec.VIEWS[1:]]
    P += [dict(trigger("tap_" + j[0], "Jack " + j[1]), refresh_display=True) for j in spec.OUTS + spec.INS]
    # the cables as parameters (settable, so a preset carries its cables): pt_<out> = which input the output feeds.
    # Not drawn on the screen (that is the cp_ pictures' job), so any number of options is fine.
    P += [{"key": "pt_" + o[0], "name": "Cable " + o[1], "options": ["-"] + [i[1] for i in spec.INS], "default": 0,
           "poll": False} for o in spec.OUTS]
    P.append({"key": "patch_info", "name": "Patch Info", "min": 0.0, "max": 0.0, "default": 0.0, "display": "string"})
    P += [{"key": "ql%d" % (i + 1), "name": "Q-Link %d" % (i + 1), "min": 0.0, "max": 1.0, "default": 0.0,
           "dynamic_name": True, "dynamic_display": True} for i in range(16)]
    # in_sec: 1 on any section page, 0 on the overview -- the header buttons show on it, one instance each
    P.append({"key": "in_sec", "name": "In Section", "options": ["Overview", "Section"], "default": 0})
    # pop_<key>: a pop-up list's open flag, owned by the engine (closed on a pick and on every page change)
    P += [{"key": "pop_" + c["key"], "name": c["name"] + " List", "options": ["Closed", "Open"], "default": 0}
          for c in spec.CONTROLS if c["kind"] == "enum" and c["widget"] == "popup"]
    # the cable and ring pictures' switches, at most JACK_GROUP + 1 positions each (spec.py)
    for o in spec.OUTS:
        for g, ins in spec.cable_groups():
            P.append({"key": "cp_%s_%d" % (o[0], g), "name": "Cable %s %d" % (o[1], g + 1),
                      "options": ["-"] + [i[1] for i in ins], "default": 0, "poll": False})
    for g, outs in enumerate(spec.groups(spec.OUTS)):
        P.append({"key": "hd_%d" % g, "name": "Held %d" % (g + 1), "options": ["-"] + [o[1] for o in outs], "default": 0})
    for g, ins in enumerate(spec.groups(spec.INS)):
        P.append({"key": "hi_%d" % g, "name": "Held In %d" % (g + 1), "options": ["-"] + [i[1] for i in ins], "default": 0})
    # patching by pages: pk is the step, pk_t / pk_c show the jack tiles / the cancel button (engine-owned)
    P.append({"key": "pk", "name": "Patch Step", "options": spec.PK_STEPS, "default": 0})
    P.append({"key": "pk_t", "name": "Patch Tiles", "options": ["Off", "On"], "default": 0})
    P.append({"key": "pk_c", "name": "Patch Cancel Shown", "options": ["Off", "On"], "default": 0})
    P += [dict(trigger(k, n), refresh_display=True) for k, n in (
        ("pk_cancel", "Patch Cancel"), ("pk_done", "Patch Done"), ("pk_unplug", "Patch Unplug"))]
    # lamps and the sequencer's step LED (engine-owned, polled)
    P.append({"key": "esp_peak", "name": "ESP Peak", "options": spec.OFF_ON, "default": 0})
    # the step lamp, split in two so each switch stays under 11 positions (the Force limit seen on pictures)
    P.append({"key": "seq_step_lo", "name": "Seq Step 1-6", "options": ["-"] + ["%d" % (i + 1) for i in range(6)], "default": 0})
    P.append({"key": "seq_step_hi", "name": "Seq Step 7-12", "options": ["-"] + ["%d" % (i + 7) for i in range(6)], "default": 0})
    P.append({"key": "seq_running", "name": "Seq Running", "options": spec.OFF_ON, "default": 0})
    keys = [p["key"] for p in P]
    assert len(keys) == len(set(keys)), "duplicate keys"
    return P


def write_params(P):
    secs = []
    for v in spec.VIEWS[1:]:
        secs.append({"label": v[2], "keys": [c["key"] for c in spec.CONTROLS if c["view"] == v[0]]})
    with open(os.path.join(ROOT, "params.json"), "w") as f:
        json.dump({"name": "MS20XXL", "params": P, "sections": secs}, f, indent=1)
        f.write("\n")


def cid(k):
    return "P_" + k.upper()


def write_header(P):
    L = ["// Generated by tools/gen_params.py from tools/spec.py -- do not edit.", "#pragma once", ""]
    for i, p in enumerate(P):
        L.append("#define %s %d" % (cid(p["key"]), i))
    L.append("#define P_COUNT %d" % len(P))

    def num(p, k, d):
        t = "%.6g" % float(p.get(k, d))
        return t + (".0f" if "." not in t and "e" not in t else "f")
    L.append("static const char *const P_KEY[P_COUNT] = {%s};" % ", ".join('"%s"' % p["key"] for p in P))
    L.append("static const char *const P_NAME[P_COUNT] = {%s};" % ", ".join('"%s"' % p["name"] for p in P))
    L.append("static const char *const P_UNIT[P_COUNT] = {%s};" % ", ".join('"%s"' % p.get("unit", "") for p in P))
    L.append("static const float P_MIN[P_COUNT] = {%s};" % ", ".join(num(p, "min", 0) for p in P))
    L.append("static const float P_MAX[P_COUNT] = {%s};" % ", ".join(
        ("%d.0f" % (len(p["options"]) - 1)) if "options" in p else num(p, "max", 1) for p in P))
    L.append("static const float P_DEF[P_COUNT] = {%s};" % ", ".join(num(p, "default", 0) for p in P))
    L.append("static const unsigned char P_NOPTS[P_COUNT] = {%s};" % ", ".join(str(len(p.get("options", []))) for p in P))
    for i, p in enumerate(P):
        if "options" in p:
            L.append("static const char *const OPTS_%d[] = {%s};" % (i, ", ".join('"%s"' % o for o in p["options"])))
    L.append("static const char *const *const P_OPT[P_COUNT] = {%s};" % ", ".join(
        ("OPTS_%d" % i) if "options" in p else "0" for i, p in enumerate(P)))
    L.append("static const unsigned char P_INT[P_COUNT] = {%s};" % ", ".join(
        "1" if p.get("display") == "int" else "0" for p in P))
    L.append("#define N_CONTROLS %d   // the sound parameters come first: indices 0..N_CONTROLS-1" % len(spec.CONTROLS))
    L.append("")
    L.append("// views (the 'view' parameter's options)")
    for i, v in enumerate(spec.VIEWS):
        L.append("#define V_%s %d" % (v[0].upper(), i))
    L.append("#define N_VIEWS %d" % len(spec.VIEWS))
    L.append("")
    L.append("// jacks: outputs O_*, inputs I_*")
    for i, o in enumerate(spec.OUTS):
        L.append("#define O_%s %d" % (o[0].upper(), i))
    L.append("#define N_OUTS %d" % len(spec.OUTS))
    for i, j in enumerate(spec.INS):
        L.append("#define I_%s %d" % (j[0].upper(), i))
    L.append("#define N_INS %d" % len(spec.INS))
    L.append("static const char *const OUT_KEY[N_OUTS] = {%s};" % ", ".join('"%s"' % o[0] for o in spec.OUTS))
    L.append("static const char *const OUT_LABEL[N_OUTS] = {%s};" % ", ".join('"%s"' % o[1] for o in spec.OUTS))
    L.append("static const char *const OUT_INFO[N_OUTS] = {%s};" % ", ".join('"%s"' % o[2] for o in spec.OUTS))
    L.append("static const char *const IN_KEY[N_INS] = {%s};" % ", ".join('"%s"' % j[0] for j in spec.INS))
    L.append("static const char *const IN_LABEL[N_INS] = {%s};" % ", ".join('"%s"' % j[1] for j in spec.INS))
    L.append("static const char *const IN_INFO[N_INS] = {%s};" % ", ".join('"%s"' % j[3] for j in spec.INS))
    vis = [p for p in P if re.match(r"cp_.*_\d+$|hd_\d+$|hi_\d+$", p["key"])]
    first = P.index(vis[0])
    assert [p["key"] for p in P[first:first + len(vis)]] == [p["key"] for p in vis], "picture switches contiguous"
    kinds, outs, grps = [], [], []
    for p in vis:
        k = p["key"]
        if k.startswith("hd_"):
            kinds.append(2); outs.append(-1); grps.append(int(k[3:]))
        elif k.startswith("hi_"):
            kinds.append(3); outs.append(-1); grps.append(int(k[3:]))
        else:
            m = re.match(r"cp_(.+)_(\d+)$", k)
            kinds.append(0); outs.append(spec.OUT_KEYS.index(m.group(1))); grps.append(int(m.group(2)))
    L.append("// cable / ring picture switches")
    L.append("#define JACK_GROUP %d" % spec.JACK_GROUP)
    L.append("#define P_VIS_FIRST %d" % first)
    L.append("#define N_VIS %d" % len(vis))
    L.append("static const unsigned char VIS_KIND[N_VIS] = {%s};" % ", ".join(map(str, kinds)))
    L.append("static const signed char VIS_OUT[N_VIS] = {%s};" % ", ".join(map(str, outs)))
    L.append("static const unsigned char VIS_GROUP[N_VIS] = {%s};" % ", ".join(map(str, grps)))
    pops = [c["key"] for c in spec.CONTROLS if c["kind"] == "enum" and c["widget"] == "popup"]
    L.append("// pop-up lists: the enum each pop_<key> opens")
    L.append("#define N_POPS %d" % len(pops))
    L.append("static const short POP_ENUM[N_POPS] = {%s};" % ", ".join(cid(k) for k in pops))
    L.append("")
    L.append("// the views' controls in Q-Link order (top row left to right, then the next): up to 16 per view, -1 = none")
    rows = []
    for v in spec.VIEWS:
        if v[0] == "overview":
            keys = spec.OVERVIEW_QLINKS
        elif v[0] == "seq":
            keys = spec.SEQ_QLINKS
        else:
            cs = [c for c in spec.CONTROLS if c["view"] == v[0]]
            cs.sort(key=lambda c: (round(c["cy"] / 60), c["cx"]))
            keys = [c["key"] for c in cs][:16]
        ids = [cid(k) for k in keys] + ["-1"] * (16 - len(keys))
        rows.append("    {%s}," % ", ".join(ids))
    L.append("static const short VIEW_QLINKS[N_VIEWS][16] = {")
    L += rows
    L.append("};")
    L.append("static const float DIV_BEATS[%d] = {%s};" % (len(spec.DIV_BEATS), ", ".join(
        "%.6ff" % b for b in spec.DIV_BEATS)))
    L.append("")
    with open(os.path.join(ROOT, "src", "param_ids.h"), "w") as f:
        f.write("\n".join(L))


# ------------------------------------------------------------------------------------------------ layout.conf
# The MS-20's own look: black panel, white print, grey knob scales; the MS-20's patch cords are yellow, and the
# accent (lit tiles, rings, the sequencer's lamps) takes the same yellow.
THEME = """scale_names=1
label_scale=1.25
theme_bg=1c1c1c
theme_panel=1c1c1c
theme_line=bdbdbd
theme_ink=f0f0f0
theme_ink_dim=c4c4c4
theme_ink_faint=777777
theme_accent=ecd626
theme_accent_hi=ffffff
theme_knob_face=141414
theme_knob_ring=3a3a3a
theme_knob_dot=f0f0f0
theme_bar=141414
theme_seg_active=ecd626
theme_seg_inactive=111111
theme_seg_active_tx=111111
theme_btn_text=f0f0f0
theme_tab_on=ecd626
theme_tab_on_tx=111111
theme_lcd=0d0d0d
theme_box=111111"""


def layout_line(c):
    v = "when=view:%d" % spec.VIEW_KEYS.index(c["view"])
    x, y = c["cx"], c["cy"] + Y0
    if c["kind"] == "knob":
        bw = 150 if c["r"] >= 46 else 118 if c["r"] >= 36 else 62
        return 'knob cx=%d cy=%d r=%d label="%s" key=%s ns=0 vs=%d bw=%d %s' % (
            x, y, c["r"], c["name"].upper(), c["key"], 24 if c["r"] >= 40 else 18, bw, v)
    if c["kind"] == "toggle":
        step = re.match(r"seq_(t|pc)\d+$", c["key"]) is not None   # the sequencer's per-step buttons are narrow
        return 'toggle cx=%d cy=%d label="%s" key=%s bw=%d ns=0 %s' % (x, y, c["name"].upper(), c["key"], 60 if step else 130, v)
    if c["kind"] == "button":
        return 'button cx=%d cy=%d label="%s" key=%s %s' % (x, y, c["name"].upper(), c["key"], v)
    if c["widget"] == "popup":
        return 'popup cx=%d cy=%d w=%d h=%d label="%s" key=%s %s' % (x, y, c["w"], c["h"], c["name"].upper(), c["key"], v)
    return 'enum_h cx=%d cy=%d sw=%d sh=%d rows=%d label="%s" key=%s %s' % (
        x, y, c["sw"], c["sh"], c["rows"], c["name"].upper(), c["key"], v)


def write_layout():
    L = ["# MS20XXL page layout. GENERATED by tools/gen_params.py from tools/spec.py -- edit spec.py, not this.",
         "# One tab; each section of the panel is a mode panel shown while 'view' is at it (the zoom). The overview",
         "# tiles, the jacks and the cables are placed and drawn by tools/post_skin.py.",
         THEME,
         "qlinks_track = " + ",".join("ql%d" % (i + 1) for i in range(16)),
         "", "[tab MS20XXL]"]
    for k, lbl, x, y in spec.NAV:   # one instance each, shown on every section page (in_sec), never swapped mid-press
        L.append('button cx=%d cy=%d label="%s" key=%s when=in_sec:1' % (x, y + Y0, lbl, k))
    for v in spec.VIEWS[1:]:
        x, y, w, h = spec.TILES[v[0]]
        L.append('button cx=%d cy=%d label="" key=go_%s when=view:0' % (x + w // 2, y + h // 2 + Y0, v[0]))
    for j in spec.OUTS + spec.INS:
        x, y, w, h = spec.pick_box(j[0])
        L.append('button cx=%d cy=%d label="" key=tap_%s when=pk_t:1' % (x + w // 2, y + h // 2 + Y0, j[0]))
    L.append('button cx=%d cy=%d label="CANCEL" key=pk_cancel when=pk_c:1' % (spec.PK_CANCEL[0], spec.PK_CANCEL[1] + Y0))
    L.append('button cx=%d cy=%d label="UNPLUG" key=pk_unplug when=pk:4' % (
        spec.PK_UNPLUG[0] + spec.PK_UNPLUG[2] // 2, spec.PK_UNPLUG[1] + spec.PK_UNPLUG[3] // 2 + Y0))
    L.append('button cx=%d cy=%d label="DONE" key=pk_done when=pk:4' % (
        spec.PK_DONE[0] + spec.PK_DONE[2] // 2, spec.PK_DONE[1] + spec.PK_DONE[3] // 2 + Y0))
    L.append('readout cx=850 cy=%d w=500 h=50 label="" key=patch_info when=view:%d' % (38 + Y0, spec.VIEW_KEYS.index('patch')))
    for c in spec.CONTROLS:
        L.append(layout_line(c))
    L.append('qlinks "MS20XXL" = ' + ",".join("ql%d" % (i + 1) for i in range(16)))
    with open(os.path.join(ROOT, "layout.conf"), "w") as f:
        f.write("\n".join(L) + "\n")


# ------------------------------------------------------------------------------------------------ inventory
def write_inventory():
    L = ["# MS20XXL inventory", "",
         "Every control and jack of the instrument, generated from `tools/spec.py` (the build checks the skin "
         "against the same list). MS-20 = on the original's panel; XXL = this plugin's addition.", "",
         "Left out, and why: the external audio input and PHONES (an MPC instrument plugin receives no audio and "
         "has one output), and the keyboard's own CV/trig sockets on the rear (MIDI does that job).", ""]
    for v in spec.VIEWS[1:]:
        cs = [c for c in spec.CONTROLS if c["view"] == v[0]]
        L += ["## " + v[1].title(), "", "| Control | Key | Range | Origin |", "|---|---|---|---|"]
        for c in cs:
            if c["kind"] == "knob":
                rng = "%g .. %g %s" % (c["min"], c["max"], c.get("unit", ""))
            elif c["kind"] == "button":
                rng = "push"
            else:
                rng = " / ".join(c["options"]) if len(c["options"]) <= 6 else "%d options" % len(c["options"])
            L.append("| %s | `%s` | %s | %s |" % (c["name"], c["key"], rng.strip(), "MS-20" if c["ms20"] else "XXL"))
        L.append("")
    L += ["## Patch panel", "", "Each output feeds one input, one cable per socket, as with real patch cords. An input "
          "with no cable uses its normalled source, as on the MS-20.", "", "### Outputs", "", "| Jack | Signal |", "|---|---|"]
    for o in spec.OUTS:
        L.append("| %s | %s |" % (o[1], o[2]))
    L += ["", "### Inputs", "", "| Jack | Unpatched | Destination |", "|---|---|---|"]
    for j in spec.INS:
        d = {None: "-", "kbd": "keyboard"}.get(j[2], dict((o[0], o[1]) for o in spec.OUTS).get(j[2], j[2]))
        L.append("| %s | %s | %s |" % (j[1], d, j[3]))
    L += ["", "%d controls, %d outputs, %d inputs." % (len(spec.CONTROLS), len(spec.OUTS), len(spec.INS)), ""]
    with open(os.path.join(ROOT, "docs", "INVENTORY.md"), "w") as f:
        f.write("\n".join(L))


# ------------------------------------------------------------------------------------------------ factory presets
# Every preset sets every sound parameter (defaults below the overrides) and every cable (pt_<out>: "-" or the input),
# so a patch always sounds the same whatever was loaded before, cables included.
def write_presets():
    out = []
    in_label = {i[0]: i[1] for i in spec.INS}
    for name, over, cables in PRESETS.PRESETS:
        vals = {}
        for c in spec.CONTROLS:
            if c["kind"] == "button":
                continue
            v = over.get(c["key"], c["default"])
            if c["kind"] in ("toggle", "enum"):
                v = c["options"][int(v)]
            vals[c["key"]] = v
        for k in over:
            assert k in spec.CTRL, "preset %s: unknown control %s" % (name, k)
        for o in spec.OUTS:
            vals["pt_" + o[0]] = in_label[cables[o[0]]] if o[0] in cables else "-"
        for o in cables:
            assert o in spec.OUT_KEYS and cables[o] in spec.IN_KEYS, "preset %s: bad cable %s" % (name, o)
        assert len(set(cables.values())) == len(cables), "preset %s: an input with two cables" % name
        out.append({"name": name, "values": vals})
    with open(os.path.join(ROOT, "presets.json"), "w") as f:
        json.dump({"presets": out}, f, indent=1)
        f.write("\n")
    return len(out)


def main():
    P = build_params()
    write_params(P)
    write_header(P)
    write_layout()
    write_inventory()
    n = write_presets()
    print("gen_params: %d parameters (%d controls), %d jacks, %d presets" % (len(P), len(spec.CONTROLS), len(spec.JACKS), n))


if __name__ == "__main__":
    main()
