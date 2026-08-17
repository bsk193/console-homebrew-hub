/* CHH Console Navigation
   D-pad    → snaps focus to nearest button; X activates it
   L-Stick  → PS5 cursor takes over; dot hides; X works natively
   Circle   → back   Triangle → home
*/
(function () {
  var INITIAL_DELAY = 300;
  var REPEAT_RATE   = 120;
  var B = { CROSS:0, CIRCLE:1, TRIANGLE:3, UP:12, DOWN:13, LEFT:14, RIGHT:15 };
  var DEADZONE = 0.20;

  /* ── Cursor dot (D-pad mode only) ───────────────────────────────── */
  var dot = document.createElement('div');
  dot.style.cssText = [
    'position:fixed','width:26px','height:26px','border-radius:50%',
    'background:rgba(255,255,255,.95)',
    'border:2.5px solid rgba(0,0,0,.3)',
    'box-shadow:0 2px 16px rgba(0,0,0,.6)',
    'pointer-events:none','z-index:2147483647',
    'transform:translate(-50%,-50%)',
    'transition:left .13s ease,top .13s ease,opacity .15s',
    'opacity:0'  /* hidden until D-pad is used */
  ].join(';');
  document.body.appendChild(dot);

  /* ── Focus ring for D-pad mode ──────────────────────────────────── */
  var sty = document.createElement('style');
  sty.textContent =
    ':focus{outline:3px solid rgba(79,135,255,.9)!important;' +
    'outline-offset:4px!important;border-radius:6px!important}';
  document.head.appendChild(sty);

  /* ── State ──────────────────────────────────────────────────────── */
  var lastSnapped = null;   // last element snapped to by D-pad
  var dpadMode    = false;  // true = D-pad driving; false = analog/PS5 cursor
  var dpadHeld = {}, dpadNext = {};
  var prev = { cross:false, circle:false, tri:false };
  var _myNav = false;       // guard to skip our own navigate calls in intercept

  /* ── Mode switch ────────────────────────────────────────────────── */
  function enterDpad() {
    dpadMode = true;
    dot.style.opacity = '1';
  }
  function enterFree() {
    dpadMode = false;
    dot.style.opacity = '0';
    // blur so :focus ring hides too
    if (document.activeElement && document.activeElement !== document.body) {
      document.activeElement.blur();
    }
  }

  /* ── Helpers ────────────────────────────────────────────────────── */
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

  function getTarget() {
    var a = document.activeElement;
    return (a && a !== document.body) ? a : lastSnapped;
  }

  /* ── Snap dot + focus ───────────────────────────────────────────── */
  function snapTo(el) {
    lastSnapped = el;
    el.focus({ preventScroll: false });
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    var c = centerOf(el);
    dot.style.left = c.x + 'px';
    dot.style.top  = c.y + 'px';
  }

  /* ── Navigate / activate ────────────────────────────────────────── */
  function activate(el) {
    if (!el) return;

    /* pulse animation */
    dot.style.transition = 'left .13s ease,top .13s ease,opacity .15s,transform .08s ease';
    dot.style.transform = 'translate(-50%,-50%) scale(.7)';
    setTimeout(function () {
      dot.style.transform = 'translate(-50%,-50%) scale(1)';
      dot.style.transition = 'left .13s ease,top .13s ease,opacity .15s';
    }, 90);

    var anchor = el.tagName === 'A' ? el : (el.closest ? el.closest('a[href]') : null);
    if (anchor && anchor.href) {
      _myNav = true;
      window.location.href = anchor.href;
      return;
    }
    /* Non-link element (button, input, etc.) */
    _myNav = true;
    el.click();
    setTimeout(function () { _myNav = false; }, 200);
  }

  /* ── Document click intercept ───────────────────────────────────── *
   * In D-pad mode, PS5 Cross fires a click at the PS5 cursor position
   * (which isn't where our dot is). We capture it and redirect.      */
  document.addEventListener('click', function (e) {
    if (_myNav) return;            // our own navigation, let it go
    if (!dpadMode) return;         // free mode: PS5 cursor handles it
    var target = getTarget();
    if (!target) return;
    if (target === e.target || target.contains(e.target)) return; // landed correctly
    e.preventDefault();
    e.stopImmediatePropagation();
    activate(target);
  }, true);

  /* Also catch pointerup — PS5 may fire pointer events instead of mouse */
  document.addEventListener('pointerup', function (e) {
    if (_myNav) return;
    if (!dpadMode) return;
    var target = getTarget();
    if (!target) return;
    if (target === e.target || target.contains(e.target)) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    /* Don't navigate on pointerup directly — wait for the click event.
       Just prevent default so the click still fires but hits our listener. */
  }, true);

  /* ── Spatial navigation ─────────────────────────────────────────── */
  function spatialNav(dir) {
    var els = getFocusables();
    if (!els.length) return;
    var cur = document.activeElement;
    if (!cur || els.indexOf(cur) === -1) {
      /* pick nearest to dot center (fallback to first element) */
      var cx = parseFloat(dot.style.left) || window.innerWidth / 2;
      var cy = parseFloat(dot.style.top)  || window.innerHeight / 2;
      var near = null, nearD = Infinity;
      for (var i = 0; i < els.length; i++) {
        var c = centerOf(els[i]);
        var d = Math.hypot(c.x - cx, c.y - cy);
        if (d < nearD) { nearD = d; near = els[i]; }
      }
      if (near) snapTo(near);
      return;
    }
    var cc = centerOf(cur);
    var best = null, bestScore = Infinity;
    for (var j = 0; j < els.length; j++) {
      var el = els[j];
      if (el === cur) continue;
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

  /* ── D-pad hold / repeat ────────────────────────────────────────── */
  function handleDpad(dir, pressed) {
    var now = Date.now();
    if (pressed) {
      if (!dpadHeld[dir]) {
        dpadHeld[dir] = now;
        dpadNext[dir] = now + INITIAL_DELAY;
        enterDpad();
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

  /* ── RAF loop ───────────────────────────────────────────────────── */
  var rafId;
  function tick() {
    rafId = requestAnimationFrame(tick);
    var pads = navigator.getGamepads ? navigator.getGamepads() : [];
    var gp = null;
    for (var i = 0; i < pads.length; i++) { if (pads[i]) { gp = pads[i]; break; } }
    if (!gp) return;

    var btns = gp.buttons;
    var anyDpad = false;

    ['up','down','left','right'].forEach(function (dir, i) {
      var idx = [B.UP, B.DOWN, B.LEFT, B.RIGHT][i];
      var p = !!(btns[idx] && btns[idx].pressed);
      if (p) anyDpad = true;
      handleDpad(dir, p);
    });

    /* Analog stick: switch to free mode */
    var lx = gp.axes[0] || 0;
    var ly = gp.axes[1] || 0;
    if (Math.abs(lx) < DEADZONE) lx = 0;
    if (Math.abs(ly) < DEADZONE) ly = 0;
    if ((lx !== 0 || ly !== 0) && dpadMode) {
      enterFree();
    }

    var cross  = !!(btns[B.CROSS]    && btns[B.CROSS].pressed);
    var circle = !!(btns[B.CIRCLE]   && btns[B.CIRCLE].pressed);
    var tri    = !!(btns[B.TRIANGLE] && btns[B.TRIANGLE].pressed);

    /* Cross in D-pad mode: activate last snapped element */
    if (cross && !prev.cross && dpadMode) {
      activate(getTarget());
    }
    if (circle && !prev.circle) history.back();
    if (tri    && !prev.tri)    location.href = '/';

    prev.cross  = cross;
    prev.circle = circle;
    prev.tri    = tri;
  }

  /* ── Init ───────────────────────────────────────────────────────── */
  function start() {
    if (rafId) return;
    /* Pre-snap to first element so lastSnapped is ready */
    var els = getFocusables();
    if (els.length) {
      lastSnapped = els[0];
      var c = centerOf(els[0]);
      dot.style.left = c.x + 'px';
      dot.style.top  = c.y + 'px';
      /* Don't auto-enter dpad mode — wait for first D-pad press */
    }
    rafId = requestAnimationFrame(tick);
  }

  /* Keyboard fallback (desktop testing) */
  document.addEventListener('keydown', function (e) {
    var map = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' };
    if (map[e.key]) { e.preventDefault(); enterDpad(); spatialNav(map[e.key]); }
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      var t = getTarget();
      if (t) activate(t);
    }
  });

  if (/PlayStation [45]/i.test(navigator.userAgent)) start();
  window.addEventListener('gamepadconnected', start);
  window.chhNav = { start: start };
})();
