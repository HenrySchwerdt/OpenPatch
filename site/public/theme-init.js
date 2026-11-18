(function () {
  try {
    var s = localStorage.getItem('op-theme');
    var t = s === 'dark' || s === 'light' ? s : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = t;
  } catch (e) {
    document.documentElement.dataset.theme = 'light';
  }
  document.documentElement.classList.add('js');
})();
