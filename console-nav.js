/* CHH Console Navigation — D-pad + gamepad support for PS5/PS4 */
(function () {
  var REPEAT_DELAY = 180;
  var B = { CROSS: 0, CIRCLE: 1, SQUARE: 2, TRIANGLE: 3, L1: 4, R1: 5, L2: 6, R2: 7, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };
  var prev = {};
  var raf;

  function focusables() {
    return Array.prototype.slice.call(
      document.querySelectorAll('a[href],button:not([disabled]),input,select,[tabindex]:not([tabindex="-1"])')
    ).filter(function (el) {
      return el.offsetParent !== null;
    });
  }

  function moveFocus(dir) {
    var els = focusables();
    if (!els.length) return;
    var cur = document.activeElement;
    var idx = els.indexOf(cur);
    var next;
    if (dir === 'down' || dir === 'right') next = els[idx + 1] || els[0];
    else next = els[idx - 1] || els[els.length - 1];
    if (next) { next.focus(); next.scrollIntoView({ block: 'nearest' }); }
  }

  function tick() {
    var pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (var pi = 0; pi < pads.length; pi++) {
      var pad = pads[pi];
      if (!pad) continue;
      var now = Date.now();
      for (var bi = 0; bi < pad.buttons.length; bi++) {
        var key = pi * 256 + bi;
        var pressed = pad.buttons[bi].pressed;
        var last = prev[key];
        if (pressed && (!last || now - last > REPEAT_DELAY)) {
          prev[key] = now;
          if (bi === B.UP || bi === B.LEFT) moveFocus('up');
          else if (bi === B.DOWN || bi === B.RIGHT) moveFocus('down');
          else if (bi === B.CROSS) {
            var el = document.activeElement;
            if (el && el !== document.body) el.click();
          }
          else if (bi === B.CIRCLE) history.back();
          else if (bi === B.TRIANGLE) location.href = '/';
        } else if (!pressed) {
          delete prev[key];
        }
      }
    }
    raf = requestAnimationFrame(tick);
  }

  function start() {
    if (raf) return;
    raf = requestAnimationFrame(tick);
  }

  /* Keyboard arrow fallback */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') { e.preventDefault(); moveFocus('down'); }
    else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') { e.preventDefault(); moveFocus('up'); }
  });

  /* Auto-start on PS5/PS4 UA or if gamepad connected */
  if (/PlayStation [45]/i.test(navigator.userAgent)) { start(); }
  window.addEventListener('gamepadconnected', start);
  window.chhNav = { start: start };
})();
