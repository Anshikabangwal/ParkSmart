/*
static/js/script.js
--------------------
Global JavaScript loaded on every page.
Page-specific JS is written inside each HTML template directly.
*/

/* ══════════════════════════════════════
   AUTO-REFRESH PARKING MAP
   Refreshes the lot map every 30 seconds
   so slot statuses stay up to date.
   Only runs on pages that have #lotMap.
══════════════════════════════════════ */
(function () {
    if (!document.getElementById('lotMap')) return;

    var REFRESH_INTERVAL = 30000; // 30 seconds

    setTimeout(function autoRefresh() {
        location.reload();
    }, REFRESH_INTERVAL);
})();


/* ══════════════════════════════════════
   CONFIRM BEFORE MANUAL RELEASE
   Asks attendant to confirm before
   releasing a slot from the dashboard.
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function () {
    var releaseForms = document.querySelectorAll('.release-form');

    releaseForms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            var vehicle = form.dataset.vehicle || 'this vehicle';
            var ok = confirm('Release slot for ' + vehicle + '?');
            if (!ok) e.preventDefault();
        });
    });
});


/* ══════════════════════════════════════
   IMAGE PREVIEW ON UPLOAD
   Shows a preview of the selected image
   before submitting the camera form.
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function () {
    var inputs = document.querySelectorAll('input[type="file"][data-preview]');

    inputs.forEach(function (input) {
        var previewId = input.dataset.preview;
        var preview   = document.getElementById(previewId);
        if (!preview) return;

        input.addEventListener('change', function () {
            var file = input.files[0];
            if (!file) return;

            var reader = new FileReader();
            reader.onload = function (e) {
                preview.src     = e.target.result;
                preview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        });
    });
});


/* ══════════════════════════════════════
   AUTO-DISMISS FLASH MESSAGES
   Flash messages disappear after 5s.
   Shared by all pages.
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function () {
    var flashes = document.querySelectorAll('.flash');
    if (!flashes.length) return;

    setTimeout(function () {
        flashes.forEach(function (f) {
            f.style.transition = 'opacity 0.5s';
            f.style.opacity    = '0';
            setTimeout(function () { f.remove(); }, 500);
        });
    }, 5000);
});