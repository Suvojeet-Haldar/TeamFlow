/* ============================================================
   TEAMFLOW — main.js
   Global utilities: dark mode, password visibility,
   local time formatting
   ============================================================ */

// ── Dark Mode ──────────────────────────────────────────────
(function () {
  var saved = localStorage.getItem('tf-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  var btn = document.getElementById('dark-btn');
  if (btn) btn.textContent = saved === 'dark' ? '☀' : '🌙';
})();

function toggleDark() {
  var current = document.documentElement.getAttribute('data-theme');
  var next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('tf-theme', next);
  var btn = document.getElementById('dark-btn');
  if (btn) btn.textContent = next === 'dark' ? '☀' : '🌙';
}

// ── Password Visibility Toggle ─────────────────────────────
function togglePassword(inputId, btn) {
  var input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
  } else {
    input.type = 'password';
    btn.textContent = '👁';
  }
}

// ── Local Time Formatting ──────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.local-time').forEach(function (el) {
    var dt = new Date(el.getAttribute('datetime'));
    el.textContent = dt.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  });
});

// ── Username availability debounce ─────────────────────────
var _checkTimer = null;
function debounceUsernameCheck(val, statusId) {
  clearTimeout(_checkTimer);
  var el = document.getElementById(statusId || 'username-status');
  if (!el) return;
  if (!val || val.length < 2) { el.textContent = ''; return; }
  _checkTimer = setTimeout(function () {
    fetch('/invite/check-username/?username=' + encodeURIComponent(val))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        el.textContent = data.taken ? '✗ Already taken' : '✓ Available';
        el.style.color = data.taken ? 'var(--danger)' : 'var(--success)';
      });
  }, 400);
}