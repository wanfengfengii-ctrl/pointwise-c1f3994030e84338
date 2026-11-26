from dataclasses import dataclass

@dataclass(frozen=True)
class BeatWindow:
    lo: int
    hi: int

def make_window(lo: int, hi: int) -> BeatWindow:
    if type(lo) is not int or type(hi) is not int or lo >= hi:
        raise ValueError('422:invalid beat window')
    return BeatWindow(lo, hi)

def spoken_interval(start: int | None, duration: int | None) -> tuple[int, int] | None:
    if start is None or duration is None:
        return None
    return (start, start + duration)

def is_covered(window: BeatWindow, interval: tuple[int, int] | None) -> bool:
    return interval is None or window.lo <= interval[0] and interval[1] <= window.hi

def first_overlap_beat(left: tuple[int, int] | None, right: tuple[int, int] | None) -> int | None:
    if left is None or right is None:
        return None
    lo = max(left[0], right[0])
    hi = min(left[1], right[1])
    return lo if lo < hi else None
