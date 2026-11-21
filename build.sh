#!/usr/bin/env bash
# Build MS20XXL for MPC OS: Gen1 (armv7-a hard-float, glibc <= 2.31 so it also loads on MPC OS 2.x) and, since 0.2.0,
# Gen2 (aarch64: MPC Live III, XL, One G2, Key G2 and later, MPC OS 3.x).
#   ./build.sh                     (MPC_VST=../mpc-vst-plugins to use another framework checkout)
# Needs: python3 + Pillow, a host gcc (for shadow_art) and Zig (pip install ziglang). No Docker.
# Output: build/package/L'Cronx - VST - MS20XXL/  (skin + ms20xxl.so) and build/pluginlist-entry.xml
set -euo pipefail
cd "$(dirname "$0")"
MPC_VST="${MPC_VST:-$PWD/third_party/mpc-vst-plugins}"
ZIG="${ZIG:-python3 -m ziglang}"
NAME="L'Cronx - VST - MS20XXL"
python3 tools/gen_params.py
mkdir -p build/host build/arm build/arm64
[ -x build/host/shadow_art ] || gcc -O2 -w -I"$MPC_VST/tools/vendor/force-shadow/tools" -x c -o build/host/shadow_art "$MPC_VST/tools/shadow_art.c" -lm
rm -rf build/skin
SHADOW_TITLE_FONT="$PWD/art/fonts/TitilliumWeb-SemiBold.ttf" SHADOW_ART="$PWD/build/host/shadow_art" python3 "$MPC_VST/tools/gen_vst.py" vst.json
python3 tools/post_skin.py "build/skin/$NAME/Plugin Skins" --preview build/preview   # panel art, knobs, jacks, cables, overview
python3 tools/check_skin.py "build/skin/$NAME/Plugin Skins"   # the inventory, all of it, on the panel
SRCS=$(python3 -c "import json; print(' '.join(json.load(open('vst.json'))['build']['sources']))")
CFLAGS=$(python3 -c "import json; print(' '.join(json.load(open('vst.json'))['build']['cflags']))")
COMMON="-O2 -fPIC -fvisibility=hidden -ffunction-sections -fdata-sections -DNDEBUG -w"
# one binary per CPU: build_so <out dir> <target flags>
build_so() {
  local D="$1" TGT="$2" OBJS="" f o
  mkdir -p "$D"
  for f in $SRCS; do
    o="$D/$(echo "$f" | tr / _).o"
    $ZIG c++ $TGT $COMMON -std=gnu++11 -fno-exceptions -fno-rtti $CFLAGS -Ibuild -I"$MPC_VST/wrapper" -c "$f" -o "$o"
    OBJS="$OBJS $o"
  done
  $ZIG cc $TGT $COMMON -std=gnu11 -Ibuild -c "$MPC_VST/wrapper/vst2_wrap.c" -o "$D/vst2_wrap.o"
  printf '{\n  global: VSTPluginMain;\n  local: *;\n};\n' > "$D/exports.map"
  $ZIG c++ $TGT -shared -fPIC -Wl,--no-undefined -Wl,--version-script="$D/exports.map" -Wl,--gc-sections -Wl,-s \
    $OBJS "$D/vst2_wrap.o" -lm -ldl -lpthread -o "$D/ms20xxl.so"
}
# 32-bit: Force, MPC X, Live, Live II, One, Key 61/37
build_so build/arm "-target arm-linux-gnueabihf.2.31 -mcpu=generic+v7a+vfp3d16-d32-neon+thumb2 -ffp-contract=off"
# 0.2.0, 64-bit: MPC Live III, XL, One G2, Key G2 and later (MPC OS 3.x; Akai's plugin folder format on 3.10.1)
build_so build/arm64 "-target aarch64-linux-gnu.2.31 -mcpu=generic -ffp-contract=off"
PKG="build/package/$NAME"
rm -rf build/package && mkdir -p "$PKG"
cp -r "build/skin/$NAME/." "$PKG/"
cp build/arm/ms20xxl.so "$PKG/"
echo "-> $PKG  (+ build/arm64/ms20xxl.so for Gen2)"
