from datetime import datetime, timedelta
from itertools import islice

import pytest
import pytz

from app.recurrence import RecurrenceError, localize, next_occurrence, parse

NOW = datetime(2026, 9, 25, 13, 50)  # a Friday afternoon
IST = "Asia/Kolkata"


def dates(text, n=6, choice=0, tz=IST, now=NOW):
    return list(islice(parse(text, tz, now)[choice].rule, n))


def test_every_2nd_tuesday_until_december_defaults_to_monthly():
    options = parse("every 2nd Tuesday at 6pm until December", IST, NOW)
    assert options[0].summary == "The 2nd Tuesday of every month at 6:00 PM, until Thu, 31 Dec 2026"
    assert list(options[0].rule) == [datetime(2026, 10, 13, 18), datetime(2026, 11, 10, 18),
                                     datetime(2026, 12, 8, 18)]


def test_every_2nd_tuesday_offers_every_other_tuesday():
    options = parse("every 2nd Tuesday at 6pm until December", IST, NOW)
    assert len(options) == 2
    assert options[1].summary.startswith("Every other Tuesday at 6:00 PM")
    assert dates("every 2nd Tuesday at 6pm until December", n=3, choice=1) == [
        datetime(2026, 9, 29, 18), datetime(2026, 10, 13, 18), datetime(2026, 10, 27, 18)]


@pytest.mark.parametrize("text", ["the 2nd tuesday of the month", "every month on the 2nd tuesday",
                                  "every 5th friday", "every other tuesday"])
def test_unambiguous_phrases_have_one_reading(text):
    assert len(parse(text, IST, NOW)) == 1


def test_every_other_anchors_on_next_matching_day():
    # Said on a Friday: must start this coming Tuesday, not 11 days out.
    assert dates("every other tuesday at 6pm", n=2) == [datetime(2026, 9, 29, 18), datetime(2026, 10, 13, 18)]


def test_time_already_passed_today_starts_tomorrow():
    assert dates("every day at 9am", n=1) == [datetime(2026, 9, 26, 9)]
    assert dates("every day at 6pm", n=1) == [datetime(2026, 9, 25, 18)]


def test_until_month_is_inclusive_and_before_is_exclusive():
    assert dates("every day at 6pm until december", n=500)[-1] == datetime(2026, 12, 31, 18)
    assert dates("every day at 6pm before december", n=500)[-1] == datetime(2026, 11, 30, 18)


def test_until_a_month_already_past_means_next_year():
    assert parse("every monday at 9am until august", IST, NOW)[0].summary.endswith("until Tue, 31 Aug 2027")


def test_month_end_clamping():
    assert dates("every month on the 31st at 9am", n=6) == [
        datetime(2026, 9, 30, 9), datetime(2026, 10, 31, 9), datetime(2026, 11, 30, 9),
        datetime(2026, 12, 31, 9), datetime(2027, 1, 31, 9), datetime(2027, 2, 28, 9)]


def test_leap_day_falls_back_to_feb_28():
    assert dates("every year on feb 29 at 9am", n=3) == [
        datetime(2027, 2, 28, 9), datetime(2028, 2, 29, 9), datetime(2029, 2, 28, 9)]


def test_fifth_weekday_skips_months_without_one():
    option = parse("every 5th friday at 8pm", IST, NOW)[0]
    assert "Months without a 5th Friday are skipped." in option.warnings
    assert list(islice(option.rule, 3)) == [datetime(2026, 10, 30, 20), datetime(2027, 1, 29, 20),
                                            datetime(2027, 4, 30, 20)]


def test_last_weekday_of_month_includes_today_if_still_ahead():
    assert dates("last friday of every month at 5pm", n=2) == [datetime(2026, 9, 25, 17), datetime(2026, 10, 30, 17)]


def test_multiple_nth_weekdays_and_monthdays():
    assert dates("every 2nd and 4th tuesday at 6 p.m.", n=3) == [
        datetime(2026, 10, 13, 18), datetime(2026, 10, 27, 18), datetime(2026, 11, 10, 18)]
    assert dates("on the 1st and 15th of every month at 10am", n=3) == [
        datetime(2026, 10, 1, 10), datetime(2026, 10, 15, 10), datetime(2026, 11, 1, 10)]


def test_weekday_ranges():
    expected = [datetime(2026, 9, 28, 8), datetime(2026, 9, 29, 8)]
    assert dates("every weekday at 8am", n=2) == expected
    assert dates("monday to friday at 8am", n=2) == expected
    assert dates("every mon-fri at 8am", n=2) == expected


def test_count_duration_and_start():
    assert len(list(parse("every tuesday and thursday at 7:30am 10 times", IST, NOW)[0].rule)) == 10
    assert dates("every day at 6pm for 3 days", n=10) == [
        datetime(2026, 9, 25, 18), datetime(2026, 9, 26, 18), datetime(2026, 9, 27, 18)]
    assert dates("every tuesday at 6pm starting october 5", n=1) == [datetime(2026, 10, 6, 18)]


def test_interval_every_n_months():
    assert dates("every 3 months on the 15th at noon", n=3) == [
        datetime(2026, 10, 15, 12), datetime(2027, 1, 15, 12), datetime(2027, 4, 15, 12)]


def test_default_time_is_announced():
    option = parse("every monday", IST, NOW)[0]
    assert option.first == datetime(2026, 9, 28, 9)
    assert any("9:00 AM" in w for w in option.warnings)


def test_wall_clock_time_is_kept_across_dst():
    ny = pytz.timezone("America/New_York")
    option = parse("every 2nd Tuesday at 6pm until December", "America/New_York", NOW)[0]
    aware = [localize(o, ny) for o in option.rule]
    assert [a.hour for a in aware] == [18, 18, 18]
    assert [a.utcoffset() for a in aware] == [timedelta(hours=-4), timedelta(hours=-5), timedelta(hours=-5)]


def test_dst_gap_moves_forward_and_overlap_uses_first():
    ny = pytz.timezone("America/New_York")
    gap = localize(datetime(2027, 3, 14, 2, 30), ny)
    assert (gap.hour, gap.minute, gap.tzname()) == (3, 30, "EDT")
    overlap = localize(datetime(2027, 11, 7, 1, 30), ny)
    assert overlap.utcoffset() == timedelta(hours=-4)


@pytest.mark.parametrize("text", ["every 2nd Tuesday at 6pm until December", "every month on the 31st",
                                  "every other tuesday", "every 2nd and 4th tuesday", "every feb 29"])
def test_stored_rule_round_trips(text):
    option = parse(text, IST, NOW)[0]
    first, second = list(islice(option.rule, 2))
    assert next_occurrence(option.rule_str, first) == second


@pytest.mark.parametrize("text, message", [
    ("every tuesday at 6", "morning or the evening"),
    ("every hour", "at most once a day"),
    ("every 30 minutes", "at most once a day"),
    ("every feb 30", "doesn't have a 30th"),
    ("every 32nd", "no 32nd day"),
    ("every tuesday at 9am and 6pm", "Only one time"),
    ("every tuesday until 2026-09-01", "before the schedule starts"),
    ("every day on the 15th", "contradict"),
    ("every tuesday until friday until monday", "Only one end date"),
    ("every tuesday until december 5 times", "either an end date or a number of times"),
    ("every blursday", "didn't understand"),
    ("whenever", "didn't understand"),
])
def test_rejects_with_helpful_message(text, message):
    with pytest.raises(RecurrenceError, match=message):
        parse(text, IST, NOW)


def test_rejects_unknown_time_zone():
    with pytest.raises(RecurrenceError, match="Unknown time zone"):
        parse("every monday", "Mars/Olympus", NOW)
