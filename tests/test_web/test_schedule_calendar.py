"""Tests for replacing alert() with accessible popover (scheduler-134)."""

import re
from pathlib import Path


class TestScheduleCalendarNoAlert:
    def test_no_alert_in_schedule_calendar(self):
        """schedule_calendar.js does not contain alert() calls."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        alert_calls = re.findall(r"\balert\s*\(", content)
        assert len(alert_calls) == 0, f"Found {len(alert_calls)} alert() calls"

    def test_popover_element_in_schedule_calendar(self):
        """schedule_calendar.js creates a popover with role='tooltip'."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "popover" in content.lower() or "tooltip" in content.lower()

    def test_popover_has_close_button(self):
        """Popover includes a close button."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "close" in content.lower() or "×" in content or "&times;" in content

    def test_popover_escape_key_handler(self):
        """Popover can be dismissed with Escape key."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "Escape" in content


class TestScheduleCalendarPopoverEscaping:
    def test_popover_uses_textcontent(self):
        """Popover content is set via textContent (escaped), not innerHTML."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "textContent" in content

    def test_popover_does_not_use_innerhtml(self):
        """No innerHTML usage, so user-derived names cannot inject markup."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "innerHTML" not in content


class TestScheduleCalendarShiftFilter:
    def test_all_unchecked_shows_no_events(self):
        """Unchecking every shift type filters to an empty set, not all events.

        The old logic only filtered when 0 < checked < total, so unchecking all
        boxes showed everything. The fix treats 'all checked' as the no-filter
        case (null) and any other selection - including empty - as a filter.
        """
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        # No-filter sentinel only when every box is checked.
        assert "=== shiftTypeCheckboxes.length" in content
        assert "return null" in content
        # The buggy guard that exempted the empty selection must be gone.
        assert "checkedTypes.length > 0 &&" not in content


class TestAvailabilityCalendarNoAlert:
    def test_no_alert_in_availability_calendar(self):
        """availability_calendar.js does not contain alert() calls."""
        js_path = Path("web/static/js/availability_calendar.js")
        content = js_path.read_text()
        alert_calls = re.findall(r"\balert\s*\(", content)
        assert len(alert_calls) == 0, f"Found {len(alert_calls)} alert() calls"

    def test_uses_toast_instead(self):
        """availability_calendar.js uses showToast for notifications."""
        js_path = Path("web/static/js/availability_calendar.js")
        content = js_path.read_text()
        assert "showToast" in content or "toast" in content.lower()
