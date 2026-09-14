# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Generate original sound FX + ambient BGM for the Spoke app.

All audio is synthesized from scratch (no samples, no licenses needed).
Run:  C:\\venv-hub\\venv\\Scripts\\python.exe tools\\gen_audio.py
Outputs into spoke\\assets\\audio\\.
"""

import math
import os
import random
import struct
import wave

SR = 22050
OUT = os.path.join(os.path.dirname(__file__), "..", "spoke", "assets", "audio")


def write_wav(name, samples, gain=1.0):
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = gain / peak if peak > gain else 1.0
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, s * scale))
            frames += struct.pack("<h", int(v * 32767))
        w.writeframes(bytes(frames))
    print(f"{name}: {len(samples)/SR:.2f}s  {os.path.getsize(path)/1024:.0f} KB")


def lowpass(samples, alpha):
    out = []
    y = 0.0
    for s in samples:
        y += alpha * (s - y)
        out.append(y)
    return out


def gen_dice_roll(rng):
    dur = 0.55
    n = int(SR * dur)
    buf = [0.0] * n
    for _ in range(5):
        start = rng.uniform(0.0, 0.32)
        i0 = int(start * SR)
        length = int(SR * rng.uniform(0.012, 0.03))
        k = rng.uniform(60.0, 110.0)
        for i in range(length):
            if i0 + i >= n:
                break
            t = i / SR
            buf[i0 + i] += rng.uniform(-1, 1) * math.exp(-k * t)
        thump = int(SR * 0.09)
        f = rng.uniform(70.0, 110.0)
        for i in range(thump):
            if i0 + i >= n:
                break
            t = i / SR
            buf[i0 + i] += 0.7 * math.sin(2 * math.pi * f * t) * math.exp(-30 * t)
    return lowpass(buf, 0.5)


def tone(freq, dur, k, overtone2=0.4, overtone3=0.15, attack=0.004):
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        a = min(1.0, t / attack) if attack > 0 else 1.0
        env = a * math.exp(-k * t)
        v = math.sin(2 * math.pi * freq * t)
        v += overtone2 * math.sin(2 * math.pi * freq * 2 * t)
        v += overtone3 * math.sin(2 * math.pi * freq * 3 * t)
        out.append(v * env)
    return out


def mix_at(buf, snd, at_seconds):
    i0 = int(at_seconds * SR)
    for i, s in enumerate(snd):
        if i0 + i < len(buf):
            buf[i0 + i] += s


def gen_crit():
    dur = 1.0
    buf = [0.0] * int(SR * dur)
    for idx, f in enumerate([440.0, 554.37, 659.25, 880.0]):
        note = tone(f, 0.6, 5.0, overtone2=0.35, overtone3=0.12)
        note = [v + 0.12 * math.sin(2 * math.pi * f * 1.006 * (i / SR)) for i, v in enumerate(note)]
        mix_at(buf, note, 0.0 + idx * 0.11)
    return buf


def gen_fail():
    dur = 0.75
    buf = [0.0] * int(SR * dur)
    n1 = tone(164.81, 0.32, 8.0, overtone2=0.25, overtone3=0.05)
    mix_at(buf, n1, 0.0)
    n2 = []
    f = 130.81
    for i in range(int(SR * 0.45)):
        t = i / SR
        bend = f * (1.0 - 0.04 * min(1.0, t / 0.45))
        env = math.exp(-7.0 * t)
        v = math.sin(2 * math.pi * bend * t) + 0.3 * math.sin(2 * math.pi * bend * 0.5 * t)
        n2.append(v * env)
    mix_at(buf, n2, 0.26)
    return buf


def gen_error():
    dur = 0.22
    n = int(SR * dur)
    buf = []
    for i in range(n):
        t = i / SR
        square = 1.0 if math.sin(2 * math.pi * 150 * t) >= 0 else -1.0
        buf.append(square * math.exp(-16 * t))
    return lowpass(buf, 0.35)


def gen_tap():
    dur = 0.05
    n = int(SR * dur)
    buf = []
    rng = random.Random(7)
    for i in range(n):
        t = i / SR
        click = rng.uniform(-1, 1) * math.exp(-220 * t) if t < 0.004 else 0.0
        ping = 0.5 * math.sin(2 * math.pi * 1250 * t) * math.exp(-90 * t)
        buf.append(click + ping)
    return lowpass(buf, 0.6)


def gen_bgm():
    loop = 24.0
    n = int(SR * loop)
    buf = [0.0] * n

    drone_a = round(73.42 * loop) / loop
    drone_b = round(110.0 * loop) / loop
    for i in range(n):
        t = i / SR
        lfo = 0.75 + 0.25 * math.sin(2 * math.pi * (3 / loop) * t)
        v = math.sin(2 * math.pi * drone_a * t) + 0.7 * math.sin(2 * math.pi * drone_b * t)
        buf[i] += 0.11 * lfo * v

    chords = [
        [146.83, 174.61, 220.0],
        [116.54, 146.83, 174.61],
        [174.61, 220.0, 261.63],
        [130.81, 164.81, 196.0],
    ]
    chord_len = loop / len(chords)
    fade = 0.75
    for c_idx, chord in enumerate(chords):
        c0 = c_idx * chord_len
        for i in range(int(chord_len * SR)):
            t_abs = c0 + i / SR
            idx = int(t_abs * SR)
            if idx >= n:
                break
            t_in = i / SR
            ramp_in = min(1.0, t_in / fade) if c_idx > 0 else min(1.0, t_in / fade)
            ramp_out = min(1.0, (chord_len - t_in) / fade) if c_idx < len(chords) - 1 else min(1.0, (chord_len - t_in) / fade)
            trem = 0.8 + 0.2 * math.sin(2 * math.pi * (8 / loop) * t_abs)
            v = sum(math.sin(2 * math.pi * f * t_abs) for f in chord)
            buf[idx] += 0.055 * ramp_in * ramp_out * trem * v

    rng = random.Random(20)
    pent = [293.66, 349.23, 392.0, 440.0, 523.25, 587.33]
    times = []
    t_cursor = 1.2
    while t_cursor < 17.5:
        times.append(t_cursor)
        t_cursor += rng.uniform(0.9, 2.2)
    for ts in times:
        f = rng.choice(pent)
        pluck = tone(f, 1.9, 3.2, overtone2=0.5, overtone3=0.22, attack=0.002)
        mix_at(buf, [s * rng.uniform(0.09, 0.15) for s in pluck], ts)

    rng = random.Random(33)
    hiss = [rng.uniform(-1, 1) for _ in range(n)]
    hiss = lowpass(hiss, 0.06)
    for i in range(n):
        buf[i] += 0.02 * hiss[i]

    return buf


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(42)
    write_wav("dice_roll.wav", gen_dice_roll(rng), gain=0.9)
    write_wav("dice_crit.wav", gen_crit(), gain=0.9)
    write_wav("dice_fail.wav", gen_fail(), gain=0.85)
    write_wav("error.wav", gen_error(), gain=0.55)
    write_wav("tap.wav", gen_tap(), gain=0.6)
    write_wav("bgm_tavern.wav", gen_bgm(), gain=0.5)


if __name__ == "__main__":
    main()
