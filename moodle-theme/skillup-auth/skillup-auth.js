/* Skillup Action Africa - auth enhancements (vanilla, no libraries).
   Loaded through Moodle "Additional HTML" (head).

   Purpose: Moodle's signup form has a required "Email (again)" confirmation
   field. We hide that redundant field (see skillup-auth.css, html.sk2-js) and
   keep it in sync with the primary email so native server-side validation
   still passes. If JavaScript is unavailable the field simply stays visible. */
(function () {
  var docEl = document.documentElement;
  if (docEl && docEl.classList) {
    docEl.classList.add('sk2-js');
  }

  function sync() {
    var email = document.getElementById('id_email');
    var again = document.getElementById('id_email2');
    if (!email || !again) {
      return;
    }
    if (again.value !== email.value) {
      again.value = email.value;
    }
    if (again.hasAttribute('required')) {
      /* Avoid "not focusable" browser error on a hidden required control. */
      again.removeAttribute('required');
      again.setAttribute('aria-required', 'false');
    }
  }

  document.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'id_email') {
      sync();
    }
  }, true);
  document.addEventListener('change', sync, true);
  document.addEventListener('submit', sync, true);
  document.addEventListener('DOMContentLoaded', sync);
  if (document.readyState !== 'loading') {
    sync();
  }
})();
