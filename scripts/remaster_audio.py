#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鸟鸣录音重制：两遍 loudnorm（先测后压）+ 可选带限，输出 44.1kHz/单声道/112k。

为什么不用一遍 loudnorm：单遍是动态模式，对峰值因数高的野外录音会低估响度，
经常给出比目标低 5dB 的结果；而改用 alimiter 手动补增益时，alimiter 的
level 选项默认会把输出自动拉到 0dBFS，反而制造削波。两遍才是对的。

用法:
  python3 scripts/remaster_audio.py 输入 输出.mp3 [--hp 250] [--lp 4200]
                                      [--i -16] [--tp -1.5] [--max 19]
只给低频鸟（鸽、鸠、鸮）用 --lp；鸣唱类不要低通，会把泛音削光。
"""
import argparse
import json
import os
import re
import subprocess
import sys

FF = "/var/tmp/birdtools/ff"
FFPROBE = "/var/tmp/birdtools/ffprobe"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def measure_levels(src, pre):
    """第一遍：只测，不写文件。"""
    af = pre + "loudnorm=I=-16:TP=-1.5:print_format=json"
    r = run([FF, "-hide_banner", "-i", src, "-af", af, "-f", "null", "-"])
    tail = r.stderr[r.stderr.rfind("{"):]
    d = json.loads(tail)
    return {
        "input_i": d["input_i"],
        "input_tp": d["input_tp"],
        "input_lra": d["input_lra"],
        "input_thresh": d["input_thresh"],
        "offset": d["target_offset"],
    }


def snr(path):
    """解码后按 50ms 分帧，用 p90-p10 估信噪比。"""
    import wave
    import math
    from array import array
    tmp = "/var/tmp/_rm_probe.wav"
    if os.path.exists(tmp):
        os.remove(tmp)
    run(["afconvert", "-f", "WAVE", "-d", "LEI16", "-c", "1", path, tmp])
    with wave.open(tmp, "rb") as w:
        sr = w.getframerate()
        a = array("h")
        a.frombytes(w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        a.byteswap()
    step = int(sr * 0.05)
    fr = []
    for i in range(0, len(a) - step + 1, step):
        s = 0
        for v in a[i:i + step]:
            s += v * v
        fr.append(math.sqrt(s / step) / 32768.0)
    fr.sort()
    db = lambda x: 20 * math.log10(max(x, 1e-9))
    peak = max(max(a), -min(a)) / 32768.0
    return db(fr[min(len(fr) - 1, int(len(fr) * 0.9))]) - db(fr[int(len(fr) * 0.1)]), db(peak)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--hp", type=int, default=0, help="高通截止频率，Hz")
    ap.add_argument("--lp", type=int, default=0, help="低通截止频率，Hz")
    ap.add_argument("--i", type=float, default=-16.0, help="目标整体响度 LUFS")
    ap.add_argument("--tp", type=float, default=-1.5, help="真实峰值上限 dBTP")
    ap.add_argument("--max", type=float, default=0, help="最长保留秒数，0 为不限")
    ap.add_argument("--trim", type=float, default=0.2, help="开头静音切除阈值时长")
    a = ap.parse_args()

    pre = "silenceremove=start_periods=1:start_silence=%s:start_threshold=-45dB," % a.trim
    if a.hp:
        pre += "highpass=f=%d:poles=2," % a.hp
    if a.lp:
        pre += "lowpass=f=%d:poles=2," % a.lp

    before = snr(a.src)
    m = measure_levels(a.src, pre)
    ln = ("loudnorm=I=%s:TP=%s:LRA=11:linear=true"
          ":measured_I=%s:measured_TP=%s:measured_LRA=%s"
          ":measured_thresh=%s:offset=%s" % (
              a.i, a.tp, m["input_i"], m["input_tp"], m["input_lra"],
              m["input_thresh"], m["offset"]))

    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error", "-i", a.src,
           "-af", pre + ln, "-ac", "1", "-ar", "44100", "-b:a", "112k"]
    if a.max:
        cmd += ["-t", str(a.max)]
    cmd.append(a.dst)
    r = run(cmd)
    if r.returncode:
        print("失败:", r.stderr[:300])
        return 1

    after = snr(a.dst)
    print("源 %s → %s" % (a.src, a.dst))
    print("  SNR  %5.1f dB → %5.1f dB" % (before[0], after[0]))
    print("  峰值 %5.1f dB → %5.1f dB" % (before[1], after[1]))
    print("  体积 %.0f KB" % (os.path.getsize(a.dst) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
