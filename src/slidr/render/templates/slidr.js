var isPresenter = window.name === 'slidr-presenter';
if (isPresenter) document.documentElement.classList.add('presenter');

var slideNotes = [{% for slide in slides %}{{ slide.notes|tojson }}{% if not loop.last %},{% endif %}{% endfor %}];

var KEYS_FWD = ['ArrowRight', 'ArrowDown', 'PageDown', ' '];
var KEYS_BACK = ['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'];
var AUTOPLAY_INTERVAL = {{ autoplay }};
var _autoAdvancing = false;

if (isPresenter) {
  // ===== PRESENTER MODE =====
  var ms = document.querySelectorAll("#pres-main section");
  var ns = document.querySelectorAll("#pres-next section");
  var nd = document.getElementById("pres-notes-text");
  var current = 0;
  var autoplayRunning = false;
  var autoplayTimer = null;
  var autoplayBtn = document.getElementById('pres-autoplay');

  function _rawShow(n) {
    if (n < 0 || n >= ms.length) return;
    for (var i = 0; i < ms.length; i++) ms[i].classList.toggle("active", i === n);
    for (var i = 0; i < ns.length; i++) ns[i].classList.toggle("active", i === n + 1);
    nd.textContent = slideNotes[n] || "No notes";
    current = n;
  }

  function show(n) {
    if (!_autoAdvancing) stopAutoplay();
    _rawShow(n);
    bc.postMessage({ slide: n });
  }

  function advance(delta) {
    var n = current + delta;
    if (n < 0 || n >= ms.length) return;
    show(n);
  }

  function startAutoplay() {
    if (AUTOPLAY_INTERVAL <= 0) return;
    autoplayRunning = true;
    if (autoplayBtn) autoplayBtn.textContent = '⏸';
    clearInterval(autoplayTimer);
    autoplayTimer = setInterval(function() { _autoAdvance(); }, AUTOPLAY_INTERVAL * 1000);
  }

  function stopAutoplay() {
    autoplayRunning = false;
    if (autoplayBtn) autoplayBtn.textContent = '⏯';
    clearInterval(autoplayTimer);
  }

  function toggleAutoplay() {
    if (autoplayRunning) { stopAutoplay(); bc.postMessage({ command: 'autoplay-stop' }); }
    else { startAutoplay(); bc.postMessage({ command: 'autoplay-start' }); }
  }

  function _autoAdvance() {
    if (current === ms.length - 1) {
      stopAutoplay();
      document.body.classList.add('autoplay-looping');
      setTimeout(function() {
        _autoAdvancing = true;
        show(0);
        _autoAdvancing = false;
        document.body.classList.remove('autoplay-looping');
        startAutoplay();
      }, 400);
      return;
    }
    _autoAdvancing = true;
    advance(1);
    _autoAdvancing = false;
  }

  if (autoplayBtn) autoplayBtn.addEventListener('click', toggleAutoplay);

  var bc = new BroadcastChannel('slidr-' + document.title);
  bc.onmessage = function(e) {
    if (e.data.slide !== undefined && e.data.slide !== current) { _rawShow(e.data.slide); }
    if (e.data.command === 'autoplay-start') { startAutoplay(); }
    if (e.data.command === 'autoplay-stop') { stopAutoplay(); }
  };
  show(0);

  document.getElementById('pres-main').addEventListener('click', function() { advance(1); });
  document.getElementById('pres-main').addEventListener('contextmenu', function(e) {
    e.preventDefault(); advance(-1);
  });

  var wheelCooldown = 0;
  document.getElementById('pres-main').addEventListener('wheel', function(e) {
    if (Math.abs(e.deltaY) < 10) return;
    var now = Date.now();
    if (now - wheelCooldown < 500) return;
    wheelCooldown = now;
    advance(e.deltaY > 0 ? 1 : -1);
  }, { passive: true });

  document.addEventListener('keydown', function(e) {
    if (KEYS_FWD.includes(e.key)) {
      e.preventDefault(); advance(1);
    } else if (KEYS_BACK.includes(e.key)) {
      e.preventDefault(); advance(-1);
    } else if (e.key === 'Home') {
      e.preventDefault(); show(0);
    } else if (e.key === 'End') {
      e.preventDefault(); show(ms.length - 1);
    } else if (e.key === 'q') {
      window.close();
    }
  });

} else {
  // ===== MAIN VIEW MODE =====
  var slides = document.querySelectorAll('body > section');
  var total = slides.length;
  if (total === 0) throw new Error('no slides found');
  var current = 0;
  var counter = document.getElementById('slidr-counter');
  var prevBtn = document.getElementById('slidr-prev');
  var nextBtn = document.getElementById('slidr-next');
  var presenterWindow = null;
  var autoplayRunning = false;
  var autoplayTimer = null;
  var autoplayBtn = document.getElementById('slidr-autoplay');

  function setScale() {
    var sw = {{ slide_w }}, sh = {{ slide_h }};
    var scale = Math.min(window.innerWidth / sw, window.innerHeight / sh);
    document.documentElement.style.setProperty('--s', scale);
  }
  setScale();
  window.addEventListener('resize', setScale);

  var _outTimer = 0;
  function _rawShow(n) {
    if (n < 0 || n >= total) return;
    var prev = slides[current];
    for (var i = 0; i < slides.length; i++) slides[i].classList.remove('outgoing');
    clearTimeout(_outTimer);
    if (prev && prev !== slides[n] && prev.hasAttribute('data-transition') && prev.getAttribute('data-transition') !== 'none') {
      prev.classList.add('outgoing');
    }
    prev && prev.classList.remove('active');
    current = n;
    if (slides[current].classList.contains('pre-render')) {
      slides[current].style.cssText = '';
    }
    slides[current].classList.add('active');
    slides[current].offsetHeight;
    var next = slides[current + 1];
    if (next && !next.classList.contains('pre-render')) {
      next.classList.add('pre-render');
      next.style.cssText = 'display:flex!important;opacity:0!important;pointer-events:none!important;z-index:-2!important';
    }
    if (prev && prev.classList.contains('outgoing')) {
      _outTimer = setTimeout(function() { prev.classList.remove('outgoing'); }, 400);
    }
    if (counter) counter.textContent = (current + 1) + ' / ' + total;
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.disabled = current === total - 1;
    try { localStorage.setItem('slidr-slide-' + document.title, current); } catch(e) {}
  }

  var show = function(n) {
    if (!_autoAdvancing) stopAutoplay();
    _rawShow(n);
    bc.postMessage({ slide: n });
  };

  for (var i = 0; i < slides.length; i++) {
    var imgs = slides[i].querySelectorAll('img');
    for (var j = 0; j < imgs.length; j++) {
      var src = imgs[j].getAttribute('src');
      if (src) (new Image()).src = src;
    }
  }

  var bc = new BroadcastChannel('slidr-' + document.title);
  bc.onmessage = function(e) {
    if (e.data.slide !== undefined && e.data.slide !== current) { stopAutoplay(); _rawShow(e.data.slide); }
    if (e.data.command === 'autoplay-start') { startAutoplay(); }
    if (e.data.command === 'autoplay-stop') { stopAutoplay(); }
  };

  function startAutoplay() {
    if (AUTOPLAY_INTERVAL <= 0) return;
    autoplayRunning = true;
    if (autoplayBtn) autoplayBtn.textContent = '⏸';
    clearInterval(autoplayTimer);
    autoplayTimer = setInterval(function() { _autoAdvance(); }, AUTOPLAY_INTERVAL * 1000);
  }

  function stopAutoplay() {
    autoplayRunning = false;
    if (autoplayBtn) autoplayBtn.textContent = '⏯';
    clearInterval(autoplayTimer);
  }

  function toggleAutoplay() {
    if (autoplayRunning) { stopAutoplay(); bc.postMessage({ command: 'autoplay-stop' }); }
    else { startAutoplay(); bc.postMessage({ command: 'autoplay-start' }); }
  }

  function _autoAdvance() {
    if (current === total - 1) {
      stopAutoplay();
      document.body.classList.add('autoplay-looping');
      setTimeout(function() {
        _autoAdvancing = true;
        show(0);
        _autoAdvancing = false;
        document.body.classList.remove('autoplay-looping');
        startAutoplay();
      }, 400);
      return;
    }
    _autoAdvancing = true;
    show(current + 1);
    _autoAdvancing = false;
  }

  if (autoplayBtn) autoplayBtn.addEventListener('click', toggleAutoplay);

  var stored = null;
  try { stored = parseInt(localStorage.getItem('slidr-slide-' + document.title), 10); } catch(e) {}
  show(isNaN(stored) ? 0 : Math.min(stored, total - 1));

  if (prevBtn) prevBtn.addEventListener('click', function() { show(current - 1); });
  if (nextBtn) nextBtn.addEventListener('click', function() { show(current + 1); });

  var fsBtn = document.getElementById('slidr-fullscreen');
  if (fsBtn) fsBtn.addEventListener('click', function() {
    if (!document.fullscreenElement) { document.documentElement.requestFullscreen(); }
    else { document.exitFullscreen(); }
  });

  document.addEventListener('keydown', function(e) {
    if (e.ctrlKey || e.metaKey) return;
    if (KEYS_BACK.includes(e.key)) {
      e.preventDefault(); show(current - 1);
    } else if (KEYS_FWD.includes(e.key)) {
      e.preventDefault(); show(current + 1);
    } else if (e.key === 'Home') {
      e.preventDefault(); show(0);
    } else if (e.key === 'End') {
      e.preventDefault(); show(total - 1);
    } else if (e.key === 'f') {
      if (!document.fullscreenElement) { document.documentElement.requestFullscreen(); }
      else { document.exitFullscreen(); }
    } else if (e.key === 'q') {
      if (presenterWindow && !presenterWindow.closed) presenterWindow.close();
    } else if (e.key === 'p') {
      e.preventDefault(); openPresenter();
    }
  });

  document.addEventListener('click', function(e) {
    var t = e.target;
    if (t.closest('button, a, input, textarea, select, #slidr-nav, #presenter-panel')) return;
    if (window.getSelection().toString()) return;
    show(current + 1);
  });

  document.addEventListener('contextmenu', function(e) {
    if (window.getSelection().toString()) return;
    e.preventDefault();
    show(current - 1);
  });

  var wheelCooldown = 0;
  document.addEventListener('wheel', function(e) {
    if (Math.abs(e.deltaY) < 10) return;
    var now = Date.now();
    if (now - wheelCooldown < 500) return;
    wheelCooldown = now;
    show(e.deltaY > 0 ? current + 1 : current - 1);
  }, { passive: true });

  var navBar = document.getElementById('slidr-nav');
  var hideTimer = null;
  function resetHideTimer() {
    if (navBar) navBar.classList.remove('hidden');
    clearTimeout(hideTimer);
    if (document.fullscreenElement) {
      hideTimer = setTimeout(function() { if (navBar) navBar.classList.add('hidden'); }, 1000);
    }
  }
  document.addEventListener('fullscreenchange', function() {
    if (document.fullscreenElement) { resetHideTimer(); }
    else { if (navBar) navBar.classList.remove('hidden'); clearTimeout(hideTimer); }
  });
  document.addEventListener('mousemove', resetHideTimer);

  function openPresenter() {
    if (presenterWindow && !presenterWindow.closed) { presenterWindow.focus(); return; }
    presenterWindow = window.open(window.location.href, 'slidr-presenter', 'width={{ slide_w }},height={{ slide_h }}');
    setTimeout(function() { if (presenterWindow) presenterWindow.focus(); }, 500);
  }

  var presenterBtn = document.getElementById('slidr-presenter');
  if (presenterBtn) presenterBtn.addEventListener('click', openPresenter);
}
