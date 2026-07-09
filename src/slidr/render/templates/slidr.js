// slidr presentation controller -- shared between main and presenter views

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

show(0);

if (prevBtn) prevBtn.addEventListener('click', function() { show(current - 1); });
if (nextBtn) nextBtn.addEventListener('click', function() { show(current + 1); });

// Fullscreen
var fsBtn = document.getElementById('slidr-fullscreen');
if (fsBtn) fsBtn.addEventListener('click', function() {
  if (!document.fullscreenElement) { document.documentElement.requestFullscreen(); }
  else { document.exitFullscreen(); }
});

// Keyboard navigation
document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') {
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

// Mouse wheel
document.addEventListener('wheel', function(e) {
  e.preventDefault();
  if (e.deltaY > 0) show(current + 1);
  else show(current - 1);
}, { passive: false });

// Presenter window
var presenterBtn = document.getElementById('slidr-presenter');
if (presenterBtn) presenterBtn.addEventListener('click', function() {
  if (presenterWindow && !presenterWindow.closed) { presenterWindow.focus(); return; }
  var pUrl = window.location.pathname.replace('.html', '.presenter.html');
  presenterWindow = window.open(pUrl, 'slidr-presenter', 'width={{ slide_w }},height={{ slide_h }}');
  setTimeout(function() { if (presenterWindow) presenterWindow.focus(); }, 500);
});

// Bidirectional sync via slidrCurrent property
var _sc = 0;
Object.defineProperty(window, 'slidrCurrent', {
  get: function() { return _sc; },
  set: function(n) { _sc = n; show(n); }
});
var _origShow = show;
show = function(n) { _origShow(n); _sc = n; };
