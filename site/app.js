/* Inside Joke project site. Reads assets/data.json and renders the format cards.
   Without JS, index.html already shows Dana's 5 GIFs with alt text. */
(function () {
  "use strict";

  var FORMATS = [
    { key: "meme", name: "Meme Desk", shape: "Square", w: 480, h: 480,
      pitch: "An original 2-beat meme: setup on top, punchline drops in. Classic meme grammar, new art every time." },
    { key: "headline", name: "Future Headline", shape: "Front page", w: 480, h: 624,
      pitch: "A trade-paper front page dated 6 months ahead, reporting the win this person is working toward. Clearly marked as an imagined edition." },
    { key: "comic", name: "Three-Panel Day", shape: "Strip", w: 720, h: 330,
      pitch: "A 3-panel strip about one real pain from their role, ending on a kind twist. Panels reveal one at a time." },
    { key: "card", name: "Collector Card", shape: "Card", w: 400, h: 560,
      pitch: "A holographic collectible card for their professional persona: nickname, stats, special move. Shimmer loops forever." },
    { key: "reply", name: "Reply Reaction", shape: "Square", w: 480, h: 480,
      pitch: "Reacts to what the prospect actually said in the thread. Their words become the setup; an animated prop delivers the beat." }
  ];
  var BY_KEY = {};
  FORMATS.forEach(function (f) { BY_KEY[f.key] = f; });

  var MECH = {
    callback: "Callback: builds the joke on their own words from the conversation.",
    incongruity: "Incongruity: sets up the expected version of their day, then swaps in a surprising outcome.",
    exaggeration: "Exaggeration: blows one real pain from their facts up to absurd scale.",
    personification: "Personification: a tool, meeting or metric from their job has feelings.",
    understatement: "Understatement: describes a big job pain in a calm, tiny way."
  };

  var HERO = [
    { p: "marcus", f: "headline" },
    { p: "dana", f: "card" },
    { p: "marcus", f: "reply" },
    { p: "dana", f: "meme" },
    { p: "marcus", f: "card" },
    { p: "dana", f: "reply" }
  ];
  var HERO_MS = 7000;

  var state = { data: null, prospect: "dana", paused: false, heroIdx: 0, heroTimer: null };
  var rm = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };

  function still() { return state.paused || rm.matches; }
  function src(p, f) { return "assets/" + p + "/" + f + (still() ? ".png" : ".gif"); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function icon(id) { return '<svg aria-hidden="true"><use href="#' + id + '"/></svg>'; }
  function pad(n) { return (n < 10 ? "0" : "") + n; }

  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }
  function load(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  /* ---------- on-image words ---------- */
  function wordRows(text) {
    var rows = [];
    Object.keys(text || {}).forEach(function (k) {
      var v = text[k];
      if (Array.isArray(v)) {
        v.forEach(function (item, i) {
          if (item && typeof item === "object") {
            rows.push([k + " " + (i + 1), (item.label || item.name || "") + ": " + (item.value != null ? item.value : item.text || "")]);
          } else {
            rows.push([k + " " + (i + 1), item]);
          }
        });
      } else if (v && typeof v === "object") {
        rows.push([k, (v.name ? v.name + ". " : "") + (v.text || "")]);
      } else {
        rows.push([k, v]);
      }
    });
    return rows;
  }

  /* ---------- scores ---------- */
  function scoresHtml(s) {
    if (!s) {
      return '<p class="scores-missing">No judge scores for this format in this run. The judge\'s reply was cut off, so the first draft that passed the code checks shipped. The judge is advisory by design, and in the study a person reads every item before it is sent.</p>';
    }
    var dims = [["funny", "Funny"], ["specific", "Specific"], ["kind", "Kind"], ["glance", "Glance"]];
    var bars = dims.map(function (d) {
      var v = Number(s[d[0]]) || 0;
      return '<dt>' + d[1] + '</dt><dd><div class="track' + (d[0] === "kind" ? " kind" : "") + '" role="img" aria-label="' + d[1] + ' ' + v + ' out of 10"><i style="width:' + (v * 10) + '%"></i></div></dd><dd class="v">' + v + '</dd>';
    }).join("");
    return '<div class="scores">' +
      '<div class="scores-head"><span class="label">Judge scores, 1 to 10</span><span class="total num">' + Number(s.total).toFixed(2) + ' <small>weighted</small></span></div>' +
      '<dl class="bars">' + bars + '</dl>' +
      '<p class="scores-note">Weights: funny 35%, specific 30%, glance 20%, kind 15%. The red tick on kind marks the floor of 7.</p>' +
      '</div>';
  }

  /* ---------- one card ---------- */
  function cardHtml(pKey, f, i) {
    var meta = BY_KEY[f];
    var r = state.data.prospects[pKey].formats[f];
    var ground = (r.grounding || []).map(function (g) {
      return '<li><span>' + esc(g.fact) + '</span><span class="field">' + esc(g.field) + '</span></li>';
    }).join("");
    var words = wordRows(r.text).map(function (w) {
      return '<li><b>' + esc(w[0]) + '</b>' + esc(w[1]) + '</li>';
    }).join("");
    return '<article class="fmt" id="fmt-' + f + '" aria-labelledby="fmt-' + f + '-t">' +
      '<div class="fmt-media"><img src="' + src(pKey, f) + '" data-p="' + pKey + '" data-f="' + f + '" width="' + meta.w + '" height="' + meta.h + '" alt="' + esc(r.alt_text) + '" loading="lazy" decoding="async"></div>' +
      '<div class="fmt-body">' +
        '<div class="fmt-kicker"><span class="n">' + pad(i + 1) + '</span><span class="k">' + esc(meta.shape) + ' &middot; ' + esc(r.gif_kb) + ' KB &middot; ' + Number(r.seconds).toFixed(1) + ' s</span></div>' +
        '<h3 id="fmt-' + f + '-t">' + esc(meta.name) + '</h3>' +
        '<p class="fmt-pitch">' + esc(meta.pitch) + '</p>' +
        '<div class="email"><div class="email-head">' + icon("i-mail") + 'Email line it wrote</div><p>' + esc(r.email_line) + '</p></div>' +
        scoresHtml(r.scores) +
        '<details class="why"><summary>Why this joke' + icon("i-plus") + '</summary><div class="why-body">' +
          '<div class="why-row"><span>Mechanism</span><span>' + esc(MECH[r.mechanism] || r.mechanism) + '</span></div>' +
          '<div class="why-row"><span>Joke target</span><span>' + esc(r.joke_target) + '</span></div>' +
          '<div class="why-row"><span>Grounding</span><ul class="grounding" aria-label="Each personal detail and the input field it came from">' + ground + '</ul></div>' +
          '<div class="why-row"><span>Words drawn</span><ul class="words">' + words + '</ul></div>' +
          '<p class="meta-line">Art backend: ' + esc(r.art_backend) + ' &middot; ' + esc(r.gif_kb) + ' KB GIF &middot; ' + Number(r.seconds).toFixed(2) + ' s for this format</p>' +
        '</div></details>' +
      '</div></article>';
  }

  /* ---------- dossier ---------- */
  function dossierHtml(pKey) {
    var e = state.data.prospects[pKey];
    var p = e.prospect;
    var rows = [["industry", p.industry], ["linkedin_headline", p.linkedin_headline], ["notes", p.notes]];
    var dl = rows.filter(function (r) { return r[1]; }).map(function (r) {
      return '<div><dt>' + r[0] + '</dt><dd>' + esc(r[1]) + '</dd></div>';
    }).join("");
    if (e.context) dl += '<div class="ctx"><dt>conversation</dt><dd>' + esc(e.context) + '</dd></div>';
    return '<div class="dossier-id"><p class="eyebrow">Input file</p>' +
      '<h3>' + esc(p.first_name + " " + p.last_name) + '</h3>' +
      '<p class="role">' + esc(p.title) + ', ' + esc(p.company) + '</p>' +
      '<p class="dossier-run">All 5 formats in <b>' + Number(e.total_seconds).toFixed(1) + ' s</b> &middot; <b>$' + Number(e.cost_usd).toFixed(2) + '</b> total</p></div>' +
      '<dl class="dossier-fields">' + dl + '</dl>';
  }

  function renderProspect(pKey) {
    state.prospect = pKey;
    $("#dossier").innerHTML = dossierHtml(pKey);
    $("#cards").innerHTML = FORMATS.map(function (f, i) { return cardHtml(pKey, f.key, i); }).join("");
    $all("#prospect-switch [role=radio]").forEach(function (b) {
      var on = b.getAttribute("data-p") === pKey;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
  }

  /* ---------- switcher (radio group keyboard pattern) ---------- */
  function bindSwitch() {
    var group = $("#prospect-switch");
    var btns = $all("[role=radio]", group);
    btns.forEach(function (b, i) {
      b.addEventListener("click", function () {
        if (state.data) { renderProspect(b.getAttribute("data-p")); store("ij-prospect", b.getAttribute("data-p")); }
      });
      b.addEventListener("keydown", function (ev) {
        var d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
        if (!d) return;
        ev.preventDefault();
        var next = btns[(i + d + btns.length) % btns.length];
        next.focus();
        next.click();
      });
    });
  }

  /* ---------- hero carousel ---------- */
  function heroCaption(item) {
    var e = state.data.prospects[item.p];
    var p = e.prospect;
    var r = e.formats[item.f];
    return "<strong>" + esc(BY_KEY[item.f].name) + "</strong> for " + esc(p.first_name + " " + p.last_name) + ", " + esc(p.title) +
      " (fictional). Made in " + Number(r.seconds).toFixed(1) + " s.";
  }

  function showHero(idx) {
    state.heroIdx = (idx + HERO.length) % HERO.length;
    var item = HERO[state.heroIdx];
    var meta = BY_KEY[item.f];
    var r = state.data.prospects[item.p].formats[item.f];
    var img = $("#hero-img");
    var pic = $("#hero-pic");
    var source = pic && pic.querySelector("source");
    var apply = function () {
      if (source) source.srcset = "assets/" + item.p + "/" + item.f + ".png";
      img.src = src(item.p, item.f);
      img.width = meta.w; img.height = meta.h;
      img.alt = r.alt_text;
      img.classList.remove("is-fading");
    };
    if (still() || img.getAttribute("src") === src(item.p, item.f)) { apply(); } else { img.classList.add("is-fading"); setTimeout(apply, 220); }
    $("#hero-cap").innerHTML = heroCaption(item);
    $all("#hero-dots button").forEach(function (b, i) { b.setAttribute("aria-current", i === state.heroIdx ? "true" : "false"); });
  }

  function heroTick() {
    clearTimeout(state.heroTimer);
    if (still()) return;
    state.heroTimer = setTimeout(function () { showHero(state.heroIdx + 1); heroTick(); }, HERO_MS);
  }

  function buildHero() {
    var dots = $("#hero-dots");
    dots.innerHTML = HERO.map(function (h, i) {
      var p = state.data.prospects[h.p].prospect;
      return '<button type="button" aria-label="Show ' + esc(BY_KEY[h.f].name) + " for " + esc(p.first_name) + '" aria-current="' + (i === 0 ? "true" : "false") + '"></button>';
    }).join("");
    $all("button", dots).forEach(function (b, i) {
      b.addEventListener("click", function () { showHero(i); heroTick(); });
    });
    showHero(0);
    var stage = $(".stage");
    stage.addEventListener("mouseenter", function () { clearTimeout(state.heroTimer); });
    stage.addEventListener("mouseleave", heroTick);
    stage.addEventListener("focusin", function () { clearTimeout(state.heroTimer); });
    stage.addEventListener("focusout", heroTick);
    heroTick();
  }

  /* ---------- motion toggle ---------- */
  function applyMotion() {
    var btn = $("#motion-toggle");
    btn.setAttribute("aria-pressed", still() ? "true" : "false");
    $(".lbl", btn).textContent = still() ? "Play GIFs" : "Pause GIFs";
    btn.title = still() ? "Show animated GIFs" : "Show still posters instead of animated GIFs";
    $all("img[data-p][data-f]").forEach(function (img) { img.src = src(img.getAttribute("data-p"), img.getAttribute("data-f")); });
    if (state.data) {
      var h = HERO[state.heroIdx];
      $("#hero-img").src = src(h.p, h.f);
      heroTick();
    }
  }

  function bindMotion() {
    var btn = $("#motion-toggle");
    state.paused = load("ij-paused") === "1";
    btn.addEventListener("click", function () {
      if (rm.matches) {
        // Reduced motion is set at the OS level; keep stills and say so.
        btn.title = "Your system asks for reduced motion, so GIFs stay paused.";
        return;
      }
      state.paused = !state.paused;
      store("ij-paused", state.paused ? "1" : "0");
      applyMotion();
    });
    if (rm.addEventListener) rm.addEventListener("change", applyMotion);
    else if (rm.addListener) rm.addListener(applyMotion);
    applyMotion();
  }

  /* ---------- copy buttons ---------- */
  function bindCopy() {
    $all(".copy").forEach(function (b) {
      b.addEventListener("click", function () {
        var text = b.getAttribute("data-copy");
        var done = function () { b.classList.add("done"); setTimeout(function () { b.classList.remove("done"); }, 1400); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () {});
        }
      });
    });
  }

  /* ---------- boot ---------- */
  bindSwitch();
  bindMotion();
  bindCopy();

  fetch("assets/data.json", { credentials: "same-origin" })
    .then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
    .then(function (data) {
      state.data = data;
      var saved = load("ij-prospect");
      renderProspect(saved && data.prospects[saved] ? saved : "dana");
      buildHero();
      applyMotion();
    })
    .catch(function () {
      // Keep the static fallback cards that index.html ships with.
    });
})();
