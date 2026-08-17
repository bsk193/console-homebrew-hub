/* CHH Console Navigation
   D-pad    → cursor snaps to nearest button/link
   L-Stick  → free cursor movement
   Cross(X) → click focused element (intercepted at document level)
   Circle   → back   Triangle → home
*/
(function () {
  var INITIAL_DELAY = 300;
  var REPEAT_RATE   = 120;
  var STICK_SPEED   = 10;
  var DEADZONE      = 0.20;
  var B = { CROSS:0, CIRCLE:1, TRIANGLE:3, UP:12, DOWN:13, LEFT:14, RIGHT:15 };

  /* ── Cursor dot ─────────────────────────────────────────────────── */
  var dot = document.createElement('div');
  dot.style.cssText = [
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
  document.body.appendChild(dot);

  /* ── Focus ring ─────────────────────────────────────────────────── */
  var sty = document.createElement('style');
  sty.textContent =
    ':focus{outline:3px solid rgba(79,135,255,.9)!important;' +
    'outline-offset:4px!important;border-radius:6px!important}';
  document.head.appendChild(sty);

  /* ── State ──────────────────────────────────────────────────────── */
  var cx = window.innerWidth  / 2;
  var cy = window.innerHeight / 2;
  var dpadHeld = {}, dpadNext = {};
  var prev = { cross:false, circle:false, tri:false };
  var _myClick = false; // guard against intercepting our own dispatched clicks

  /* ── Dot position ───────────────────────────────────────────────── */
  function placeDot(x, y, animate) {
    cx = x; cy = y;
    dot.style.transition = animate ? 'left .14s ease,top .14s ease' : 'none';
    dot.style.left = cx + 'px';
    dot.style.top  = cy + 'px';
  }

  /* ── Focusables ─────────────────────────────────────────────────── */
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

  /* ── Snap dot + focus ───────────────────────────────────────────── */
  function snapTo(el) {
    el.focus({ preventScroll: false });
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    var c = centerOf(el);
    placeDot(c.x, c.y, true);
  }

  /* ── Spatial nav ────────────────────────────────────────────────── */
  function spatialNav(dir) {
    var els = getFocusables();
    if (!els.length) return;

    var cur_el = document.activeElement;
    if (!cur_el || els.indexOf(cur_el) === -1) {
      // nothing focused — pick nearest to dot
      var near = null, nearD = Infinity;
      for (var i = 0; i < els.length; i++) {
        var c = centerOf(els[i]);
        var d = Math.hypot(c.x - cx, c.y - cy);
        if (d < nearD) { nearD = d; near = els[i]; }
      }
      if (near) snapTo(near);
      return;
    }

    var cc = centerOf(cur_el);
    var best = null, bestScore = Infinity;
    for (var j = 0; j < els.length; j++) {
      var el = els[j];
      if (el === cur_el) continue;
      var ec = centerOf(el);
      var dx = ec.x - cc.x, dy = ec.y - cc.y;
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

  /* ── Activate focused element ───────────────────────────────────── */
  function activate(el) {
    if (!el) return;
    dot.style.transition = 'transform .1s ease';
    dot.style.transform  = 'translate(-50%,-50%) scale(.7)';
    setTimeout(function () { dot.style.transform = 'translate(-50%,-50%)'; }, 110);

    /* Direct navigation for links — most reliable on PS5 */
    var anchor = (el.tagName === 'A') ? el : (el.closest ? el.closest('a[href]') : null);
    if (anchor && anchor.href) {
      window.location.href = anchor.href;
      return;
    }
    /* Everything else — dispatch a trusted-like click */
    _myClick = true;
    el.click();
    _myClick = false;
  }

  /* ── Document-level click intercept ────────────────────────────── *
   * PS5 Cross fires a native click at the PS5 system cursor position.
   * If that position misses our focused element, we catch it here
   * and redirect to whatever element is focused.                     */
  document.addEventListener('click', function (e) {
    if (_myClick) return; // our own dispatch — let it through
    var focused = document.activeElement;
    if (!focused || focused === document.body) return;
    if (focused === e.target || focused.contains(e.target)) return; // already correct
    // Click landed somewhere else — redirect to focused element
    e.preventDefault();
    e.stopImmediatePropagation();
    activate(focused);
  }, true /* capture */);

  /* ── RAF loop ───────────────────────────────────────────────────── */
  var rafId;
  function tick() {
    rafId = requestAnimationFrame(tick);
    var pads = navigator.getGamepads ? navigator.getGamepads() : [];
    var gp = null;
    for (var i = 0; i < pads.length; i++) { if (pads[i]) { gp = pads[i]; break; } }
    if (!gp) return;

    var btns = gp.buttons;

    handleDpad('up',    !!(btns[B.UP]    && btns[B.UP].pressed));
    handleDpad('down',  !!(btns[B.DOWN]  && btns[B.DOWN].pressed));
    handleDpad('left',  !!(btns[B.LEFT]  && btns[B.LEFT].pressed));
    handleDpad('right', !!(btns[B.RIGHT] && btns[B.RIGHT].pressed));

    /* Left stick → free dot movement (no focus change) */
    var lx = gp.axes[0] || 0;
    var ly = gp.axes[1] || 0;
    if (Math.abs(lx) < DEADZONE) lx = 0;
    if (Math.abs(ly) < DEADZONE) ly = 0;
    if (lx !== 0 || ly !== 0) {
      var nx = Math.max(0, Math.min(window.innerWidth,  cx + lx * STICK_SPEED));
      var ny = Math.max(0, Math.min(window.innerHeight, cy + ly * STICK_SPEED));
      placeDot(nx, ny, false);
    }

    var cross  = !!(btns[B.CROSS]    && btns[B.CROSS].pressed);
    var circle = !!(btns[B.CIRCLE]   && btns[B.CIRCLE].pressed);
    var tri    = !!(btns[B.TRIANGLE] && btns[B.TRIANGLE].pressed);

    /* Cross: activate focused element directly (backup to the intercept) */
    if (cross && !prev.cross) {
      var focused = document.activeElement;
      if (focused && focused !== document.body) activate(focused);
    }
    if (circle && !prev.circle) history.back();
    if (tri    && !prev.tri)    location.href = '/';

    prev.cross  = cross;
    prev.circle = circle;
    prev.tri    = tri;
  }

  function start() {
    if (rafId) return;
    var els = getFocusables();
    if (els.length) snapTo(els[0]);
    rafId = requestAnimationFrame(tick);
  }

  /* Keyboard arrows (desktop testing) */
  document.addEventListener('keydown', function (e) {
    var map = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' };
    if (map[e.key]) { e.preventDefault(); spatialNav(map[e.key]); }
    if (e.key === 'Enter') {
      var focused = document.activeElement;
      if (focused && focused !== document.body) activate(focused);
    }
  });

  if (/PlayStation [45]/i.test(navigator.userAgent)) start();
  window.addEventListener('gamepadconnected', start);
  window.chhNav = { start: start };
})();
