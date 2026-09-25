/* 主题在 CSS 加载前应用，避免闪烁
   独立文件（而非 index.html 内联脚本）以便面板 CSP 只放行同源脚本 */
(function () {
  var saved = localStorage.getItem('atri_theme');
  var theme = saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
})();
