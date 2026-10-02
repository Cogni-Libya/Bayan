"""Contact sheet of the stills: python sheet.py OUT.png [first last]"""
import sys, glob
from PIL import Image
fs = sorted(glob.glob('out/media/images/scenes/S*.png'))
a, b = (int(sys.argv[2]) - 1, int(sys.argv[3])) if len(sys.argv) > 3 else (0, len(fs))
ims = [Image.open(f).convert('RGB').resize((722, 500)) for f in fs[a:b]]
S = Image.new('RGB', (722 * 2, 500 * ((len(ims) + 1) // 2)))
for i, im in enumerate(ims):
    S.paste(im, ((i % 2) * 722, (i // 2) * 500))
S.save(sys.argv[1])
