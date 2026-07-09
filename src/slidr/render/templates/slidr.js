var isPresenter = window.name === 'slidr-presenter';
if (isPresenter) document.documentElement.classList.add('presenter');

var slideNotes = [{% for slide in slides %}"{{ slide.notes|e }}"{% if not loop.last %},{% endif %}{% endfor %}];

if (isPresenter) {
  // ===== PRESENTER MODE =====
  var ms = document.querySelectorAll("#pres-main section");
  var ns = document.querySelectorAll("#pres-next section");
  var nd = document.getElementById("pres-notes");
  var current = 0;

  function show(n) {
    if (n < 0 || n >= ms.length) return;
    for (var i = 0; i < ms.length; i++) ms[i].classList.toggle("active", i === n);
    for (var i = 0; i < ns.length; i++) ns[i].classList.toggle("active", i === n + 1);
    nd.textContent = slideNotes[n] || "No notes";
    current = n;
  }

  var bc = new BroadcastChannel('slidr-' + document.title);
  bc.onmessage = function(e) {
    if (e.data.slide !== undefined && e.data.slide !== current) show(e.data.slide);
  };
  show(0);

  function advance(delta) {
    var n = current + delta;
    if (n < 0 || n >= ms.length) return;
    show(n);
    bc.postMessage({ slide: n });
  }

  document.getElementById('pres-main').addEventListener('click', function() { advance(1); });
  document.getElementById('pres-main').addEventListener('contextmenu', function(e) {
    e.preventDefault(); advance(-1);
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'PageDown' || e.key === ' ') {
      e.preventDefault(); advance(1);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp' || e.key === 'Backspace') {
      e.preventDefault(); advance(-1);
    } else if (e.key === 'Home') {
      e.preventDefault(); show(0); bc.postMessage({ slide: 0 });
    } else if (e.key === 'End') {
      e.preventDefault(); show(ms.length - 1); bc.postMessage({ slide: ms.length - 1 });
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

  function setScale() {
    var sw = {{ slide_w }}, sh = {{ slide_h }};
    var scale = Math.min(window.innerWidth / sw, window.innerHeight / sh);
    document.documentElement.style.setProperty('--s', scale);
  }
  setScale();
  window.addEventListener('resize', setScale);

  function show(n) {
    if (n < 0 || n >= total) return;
    slides[current].classList.remove('active');
    current = n;
    slides[current].classList.add('active');
    if (counter) counter.textContent = (current + 1) + ' / ' + total;
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.disabled = current === total - 1;
  }

  var bc = new BroadcastChannel('slidr-' + document.title);
  var _origShow = show;
  show = function(n) {
    _origShow(n);
    bc.postMessage({ slide: n });
  };
  bc.onmessage = function(e) {
    if (e.data.slide !== undefined && e.data.slide !== current) _origShow(e.data.slide);
  };

  show(0);

  if (prevBtn) prevBtn.addEventListener('click', function() { show(current - 1); });
  if (nextBtn) nextBtn.addEventListener('click', function() { show(current + 1); });

  var fsBtn = document.getElementById('slidr-fullscreen');
  if (fsBtn) fsBtn.addEventListener('click', function() {
    if (!document.fullscreenElement) { document.documentElement.requestFullscreen(); }
    else { document.exitFullscreen(); }
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp' || e.key === 'Backspace') {
      e.preventDefault(); show(current - 1);
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'PageDown' || e.key === ' ') {
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
    }
  });

  document.addEventListener('click', function(e) {
    var t = e.target;
    if (t.closest('button, a, input, textarea, select, #slidr-nav, #presenter-panel')) return;
    show(current + 1);
  });

  document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
    show(current - 1);
  });

  var presenterBtn = document.getElementById('slidr-presenter');
  if (presenterBtn) presenterBtn.addEventListener('click', function() {
    if (presenterWindow && !presenterWindow.closed) { presenterWindow.focus(); return; }
    presenterWindow = window.open(window.location.href, 'slidr-presenter', 'width={{ slide_w }},height={{ slide_h }}');
    setTimeout(function() { if (presenterWindow) presenterWindow.focus(); }, 500);
  });
}
