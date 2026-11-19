/* Runs before first paint: applies the saved colour theme and marks the page as JS-enabled. */
(function () {
  var d = document.documentElement;
  d.classList.add('js');
  try {
    var t = localStorage.getItem('op-theme');
    if (t === 'light' || t === 'dark') d.setAttribute('data-theme', t);
  } catch (e) { /* storage blocked: stay on automatic */ }
})();
