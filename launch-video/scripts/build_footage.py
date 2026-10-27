"""Trim + retime the screen recordings into per-scene 30fps clips for Remotion.

Each clip is a concat of segments (recording, start, end, speed[, opts]) frozen on its last
frame (tpad) up to `total` seconds so the scene can hold on the result.

opts (per segment):
  cover    list of (x, y, w, h, t0, t1) black boxes in SOURCE pixels, burned into the clip between
           t0 and t1 SOURCE seconds (converted to segment time inside chain()). Used to hide secrets (webhook URL, API key, token).
  blur_x   blur the left `blur_x` source pixels (other people's names in a chat sidebar).
Clips with pad=True are letterboxed onto a 2880x1862 canvas so recordings of different
aspect ratios share one window shape.
"""
import glob, subprocess, sys
D = "/Users/punyasurana/Documents/Screenshot"
OUT = "/Users/punyasurana/Documents/CYPHEX_CLI/launch-video/public/footage"
KEYS = ["6.15.14", "6.18.14", "6.19.56", "6.24.56", "11.39.43", "11.44.43"]
REC = {k: sorted(glob.glob(f"{D}/Screen Recording 2026-10-27 at {k}*.mov"))[0] for k in KEYS}
W, H = 2880, 1862

# Webhook URL (with API key + token) is printed on the prompt row while typed and on its own line after.
HIDE_URL = [(430, 1990, 3026, 56, 2.85, 5.4), (0, 770, 3456, 52, 3.3, 7.0)]

CLIPS = {
    "intro":   dict(total=5.0,  segs=[("6.18.14", 13.5, 18.5, 1.0)]),
    "scan":    dict(total=8.5,  segs=[("6.18.14", 19.0, 23.9, 0.75)]),
    "swarm":   dict(total=9.0,  segs=[("6.15.14", 104.5, 113.8, 1.0)]),
    "hyp":     dict(total=10.5, segs=[("6.15.14", 34.5, 37.8, 1.0), ("6.15.14", 0.0, 26.0, 2.4)]),
    "council": dict(total=5.33, segs=[("6.19.56", 0.0, 11.3, 2.0)]),
    "genome":  dict(total=7.84, segs=[("6.24.56", 0.0, 4.6, 0.62)]),
    "arena":   dict(total=5.67, segs=[("6.24.56", 4.8, 10.4, 1.0)]),
    "patch":   dict(total=10.5, segs=[("6.24.56", 9.5, 17.5, 1.5), ("6.24.56", 28.8, 36.8, 2.2)]),
    # webhook connected in the terminal (URL + token hidden), then the Chat space says hello
    "connect": dict(total=7.5,  pad=True, segs=[("11.44.43", 0.6, 5.9, 1.3, dict(cover=HIDE_URL)),
                                               ("11.44.43", 9.2, 12.6, 1.0, dict(blur_x=830))]),
    # the Google Sheet filling with every endpoint / vulnerability, then the scan banners
    "sheet":   dict(total=6.0,  pad=True, segs=[("11.39.43", 2.0, 15.0, 2.2)]),
    # real-time Cyphex Buddy messages in the Chat space (sidebar names blurred)
    "chat":    dict(total=6.67, pad=True, segs=[("11.44.43", 38.0, 46.6, 1.3, dict(blur_x=560))]),
}

def chain(i, seg, pad):
    rec, a, b, sp = seg[:4]
    o = seg[4] if len(seg) > 4 else {}
    f = [f"[{i}:v]setpts=(PTS-STARTPTS)/{sp},fps=30"]
    for (x, y, w, h, t0, t1) in o.get("cover", []):
        f.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill:enable='between(t,{(t0 - a) / sp},{(t1 - a) / sp})'")
    base = ",".join(f)
    if "blur_x" in o:
        bx = o["blur_x"]
        base += f",split[a{i}][b{i}];[b{i}]crop={bx}:ih:0:0,boxblur=40:6[c{i}];[a{i}][c{i}]overlay=0:0"
    fit = (f",scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
           if pad else f",scale={W}:-2")
    return base + fit + f",format=yuv420p[v{i}]"

for name in (sys.argv[1:] or list(CLIPS)):
    c = CLIPS[name]
    cmd = ["ffmpeg", "-y", "-v", "error"]
    chains = []
    for i, seg in enumerate(c["segs"]):
        cmd += ["-ss", str(seg[1]), "-t", str(seg[2] - seg[1]), "-i", REC[seg[0]]]
        chains.append(chain(i, seg, c.get("pad", False)))
    n = len(c["segs"])
    cat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[c]"
    fc = ";".join(chains + [cat, f"[c]tpad=stop_mode=clone:stop_duration={c['total']},trim=duration={c['total']},setpts=PTS-STARTPTS[o]"])
    cmd += ["-filter_complex", fc, "-map", "[o]", "-an", "-c:v", "libx264", "-crf", "22", "-preset", "medium",
            "-g", "30", "-movflags", "+faststart", f"{OUT}/{name}.mp4"]
    subprocess.run(cmd, check=True)
    print("built", name)
