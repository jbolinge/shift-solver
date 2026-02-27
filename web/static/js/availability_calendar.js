/**
 * Availability Calendar - FullCalendar integration for shift-solver.
 *
 * Initializes a FullCalendar month view that:
 *  - Fetches availability events from /availability/events/?worker_id=...
 *  - Allows clicking a date to cycle through states:
 *    (none) -> Unavailable -> Preferred -> Required -> (clear)
 *  - Shows toast notifications for success/error feedback
 *  - Displays a loading pulse on the clicked date cell while the request is in-flight
 */

document.addEventListener("DOMContentLoaded", function () {
    var calendarEl = document.getElementById("calendar");
    var workerSelect = document.getElementById("worker-select");

    if (!calendarEl || !workerSelect) {
        return;
    }

    // State cycle: no entry -> unavailable -> preferred -> required -> clear
    var STATE_CYCLE = {
        "": "unavailable",
        "unavailable": "preferred",
        "preferred": "required",
        "required": "clear",
    };

    var STATE_LABELS = {
        "unavailable": "Unavailable",
        "preferred": "Preferred",
        "required": "Required",
        "clear": "Clear",
    };

    /**
     * Show a toast notification.
     * @param {string} message - Text to display
     * @param {"success"|"error"} type - Toast variant
     */
    function showToast(message, type) {
        var container = document.getElementById("toast-container");
        if (!container) return;

        var toast = document.createElement("div");
        var bgColor = type === "success" ? "bg-green-600" : "bg-red-600";
        toast.className =
            bgColor +
            " text-white text-sm font-medium px-4 py-2 rounded-lg shadow-lg toast-enter";
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(function () {
            toast.classList.remove("toast-enter");
            toast.classList.add("toast-exit");
            toast.addEventListener("animationend", function () {
                toast.remove();
            });
        }, 2500);
    }

    /**
     * Extract the CSRF token from the body's hx-headers attribute.
     * @returns {string} CSRF token value or empty string
     */
    function getCSRFToken() {
        var body = document.body;
        var raw = body.getAttribute("hx-headers") || body.getAttribute("data-hx-headers");
        if (!raw) return "";
        try {
            var parsed = JSON.parse(raw);
            return parsed["X-CSRFToken"] || "";
        } catch (e) {
            return "";
        }
    }

    /**
     * Format a date string (YYYY-MM-DD) as a short label like "Mar 15".
     * @param {string} dateStr - ISO date string
     * @returns {string}
     */
    function formatDateLabel(dateStr) {
        var d = new Date(dateStr + "T00:00:00");
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    }

    /**
     * Get the current status of a date from calendar events.
     * @param {string} dateStr - ISO date string (YYYY-MM-DD)
     * @returns {string} Current status or "" if no entry
     */
    function getCurrentStatus(dateStr) {
        var events = calendar.getEvents();
        for (var i = 0; i < events.length; i++) {
            var eventDate = events[i].startStr;
            if (eventDate === dateStr && events[i].extendedProps.status) {
                return events[i].extendedProps.status;
            }
        }
        return "";
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

            // Determine next status in cycle
            var currentStatus = getCurrentStatus(info.dateStr);
            var nextStatus = STATE_CYCLE[currentStatus] || "unavailable";

            // Visual loading feedback: pulse the clicked date cell
            var cellEl = info.dayEl;
            cellEl.style.opacity = "0.5";
            cellEl.style.transition = "opacity 0.2s";

            var formData = new FormData();
            formData.append("worker_id", workerId);
            formData.append("date", info.dateStr);
            formData.append("status", nextStatus);

            var csrfToken = getCSRFToken();
            var headers = {};
            if (csrfToken) {
                headers["X-CSRFToken"] = csrfToken;
            }

            fetch("/availability/update/", {
                method: "POST",
                body: formData,
                headers: headers,
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Server returned " + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    cellEl.style.opacity = "";
                    calendar.refetchEvents();

                    var label = formatDateLabel(info.dateStr);
                    var statusLabel = STATE_LABELS[nextStatus] || nextStatus;
                    if (nextStatus === "clear") {
                        showToast(label + " cleared", "success");
                    } else {
                        showToast(label + " marked as " + statusLabel, "success");
                    }
                })
                .catch(function (err) {
                    cellEl.style.opacity = "";
                    console.error("Failed to update availability:", err);
                    showToast("Failed to update availability", "error");
                });
        },
    });

    calendar.render();

    // Re-fetch events when the worker selection changes
    workerSelect.addEventListener("change", function () {
        calendar.refetchEvents();
    });
});
