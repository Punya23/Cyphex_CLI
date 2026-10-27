"""Trim + retime the screen recordings into per-scene 30fps clips for Remotion.
Each clip = concat of (recording, start, end, speed) segments, then frozen on its
last frame (tpad) up to `total` seconds so the scene can hold on the result."""
import glob, subprocess, sys
D = "/Users/punyasurana/Documents/Screenshot"
OUT = "/Users/punyasurana/Documents/CYPHEX_CLI/launch-video/public/footage"
REC = {k: sorted(glob.glob(f"{D}/Screen Recording 2026-10-27 at {k}*.mov"))[0]
       for k in ["6.15.14", "6.18.14", "6.19.56", "6.24.56"]}
CLIPS = {
    "intro":   dict(total=5.5,  segs=[("6.18.14", 13.5, 19.0, 1.0)]),
    "scan":    dict(total=9.0,  segs=[("6.18.14", 19.0, 23.9, 0.75)]),
    "swarm":   dict(total=9.34, segs=[("6.15.14", 104.5, 113.8, 1.0)]),
    "hyp":     dict(total=15.0, segs=[("6.15.14", 34.5, 37.8, 1.0), ("6.15.14", 0.0, 26.0, 2.0)]),
    "council": dict(total=5.67, segs=[("6.19.56", 0.0, 11.3, 2.0)]),
    "genome":  dict(total=8.34, segs=[("6.24.56", 0.0, 4.6, 0.62)]),
    "arena":   dict(total=5.67, segs=[("6.24.56", 4.8, 10.4, 1.0)]),
    "patch":   dict(total=11.0, segs=[("6.24.56", 9.5, 17.5, 1.5), ("6.24.56", 28.8, 36.8, 2.2)]),
}
only = sys.argv[1:] or list(CLIPS)
for name in only:
    c = CLIPS[name]
    cmd = ["ffmpeg", "-y", "-v", "error"]
    chains = []
    for i, (rec, a, b, sp) in enumerate(c["segs"]):
        cmd += ["-ss", str(a), "-t", str(b - a), "-i", REC[rec]]
        chains.append(f"[{i}:v]setpts=(PTS-STARTPTS)/{sp},fps=30,scale=2880:-2,format=yuv420p[v{i}]")
    n = len(c["segs"])
    cat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[c]"
    fc = ";".join(chains + [cat, f"[c]tpad=stop_mode=clone:stop_duration={c['total']},trim=duration={c['total']},setpts=PTS-STARTPTS[o]"])
    cmd += ["-filter_complex", fc, "-map", "[o]", "-an", "-c:v", "libx264", "-crf", "22", "-preset", "medium",
            "-g", "30", "-movflags", "+faststart", f"{OUT}/{name}.mp4"]
    subprocess.run(cmd, check=True)
    print("built", name)
