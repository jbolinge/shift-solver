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
            var props = info.event.extendedProps;
            alert(
                props.worker_name +
                    "\n" +
                    props.shift_type +
                    " (" +
                    props.shift_category +
                    ")"
            );
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
