/* CHH Console Navigation — spatial D-pad navigation for PS5/PS4 */
(function () {
  var INITIAL_DELAY = 350;  // ms before first repeat fires on hold
  var REPEAT_RATE   = 130;  // ms between repeats while holding
  var B = { CROSS: 0, CIRCLE: 1, SQUARE: 2, TRIANGLE: 3, L1: 4, R1: 5, L2: 6, R2: 7, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };

  var raf;
  var dpadHeld   = {};  // { dir: timestamp first pressed }
  var dpadNext   = {};  // { dir: timestamp next repeat fires }
  var prevCross  = false;
  var prevCircle = false;
  var prevTri    = false;

  /* Inject a visible focus ring so the user can always see what's selected */
  var style = document.createElement('style');
  style.textContent = [
    ':focus{outline:3px solid rgba(79,135,255,.9)!important;outline-offset:3px!important;border-radius:6px}',
    ':focus:not(:focus-visible){outline:none!important}',
    ':focus-visible{outline:3px solid rgba(79,135,255,.9)!important;outline-offset:3px!important;border-radius:6px}'
  ].join('');
  document.head.appendChild(style);

  function focusables() {
    return Array.prototype.slice.call(
      document.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])')
    ).filter(function (el) {
      var r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && el.offsetParent !== null;
    });
  }

  function center(el) {
    var r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  function spatialNav(dir) {
    var els = focusables();
    if (!els.length) return;

    var cur = document.activeElement;
    if (!cur || els.indexOf(cur) === -1) {
      // Nothing focused yet — pick first visible element
      els[0].focus({ preventScroll: false });
      return;
    }

    var cc = center(cur);
    var best = null, bestScore = Infinity;

    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el === cur) continue;
      var ec = center(el);
      var dx = ec.x - cc.x;
      var dy = ec.y - cc.y;

      // Must be strictly in the pressed direction
      var inDir = (dir === 'up'    && dy < -8) ||
                  (dir === 'down'  && dy >  8) ||
                  (dir === 'left'  && dx < -8) ||
                  (dir === 'right' && dx >  8);
      if (!inDir) continue;

      // Primary axis distance + perpendicular penalty (×1.8)
      var primary = (dir === 'up' || dir === 'down') ? Math.abs(dy) : Math.abs(dx);
      var perp    = (dir === 'up' || dir === 'down') ? Math.abs(dx) : Math.abs(dy);
      var score   = primary + perp * 1.8;

      if (score < bestScore) { bestScore = score; best = el; }
    }

    if (best) {
      best.focus({ preventScroll: false });
      best.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function handleDir(dir, pressed) {
    var now = Date.now();
    if (pressed) {
      if (!dpadHeld[dir]) {
        dpadHeld[dir] = now;
        dpadNext[dir] = now + INITIAL_DELAY;
        spatialNav(dir);
      } else if (now >= dpadNext[dir]) {
        dpadNext[dir] = now + REPEAT_RATE;
        spatialNav(dir);
      }
    } else {
      delete dpadHeld[dir];
      delete dpadNext[dir];
    }
  }

  function tick() {
    var pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (var pi = 0; pi < pads.length; pi++) {
      var pad = pads[pi];
      if (!pad) continue;

      var btns = pad.buttons;
      handleDir('up',    !!(btns[B.UP]    && btns[B.UP].pressed));
      handleDir('down',  !!(btns[B.DOWN]  && btns[B.DOWN].pressed));
      handleDir('left',  !!(btns[B.LEFT]  && btns[B.LEFT].pressed));
      handleDir('right', !!(btns[B.RIGHT] && btns[B.RIGHT].pressed));

      var cross  = !!(btns[B.CROSS]    && btns[B.CROSS].pressed);
      var circle = !!(btns[B.CIRCLE]   && btns[B.CIRCLE].pressed);
      var tri    = !!(btns[B.TRIANGLE] && btns[B.TRIANGLE].pressed);

      if (cross && !prevCross) {
        var el = document.activeElement;
        if (el && el !== document.body) el.click();
      }
      if (circle && !prevCircle) history.back();
      if (tri    && !prevTri)    location.href = '/';

      prevCross  = cross;
      prevCircle = circle;
      prevTri    = tri;
    }
    raf = requestAnimationFrame(tick);
  }

  function start() {
    if (raf) return;
    raf = requestAnimationFrame(tick);
  }

  /* Keyboard arrow fallback (desktop testing) */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowUp')    { e.preventDefault(); spatialNav('up');    }
    else if (e.key === 'ArrowDown')  { e.preventDefault(); spatialNav('down');  }
    else if (e.key === 'ArrowLeft')  { e.preventDefault(); spatialNav('left');  }
    else if (e.key === 'ArrowRight') { e.preventDefault(); spatialNav('right'); }
  });

  if (/PlayStation [45]/i.test(navigator.userAgent)) { start(); }
  window.addEventListener('gamepadconnected', start);
  window.chhNav = { start: start };
})();
