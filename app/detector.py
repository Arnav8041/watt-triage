"""Is an Appliance's latest run of Readings far from its own normal? Just maths, no database.

Settings (env vars, with defaults): DETECTOR_WINDOW 120, DETECTOR_PERSISTENCE 3,
DETECTOR_Z_THRESHOLD 4.0, DETECTOR_MIN_BASELINE 30.
"""
import os
from statistics import fmean, pstdev


def window():
    return int(os.environ.get("DETECTOR_WINDOW", 120))  # readings in the baseline


def persistence():
    return int(os.environ.get("DETECTOR_PERSISTENCE", 3))  # newest readings that must all be abnormal


def threshold():
    return float(os.environ.get("DETECTOR_Z_THRESHOLD", 4.0))  # how many std devs counts as abnormal


def min_baseline():
    return max(2, int(os.environ.get("DETECTOR_MIN_BASELINE", 30)))  # need at least 2 to have any spread


def check(watts):
    """`watts` is newest first. Score the newest few against a baseline made from the older ones.

    Returns (z, mean, stddev, baseline_size) if all of them are abnormal, else None.
    """
    recent, baseline = watts[: persistence()], watts[persistence() :]
    if len(baseline) < min_baseline():
        return None  # not enough history
    mean, stddev = fmean(baseline), pstdev(baseline)
    if stddev == 0:
        return None  # flat history, can't divide by 0
    zs = [(w - mean) / stddev for w in recent]
    if all(abs(z) > threshold() for z in zs):
        return zs[0], mean, stddev, len(baseline)
    return None
