#!/usr/bin/env python3
"""Draws art/tile.png, the 270x110 picture MPC's Sounds > INSTRUMENTS browser shows for MS20XXL."""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_skin as P  # noqa: E402

im = Image.new("RGBA", (270, 110), P.PANEL + (255,))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, 269, 109], outline=(120, 120, 120), width=2)
knob = P.art("knob_big.png").resize((52, 52), Image.LANCZOS)
for i, a in enumerate((-120, -30, 60)):
    im.alpha_composite(knob.rotate(-a, resample=Image.BICUBIC), (14 + i * 58, 48))
cab, x0, y0 = P.draw_cable((196, 62), (250, 92), P.spec.CABLE_COLOURS[0], 0.8, clip=(0, 0, 270, 110))
im.alpha_composite(cab, (x0, y0))
d.text((14, 22), "MS20XXL", font=P.font(30), fill=P.INK, anchor="lm")
d.text((256, 24), "L'Cronx", font=P.font(16), fill=P.YELLOW, anchor="rm")
im.convert("RGB").save(os.path.join(P.ROOT, "art", "tile.png"))
print("tile: art/tile.png")
