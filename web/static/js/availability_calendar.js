/**
 * Availability Calendar - FullCalendar integration for shift-solver.
 *
 * Initializes a FullCalendar month view that:
 *  - Fetches availability events from /availability/events/?worker_id=...
 *  - Allows clicking a date to toggle availability via POST /availability/update/
 *  - Updates the calendar after each toggle
 */

document.addEventListener("DOMContentLoaded", function () {
    var calendarEl = document.getElementById("calendar");
    var workerSelect = document.getElementById("worker-select");

    if (!calendarEl || !workerSelect) {
        return;
    }

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: "dayGridMonth",
        selectable: true,
        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth",
        },
        events: function (info, successCallback, failureCallback) {
            var workerId = workerSelect.value;
            if (!workerId) {
                successCallback([]);
                return;
            }
            var url =
                "/availability/events/?worker_id=" +
                encodeURIComponent(workerId) +
                "&start=" +
                info.startStr +
                "&end=" +
                info.endStr;
            fetch(url)
                .then(function (response) {
                    return response.json();
                })
                .then(function (data) {
                    successCallback(data);
                })
                .catch(function (err) {
                    console.error("Failed to fetch events:", err);
                    failureCallback(err);
                });
        },
        dateClick: function (info) {
            var workerId = workerSelect.value;
            if (!workerId) {
                alert("Please select a worker first.");
                return;
            }

            var formData = new FormData();
            formData.append("worker_id", workerId);
            formData.append("date", info.dateStr);

            // Get CSRF token from the HTMX header attribute on body
            var csrfToken = document.querySelector(
                "[hx-headers], [data-hx-headers]"
            );
            var headers = {};
            if (csrfToken) {
                try {
                    var parsed = JSON.parse(
                        csrfToken.getAttribute("hx-headers") ||
                            csrfToken.getAttribute("data-hx-headers")
                    );
                    if (parsed["X-CSRFToken"]) {
                        headers["X-CSRFToken"] = parsed["X-CSRFToken"];
                    }
                } catch (e) {
                    // Ignore parse errors
                }
            }

            fetch("/availability/update/", {
                method: "POST",
                body: formData,
                headers: headers,
            })
                .then(function (response) {
                    return response.json();
                })
                .then(function () {
                    calendar.refetchEvents();
                })
                .catch(function (err) {
                    console.error("Failed to update availability:", err);
                });
        },
    });

    calendar.render();

    // Re-fetch events when the worker selection changes
    workerSelect.addEventListener("change", function () {
        calendar.refetchEvents();
    });
});
