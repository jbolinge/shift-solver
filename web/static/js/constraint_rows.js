// Add/remove repeatable rows in the structured constraint editors
// (shift_frequency requirements, shift_order_preference rules).
//
// Uses event delegation on the document so it keeps working for form markup
// that HTMX swaps into the constraints table after page load.
(function () {
    "use strict";

    // Guard against double-binding when the constraints page is re-loaded via
    // an HTMX swap (the script tag would otherwise run again).
    if (window.__constraintRowsBound) {
        return;
    }
    window.__constraintRowsBound = true;

    function handleClick(event) {
        var addBtn = event.target.closest("[data-add-row]");
        if (addBtn) {
            event.preventDefault();
            var tmpl = document.querySelector(addBtn.getAttribute("data-row-template"));
            var container = document.querySelector(addBtn.getAttribute("data-rows-target"));
            if (tmpl && container && tmpl.content) {
                container.appendChild(tmpl.content.cloneNode(true));
            }
            return;
        }

        var removeBtn = event.target.closest("[data-remove-row]");
        if (removeBtn) {
            event.preventDefault();
            var row = removeBtn.closest(".sf-row, .sop-row");
            if (row) {
                row.remove();
            }
        }
    }

    document.addEventListener("click", handleClick);
})();
