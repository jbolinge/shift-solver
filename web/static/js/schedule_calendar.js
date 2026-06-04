/**
 * Schedule Calendar - FullCalendar integration for viewing solver results.
 *
 * Displays assignments as colored events on a calendar with filtering
 * by worker and shift type.
 */

document.addEventListener("DOMContentLoaded", function () {
    var calendarEl = document.getElementById("schedule-calendar");
    if (!calendarEl) {
        return;
    }

    var eventsUrl = calendarEl.dataset.eventsUrl;
    var initialDate = calendarEl.dataset.initialDate;
    var workerFilter = document.getElementById("worker-filter");
    var shiftTypeCheckboxes = document.querySelectorAll(".shift-type-filter");

    // The worker filter is applied server-side; shift-type filtering is done
    // entirely client-side so the behavior is consistent for any selection.
    function buildEventsUrl() {
        if (workerFilter && workerFilter.value) {
            return eventsUrl + "?worker_id=" + encodeURIComponent(workerFilter.value);
        }
        return eventsUrl;
    }

    // Returns the list of checked shift-type ids, or null when every box is
    // checked (null means "no filter" -> show all). An empty list means the
    // user unchecked everything -> show nothing.
    function checkedShiftTypeIds() {
        var checked = [];
        shiftTypeCheckboxes.forEach(function (cb) {
            if (cb.checked) {
                checked.push(parseInt(cb.value, 10));
            }
        });
        if (checked.length === shiftTypeCheckboxes.length) {
            return null;
        }
        return checked;
    }

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: "dayGridMonth",
        initialDate: initialDate || undefined,
        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay,listMonth",
        },
        events: function (info, successCallback, failureCallback) {
            fetch(buildEventsUrl())
                .then(function (response) {
                    return response.json();
                })
                .then(function (data) {
                    var allowed = checkedShiftTypeIds();
                    if (allowed !== null) {
                        data = data.filter(function (event) {
                            return (
                                allowed.indexOf(
                                    event.extendedProps.shift_type_id
                                ) !== -1
                            );
                        });
                    }
                    successCallback(data);
                })
                .catch(function (err) {
                    console.error("Failed to fetch schedule events:", err);
                    failureCallback(err);
                });
        },
        eventClick: function (info) {
            showEventPopover(info);
        },
    });

    calendar.render();

    // Re-fetch events when filters change
    if (workerFilter) {
        workerFilter.addEventListener("change", function () {
            calendar.refetchEvents();
        });
    }
    shiftTypeCheckboxes.forEach(function (cb) {
        cb.addEventListener("change", function () {
            calendar.refetchEvents();
        });
    });

    // Build the event detail popover from DOM nodes using textContent so that
    // worker/shift names containing HTML characters cannot break the markup or
    // inject script (user-derived strings are never assigned as raw markup).
    function showEventPopover(info) {
        var existing = document.getElementById("event-popover");
        if (existing) {
            existing.remove();
        }

        var event = info.event;
        var props = event.extendedProps || {};

        var popover = document.createElement("div");
        popover.id = "event-popover";
        popover.setAttribute("role", "tooltip");
        popover.className =
            "absolute z-50 bg-white border border-gray-200 rounded-lg " +
            "shadow-lg p-4 max-w-xs";

        var header = document.createElement("div");
        header.className = "flex justify-between items-start mb-2";

        var title = document.createElement("h3");
        title.className = "font-semibold text-gray-900";
        title.textContent = event.title || "";

        var closeBtn = document.createElement("button");
        closeBtn.id = "popover-close";
        closeBtn.className =
            "text-gray-400 hover:text-gray-600 text-lg leading-none ml-2";
        closeBtn.setAttribute("aria-label", "Close");
        closeBtn.textContent = "×";

        header.appendChild(title);
        header.appendChild(closeBtn);

        var startTime = event.start ? event.start.toLocaleTimeString() : "N/A";
        var endTime = event.end ? event.end.toLocaleTimeString() : "N/A";

        var dl = document.createElement("dl");
        dl.className = "text-sm text-gray-600 space-y-1";

        function addRow(label, value) {
            var row = document.createElement("div");
            var dt = document.createElement("dt");
            dt.className = "inline font-medium";
            dt.textContent = label + ":";
            var dd = document.createElement("dd");
            dd.className = "inline";
            dd.textContent = value;
            row.appendChild(dt);
            row.appendChild(document.createTextNode(" "));
            row.appendChild(dd);
            dl.appendChild(row);
        }

        addRow("Worker", props.worker_name || "N/A");
        addRow("Shift", props.shift_type || event.title || "N/A");
        addRow("Category", props.shift_category || "N/A");
        addRow("Time", startTime + " - " + endTime);

        popover.appendChild(header);
        popover.appendChild(dl);

        // Position near the clicked element
        var rect = info.el.getBoundingClientRect();
        popover.style.top = rect.bottom + window.scrollY + 4 + "px";
        popover.style.left = rect.left + window.scrollX + "px";
        document.body.appendChild(popover);

        // Close handlers
        closeBtn.addEventListener("click", function () {
            popover.remove();
        });

        // Outside click
        setTimeout(function () {
            document.addEventListener("click", function handler(e) {
                if (!popover.contains(e.target) && e.target !== info.el) {
                    popover.remove();
                    document.removeEventListener("click", handler);
                }
            });
        }, 0);

        // Escape key
        document.addEventListener("keydown", function handler(e) {
            if (e.key === "Escape") {
                popover.remove();
                document.removeEventListener("keydown", handler);
            }
        });
    }
});
