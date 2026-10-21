"""Natural-language recurrence -> RFC 5545 RRULE, evaluated as wall-clock time in an IANA time zone.

Rules are expanded on naive local datetimes (so "6pm" stays 6pm across DST changes) and only
attached to a zone when compared against real time, via `localize`.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import islice

import pytz
from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU, rrule, rrulestr

DEFAULT_TZ = "Asia/Kolkata"
MAX_TEXT = 300


class RecurrenceError(ValueError):
    pass


# ── Time zones ────────────────────────────────────────────────────────────────

def is_valid_tz(name: str | None) -> bool:
    return bool(name) and name in pytz.all_timezones_set


def get_tz(name: str | None):
    return pytz.timezone(name if is_valid_tz(name) else DEFAULT_TZ)


def localize(naive: datetime, tz) -> datetime:
    """Attach tz to a wall-clock time. Times skipped by a DST jump move forward; repeated times use the first."""
    try:
        return tz.localize(naive, is_dst=None)
    except pytz.NonExistentTimeError:
        return tz.normalize(tz.localize(naive, is_dst=False))
    except pytz.AmbiguousTimeError:
        return tz.localize(naive, is_dst=True)


def now_in(tz) -> datetime:
    return datetime.now(tz).replace(tzinfo=None, microsecond=0)


def next_occurrence(rule: str, after: datetime) -> datetime | None:
    return rrulestr(rule).after(after)


# ── Vocabulary ────────────────────────────────────────────────────────────────

_WEEKDAYS = {"monday": 0, "mon": 0, "tuesday": 1, "tues": 1, "tue": 1, "wednesday": 2, "wed": 2,
             "thursday": 3, "thurs": 3, "thur": 3, "thu": 3, "friday": 4, "fri": 4,
             "saturday": 5, "sat": 5, "sunday": 6, "sun": 6}
_MONTHS = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4,
           "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
           "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11,
           "nov": 11, "december": 12, "dec": 12}
_ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
             "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "last": -1}
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
              "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
_WD_OBJ = (MO, TU, WE, TH, FR, SA, SU)
_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTH_NAMES = ("", "January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December")
_MAX_DAYS = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _alt(words) -> str:
    return "(?:" + "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True)) + ")"


_SFX = r"(?:st|nd|rd|th)"
_WD = _alt(_WEEKDAYS)
_MON = _alt(_MONTHS)
_ORD = _alt(_ORDINALS)
_NUMW = _alt(_NUM_WORDS)
_AND = r"(?:\s+and\s+|\s*&\s*|\s*/\s*)"
_DOW_W = rf"\b{_WD}s?\b"
_DOW_LIST = rf"{_DOW_W}(?:(?:{_AND}|\s+){_DOW_W})*"

_DATE = (rf"\b(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}"
         rf"|{_MON}\s+\d{{1,2}}{_SFX}?(?:\s+\d{{4}})?"
         rf"|\d{{1,2}}{_SFX}?\s+(?:of\s+)?{_MON}(?:\s+\d{{4}})?"
         rf"|(?:the\s+)?end\s+of\s+(?:(?:the|this|next)\s+)?(?:month|year)"
         rf"|(?:the\s+)?end\s+of\s+{_MON}(?:\s+\d{{4}})?"
         rf"|{_MON}(?:\s+\d{{4}})?"
         rf"|today|tomorrow|now"
         rf"|(?:next\s+)?{_WD})\b")

_TOO_OFTEN = rf"\b(?:hourly|every\s+(?:\d+\s+|{_NUMW}\s+|other\s+)?(?:hour|minute)s?)\b"
_TIMES = (
    ("ampm", r"\b(?:at\s+)?(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ap>am|pm)\b"),
    ("24h", r"\b(?:at\s+)?(?P<h>\d{1,2})[:.](?P<m>\d{2})\b"),
    ("word", r"\b(?:at\s+)?(?P<w>noon|midday|midnight)\b"),
    ("bare", r"\bat\s+(?P<h>\d{1,2})\b"),
)
_RANGE = (rf"\b(?:(?:every|each|on|from)\s+)?(?P<a>{_WD})s?\b\s*(?:-|\bto\b|\bthrough\b|\bthru\b)\s*"
          rf"(?P<b>{_WD})s?\b")
_COUNT = rf"\b(?:for\s+)?(?P<n>\d+|{_NUMW})\s+(?:times|occurrences)\b"
_FOR = rf"\bfor\s+(?:the\s+)?(?:next\s+)?(?P<n>\d+|an?|{_NUMW})\s+(?P<unit>day|week|month|year)s?\b"
_END = (r"\b(?P<kw>up to|ending on|ends on|ending|ends|until|till|til|through|thru|before|by|to)"
        rf"\s+(?P<date>{_DATE})")
_START = (r"\b(?:starting|starts|start|beginning|begins|begin|from|effective)(?:\s+(?:on|from))?"
          rf"\s+(?P<date>{_DATE})")

_OF_MONTH = r"\s+(?:day\s+)?(?:of|in)\s+(?:(?:the|every|each|a)\s+)?month\b"
_P_WEEKDAYS = r"\b(?:(?:every|each|on)\s+)?week(?P<kind>day|end)s?\b"
_P_LASTDAY = rf"\b(?:(?:every|each|on)\s+)?(?:the\s+)?(?:last\s+day|end)(?:{_OF_MONTH})"
_P_YEARDATE = (rf"\b(?:(?:every|each|on)\s+)?(?:the\s+)?(?:(?P<m1>{_MON})\s+(?:the\s+)?(?P<d1>\d{{1,2}}){_SFX}?"
               rf"|(?P<d2>\d{{1,2}}){_SFX}?\s+(?:of\s+)?(?P<m2>{_MON}))\b")
_P_FREQ = (rf"\b(?:(?:every|each)\s+(?:(?P<n>\d+{_SFX}?|{_NUMW}|other|second|third|fourth|fifth)\s+)?"
           r"(?P<unit>day|week|month|year)s?"
           r"|(?P<adv>daily|weekly|monthly|yearly|annually|fortnightly|biweekly)|every\s+fortnight)\b")
_P_OTHER_DOW = rf"\b(?:every|each)\s+other\s+(?P<dows>{_DOW_LIST})"
_P_NTH = (rf"\b(?:(?P<every>every|each)\s+|on\s+)?(?:the\s+)?(?P<ords>{_ORD}(?:{_AND}{_ORD})*)"
          rf"\s+(?P<dow>{_WD})s?\b(?P<ofm>{_OF_MONTH})?")
_P_MONTHDAY = (rf"\b(?:(?:every|each)\s+|on\s+)?(?:the\s+)?"
               rf"(?P<days>\d{{1,2}}{_SFX}(?:{_AND}(?:the\s+)?\d{{1,2}}{_SFX})*|(?<=the )\d{{1,2}})"
               rf"(?:{_OF_MONTH})?")
_P_DOWS = rf"\b(?:(?:every|each|on)\s+)?(?P<dows>{_DOW_LIST})"

_FILLER = {"on", "at", "the", "and", "of", "in", "a", "please", "remind", "me", "repeat",
           "repeats", "repeating", "recurring", "reminder", "it"}


# ── Formatting ────────────────────────────────────────────────────────────────

def _ordinal(n: int) -> str:
    if n == -1:
        return "last"
    sfx = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{sfx}"


def fmt_time(h: int, m: int) -> str:
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def fmt_date(d: date) -> str:
    return f"{d.strftime('%a')}, {d.day} {d.strftime('%b')} {d.year}"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ── Parsed structures ─────────────────────────────────────────────────────────

@dataclass
class _Pattern:
    freq: int
    interval: int = 1
    dows: list[int] | None = None
    nth: list[tuple[int, int]] | None = None   # (n, weekday): (2, 1) = 2nd Tuesday
    monthday: list[int] | None = None          # 1..31, or -1 for the last day
    yeardate: tuple[int, int] | None = None    # (month, day)


@dataclass
class _Parsed:
    patterns: list[_Pattern]                   # primary reading first, then alternatives
    hour: int
    minute: int
    start: date | None
    until: date | None                         # last day included
    count: int | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Interpretation:
    rule: rrule
    summary: str
    warnings: list[str]

    @property
    def rule_str(self) -> str:
        return str(self.rule)

    @property
    def first(self) -> datetime:
        return next(iter(self.rule))

    def preview(self, tz, n: int = 5) -> dict:
        occ = []
        for o in islice(self.rule, n):
            aware = localize(o, tz)
            occ.append({"iso": aware.isoformat(),
                        "label": f"{fmt_date(o.date())} · {fmt_time(aware.hour, aware.minute)} {aware.tzname()}"})
        return {"summary": self.summary, "warnings": self.warnings,
                "first": self.first.isoformat(timespec="minutes"), "occurrences": occ}


# ── Parsing ───────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"(?<![a-z])([ap])\.\s?m\b\.?", r"\1m", s)
    s = s.replace("bi-weekly", "biweekly").replace("’", "'")
    s = re.sub(r"[,;!?()\"]", " ", s)
    s = re.sub(r"\.(?!\d)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _cut(s: str, m: re.Match) -> str:
    return re.sub(r"\s+", " ", f"{s[:m.start()]} {s[m.end():]}").strip()


def _take(pattern: str, s: str):
    m = re.search(pattern, s)
    return (m, _cut(s, m)) if m else (None, s)


def _take_once(pattern: str, s: str, what: str):
    m, s = _take(pattern, s)
    if m and re.search(pattern, s):
        raise RecurrenceError(f"Only one {what} is allowed.")
    return m, s


def _to_int(tok: str) -> int:
    tok = re.sub(rf"^(\d+){_SFX}$", r"\1", tok)
    if tok.isdigit():
        return int(tok)
    if tok in ("a", "an"):
        return 1
    if tok == "other":
        return 2
    return _NUM_WORDS.get(tok) or _ORDINALS[tok]


def _dows_in(text: str) -> list[int]:
    return sorted({_WEEKDAYS[w] for w in re.findall(rf"\b({_WD})s?\b", text)})


def _mkdate(y: int, m: int, d: int) -> date:
    try:
        return date(y, m, d)
    except ValueError:
        raise RecurrenceError(f"{d} {_MONTH_NAMES[m]} {y} isn't a real date.") from None


def _month_end(y: int, m: int) -> date:
    return (date(y, m, 1) + relativedelta(months=1)) - timedelta(days=1)


def _next_date(month: int, day: int, ref: date) -> date:
    for y in range(ref.year, ref.year + 9):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if d >= ref:
            return d
    raise RecurrenceError(f"{day} {_MONTH_NAMES[month]} isn't a real date.")


def _resolve(phrase: str, today: date, ref: date, strictly_after: bool) -> tuple[date, date]:
    """Return the (first, last) day a date phrase covers. Month names cover the whole month."""
    p = phrase.strip()
    if p in ("today", "now"):
        return today, today
    if p == "tomorrow":
        d = today + timedelta(days=1)
        return d, d
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", p):
        y, mo, d = map(int, m.groups())
        if not 1 <= mo <= 12:
            raise RecurrenceError(f"'{p}' isn't a real date.")
        d = _mkdate(y, mo, d)
        return d, d
    if m := re.fullmatch(r"(?:the\s+)?end\s+of\s+(?:(the|this|next)\s+)?(month|year)", p):
        base = ref + (relativedelta(**{m[2] + "s": 1}) if m[1] == "next" else relativedelta())
        d = _month_end(base.year, base.month) if m[2] == "month" else date(base.year, 12, 31)
        return d, d
    if m := re.fullmatch(rf"(?:the\s+)?end\s+of\s+({_MON})(?:\s+(\d{{4}}))?", p):
        mo = _MONTHS[m[1]]
        y = int(m[2]) if m[2] else (ref.year if _month_end(ref.year, mo) >= ref else ref.year + 1)
        d = _month_end(y, mo)
        return d, d
    m = (re.fullmatch(rf"(?P<mon>{_MON})\s+(?P<day>\d{{1,2}}){_SFX}?(?:\s+(?P<y>\d{{4}}))?", p)
         or re.fullmatch(rf"(?P<day>\d{{1,2}}){_SFX}?\s+(?:of\s+)?(?P<mon>{_MON})(?:\s+(?P<y>\d{{4}}))?", p))
    if m:
        mo, day = _MONTHS[m["mon"]], int(m["day"])
        d = _mkdate(int(m["y"]), mo, day) if m["y"] else _next_date(mo, day, ref)
        return d, d
    if m := re.fullmatch(rf"({_MON})(?:\s+(\d{{4}}))?", p):
        mo = _MONTHS[m[1]]
        y = int(m[2]) if m[2] else (ref.year if _month_end(ref.year, mo) >= ref else ref.year + 1)
        return date(y, mo, 1), _month_end(y, mo)
    if m := re.fullmatch(rf"(next\s+)?({_WD})", p):
        delta = (_WEEKDAYS[m[2]] - ref.weekday()) % 7
        if delta == 0 and (strictly_after or m[1]):
            delta = 7
        d = ref + timedelta(days=delta)
        return d, d
    raise RecurrenceError(f"I couldn't read the date '{phrase}'.")


def _take_time(s: str, warnings: list[str]):
    found = []
    for kind, pat in _TIMES:
        while m := re.search(pat, s):
            found.append((kind, m))
            s = _cut(s, m)
    if not found:
        return None, None, s
    if len(found) > 1:
        raise RecurrenceError("Only one time per reminder is supported. "
                              "Create a separate reminder for each time of day.")
    kind, m = found[0]
    if kind == "word":
        return (0 if m["w"] == "midnight" else 12), 0, s
    h, mi = int(m["h"]), int(m.groupdict().get("m") or 0)
    bad = RecurrenceError(f"'{m[0].strip()}' isn't a valid time.")
    if mi > 59:
        raise bad
    if kind == "ampm":
        if not 1 <= h <= 12:
            raise bad
        return (h % 12) + (12 if m["ap"] == "pm" else 0), mi, s
    if kind == "bare" and 1 <= h <= 12:
        raise RecurrenceError(f"Is {h} in the morning or the evening? Write {h}am or {h}pm.")
    if h > 23:
        raise bad
    if kind == "24h" and 1 <= h <= 11 and not m["h"].startswith("0"):
        warnings.append(f"Reading {h}:{mi:02d} as {fmt_time(h, mi)}. Add 'pm' if you meant the evening.")
    return h, mi, s


def _take_patterns(s: str, range_dows: list[int] | None, ref: date, warnings: list[str]) -> list[_Pattern]:
    sel: dict = {}

    def put(kind, value):
        if kind in sel and kind in ("dows", "monthday", "nth"):
            sel[kind] = sorted(set(sel[kind]) | set(value))
            return
        if sel:
            raise RecurrenceError("That mixes different kinds of days. Pick one, like "
                                  "'every Tuesday' or 'the 15th of every month'.")
        sel[kind] = value

    if range_dows:
        put("dows", range_dows)
    freq = interval = None
    single_every_nth = False

    while True:
        m, s = _take(_P_WEEKDAYS, s)
        if not m:
            break
        put("dows", [0, 1, 2, 3, 4] if m["kind"] == "day" else [5, 6])
    while True:
        m, s = _take(_P_LASTDAY, s)
        if not m:
            break
        put("monthday", [-1])
    while True:
        m, s = _take(_P_YEARDATE, s)
        if not m:
            break
        mo, d = _MONTHS[m["m1"] or m["m2"]], int(m["d1"] or m["d2"])
        if not 1 <= d <= _MAX_DAYS[mo]:
            raise RecurrenceError(f"{_MONTH_NAMES[mo]} doesn't have a {_ordinal(d)} day.")
        put("yeardate", (mo, d))
    m, s = _take_once(_P_FREQ, s, "repeat interval")
    if m:
        if m["adv"]:
            freq, interval = {"daily": (DAILY, 1), "weekly": (WEEKLY, 1), "monthly": (MONTHLY, 1),
                              "yearly": (YEARLY, 1), "annually": (YEARLY, 1),
                              "fortnightly": (WEEKLY, 2), "biweekly": (WEEKLY, 2)}[m["adv"]]
            if m["adv"] == "biweekly":
                warnings.append("Reading 'biweekly' as every 2 weeks.")
        elif m["unit"] is None:
            freq, interval = WEEKLY, 2
        else:
            freq = {"day": DAILY, "week": WEEKLY, "month": MONTHLY, "year": YEARLY}[m["unit"]]
            interval = _to_int(m["n"]) if m["n"] else 1
    m, s = _take(_P_OTHER_DOW, s)
    if m:
        if freq is not None:
            raise RecurrenceError("Use either 'every other <day>' or 'every N weeks', not both.")
        freq, interval = WEEKLY, 2
        put("dows", _dows_in(m["dows"]))
    while True:
        m, s = _take(_P_NTH, s)
        if not m:
            break
        ords = [_ORDINALS[o] for o in re.findall(rf"\b{_ORD}\b", m["ords"])]
        dow = _WEEKDAYS[m["dow"]]
        single_every_nth = bool(m["every"]) and not m["ofm"] and len(ords) == 1 and 2 <= ords[0] <= 4
        put("nth", [(n, dow) for n in ords])
    while True:
        m, s = _take(_P_MONTHDAY, s)
        if not m:
            break
        days = [int(d) for d in re.findall(r"\d+", m["days"])]
        for d in days:
            if not 1 <= d <= 31:
                raise RecurrenceError(f"There's no {_ordinal(d)} day in a month.")
        put("monthday", days)
    while True:
        m, s = _take(_P_DOWS, s)
        if not m:
            break
        put("dows", _dows_in(m["dows"]))

    left = [w for w in s.split() if w not in _FILLER]
    if left:
        raise RecurrenceError(f"I didn't understand \"{' '.join(left)}\". Try something like "
                              "'every 2nd Tuesday at 6pm until December'.")

    kind, value = next(iter(sel.items()), (None, None))
    implied_freq = freq is None
    if freq is None:
        if kind is None:
            raise RecurrenceError("I couldn't tell how often to repeat. Try 'every Monday', "
                                  "'every 2nd Tuesday' or 'the 15th of every month'.")
        freq = {"dows": WEEKLY, "nth": MONTHLY, "monthday": MONTHLY, "yeardate": YEARLY}[kind]
        interval = 1
    if not 1 <= interval <= 365:
        raise RecurrenceError("The repeat interval must be between 1 and 365.")
    allowed = {DAILY: set(), WEEKLY: {"dows"}, MONTHLY: {"dows", "nth", "monthday"}, YEARLY: {"yeardate"}}
    if kind and kind not in allowed[freq]:
        raise RecurrenceError("Those parts contradict each other (like 'every day' with 'the 15th'). "
                              "Try one pattern, such as 'every Tuesday' or 'the 15th of every month'.")

    p = _Pattern(freq, interval)
    if kind:
        setattr(p, kind, value)
    elif freq == WEEKLY:
        p.dows = [ref.weekday()]
    elif freq == MONTHLY:
        p.monthday = [ref.day]
    elif freq == YEARLY:
        p.yeardate = (ref.month, ref.day)

    patterns = [p]
    # "every 2nd Tuesday" can mean the 2nd Tuesday of each month or every other Tuesday.
    if implied_freq and kind == "nth" and single_every_nth:
        n, dow = value[0]
        patterns.append(_Pattern(WEEKLY, n, dows=[dow]))
    return patterns


def _parse_text(s: str, today: date) -> _Parsed:
    warnings: list[str] = []
    if re.search(_TOO_OFTEN, s):
        raise RecurrenceError("Reminders can repeat at most once a day.")
    hour, minute, s = _take_time(s, warnings)
    if hour is None:
        hour, minute = 9, 0
        warnings.append("No time given, so it's set for 9:00 AM.")

    range_dows = None
    m, s = _take(_RANGE, s)
    if m:
        a, b = _WEEKDAYS[m["a"]], _WEEKDAYS[m["b"]]
        range_dows = sorted({(a + i) % 7 for i in range((b - a) % 7 + 1)})

    count = None
    m, s = _take_once(_COUNT, s, "repeat count")
    if m:
        count = _to_int(m["n"])
        if not 1 <= count <= 1000:
            raise RecurrenceError("The number of times must be between 1 and 1000.")
    span, s = _take_once(_FOR, s, "duration")
    end, s = _take_once(_END, s, "end date")
    start_m, s = _take_once(_START, s, "start date")

    start = None
    if start_m:
        start = max(_resolve(start_m["date"], today, today, strictly_after=False)[0], today)
    ref = start or today

    until = None
    if end:
        first, last = _resolve(end["date"], today, ref, strictly_after=True)
        until = first - timedelta(days=1) if end["kw"] == "before" else last
    if span:
        if until:
            raise RecurrenceError("Use either an end date or a duration, not both.")
        until = ref + relativedelta(**{span["unit"] + "s": _to_int(span["n"])}) - timedelta(days=1)
    if count and until:
        raise RecurrenceError("Use either an end date or a number of times, not both.")
    if until and until < ref:
        raise RecurrenceError(f"The end date ({fmt_date(until)}) is before the schedule starts.")

    patterns = _take_patterns(s, range_dows, ref, warnings)
    return _Parsed(patterns, hour, minute, start, until, count, warnings)


# ── Building rules ────────────────────────────────────────────────────────────

def _by_parts(p: _Pattern, hour: int, minute: int) -> dict:
    by = {"byhour": hour, "byminute": minute, "bysecond": 0, "wkst": MO}
    if p.dows is not None:
        by["byweekday"] = [_WD_OBJ[d] for d in p.dows]
    if p.nth:
        by["byweekday"] = [_WD_OBJ[d](n) for n, d in p.nth]
    if p.yeardate:
        mo, d = p.yeardate
        by["bymonth"] = mo
        if (mo, d) == (2, 29):
            by.update(bymonthday=[28, 29], bysetpos=-1)
        else:
            by["bymonthday"] = d
    elif p.monthday:
        if len(p.monthday) == 1 and p.monthday[0] >= 29:
            by.update(bymonthday=list(range(28, p.monthday[0] + 1)), bysetpos=-1)
        else:
            by["bymonthday"] = p.monthday
    return by


def _describe(p: _Pattern, parsed: _Parsed) -> str:
    n = p.interval
    if p.freq == DAILY:
        text = "Every day" if n == 1 else "Every other day" if n == 2 else f"Every {n} days"
    elif p.freq == WEEKLY:
        group = {(0, 1, 2, 3, 4): "weekday", (5, 6): "weekend"}.get(tuple(p.dows))
        if group:
            text = (f"Every {group}" if n == 1
                    else f"{'Every other week' if n == 2 else f'Every {n} weeks'} on {group}s")
        else:
            days = _join([_DAY_NAMES[d] for d in p.dows])
            text = f"Every {days}" if n == 1 else f"Every other {days}" if n == 2 else f"Every {n} weeks on {days}"
    elif p.freq == MONTHLY:
        if p.nth:
            ords = _join([_ordinal(k) for k, _ in sorted(p.nth, key=lambda x: (x[0] == -1, x[0]))])
            days = f"{ords} {_DAY_NAMES[p.nth[0][1]]}"
        elif p.monthday:
            labels = [_ordinal(d) for d in sorted(d for d in p.monthday if d > 0)]
            days = _join(labels + (["last day"] if -1 in p.monthday else []))
        else:
            days = None
        if days:
            text = (f"The {days} of every month" if n == 1
                    else f"{'Every other month' if n == 2 else f'Every {n} months'} on the {days}")
        else:
            period = "every month" if n == 1 else "every other month" if n == 2 else f"every {n} months"
            text = f"Every {_join([_DAY_NAMES[d] for d in p.dows])}, {period}"
    else:
        period = "Every year" if n == 1 else "Every other year" if n == 2 else f"Every {n} years"
        text = f"{period} on {p.yeardate[1]} {_MONTH_NAMES[p.yeardate[0]]}"
    text += f" at {fmt_time(parsed.hour, parsed.minute)}"
    if parsed.start:
        text += f", starting {fmt_date(parsed.start)}"
    if parsed.until:
        text += f", until {fmt_date(parsed.until)}"
    if parsed.count:
        text += ", once" if parsed.count == 1 else f", {parsed.count} times"
    return text


def _pattern_warnings(p: _Pattern) -> list[str]:
    out = []
    for n, d in p.nth or []:
        if n == 5:
            out.append(f"Months without a 5th {_DAY_NAMES[d]} are skipped.")
    if p.monthday:
        late = [d for d in p.monthday if d >= 29]
        if len(p.monthday) == 1 and late:
            out.append("In shorter months it falls on the last day of the month.")
        elif late:
            out.append(f"Months without a {_join([_ordinal(d) for d in late])} skip that date.")
    if p.yeardate == (2, 29):
        out.append("In non-leap years it falls on 28 February.")
    return out


def _build(p: _Pattern, parsed: _Parsed, now: datetime) -> Interpretation:
    ref = max(datetime.combine(parsed.start, time.min), now) if parsed.start else now
    until = datetime.combine(parsed.until, time(23, 59, 59)) if parsed.until else None
    by = _by_parts(p, parsed.hour, parsed.minute)
    # Anchor intervals on the first real occurrence, so "every other Tuesday" said on a
    # Friday starts next Tuesday rather than in 11 days.
    probe = rrule(p.freq, dtstart=datetime.combine(ref.date(), time(parsed.hour, parsed.minute)),
                  until=until, **by)
    first = probe.after(ref, inc=True)
    if first is None:
        raise RecurrenceError(f"That never happens before the end date ({fmt_date(parsed.until)}).")
    rule = rrule(p.freq, interval=p.interval, dtstart=first, until=until, count=parsed.count, **by)
    return Interpretation(rule, _describe(p, parsed), parsed.warnings + _pattern_warnings(p))


def parse(text: str, tz_name: str, now: datetime | None = None) -> list[Interpretation]:
    """Parse text into one or more readings (the first is the default).

    `now` is the naive wall-clock time in tz_name; defaults to the real current time.
    """
    if not is_valid_tz(tz_name):
        raise RecurrenceError(f"Unknown time zone '{tz_name}'.")
    if not text or not text.strip():
        raise RecurrenceError("Describe how the reminder repeats, e.g. 'every Monday at 9am'.")
    if len(text) > MAX_TEXT:
        raise RecurrenceError(f"Keep the description under {MAX_TEXT} characters.")
    now = now or now_in(pytz.timezone(tz_name))
    parsed = _parse_text(_normalize(text), now.date())
    return [_build(p, parsed, now) for p in parsed.patterns]
