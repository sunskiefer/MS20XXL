#!/usr/bin/env python3
"""Turn the generated skin into the MS20XXL panel.

    python3 tools/post_skin.py "<skin dir>/Plugin Skins" [--preview build/preview]

mpc-vst-plugins' gen_vst.py builds a working skin from layout.conf: one tab whose sections are mode panels shown while
the 'view' parameter is at them. This script then, in the built skin:
  - paints a full panel image per view in the MS-20's own look (black panel, white print, the section frames and
    titles, the knob scales 0..10) and the overview, whose tiles are each section's page in miniature, composed
    from the skin itself at the default settings;
  - redraws the knob filmstrips from LXRXXL BAZZLINE's knob pictures (big, medium, small, and the data knob for the
    stepped values), the switches, the sequencer's buttons and lamps, the navigation buttons, and makes the jack and
    overview-tile buttons transparent touch areas;
  - draws the patch panel as the MS-20's: the block diagram with its hex sockets in the panel's positions, and
    adds the cables: for every output and every input, one picture of that yellow cable, each shown only while its
    switch parameter says so (IndexedEnabling, the same mechanism as the framework's popups and mode panels):
    cp_<out>_<group>, at most 10 positions each (spec.py). The engine sets them from the patch and the view. The
    rings of the jack waiting for its other end (hd_ / hi_) work the same way.
Everything injected goes right after the background, so every control stays on top and keeps its touches.
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec  # noqa: E402

W, H = 1280, 628
FONT = os.path.join(ROOT, "art", "fonts", "TitilliumWeb-SemiBold.ttf")
ART = os.path.join(ROOT, "art", "panel")
PANEL = (28, 28, 28)
HEADER = (16, 16, 16)
LINE = (214, 214, 214)
INK = (240, 240, 240)
DIM = (178, 178, 178)
YELLOW = (236, 214, 38)
LED_OFF = (70, 52, 10)
SS = 2   # supersampling for drawn art
TAB = "MS20XXL|MS20XXL"
KNOB_SPAN = 150   # degrees each side of 12 o'clock, as the MS-20's scales

# sub-frames on the zoomed pages: (view, title, x0, y0, x1, y1), the MS-20's section boxes
FRAMES = [
    ("vco", "VOLTAGE CONTROLLED OSCILLATOR 1", 14, 84, 456, 622),
    ("vco", "VOLTAGE CONTROLLED OSCILLATOR 2", 466, 84, 898, 622),
    ("vco", "VCO MIXER", 908, 84, 1266, 622),
    ("vcf", "VOLTAGE CONTROLLED HIGHPASS FILTER", 14, 84, 626, 622),
    ("vcf", "VOLTAGE CONTROLLED LOWPASS FILTER", 636, 84, 1266, 622),
    ("mod", "FREQUENCY MODULATION", 14, 84, 436, 622),
    ("mod", "MODULATION GENERATOR", 446, 84, 906, 622),
    ("mod", "VCA  /  VELOCITY  (XXL)", 916, 84, 1266, 622),
    ("env", "ENVELOPE GENERATOR 1", 14, 84, 620, 622),
    ("env", "ENVELOPE GENERATOR 2", 630, 84, 1266, 622),
    ("esp", "EXTERNAL SIGNAL PROCESSOR", 14, 84, 1266, 622),
    ("seq", "CLOCK  /  SEQUENCE", 14, 84, 436, 622),
    ("seq", "SEQUENCER", 446, 84, 1266, 622),
    ("setup", "KEYBOARD  /  MIDI", 14, 84, 1266, 350),
    ("setup", "SAMPLE & HOLD NORMALS  /  ANALOG", 14, 360, 1266, 622),
]
# the sub-titles the original prints over groups of knobs
SUBTITLES = [
    ("vcf", "CUTOFF FREQUENCY MODULATION", 310, 352), ("vcf", "CUTOFF FREQUENCY MODULATION", 870, 352),
    ("mod", "PW MODULATION  (XXL)", 235, 352),
]


def font(size):
    return ImageFont.truetype(FONT, int(size))


def art(name):
    return Image.open(os.path.join(ART, name)).convert("RGBA")


# ------------------------------------------------------------------------------------------------ the skin's data
def load_param_keys():
    keys = []
    for line in open(os.path.join(ROOT, "build", "params.h")):
        m = re.match(r'\s*\{"([^"]+)",', line)
        if m:
            keys.append(m.group(1))
    return keys


class Skin:
    def __init__(self, folder):
        self.dir = folder
        self.path = os.path.join(folder, "TUI.json")
        self.tui = json.load(open(self.path))
        self.defs_list = self.tui["pageData"]["componentDefinitions"]["localComponentDefinitions"]
        self.defs = {d["key"]: d["value"] for d in self.defs_list}
        self.page = self.defs[TAB]
        self.keys = load_param_keys()
        self.index = {k: i for i, k in enumerate(self.keys)}
        self.params = {p["key"]: p for p in json.load(open(os.path.join(ROOT, "params.json")))["params"]}

    def param_of(self, inst):
        for m in inst["handle remapping"]["map"]:
            if m["key"] == "Data" and m["value"].startswith("Parameter "):
                return self.keys[int(m["value"].split()[1])]
        return None

    def instances(self, key):
        return [c for c in self.page["componentsData"] if self.param_of(c) == key]

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.tui, f, separators=(",", ":"))


def bounds(b):
    return [int(round(float(x))) for x in b.split()]


def bstr(x, y, w, h):
    return "%d %d %d %d" % (x, y, w, h)


def image_instance(name, img, x, y, w, h, handles):
    return {"version": 2,
            "componentData": {"version": 1, "name": name, "type": "Image",
                              "data": {"version": 2, "imageType": "Regular", "colour": "0", "image": img}},
            "handle remapping": {"version": 1, "map": []},
            "bounds": {"version": 2, "acceptsHWFocus": "No", "showWhenDataModelInvalid": "Show", "whenVisible": "Always",
                       "boundsType": "Absolute", "bounds": bstr(x, y, w, h),
                       "additionalInvalidatingHandles": handles}}


# ------------------------------------------------------------------------------------------------ art primitives
def knob_picture(R):
    """the BAZZLINE knob for a radius: big for the big ones, medium for the small ones, small for the step knobs"""
    if R >= 56:
        return art("knob_big.png")
    if R >= 40:
        return art("knob_med.png")
    return art("knob_small.png")


def write_knob_strips(skin):
    """128 frames of the knob turning -150..+150 degrees (the framework's rule: numFrames 127, frames <= 126 px)"""
    done = []
    for name in sorted(os.listdir(skin.dir)):
        m = re.match(r"sh_knob_r(\d+)\.png$", name)
        if not m:
            continue
        R = int(m.group(1))
        F = 2 * R + 10
        pic = knob_picture(R).resize((F * 2, F * 2), Image.LANCZOS)
        strip = Image.new("RGBA", (F, F * 128), (0, 0, 0, 0))
        for i in range(128):
            ang = -KNOB_SPAN + 2 * KNOB_SPAN * i / 127.0
            strip.paste(pic.rotate(-ang, resample=Image.BICUBIC).resize((F, F), Image.LANCZOS), (0, i * F))
        assert strip.size[1] <= 16128
        strip.save(os.path.join(skin.dir, name), optimize=True)
        done.append(R)
    return done


def switch_image(on, w=84, h=40):
    """an MS-20-style toggle: a dark rocker, the lit side yellow"""
    S = 4
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=5 * S, fill=(12, 12, 12, 255), outline=(150, 150, 150, 255),
                        width=S)
    kw = int(w * S * 0.48)
    x0 = w * S - kw - 3 * S if on else 3 * S
    col = YELLOW if on else (90, 90, 90)
    d.rounded_rectangle([x0, 3 * S, x0 + kw, h * S - 3 * S], radius=3 * S, fill=col + (255,))
    return im.resize((w, h), Image.LANCZOS)


def push_button_image(on, w, h, lamp=True):
    """the sequencer's square buttons (TRIGGER / PORTAMENTO C): black cap, a lamp that lights yellow"""
    S = 4
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=4 * S, fill=(14, 14, 14, 255), outline=(130, 130, 130, 255),
                        width=S)
    d.rounded_rectangle([3 * S, 3 * S, w * S - 4 * S, h * S - 4 * S], radius=3 * S, fill=(34, 34, 34, 255))
    if lamp:
        r = 6 * S
        cx, cy = w * S / 2.0, h * S / 2.0
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(YELLOW if on else LED_OFF) + (255,))
        if on:
            d.ellipse([cx - r * 2, cy - r * 2, cx + r * 2, cy + r * 2], outline=YELLOW + (70,), width=3 * S)
    return im.resize((w, h), Image.LANCZOS)


def nav_image(label, on, w, h):
    S = 4
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=8 * S, fill=(YELLOW if on else (20, 20, 20)) + (255,),
                        outline=(140, 140, 140, 255), width=2 * S)
    ink = (17, 17, 17, 255) if on else INK + (255,)
    if label in ("<", ">"):
        cx, cy, s = w * S / 2, h * S / 2, h * S * 0.26
        pts = [(cx - s * 0.6, cy - s), (cx - s * 0.6, cy + s), (cx + s * 0.8, cy)] if label == ">" else \
              [(cx + s * 0.6, cy - s), (cx + s * 0.6, cy + s), (cx - s * 0.8, cy)]
        d.polygon(pts, fill=ink)
    else:
        f = font(22 * S)
        d.text((w * S / 2, h * S / 2), label, font=f, fill=ink, anchor="mm")
    return im.resize((w, h), Image.LANCZOS)


def blank(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def tile_highlight(w, h):
    im = Image.new("RGBA", (w, h), YELLOW + (50,))
    ImageDraw.Draw(im).rectangle([0, 0, w - 1, h - 1], outline=YELLOW + (255,), width=4)
    return im


def ring_image(r=34, wdt=5):
    S = 4
    im = Image.new("RGBA", (2 * r * S, 2 * r * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([S, S, 2 * r * S - S, 2 * r * S - S], outline=YELLOW + (255,), width=wdt * S)
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


def led_image(on, r=11, colour=(255, 60, 50)):
    S = 4
    im = Image.new("RGBA", (2 * r * S, 2 * r * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, 2 * r * S - 1, 2 * r * S - 1], fill=(20, 20, 20, 255))
    col = colour + (255,) if on else tuple(int(c * 0.3) for c in colour) + (255,)
    d.ellipse([3 * S, 3 * S, 2 * r * S - 3 * S, 2 * r * S - 3 * S], fill=col)
    if on:
        d.ellipse([6 * S, 6 * S, 11 * S, 11 * S], fill=(255, 245, 220, 255))
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


# the waveform glyphs on the option tiles
def glyph(d, kind, x, y, w, h, col, S=1):
    """draws a waveform glyph into box (x, y, w, h)"""
    x0, y0, x1, y1 = x, y, x + w, y + h
    cy = (y0 + y1) / 2.0
    lw = max(2, int(2.2 * S))
    if kind == "tri":
        d.line([(x0, y1), (x0 + w * 0.25, y0), (x0 + w * 0.5, y1), (x0 + w * 0.75, y0), (x1, y1)], fill=col, width=lw, joint="curve")
    elif kind == "saw":
        d.line([(x0, y1), (x0 + w * 0.5, y0), (x0 + w * 0.5, y1), (x1, y0), (x1, y1)], fill=col, width=lw)
    elif kind == "pulse":
        d.line([(x0, y1), (x0, y0), (x0 + w * 0.2, y0), (x0 + w * 0.2, y1), (x0 + w * 0.5, y1), (x0 + w * 0.5, y0),
                (x0 + w * 0.7, y0), (x0 + w * 0.7, y1), (x1, y1)], fill=col, width=lw)
    elif kind == "square":
        d.line([(x0, y1), (x0, y0), (x0 + w * 0.25, y0), (x0 + w * 0.25, y1), (x0 + w * 0.5, y1), (x0 + w * 0.5, y0),
                (x0 + w * 0.75, y0), (x0 + w * 0.75, y1), (x1, y1)], fill=col, width=lw)
    elif kind == "noise":
        import random
        rnd = random.Random(7)
        pts = [(x0 + i * w / 14.0, y0 + rnd.random() * h) for i in range(15)]
        d.line(pts, fill=col, width=lw)
    elif kind == "ring":
        r = h * 0.45
        d.ellipse([x0 + w * 0.5 - r, cy - r, x0 + w * 0.5 + r, cy + r], outline=col, width=lw)
        d.line([(x0 + w * 0.5 - r * 0.7, cy - r * 0.7), (x0 + w * 0.5 + r * 0.7, cy + r * 0.7)], fill=col, width=lw)
        d.line([(x0 + w * 0.5 - r * 0.7, cy + r * 0.7), (x0 + w * 0.5 + r * 0.7, cy - r * 0.7)], fill=col, width=lw)


GLYPHS = {"Triangle": "tri", "Sawtooth": "saw", "Pulse": "pulse", "White Noise": "noise", "Square": "square",
          "Ring Mod": "ring"}
SHORT = {"Triangle": "TRI", "Sawtooth": "SAW", "Pulse": "PULSE", "White Noise": "NOISE", "Square": "SQUARE",
         "Ring Mod": "RING", "2 Voices": "2 VOICES", "4 Voices": "4 VOICES", "Low Note": "LOW", "High Note": "HIGH",
         "Last Note": "LAST", "Wheel Jack": "JACK", "MG Pitch": "MG PITCH", "LPF Cutoff": "LPF", "White Noise ": "WHITE",
         "Pink Noise": "PINK", "MG Tri": "MG TRI", "MG Rect": "MG RECT", "KBD Trig": "KBD TRIG", "Seq Trig": "SEQ TRIG",
         "12 Loop": "12 LOOP", "12 Once": "12 ONCE", "24 Loop": "24 LOOP", "24 Once": "24 ONCE"}


def seg_image(label, on, w, h):
    """an option tile of a rotary-switch group: black, white text; the chosen one yellow with black text"""
    S = 3
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([S, S, w * S - S - 1, h * S - S - 1], radius=5 * S, fill=(YELLOW if on else (16, 16, 16)) + (255,),
                        outline=(150, 150, 150, 255), width=S)
    ink = (17, 17, 17) if on else INK
    txt = SHORT.get(label, label).upper()
    if label in GLYPHS:
        gw = min(38 * S, int(w * S * 0.36))
        glyph(d, GLYPHS[label], 8 * S, int(h * S * 0.3), gw, int(h * S * 0.4), ink, S)
        size = 18
        while size > 15 and d.textlength(txt, font=font(size * S)) > (w - 56) * S:
            size -= 1
        d.text(((8 + gw / S + (w - 8 - gw / S) / 2.0) * S, h * S / 2.0), txt, font=font(size * S), fill=ink, anchor="mm")
    else:
        size = 19
        while size > 15 and d.textlength(txt, font=font(size * S)) > (w - 12) * S:
            size -= 1
        d.text((w * S / 2.0, h * S / 2.0), txt, font=font(size * S), fill=ink, anchor="mm")
    return im.resize((w, h), Image.LANCZOS)


def write_segments(skin, folder):
    for key, d in skin.defs.items():
        m = re.match(r"shSeg_(.+)_(\d+)$", key)
        if not m or m.group(1) not in skin.params:
            continue
        label = skin.params[m.group(1)]["options"][int(m.group(2))]
        for sub in d["componentsData"]:
            if sub["componentData"]["type"] != "Button":
                continue
            _, _, w, h = bounds(sub["bounds"]["bounds"])
            data = sub["componentData"]["data"]
            seg_image(label, True, w, h).save(os.path.join(folder, data["onImage"]))
            seg_image(label, False, w, h).save(os.path.join(folder, data["offImage"]))


# ------------------------------------------------------------------------------------------------ pop-up lists
POP_ARROW_W = 70     # the arrow box on a pop-up field's right end: tap it to open / close the list
POP_TEXT = 24


def pop_arrow_image(open_, w, h):
    S = 4
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=6 * S, fill=YELLOW + (255,) if open_ else (18, 18, 18, 255),
                        outline=(130, 130, 130, 255), width=2 * S)
    d.rectangle([0, 2 * S, 6 * S, h * S - 2 * S], fill=YELLOW + (255,) if open_ else (18, 18, 18, 255))
    d.line([0, 4 * S, 0, h * S - 4 * S], fill=(130, 130, 130, 255), width=2 * S)
    cx, cy, a = w * S / 2.0, h * S / 2.0, 11 * S
    ink = (17, 17, 17, 255) if open_ else YELLOW + (255,)
    if open_:
        d.polygon([(cx - a, cy + a * 0.55), (cx + a, cy + a * 0.55), (cx, cy - a * 0.65)], fill=ink)
    else:
        d.polygon([(cx - a, cy - a * 0.55), (cx + a, cy - a * 0.55), (cx, cy + a * 0.65)], fill=ink)
    return im.resize((w, h), Image.LANCZOS)


def pop_option_image(label, on, w, h):
    S = 2
    im = Image.new("RGBA", (w * S, h * S), YELLOW + (255,) if on else (16, 16, 16, 255))
    d = ImageDraw.Draw(im)
    size = POP_TEXT
    while size > 16 and d.textlength(label, font=font(size * S)) > (w - 16) * S:
        size -= 1
    d.text((w * S / 2.0, h * S / 2.0), label, font=font(size * S), fill=(17, 17, 17) if on else INK, anchor="mm")
    if not on:
        d.line([8 * S, h * S - 1, w * S - 8 * S, h * S - 1], fill=(48, 48, 48), width=S)
    return im.resize((w, h), Image.LANCZOS)


def fix_popups(skin, folder):
    """The framework's pop-up fields, rebuilt as in PS3100XXL 0.1.3: the list's open flag is the engine's pop_<key>,
    the field itself is a Q-Link focus on the value, the arrow box on its right opens and closes the list, and the
    options are redrawn in the panel's font at a readable size."""
    comps = skin.page["componentsData"]
    tog = next(v for k, v in skin.defs.items() if k.startswith("shToggle"))
    pops = [c for c in spec.CONTROLS if c["kind"] == "enum" and c["widget"] == "popup"]
    remap = {"Parameter %d" % skin.index[c["key"] + "__open"]: "Parameter %d" % skin.index["pop_" + c["key"]] for c in pops}
    remap_ie = {}
    for old, new in remap.items():
        remap_ie["IndexedEnabling/1/2/" + old] = "IndexedEnabling/1/2/" + new
    out = []
    for inst in comps:
        t = inst["componentData"]["type"]
        hs = inst["bounds"].get("additionalInvalidatingHandles", [])
        inst["bounds"]["additionalInvalidatingHandles"] = [remap_ie.get(h, h) for h in hs]
        for m in inst["handle remapping"]["map"]:
            if m["key"] == "Data" and m["value"] in remap and not t.startswith("shPopField"):
                m["value"] = remap[m["value"]]
        out.append(inst)
        if not t.startswith("shPopField"):
            continue
        mp = {m["key"]: m["value"] for m in inst["handle remapping"]["map"]}
        pop = remap[mp["Data"]]
        x, y, w, h = bounds(inst["bounds"]["bounds"])
        fkey = "msPopField_%dx%d" % (w, h)
        if fkey not in skin.defs:
            d = json.loads(json.dumps(skin.defs[t]))
            d["actions"] = [a for a in d["actions"] if a["onAction"] == "Mouse Down"]
            d["actions"][0]["handler"] = "Q-Link"
            for sub in d["componentsData"]:
                if sub["componentData"]["type"] == "Label":
                    sub["bounds"]["bounds"] = bstr(8, 0, w - POP_ARROW_W - 12, h)
            skin.defs_list.append({"key": fkey, "value": d})
            skin.defs[fkey] = d
        inst["componentData"]["type"] = fkey
        inst["handle remapping"]["map"] = [{"key": "Data", "value": mp["Text"]}, {"key": "Text", "value": mp["Text"]}]
        akey = "msPopArrow_%dx%d" % (POP_ARROW_W, h)
        if akey not in skin.defs:
            d = json.loads(json.dumps(tog))
            d["actions"] = [a for a in d["actions"] if a["onAction"] == "Mouse Down"]
            assert d["actions"] and d["actions"][0]["handler"] == "Q-Link", "switch template changed"
            for sub in d["componentsData"]:
                sub["bounds"]["bounds"] = bstr(0, 0, POP_ARROW_W, h)
                if sub["componentData"]["type"] == "Button":
                    sub["componentData"]["data"]["offImage"] = "ms_pop_arrow_%d_off.png" % h
                    sub["componentData"]["data"]["onImage"] = "ms_pop_arrow_%d_on.png" % h
            pop_arrow_image(False, POP_ARROW_W, h).save(os.path.join(folder, "ms_pop_arrow_%d_off.png" % h))
            pop_arrow_image(True, POP_ARROW_W, h).save(os.path.join(folder, "ms_pop_arrow_%d_on.png" % h))
            skin.defs_list.append({"key": akey, "value": d})
            skin.defs[akey] = d
        arrow = json.loads(json.dumps(inst))
        arrow["componentData"]["type"] = akey
        arrow["componentData"]["name"] = inst["componentData"]["name"] + " list"
        arrow["handle remapping"]["map"] = [{"key": "Data", "value": pop}]
        arrow["bounds"]["bounds"] = bstr(x + w - POP_ARROW_W, y, POP_ARROW_W, h)
        arrow["bounds"]["acceptsHWFocus"] = "No"
        out.append(arrow)
    comps[:] = out
    done = set()
    for key, d in skin.defs.items():
        m = re.match(r"shPopOpt_\d+_(.+)_(\d+)$", key)
        if not m:
            continue
        label = skin.params[m.group(1)]["options"][int(m.group(2))]
        for sub in d["componentsData"]:
            if sub["componentData"]["type"] != "Button":
                continue
            _, _, w, h = bounds(sub["bounds"]["bounds"])
            data = sub["componentData"]["data"]
            for name, on in ((data["onImage"], True), (data["offImage"], False)):
                if name not in done:
                    done.add(name)
                    pop_option_image(label, on, w, h).save(os.path.join(folder, name))
    left = [i for i in comps if any(m["value"] in remap for m in i["handle remapping"]["map"]) or
            any(h.split("/")[-1] in remap for h in i["bounds"].get("additionalInvalidatingHandles", []))]
    assert not left, "pop-up parts still on <key>__open: %r" % [i["componentData"]["name"] for i in left]


# ------------------------------------------------------------------------------------------------ panels
def text(d, xy, s, size, fill=INK, anchor="mm"):
    d.text((xy[0] * SS, xy[1] * SS), s, font=font(size * SS), fill=fill, anchor=anchor)


def knob_scale(d, c):
    """the MS-20's printed scale: ticks 0..10 around 300 degrees, numbered"""
    cx, cy, R = c["cx"], c["cy"], c["r"]
    lo, hi = c["min"], c["max"]
    bipolar = lo < 0 < hi
    n = 10
    for i in range(n + 1):
        a = math.radians(-KNOB_SPAN + 2 * KNOB_SPAN * i / n - 90)
        r0, r1 = R + 6, R + (14 if i in (0, 5, 10) else 10)
        d.line([((cx + math.cos(a) * r0) * SS, (cy + math.sin(a) * r0) * SS),
                ((cx + math.cos(a) * r1) * SS, (cy + math.sin(a) * r1) * SS)], fill=LINE, width=2 * SS)
        if R < 30:
            continue
        if (R >= 46 and i % 2 == 0) or (R < 46 and i in (0, 10)):
            if bipolar:
                v = lo + (hi - lo) * i / n
                lab = ("%+g" % v) if v else "0"
                if abs(hi) == 100:
                    lab = ("%+d" % v) if v else "0"
            else:
                lab = "%d" % round(lo + (hi - lo) * i / n) if hi - lo <= 12 else "%g" % (lo + (hi - lo) * i / n)
                if c["key"] == "seq_swing":
                    lab = "%d" % round(50 + 25 * i / n)
            text(d, (cx + math.cos(a) * (R + 26), cy + math.sin(a) * (R + 25)), lab, 16 if R >= 40 else 15, DIM)


def control_box(c):
    if c["kind"] == "knob":
        return c["cx"] - c["r"], c["cy"] - c["r"], 2 * c["r"], 2 * c["r"]
    if c["kind"] == "enum" and c["widget"] == "enum_h":
        per = int(math.ceil(len(c["options"]) / float(c["rows"])))
        w, h = per * c["sw"], c["rows"] * c["sh"]
        return c["cx"] - w // 2, c["cy"] - h // 2, w, h
    if c["kind"] == "enum":
        return c["cx"] - c["w"] // 2, c["cy"] - c["h"] // 2, c["w"], c["h"]
    if c["kind"] == "toggle":
        return c["cx"] - 42, c["cy"] - 20, 84, 40
    return c["cx"] - 60, c["cy"] - 20, 120, 40


def short_name(c):
    """the label printed by a control: the panel's own words, without the section prefix the parameter name carries"""
    name = c["name"].upper().replace(" (UNPATCHED)", "")
    for pre in ("VCO 1 ", "VCO 2 ", "HPF ", "LPF ", "EG1 ", "EG2 ", "MG ", "FREQ MOD ", "PW MOD ", "VCA MOD "):
        if name.startswith(pre) and c["view"] in ("vco", "vcf", "env", "mod") and name != pre.strip():
            name = name[len(pre):]
            break
    if c["key"] == "mg_mode":
        name = "MG"
    if c["key"] in ("seq_range_a", "seq_range_b", "seq_range_c"):
        name = "RANGE " + name[-1]
    if c["key"] == "seq_length":
        name = "LENGTH"
    if c["key"] == "seq_mode":
        name = "MODE"
    name = name.replace("PORTAMENTO A/B", "PORTA A/B").replace("PORTAMENTO C", "PORTA C")
    return name


def is_step_button(c):
    return c["kind"] == "toggle" and re.match(r"seq_(t|pc)\d+$", c["key"]) is not None


def page_base(title):
    im = Image.new("RGB", (W * SS, H * SS), PANEL)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W * SS, 70 * SS], fill=HEADER)
    d.line([0, 70 * SS, W * SS, 70 * SS], fill=LINE, width=2 * SS)
    text(d, (420, 36), title, 28, INK, "lm")
    return im, d


def draw_frames(d, vkey):
    for v, title, x0, y0, x1, y1 in FRAMES:
        if v != vkey:
            continue
        d.rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], outline=LINE, width=2 * SS)
        d.rectangle([x0 * SS, y0 * SS, x1 * SS, (y0 + 30) * SS], fill=(58, 58, 58))
        text(d, (x0 + 12, y0 + 15), title, 19, INK, "lm")
    for v, title, x, y in SUBTITLES:
        if v == vkey:
            text(d, (x, y), title, 17, DIM)


def view_panel(vkey, title):
    im, d = page_base(title)
    draw_frames(d, vkey)
    for c in spec.CONTROLS:
        if c["view"] != vkey:
            continue
        x, y, w, h = control_box(c)
        if c["kind"] == "knob":
            knob_scale(d, c)
            name = c["name"].upper()
            # the sequencer's step knobs are named by their row and step; keep those labels short
            if c["key"].startswith("seq_") and c["r"] == spec.STEP:
                continue
            name = short_name(c)
            ly = y + h + (40 if c["r"] >= 40 else 34)
            text(d, (c["cx"], ly), name, 18 if c["r"] >= 40 else 16)
        elif c["kind"] == "button":
            pass
        elif is_step_button(c):
            continue
        else:
            text(d, (c["cx"], y - (30 if c["kind"] == "toggle" else 20)), short_name(c), 18)
            if c["kind"] == "enum" and c["widget"] == "popup":
                d.rounded_rectangle([x * SS, y * SS, (x + w) * SS, (y + h) * SS], radius=6 * SS, fill=(18, 18, 18),
                                    outline=(130, 130, 130), width=2 * SS)
    if vkey == "seq":
        seq_panel(d)
    if vkey == "esp":
        esp_panel(d)
    if vkey == "patch":
        patch_diagram(d)
        patch_sockets(d)
    if vkey == "setup":
        text(d, (640, 596), "WHEEL: the mod wheel goes to the WHEEL jack, or straight to MG pitch depth or the LPF cutoff", 16, DIM)
    return im.resize((W, H), Image.LANCZOS)


def seq_panel(d):
    for i in range(12):
        x = spec.SEQ_X0 + i * spec.SEQ_DX
        text(d, (x, 140), "%d" % (i + 1), 17, INK)
    for row in ("a", "b", "c"):
        y = spec.SEQ_ROWS[row]
        text(d, (spec.SEQ_X0 - 42, y), row.upper(), 26, INK)
    text(d, (spec.SEQ_X0 - 42, spec.SEQ_PORTA_Y - 12), "PORTA", 15, DIM)
    text(d, (spec.SEQ_X0 - 42, spec.SEQ_PORTA_Y + 8), "C", 18, INK)
    text(d, (spec.SEQ_X0 - 42, spec.SEQ_TRIG_Y), "TRIG", 18, INK)
    d.line([(spec.SEQ_X0 - 30) * SS, 420 * SS, 1250 * SS, 420 * SS], fill=(90, 90, 90), width=2 * SS)
    d.line([(spec.SEQ_X0 - 30) * SS, 506 * SS, 1250 * SS, 506 * SS], fill=(90, 90, 90), width=2 * SS)


def esp_panel(d):
    # the signal flow printed across the page: SIGNAL IN -> AMP -> BPF -> F-V -> CV OUT ... as the patch panel shows it
    y = 440
    blocks = [("SIGNAL IN", 120), ("AMP", 300), ("BAND PASS FILTER", 530), ("F-V CONVERTER", 780), ("CV OUT", 1000)]
    for i, (lab, x) in enumerate(blocks):
        box_w = 64 + len(lab) * 9
        d.rounded_rectangle([(x - box_w / 2) * SS, (y - 22) * SS, (x + box_w / 2) * SS, (y + 22) * SS], radius=6 * SS,
                            outline=LINE, width=2 * SS)
        text(d, (x, y), lab, 17)
        if i:
            px = blocks[i - 1][1] + (64 + len(blocks[i - 1][0]) * 9) / 2
            d.line([px * SS, y * SS, (x - box_w / 2) * SS, y * SS], fill=LINE, width=2 * SS)
    text(d, (640, 520), "ENVELOPE FOLLOWER  ->  ENV OUT       THRESHOLD  ->  TRIG OUT       PEAK lamp above SIGNAL LEVEL", 17, DIM)
    text(d, (640, 560), "Patch SIGNAL OUT, a VCO or noise into SIGNAL IN on the patch panel; an MPC instrument gets no audio input.", 16, DIM)


# ------------------------------------------------------------------------------------------------ the patch panel
def hex_socket(d, x, y, r=spec.JACK_R, dim=False):
    """an MS-20 jack: hex nut, a washer, the black hole"""
    pts = [((x + r * math.cos(math.radians(60 * k + 30))) * SS, (y + r * math.sin(math.radians(60 * k + 30))) * SS)
           for k in range(6)]
    d.polygon(pts, fill=(96, 96, 96) if dim else (170, 170, 170))
    d.polygon([((x + (r - 3) * math.cos(math.radians(60 * k + 30))) * SS, (y + (r - 3) * math.sin(math.radians(60 * k + 30))) * SS)
               for k in range(6)], outline=(60, 60, 60), width=SS)
    rr = r - 6
    d.ellipse([(x - rr) * SS, (y - rr) * SS, (x + rr) * SS, (y + rr) * SS], fill=(130, 130, 130) if not dim else (70, 70, 70))
    d.ellipse([(x - 9) * SS, (y - 9) * SS, (x + 9) * SS, (y + 9) * SS], fill=(4, 4, 4))


def box(d, x, y, w, h, lines, size=16, fill=None):
    d.rounded_rectangle([(x - w / 2) * SS, (y - h / 2) * SS, (x + w / 2) * SS, (y + h / 2) * SS], radius=4 * SS,
                        outline=LINE, width=2 * SS, fill=fill)
    n = len(lines)
    for i, ln in enumerate(lines):
        text(d, (x, y + (i - (n - 1) / 2.0) * (size + 2)), ln, size)


def arrow(d, p1, p2, head=True):
    d.line([(p1[0] * SS, p1[1] * SS), (p2[0] * SS, p2[1] * SS)], fill=LINE, width=2 * SS)
    if head:
        ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        a1, a2 = ang + math.radians(150), ang - math.radians(150)
        s = 7
        d.polygon([(p2[0] * SS, p2[1] * SS), ((p2[0] + s * math.cos(a1)) * SS, (p2[1] + s * math.sin(a1)) * SS),
                   ((p2[0] + s * math.cos(a2)) * SS, (p2[1] + s * math.sin(a2)) * SS)], fill=LINE)


def patch_diagram(d):
    """the MS-20's block diagram, drawn around the sockets in their panel positions (lines first, boxes on top)"""
    C, R = spec.COLS, spec.ROWS
    y = 96
    chain = [("VCO 1", C[0]), ("VCO 2", C[1]), ("MIXER", C[2]), ("HPF", C[3]), ("LPF", C[4]), ("VCA", C[5])]
    boxes = []   # (x, y, w, h, lines, size)
    # the signal path across the top, each block dropping to its jack
    for i, (lab, x) in enumerate(chain):
        boxes.append((x, y, 76, 32, [lab], 16))
        if i:
            arrow(d, (chain[i - 1][1] + 38, y), (x - 38, y))
        d.line([x * SS, (y + 16) * SS, x * SS, (R[0] - 24) * SS], fill=LINE, width=2 * SS)
    arrow(d, (C[5] + 38, y), (C[8] - 2, y))
    d.line([C[8] * SS, y * SS, C[8] * SS, (R[0] - 24) * SS], fill=LINE, width=2 * SS)
    # MOD GEN between its two outs
    mx = (C[0] + C[1]) / 2
    arrow(d, (mx, R[1]), (C[0] + 24, R[1]))
    arrow(d, (mx, R[1]), (C[1] - 24, R[1]))
    boxes.append((mx, R[1], 62, 44, ["MOD", "GEN"], 15))
    # EG 1: out and rev out on the left, its trigger below
    ex = (C[3] + C[4]) / 2
    arrow(d, (ex, R[1]), (C[2] + 24, R[1]))
    d.line([ex * SS, R[1] * SS, ex * SS, R[2] * SS], fill=LINE, width=2 * SS)
    arrow(d, (ex, R[2]), (C[2] + 24, R[2]))
    arrow(d, (C[4] - 24, R[2]), (ex + 2, R[2]))
    boxes.append((ex, R[1], 62, 44, ["EG 1"], 16))
    # EG 2: rev out and out on the right
    ex2 = (C[4] + C[5]) / 2 - 2
    arrow(d, (ex2, R[1]), (C[5] - 24, R[1]))
    d.line([ex2 * SS, R[1] * SS, ex2 * SS, R[2] * SS], fill=LINE, width=2 * SS)
    arrow(d, (ex2, R[2]), (C[5] - 24, R[2]))
    boxes.append((ex2, R[1], 58, 44, ["EG 2"], 16))
    # KBD: CV out, trig out; its normals into VCO 1+2 CV IN and TRIG IN
    kx, ky = (C[7] + C[8]) / 2 + 8, (R[1] + R[2]) / 2
    d.line([kx * SS, ky * SS, C[8] * SS, R[1] * SS], fill=LINE, width=2 * SS)
    d.line([kx * SS, ky * SS, C[8] * SS, R[2] * SS], fill=LINE, width=2 * SS)
    arrow(d, (C[8] - 24, R[1]), (C[7] + 24, R[1]))
    arrow(d, (C[8] - 24, R[2]), (C[7] + 24, R[2]))
    boxes.append((kx, ky, 54, 32, ["KBD"], 16))
    # S&H: clock from above, in to out
    sx = (C[0] + C[1]) / 2
    d.line([C[0] * SS, (R[2] + 24) * SS, C[0] * SS, (R[3] - 24) * SS], fill=LINE, width=2 * SS)
    arrow(d, (C[0] + 24, R[3]), (sx, R[3]))
    arrow(d, (sx, R[3]), (C[1] - 24, R[3]))
    boxes.append((sx, R[3], 62, 44, ["S&H"], 16))
    # the modulation VCA: a triangle, its control from above
    vx = (C[2] + C[3]) / 2
    arrow(d, (C[2] + 24, R[3]), (vx - 18, R[3]))
    arrow(d, (vx + 18, R[3]), (C[3] - 24, R[3]))
    d.line([C[3] * SS, (R[2] + 24) * SS, vx * SS, (R[3] - 14) * SS], fill=LINE, width=2 * SS)
    d.polygon([((vx - 18) * SS, (R[3] - 20) * SS), ((vx - 18) * SS, (R[3] + 20) * SS), ((vx + 18) * SS, R[3] * SS)],
              fill=PANEL, outline=LINE, width=2 * SS)
    # noise
    nx = (C[4] + C[5]) / 2
    arrow(d, (nx, R[3]), (C[4] + 24, R[3]))
    arrow(d, (nx, R[3]), (C[5] - 24, R[3]))
    boxes.append((nx, R[3], 62, 44, ["NOISE", "GEN"], 15))
    text(d, ((C[6] + C[8]) / 2, R[3] - 56), "MANUAL CONTROL", 16, DIM)
    # the ESP row
    d.line([20 * SS, (R[4] - 54) * SS, 1260 * SS, (R[4] - 54) * SS], fill=LINE, width=2 * SS)
    text(d, (330, R[4] - 66), "EXTERNAL SIGNAL PROCESSOR", 17, INK)
    text(d, (980, R[4] - 66), "XXL OUTPUTS", 17, INK)
    ax = (C[0] + C[1]) / 2
    arrow(d, (C[0] + 24, R[4]), (ax - 16, R[4]))
    arrow(d, (ax + 16, R[4]), (C[1] - 24, R[4]))
    d.polygon([((ax - 16) * SS, (R[4] - 18) * SS), ((ax - 16) * SS, (R[4] + 18) * SS), ((ax + 16) * SS, R[4] * SS)],
              fill=PANEL, outline=LINE, width=2 * SS)
    for i, lab in ((1, ["BPF"]), (2, ["F-V"])):
        bx = (C[i] + C[i + 1]) / 2
        arrow(d, (C[i] + 24, R[4]), (bx, R[4]))
        arrow(d, (bx, R[4]), (C[i + 1] - 24, R[4]))
        boxes.append((bx, R[4], 62, 44, lab, 16))
    fx = (C[3] + C[4]) / 2
    d.line([(C[2] + 50) * SS, R[4] * SS, fx * SS, R[4] * SS], fill=LINE, width=2 * SS)
    arrow(d, (fx, R[4]), (C[4] - 24, R[4]))
    arrow(d, (C[4] + 24, R[4]), (C[5] - 24, R[4]))
    boxes.append((fx, R[4] + 28, 62, 40, ["ENV", "FOLL"], 15))
    d.line([fx * SS, (R[4] + 8) * SS, fx * SS, R[4] * SS], fill=LINE, width=2 * SS)
    # the XXL row: the sequencer
    d.line([20 * SS, (R[5] - 52) * SS, 1260 * SS, (R[5] - 52) * SS], fill=LINE, width=2 * SS)
    text(d, (760, R[5] - 64), "SEQUENCER  (SQ-10 STYLE)", 17, INK)
    text(d, (1040, R[5] - 64), "PW MOD", 17, INK)
    for x, yy, w, h, lines, size in boxes:
        box(d, x, yy, w, h, lines, size, fill=PANEL)


LEGEND = {"total": "-5V~+5V", "freq": "-5V~+5V", "ext_in": "3VPP MAX", "hpf_cv": "-5V~+5V", "lpf_cv": "-5V~+5V",
          "init_gain": "0V~+5V", "mg_tri": "+2.5V/-2.5V", "mg_rect": "+5V/0V", "eg1_out": "+5V/0V", "eg2_rev": "+5V~0V",
          "eg1_rev": "+5V~0V", "eg2_out": "0V~+5V", "kbd_cv": "HZ/V", "vco12_cv": "HZ/V", "vco2_cv": "HZ/V",
          "kbd_trig": "+5V GATE", "trig_in": "GATE", "eg1_trig": "GATE", "sh_clock": "EDGE", "vca_ctl": "0V~+5V",
          "pink": "-5V~+5V", "white": "-5V~+5V", "wheel": "0V~+5V", "mom": "+5V/0V", "esp_cv": "HZ/V", "esp_env": "0V~+5V",
          "esp_trig": "+5V GATE", "sig_out": "5VPP"}


def patch_sockets(d, dim_outs=False, dim_ins=False):
    outs = set(spec.OUT_KEYS)
    for key, (x, y) in spec.JACKS.items():
        is_out = key in outs
        lab = dict((o[0], o[1]) for o in spec.OUTS)[key] if is_out else dict((i[0], i[1]) for i in spec.INS)[key]
        dim = (dim_outs and is_out) or (dim_ins and not is_out)
        text(d, (x, y - 36), lab, 16, (120, 120, 120) if dim else (INK if is_out else YELLOW))
        hex_socket(d, x, y, dim=dim)



def pick_panel(k):
    """The patch page's steps. 1: the panel; 2: an output waits (the other outputs dim, every input lit);
    3: an input waits (the inputs dim); 4: the cable between its two sockets."""
    if k == 4:
        im, d = page_base("PATCH PANEL")
        text(d, (W // 2, 140), "CONNECTED", 44, YELLOW)
        x1, x2, y = 330, W - 330, 340
        cab, cx0, cy0 = draw_cable((x1, y), (x2, y), spec.CABLE_COLOURS[0], 2.4, clip=(0, 72, W, H))
        base = im.resize((W, H), Image.LANCZOS).convert("RGBA")
        base.alpha_composite(cab, (cx0, cy0))
        im = base.convert("RGB").resize((W * SS, H * SS), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        for x, lab in ((x1, "OUTPUT"), (x2, "INPUT")):
            hex_socket(d, x, y, r=40)
            text(d, (x, y + 84), lab, 26, DIM)
        text(d, (W // 2, 506), "UNPLUG takes the cable out.  DONE keeps it.", 24, DIM)
        return im.resize((W, H), Image.LANCZOS)
    im, d = page_base("PATCH PANEL")
    draw_frames(d, "patch")
    for c in spec.CONTROLS:
        if c["view"] == "patch":
            x, y, w, h = control_box(c)
            if c["kind"] == "knob":
                knob_scale(d, c)
                text(d, (c["cx"], y + h + 40), c["name"].upper(), 18)
            elif c["kind"] == "toggle":
                text(d, (c["cx"], y - 20), "SWITCH", 16)
    patch_diagram(d)
    patch_sockets(d, dim_outs=(k == 2), dim_ins=(k == 3))
    if k in (2, 3):
        for key, (x, y) in spec.JACKS.items():
            fit = (key in spec.IN_KEYS) if k == 2 else (key in spec.OUT_KEYS)
            if fit:
                r = 31
                d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], outline=YELLOW, width=4 * SS)
    return im.resize((W, H), Image.LANCZOS)


# ------------------------------------------------------------------------------------------------ cables
def cable_points(p1, p2, n=48, floor=1e9):
    (x1, y1), (x2, y2) = p1, p2
    dist = math.hypot(x2 - x1, y2 - y1)
    sag = 26 + 0.2 * dist
    bow = 0.0
    if abs(x2 - x1) < 0.35 * abs(y2 - y1):
        bow = (0.18 * abs(y2 - y1) + 20) * (1 if x1 < W / 2 else -1)
    low = min(max(y1, y2) + sag, floor)
    c1 = (x1 + (x2 - x1) * 0.2 + bow, low)
    c2 = (x2 - (x2 - x1) * 0.2 + bow, low)
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * x1 + b * c1[0] + c * c2[0] + e * x2, a * y1 + b * c1[1] + c * c2[1] + e * y2))
    return pts


def draw_cable(p1, p2, colour, scale=1.0, clip=(0, 0, W, H)):
    """-> (image, x, y) of the cable from p1 to p2 (page coordinates), cropped to what it covers."""
    width, outline, plug = 6.5 * scale, 10 * scale, 11 * scale
    pts = cable_points(p1, p2, floor=clip[3] + (clip[3] - max(p1[1], p2[1])) * 0.33 - 4 * outline)
    m = outline + plug + 2
    x0 = max(clip[0], int(math.floor(min(p[0] for p in pts) - m)))
    y0 = max(clip[1], int(math.floor(min(p[1] for p in pts) - m)))
    x1 = min(clip[2], int(math.ceil(max(p[0] for p in pts) + m)))
    y1 = min(clip[3], int(math.ceil(max(p[1] for p in pts) + m)))
    S = 3
    im = Image.new("RGBA", ((x1 - x0) * S, (y1 - y0) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    sp = [((x - x0) * S, (y - y0) * S) for x, y in pts]
    dark = tuple(int(v * 0.45) for v in colour)
    d.line(sp, fill=dark + (235,), width=max(1, int(outline * S)), joint="curve")
    d.line(sp, fill=colour + (240,), width=max(1, int(width * S)), joint="curve")
    hl = tuple(min(255, int(v * 1.25) + 30) for v in colour)
    d.line([(x, y - width * S * 0.22) for x, y in sp], fill=hl + (150,), width=max(1, int(width * S * 0.25)))
    for (x, y) in (sp[0], sp[-1]):   # the plugs: black MS-20 plugs with a yellow boot
        r = plug * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=(20, 20, 20, 255))
        d.ellipse([x - r * 0.72, y - r * 0.72, x + r * 0.72, y + r * 0.72], fill=colour + (255,))
        d.ellipse([x - r * 0.35, y - r * 0.55, x + r * 0.1, y - r * 0.1], fill=hl + (200,))
    im = im.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    return im, x0, y0


def tile_pieces(im, x0, y0, T):
    a = im.split()[3]
    out = []
    for gy in range((y0 // T) * T, y0 + im.size[1], T):
        for gx in range((x0 // T) * T, x0 + im.size[0], T):
            bx0, by0 = max(gx, x0) - x0, max(gy, y0) - y0
            bx1, by1 = min(gx + T, x0 + im.size[0]) - x0, min(gy + T, y0 + im.size[1]) - y0
            if bx1 <= bx0 or by1 <= by0:
                continue
            bb = a.crop((bx0, by0, bx1, by1)).getbbox()
            if not bb:
                continue
            l, t, r, b = bx0 + bb[0], by0 + bb[1], bx0 + bb[2], by0 + bb[3]
            out.append((im.crop((l, t, r, b)), x0 + l, y0 + t))
    return out


# ------------------------------------------------------------------------------------------------ compositing
class Composer:
    """Draws the page as MPC would for a given state (param key -> value index or 0..1), from the skin itself."""

    def __init__(self, skin):
        self.skin = skin
        self.cache = {}

    def img(self, name):
        if name not in self.cache:
            self.cache[name] = Image.open(os.path.join(self.skin.dir, name)).convert("RGBA")
        return self.cache[name]

    def shown(self, inst, state):
        for h in inst["bounds"]["additionalInvalidatingHandles"]:
            m = re.match(r"IndexedEnabling/(\d+)/(\d+)/Parameter (\d+)", h)
            if m and state.get(self.skin.keys[int(m.group(3))], 0) != int(m.group(1)):
                return False
        return True

    def norm(self, key, state):
        p = self.skin.params.get(key)
        if p is None:
            return 0.0
        v = state[key] if key in state else p.get("default", 0)
        if "options" in p:
            n = len(p["options"])
            return v / float(n - 1) if n > 1 else 0.0
        lo, hi = p.get("min", 0), p.get("max", 1)
        return (v - lo) / (hi - lo) if hi > lo else 0.0

    def value(self, key, state):
        p = self.skin.params.get(key)
        if key in state:
            return state[key]
        return p.get("default", 0) if p else 0

    def compose(self, state, skip_images=()):
        page = Image.new("RGBA", (W, H), PANEL + (255,))
        for inst in self.skin.page["componentsData"]:
            if not self.shown(inst, state):
                continue
            x, y, w, h = bounds(inst["bounds"]["bounds"])
            t = inst["componentData"]["type"]
            if t == "Image":
                name = inst["componentData"]["data"]["image"]
                if name and not any(name.startswith(s) for s in skip_images):
                    page.alpha_composite(self.img(name).resize((w, h)) if self.img(name).size != (w, h)
                                         else self.img(name), (x, y))
                continue
            d = self.skin.defs.get(t)
            if not d:
                continue
            key = self.skin.param_of(inst)
            for sub in d["componentsData"]:
                st = sub["componentData"]["type"]
                sx, sy, sw, sh = bounds(sub["bounds"]["bounds"])
                data = sub["componentData"].get("data", {})
                if st == "Knob" and data.get("filmStrip"):
                    strip = self.img(data["filmStrip"])
                    F = strip.size[0]
                    fr = int(round(self.norm(key, state) * 127))
                    page.alpha_composite(strip.crop((0, fr * F, F, fr * F + F)).resize((sw, sh)), (x + sx, y + sy))
                elif st == "Button":
                    if sub["bounds"].get("whenVisible") == "WhenFocussed":
                        continue
                    n = data.get("numButtonsInGroup", 1)
                    v = self.value(key, state)
                    on = (int(round(v)) == data.get("buttonId", 0)) if n > 1 else bool(round(v)) and not \
                        (self.skin.params.get(key, {}).get("momentary"))
                    name = data.get("onImage") if on else data.get("offImage")
                    if name:
                        im = self.img(name)
                        page.alpha_composite(im.resize((sw, sh)) if im.size != (sw, sh) else im, (x + sx, y + sy))
                elif st == "Image" and data.get("image"):
                    page.alpha_composite(self.img(data["image"]).resize((sw, sh)), (x + sx, y + sy))
        return page


# ------------------------------------------------------------------------------------------------ main
def main():
    folder = sys.argv[1]
    preview = None
    if "--preview" in sys.argv:
        preview = sys.argv[sys.argv.index("--preview") + 1]
    skin = Skin(folder)
    vidx = skin.index["view"]
    nviews = len(spec.VIEWS)
    comps = skin.page["componentsData"]

    # 1) drop the framework's per-mode backgrounds, keep the plain base
    comps[:] = [c for c in comps if not (c["componentData"]["type"] == "Image" and
                                         c["componentData"]["data"].get("image", "").startswith("sh_mode_"))]
    for name in os.listdir(folder):
        if name.startswith("sh_mode_"):
            os.remove(os.path.join(folder, name))
    Image.new("RGB", (W, H), PANEL).save(os.path.join(folder, "sh_bg_0.png"))

    # 2) knobs, switches, option tiles, buttons
    radii = write_knob_strips(skin)
    for key, d in skin.defs.items():   # the value under the knob, below the printed scale's end numbers
        if key.startswith("shKnob"):
            for sub in d["componentsData"]:
                x, y, w, h = bounds(sub["bounds"]["bounds"])
                if sub["componentData"]["type"] == "Label":
                    sub["bounds"]["bounds"] = bstr(x, y + 22, w, h)
                elif sub["componentData"]["type"] == "Focus":
                    sub["bounds"]["bounds"] = bstr(x, y, w, h + 22)
    for inst in comps:
        if inst["componentData"]["type"].startswith("shKnob"):
            x, y, w, h = bounds(inst["bounds"]["bounds"])
            inst["bounds"]["bounds"] = bstr(x, y, w, h + 22)
    write_segments(skin, folder)
    step_keys = {c["key"] for c in spec.CONTROLS if is_step_button(c)}
    switch_image(True).save(os.path.join(folder, "ms_switch_on.png"))
    switch_image(False).save(os.path.join(folder, "ms_switch_off.png"))
    push_button_image(True, 52, 40).save(os.path.join(folder, "ms_push_on.png"))
    push_button_image(False, 52, 40).save(os.path.join(folder, "ms_push_off.png"))
    for key, d in skin.defs.items():
        if key.startswith("shToggle"):
            d["componentsData"] = [s for s in d["componentsData"] if s["componentData"]["type"] != "Label"]
            narrow = "bw60" in key
            for s in d["componentsData"]:
                if s["componentData"]["type"] == "Focus":
                    s["bounds"]["bounds"] = bstr(0, 0, 60, 48) if narrow else bstr(0, 0, 130, 48)
                if s["componentData"]["type"] == "Button":
                    s["bounds"]["bounds"] = bstr(4, 4, 52, 40) if narrow else bstr(23, 4, 84, 40)
                    s["componentData"]["data"]["onImage"] = "ms_push_on.png" if narrow else "ms_switch_on.png"
                    s["componentData"]["data"]["offImage"] = "ms_push_off.png" if narrow else "ms_switch_off.png"
    for c in spec.CONTROLS:
        if c["kind"] == "toggle":
            for inst in skin.instances(c["key"]):
                if c["key"] in step_keys:
                    inst["bounds"]["bounds"] = bstr(c["cx"] - 30, c["cy"] - 24, 60, 48)
                else:
                    inst["bounds"]["bounds"] = bstr(c["cx"] - 65, c["cy"] - 24, 130, 48)

    def restyle_trigger(prefix, w, h, off_img, on_img, place):
        for key, d in skin.defs.items():
            if not key.startswith(prefix):
                continue
            d["componentsData"] = [s for s in d["componentsData"] if s["componentData"]["type"] != "Label"]
            for s in d["componentsData"]:
                s["bounds"]["bounds"] = bstr(0, 0, w, h)
                if s["componentData"]["type"] == "Button":
                    s["componentData"]["data"]["offImage"] = off_img
                    s["componentData"]["data"]["onImage"] = on_img
        for inst in comps:
            if inst["componentData"]["type"].startswith(prefix):
                inst["bounds"]["bounds"] = bstr(*place(inst))

    navpos = {k: (x, y) for k, _, x, y in spec.NAV}
    navsize = {"nav_zoom": (150, 52), "nav_prev": (90, 52), "nav_next": (90, 52)}
    for k, lbl, _, _ in spec.NAV:
        w, h = navsize[k]
        nav_image(lbl, False, w, h).save(os.path.join(folder, "ms_%s_off.png" % k))
        nav_image(lbl, True, w, h).save(os.path.join(folder, "ms_%s_on.png" % k))
        restyle_trigger("shTrig_%s_" % k, w, h, "ms_%s_off.png" % k, "ms_%s_on.png" % k,
                        lambda inst, k=k, w=w, h=h: (navpos[k][0] - w // 2, navpos[k][1] - h // 2, w, h))
    st = spec.CTRL["seq_step_btn"]
    nav_image("STEP", False, 120, 52).save(os.path.join(folder, "ms_step_off.png"))
    nav_image("STEP", True, 120, 52).save(os.path.join(folder, "ms_step_on.png"))
    restyle_trigger("shTrig_seq_step_btn_", 120, 52, "ms_step_off.png", "ms_step_on.png",
                    lambda inst: (st["cx"] - 60, st["cy"] - 26, 120, 52))
    blank(4, 4).save(os.path.join(folder, "ms_blank.png"))
    pr = Image.new("RGBA", (spec.PICK_W, spec.PICK_H), (0, 0, 0, 0))
    pr.alpha_composite(ring_image(34), ((spec.PICK_W - 68) // 2, (spec.PICK_H - 68) // 2 - 2))
    pr.save(os.path.join(folder, "ms_pick_on.png"))
    for j in spec.OUTS + spec.INS:
        bx, by, bw, bh = spec.pick_box(j[0])
        restyle_trigger("shTrig_tap_%s_" % j[0], bw, bh, "ms_blank.png", "ms_pick_on.png",
                        lambda inst, bx=bx, by=by, bw=bw, bh=bh: (bx, by, bw, bh))
    for key, label, bx in (("pk_cancel", "CANCEL", (spec.PK_CANCEL[0] - 80, spec.PK_CANCEL[1] - 26, 160, 52)),
                           ("pk_unplug", "UNPLUG", spec.PK_UNPLUG), ("pk_done", "DONE", spec.PK_DONE)):
        nav_image(label, False, bx[2], bx[3]).save(os.path.join(folder, "ms_%s_off.png" % key))
        nav_image(label, True, bx[2], bx[3]).save(os.path.join(folder, "ms_%s_on.png" % key))
        restyle_trigger("shTrig_%s_" % key, bx[2], bx[3], "ms_%s_off.png" % key, "ms_%s_on.png" % key,
                        lambda inst, bx=bx: bx)
    for v in spec.VIEWS[1:]:
        tx, ty, tw, th = spec.TILES[v[0]]
        tile_highlight(tw, th).save(os.path.join(folder, "ms_tile_on_%s.png" % v[0]))
        restyle_trigger("shTrig_go_%s_" % v[0], tw, th, "ms_blank.png", "ms_tile_on_%s.png" % v[0],
                        lambda inst, tx=tx, ty=ty, tw=tw, th=th: (tx, ty, tw, th))

    fix_popups(skin, folder)

    # 3) view panels and the patch steps (drawn after the controls are final, so the overview can compose them)
    injected = []
    for i, v in enumerate(spec.VIEWS):
        if i == 0:
            continue
        (view_panel(v[0], v[1]) if v[0] != "patch" else pick_panel(1)).save(os.path.join(folder, "ms_view_%d.png" % i))
        injected.append(image_instance("Panel", "ms_view_%d.png" % i, 0, 0, W, H,
                                       ["IndexedEnabling/%d/%d/Parameter %d" % (i, nviews, vidx)]))
    pk_idx = skin.index["pk"]
    for k in range(2, len(spec.PK_STEPS)):   # step 1 is the plain patch panel (the view's own picture)
        pick_panel(k).save(os.path.join(folder, "ms_pick_%d.png" % k))
        injected.append(image_instance("Panel", "ms_pick_%d.png" % k, 0, 0, W, H,
                                       ["IndexedEnabling/%d/%d/Parameter %d" % (k, len(spec.PK_STEPS), pk_idx)]))
    # lamps: the ESP PEAK lamp, the sequencer's step lamps and RUN lamp
    led_image(False).save(os.path.join(folder, "ms_led_off.png"))
    led_image(True).save(os.path.join(folder, "ms_led_on.png"))
    led_image(False, colour=YELLOW).save(os.path.join(folder, "ms_yled_off.png"))
    led_image(True, colour=YELLOW).save(os.path.join(folder, "ms_yled_on.png"))
    el = spec.CTRL["esp_level"]
    led_xy = (el["cx"] + 90, el["cy"] - 90)
    ei = spec.VIEW_KEYS.index("esp")
    injected.append(image_instance("LED", "ms_led_off.png", led_xy[0] - 11, led_xy[1] - 11, 22, 22,
                                   ["IndexedEnabling/%d/%d/Parameter %d" % (ei, nviews, vidx)]))
    injected.append(image_instance("LED", "ms_led_on.png", led_xy[0] - 11, led_xy[1] - 11, 22, 22,
                                   ["IndexedEnabling/1/2/Parameter %d" % skin.index["esp_peak"]]))
    si = spec.VIEW_KEYS.index("seq")
    for i in range(12):
        x = spec.SEQ_X0 + i * spec.SEQ_DX
        y = spec.SEQ_ROWS["a"] - 66   # the step lamps, above the step numbers
        injected.append(image_instance("LED", "ms_yled_off.png", x - 9, y - 9, 18, 18,
                                       ["IndexedEnabling/%d/%d/Parameter %d" % (si, nviews, vidx)]))
        key = "seq_step_lo" if i < 6 else "seq_step_hi"
        injected.append(image_instance("LED", "ms_yled_on.png", x - 9, y - 9, 18, 18,
                                       ["IndexedEnabling/%d/7/Parameter %d" % (1 + i % 6, skin.index[key])]))
    rn = spec.CTRL["seq_run"]
    injected.append(image_instance("LED", "ms_yled_off.png", rn["cx"] + 76 - 11, rn["cy"] - 11, 22, 22,
                                   ["IndexedEnabling/%d/%d/Parameter %d" % (si, nviews, vidx)]))
    injected.append(image_instance("LED", "ms_yled_on.png", rn["cx"] + 76 - 11, rn["cy"] - 11, 22, 22,
                                   ["IndexedEnabling/1/2/Parameter %d" % skin.index["seq_running"]]))
    comps[1:1] = injected   # right after the base background: under every control

    # the overview: each tile is its page in miniature, composed from the skin at the default settings
    composer = Composer(skin)
    ov = Image.new("RGB", (W * SS, H * SS), PANEL)
    d = ImageDraw.Draw(ov)
    d.rectangle([0, 0, W * SS, 70 * SS], fill=HEADER)
    d.line([0, 70 * SS, W * SS, 70 * SS], fill=LINE, width=2 * SS)
    text(d, (24, 36), "MS20XXL", 34, INK, "lm")
    text(d, (224, 38), "SEMI-MODULAR SYNTHESIZER  +  STEP SEQUENCER", 20, DIM, "lm")
    text(d, (1262, 36), "TAP A SECTION TO ZOOM IN", 20, DIM, "rm")
    ov = ov.resize((W, H), Image.LANCZOS)
    for i, v in enumerate(spec.VIEWS):
        if i == 0:
            continue
        tx, ty, tw, th = spec.TILES[v[0]]
        page = composer.compose({"view": i, "pk": 1 if v[0] == "patch" else 0}, skip_images=("ms_led_on", "ms_yled_on")).convert("RGB")
        thumb = page.crop((0, 72, W, H))
        band = 28
        s = min((tw - 4) / float(thumb.size[0]), (th - band - 2) / float(thumb.size[1]))
        tim = thumb.resize((max(1, int(thumb.size[0] * s)), max(1, int(thumb.size[1] * s))), Image.LANCZOS)
        ov.paste(tim, (tx + (tw - tim.size[0]) // 2, ty + band + (th - band - tim.size[1]) // 2))
        dd = ImageDraw.Draw(ov)
        dd.rectangle([tx, ty, tx + tw - 1, ty + th - 1], outline=(130, 130, 130), width=2)
        dd.rectangle([tx + 2, ty + 2, tx + tw - 3, ty + 27], fill=HEADER)
        dd.text((tx + 10, ty + 14), v[2], font=font(18), fill=YELLOW, anchor="lm")
    sx, sy, sw, sh = spec.TILES["setup"]
    dd = ImageDraw.Draw(ov)
    bx = sx + sw + 6
    dd.rectangle([bx, sy, W - 2, sy + sh - 1], fill=HEADER, outline=(130, 130, 130), width=2)
    dd.text(((bx + W) // 2, sy + 42), "L'Cronx", font=font(30), fill=INK, anchor="mm")
    dd.text(((bx + W) // 2, sy + 84), "after the Korg MS-20 and SQ-10", font=font(18), fill=DIM, anchor="mm")
    tx, ty, tw, th = spec.TILES["patch"]
    hx = tx + tw + 30
    lines = ["Tap a section to work on it.", "OVERVIEW comes back here,", "< > step through the sections.", "",
             "PATCH PANEL: tap a jack, then", "the other end, to patch.", "A patched jack shows its cable.",
             "Presets load their cables too.", "Q-Links follow the section", "on screen."]
    for k, ln in enumerate(lines):
        dd.text((hx, ty + 16 + k * 27), ln, font=font(21), fill=DIM, anchor="lm")
    ov.save(os.path.join(folder, "ms_view_0.png"))
    comps.insert(1, image_instance("Panel", "ms_view_0.png", 0, 0, W, H,
                                   ["IndexedEnabling/0/%d/Parameter %d" % (nviews, vidx)]))

    # 4) the patched cables, drawn on the patch panel (transparent pictures, one per output and input, each switched
    # by a small parameter: spec.cable_param, at most JACK_GROUP + 1 positions). Shown on the patch steps 1-3; the
    # connected page (4) has its own cable.
    pos = dict(spec.JACKS)
    cable_insts, pieces, total_px = [], 0, 0
    for oi, o in enumerate(spec.OUTS):
        colour = spec.CABLE_COLOURS[oi % len(spec.CABLE_COLOURS)]
        for j in spec.INS:
            key, opt, nopt = spec.cable_param(o, j)
            im, x0, y0 = draw_cable(pos[o[0]], pos[j[0]], colour, 1.0, clip=(0, 72, W, H))
            handle = ["IndexedEnabling/%d/%d/Parameter %d" % (opt, nopt, skin.index[key])]
            for k, (piece, px, py) in enumerate(tile_pieces(im, x0, y0, spec.CABLE_TILE)):
                name = "ms_cab_%s_%s_%d.png" % (o[0], j[0], k)
                piece.save(os.path.join(folder, name), optimize=True)
                total_px += piece.size[0] * piece.size[1]
                pieces += 1
                cable_insts.append(image_instance("Cable", name, px, py, piece.size[0], piece.size[1], handle))
    at = 1 + len(injected) + 1
    comps[at:at] = cable_insts
    skin.save()

    print("post_skin: %d views, knob radii %s, %d cable pieces (%.1f MB decoded), %d components" % (
        nviews, radii, pieces, total_px * 4 / 1e6, len(comps)))

    if preview:
        os.makedirs(preview, exist_ok=True)
        for i, v in enumerate(spec.VIEWS):
            st = {"view": i, "in_sec": 1 if i else 0, "pk": 1 if v[0] == "patch" else 0, "pk_t": 1 if v[0] == "patch" else 0}
            composer.compose(st).convert("RGB").save(os.path.join(preview, "view_%02d_%s.png" % (i, v[0])))
        for k in range(1, len(spec.PK_STEPS)):
            composer.compose({"view": spec.VIEW_KEYS.index("patch"), "in_sec": 1, "pk": k, "pk_t": 1 if k < 4 else 0,
                              "pk_c": 1 if 1 < k < 4 else 0, "cp_mg_tri_0": 1, "cp_eg1_out_0": 5, "cp_seq_a_0": 1,
                              "cp_kbd_trig_1": 5}).convert("RGB").save(os.path.join(preview, "pick_%d.png" % k))


if __name__ == "__main__":
    main()
