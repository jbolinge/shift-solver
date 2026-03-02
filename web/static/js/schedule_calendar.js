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

    function buildEventsUrl() {
        var url = eventsUrl + "?";
        var params = [];

        if (workerFilter && workerFilter.value) {
            params.push("worker_id=" + encodeURIComponent(workerFilter.value));
        }

        // Collect unchecked shift types for exclusion (we filter by checked ones)
        var checkedTypes = [];
        shiftTypeCheckboxes.forEach(function (cb) {
            if (cb.checked) {
                checkedTypes.push(cb.value);
            }
        });

        // If not all checked, filter by the single selected type
        // For simplicity, if only one is checked, filter by it
        if (
            checkedTypes.length > 0 &&
            checkedTypes.length < shiftTypeCheckboxes.length
        ) {
            // Use shift_type_id filter for single selection
            if (checkedTypes.length === 1) {
                params.push(
                    "shift_type_id=" + encodeURIComponent(checkedTypes[0])
                );
            }
        }

        return url + params.join("&");
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
                    // Client-side filtering for multiple shift types
                    var checkedTypes = [];
                    shiftTypeCheckboxes.forEach(function (cb) {
                        if (cb.checked) {
                            checkedTypes.push(parseInt(cb.value));
                        }
                    });

                    if (
                        checkedTypes.length > 0 &&
                        checkedTypes.length < shiftTypeCheckboxes.length
                    ) {
                        data = data.filter(function (event) {
                            return (
                                checkedTypes.indexOf(
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
            // Remove any existing popover
            var existing = document.getElementById('event-popover');
            if (existing) existing.remove();

            var event = info.event;
            var props = event.extendedProps;

            // Create popover element
            var popover = document.createElement('div');
            popover.id = 'event-popover';
            popover.setAttribute('role', 'tooltip');
            popover.className = 'absolute z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs';

            var startTime = event.start ? event.start.toLocaleTimeString() : 'N/A';
            var endTime = event.end ? event.end.toLocaleTimeString() : 'N/A';

            popover.innerHTML =
                '<div class="flex justify-between items-start mb-2">' +
                    '<h3 class="font-semibold text-gray-900">' + (event.title || '') + '</h3>' +
                    '<button id="popover-close" class="text-gray-400 hover:text-gray-600 text-lg leading-none ml-2"' +
                    ' aria-label="Close">&times;</button>' +
                '</div>' +
                '<dl class="text-sm text-gray-600 space-y-1">' +
                    '<div><dt class="inline font-medium">Worker:</dt> <dd class="inline">' + (props.worker_name || 'N/A') + '</dd></div>' +
                    '<div><dt class="inline font-medium">Shift:</dt> <dd class="inline">' + (props.shift_type || event.title) + '</dd></div>' +
                    '<div><dt class="inline font-medium">Category:</dt> <dd class="inline">' + (props.shift_category || 'N/A') + '</dd></div>' +
                    '<div><dt class="inline font-medium">Time:</dt> <dd class="inline">' + startTime + ' - ' + endTime + '</dd></div>' +
                '</dl>';

            // Position near the clicked element
            var rect = info.el.getBoundingClientRect();
            popover.style.top = (rect.bottom + window.scrollY + 4) + 'px';
            popover.style.left = (rect.left + window.scrollX) + 'px';
            document.body.appendChild(popover);

            // Close handlers
            document.getElementById('popover-close').addEventListener('click', function() { popover.remove(); });

            // Outside click
            setTimeout(function() {
                document.addEventListener('click', function handler(e) {
                    if (!popover.contains(e.target) && e.target !== info.el) {
                        popover.remove();
                        document.removeEventListener('click', handler);
                    }
                });
            }, 0);

            // Escape key
            document.addEventListener('keydown', function handler(e) {
                if (e.key === 'Escape') {
                    popover.remove();
                    document.removeEventListener('keydown', handler);
                }
            });
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
});
