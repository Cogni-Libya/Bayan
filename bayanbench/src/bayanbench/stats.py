"""Pass rates with 95% intervals from a cluster bootstrap over documents: sentences from one document tend to pass or
fail together, so resampling sentences would give intervals that are too narrow (Miller 2024)."""
import collections
import random


def ci(xs, n=2000):
    """(rate %, low %, high %) for xs = [(document, 0/1 or bool)]; NaNs when xs is empty."""
    if not xs:
        return (float("nan"),) * 3
    by = collections.defaultdict(list)
    for d, v in xs:
        by[d].append(int(v))
    groups, rng = list(by.values()), random.Random(1)
    m = sum(int(v) for _, v in xs) / len(xs)
    bs = []
    for _ in range(n):
        g = rng.choices(groups, k=len(groups))
        bs.append(sum(sum(x) for x in g) / sum(len(x) for x in g))
    bs.sort()
    return 100 * m, 100 * bs[int(0.025 * n)], 100 * bs[int(0.975 * n)]


def paired(a, b):
    """Difference in pass rate a - b (points, with interval) over the items both have, clustered by document.
    a, b: {item id: (document, passed)}. Returns ((diff, low, high), n common)."""
    common = sorted(set(a) & set(b))
    return ci([(a[i][0], int(a[i][1]) - int(b[i][1])) for i in common]), len(common)
