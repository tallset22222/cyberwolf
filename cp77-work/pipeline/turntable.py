#!/usr/bin/env python3
"""Rotating preview (animated GIF) of an exported .glb, rendered from the file with its own skins and materials."""
import io, os, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_preview import world_triangles, draw

path = sys.argv[1]; frames = int(sys.argv[2]) if len(sys.argv) > 2 else 16
T, C = world_triangles(path)
C = C if (C != 0.8).any() else None
c = T.reshape(-1, 3).mean(0)
lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
r = max(hi[0] - lo[0], hi[2] - lo[2]) * 0.6
imgs = []
for k in range(frames):
    a = 2 * np.pi * k / frames
    Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    Tk = (T - c) @ Ry.T
    fig, ax = plt.subplots(figsize=(3.2, 5), dpi=90)
    draw(ax, Tk, 0, 1, 2, '', C=C)
    ax.set_xlim(-r, r); ax.set_ylim(lo[1] - c[1], hi[1] - c[1]); ax.axis('off')
    fig.tight_layout(pad=0.1); buf = io.BytesIO(); fig.savefig(buf, format='png'); plt.close(fig)
    imgs.append(Image.open(buf).convert('P', palette=Image.ADAPTIVE))
out = path[:-4] + '.turntable.gif'
imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=180, loop=0)
print(out, frames, 'frames')
