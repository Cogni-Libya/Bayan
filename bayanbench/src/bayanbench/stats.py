"""Rates and means with 95% intervals from a cluster bootstrap over documents: sentences from one document tend to pass
or fail together, so resampling sentences would give intervals that are too narrow (Miller 2024)."""
import collections
import random


def ci(xs, n=2000, scale=100):
    """(mean, low, high) times scale for xs = [(document, value)], value a bool (a rate: scale 100 gives %) or a
    number (a mean: pass scale=1); NaNs when xs is empty."""
    if not xs:
        return (float("nan"),) * 3
    by = collections.defaultdict(list)
    for d, v in xs:
        by[d].append(float(v))
    groups, rng = list(by.values()), random.Random(1)
    m = sum(float(v) for _, v in xs) / len(xs)
    bs = []
    for _ in range(n):
        g = rng.choices(groups, k=len(groups))
        bs.append(sum(sum(x) for x in g) / sum(len(x) for x in g))
    bs.sort()
    return scale * m, scale * bs[int(0.025 * n)], scale * bs[int(0.975 * n)]


def paired(a, b, scale=100):
    """Difference a - b (with interval) over the items both have, clustered by document.
    a, b: {item id: (document, value)}. Returns ((diff, low, high), n common)."""
    common = sorted(set(a) & set(b))
    return ci([(a[i][0], float(a[i][1]) - float(b[i][1])) for i in common], scale=scale), len(common)
