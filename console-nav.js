/* CHH Console Navigation
   D-pad  → cursor snaps to nearest button/link in that direction
   L-Stick → cursor moves freely (like a mouse)
   Cross  → click whatever the cursor is on
   Circle → history back
   Triangle → go home
*/
(function () {
  var INITIAL_DELAY = 300;
  var REPEAT_RATE   = 120;
  var STICK_SPEED   = 10;
  var DEADZONE      = 0.20;
  var B = { CROSS:0, CIRCLE:1, TRIANGLE:3, UP:12, DOWN:13, LEFT:14, RIGHT:15 };

  /* ── Cursor element ─────────────────────────────────────────────── */
  var cur = document.createElement('div');
  cur.style.cssText = [
    'position:fixed',
    'width:22px','height:22px',
    'border-radius:50%',
    'background:rgba(255,255,255,.92)',
    'border:2px solid rgba(0,0,0,.25)',
    'box-shadow:0 2px 14px rgba(0,0,0,.55)',
    'pointer-events:none',
    'z-index:2147483647',
    'transform:translate(-50%,-50%)',
    'will-change:left,top',
    'transition:none'
  ].join(';');
  document.body.appendChild(cur);

  /* ── Focus ring ─────────────────────────────────────────────────── */
  var sty = document.createElement('style');
  sty.textContent =
    ':focus-visible{outline:3px solid rgba(79,135,255,.9)!important;' +
    'outline-offset:4px!important;border-radius:6px!important}';
  document.head.appendChild(sty);

  /* ── State ──────────────────────────────────────────────────────── */
  var cx = window.innerWidth  / 2;
  var cy = window.innerHeight / 2;
  var snapped = false;           // true while cursor is locked on an element
  var dpadHeld = {}, dpadNext = {};
  var prev = { cross:false, circle:false, tri:false };

  /* ── Cursor position ────────────────────────────────────────────── */
  function placeCursor(x, y, animate) {
    cx = x; cy = y;
    cur.style.transition = animate ? 'left .14s ease,top .14s ease' : 'none';
    cur.style.left = cx + 'px';
    cur.style.top  = cy + 'px';
  }

  /* ── Focusable elements ─────────────────────────────────────────── */
  function getFocusables() {
    return Array.prototype.slice.call(
      document.querySelectorAll(
        'a[href],button:not([disabled]),input:not([disabled]),' +
        'select:not([disabled]),[tabindex]:not([tabindex="-1"])'
      )
    ).filter(function (el) {
      var r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && el.offsetParent !== null;
    });
  }

  function centerOf(el) {
    var r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  /* ── Snap cursor to element ─────────────────────────────────────── */
  function snapTo(el) {
    el.focus({ preventScroll: false });
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    var c = centerOf(el);
    placeCursor(c.x, c.y, true);
    snapped = true;
  }

  /* ── Spatial navigation ─────────────────────────────────────────── */
  function spatialNav(dir) {
    var els = getFocusables();
    if (!els.length) return;

    var cur_el = document.activeElement;
    // If nothing focused, snap to nearest element to the cursor
    if (!cur_el || els.indexOf(cur_el) === -1) {
      var nearest = nearestTo(els, cx, cy);
      if (nearest) snapTo(nearest);
      return;
    }

    var cc = centerOf(cur_el);
    var best = null, bestScore = Infinity;

    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el === cur_el) continue;
      var ec = centerOf(el);
      var dx = ec.x - cc.x;
      var dy = ec.y - cc.y;

      var inDir = (dir === 'up'    && dy < -6) ||
                  (dir === 'down'  && dy >  6) ||
                  (dir === 'left'  && dx < -6) ||
                  (dir === 'right' && dx >  6);
      if (!inDir) continue;

      var primary = (dir === 'up' || dir === 'down') ? Math.abs(dy) : Math.abs(dx);
      var perp    = (dir === 'up' || dir === 'down') ? Math.abs(dx) : Math.abs(dy);
      var score   = primary + perp * 1.6;
      if (score < bestScore) { bestScore = score; best = el; }
    }

    if (best) snapTo(best);
  }

  function nearestTo(els, x, y) {
    var best = null, bestD = Infinity;
    for (var i = 0; i < els.length; i++) {
      var c = centerOf(els[i]);
      var d = Math.hypot(c.x - x, c.y - y);
      if (d < bestD) { bestD = d; best = els[i]; }
    }
    return best;
  }

  /* ── D-pad hold repeat ──────────────────────────────────────────── */
  function handleDpad(dir, pressed) {
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

  /* ── Click at cursor ────────────────────────────────────────────── */
  function clickCurrent() {
    // Pulse animation
    cur.style.transition = 'transform .1s ease';
    cur.style.transform  = 'translate(-50%,-50%) scale(.7)';
    setTimeout(function () {
      cur.style.transform = 'translate(-50%,-50%) scale(1)';
    }, 110);

    var el = document.activeElement;
    if (el && el !== document.body) {
      el.click();
    } else {
      var hit = document.elementFromPoint(cx, cy);
      if (hit) hit.click();
    }
  }

  /* ── Main RAF loop ──────────────────────────────────────────────── */
  var rafId;
  function tick() {
    rafId = requestAnimationFrame(tick);
    var pads = navigator.getGamepads ? navigator.getGamepads() : [];
    var gp = null;
    for (var i = 0; i < pads.length; i++) { if (pads[i]) { gp = pads[i]; break; } }
    if (!gp) return;

    var btns = gp.buttons;

    /* D-pad → snap navigation */
    handleDpad('up',    !!(btns[B.UP]    && btns[B.UP].pressed));
    handleDpad('down',  !!(btns[B.DOWN]  && btns[B.DOWN].pressed));
    handleDpad('left',  !!(btns[B.LEFT]  && btns[B.LEFT].pressed));
    handleDpad('right', !!(btns[B.RIGHT] && btns[B.RIGHT].pressed));

    /* Left stick → free cursor movement */
    var lx = gp.axes[0] || 0;
    var ly = gp.axes[1] || 0;
    if (Math.abs(lx) < DEADZONE) lx = 0;
    if (Math.abs(ly) < DEADZONE) ly = 0;
    if (lx !== 0 || ly !== 0) {
      var nx = Math.max(0, Math.min(window.innerWidth,  cx + lx * STICK_SPEED));
      var ny = Math.max(0, Math.min(window.innerHeight, cy + ly * STICK_SPEED));
      placeCursor(nx, ny, false);
      snapped = false;
      // Blur so focus ring doesn't fight with free cursor
      if (document.activeElement && document.activeElement !== document.body) {
        document.activeElement.blur();
      }
    }

    /* Cross → click */
    var cross = !!(btns[B.CROSS]    && btns[B.CROSS].pressed);
    var circ  = !!(btns[B.CIRCLE]   && btns[B.CIRCLE].pressed);
    var tri   = !!(btns[B.TRIANGLE] && btns[B.TRIANGLE].pressed);

    if (cross && !prev.cross) clickCurrent();
    if (circ  && !prev.circle) history.back();
    if (tri   && !prev.tri)   location.href = '/';

    prev.cross  = cross;
    prev.circle = circ;
    prev.tri    = tri;
  }

  function start() {
    if (rafId) return;
    // Snap to first focusable element on start
    var els = getFocusables();
    if (els.length) snapTo(els[0]);
    rafId = requestAnimationFrame(tick);
  }

  /* Keyboard arrows for desktop testing */
  document.addEventListener('keydown', function (e) {
    var map = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' };
    if (map[e.key]) { e.preventDefault(); spatialNav(map[e.key]); }
  });

  if (/PlayStation [45]/i.test(navigator.userAgent)) start();
  window.addEventListener('gamepadconnected', start);
  window.chhNav = { start: start };
})();
