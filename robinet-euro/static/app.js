// ===== Robinet € — logique frontend =====
const API = {
  token: localStorage.getItem("rb_token") || null,

  async req(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = "Bearer " + this.token;
    const res = await fetch("/api/" + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      if (res.status === 401) { this.logout(); }
      throw new Error(data.error || "Erreur réseau");
    }
    return data;
  },
  get(p) { return this.req("GET", p); },
  post(p, b) { return this.req("POST", p, b || {}); },
  logout() {
    this.token = null;
    localStorage.removeItem("rb_token");
    showAuth();
  },
};

// ===== helpers =====
const eur = (c) => (c / 100).toFixed(2).replace(".", ",") + " €";

function toast(msg, type) {
  const c = document.getElementById("toast-container");
  const t = document.createElement("div");
  t.className = "toast" + (type ? " " + type : "");
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3500);
  if (type === "gold") playCashSound();
}

function playCashSound() {
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!window.__cashAudio) window.__cashAudio = new AC();
    const ctx = window.__cashAudio;
    if (ctx.state === "suspended") ctx.resume();
    const now = ctx.currentTime;
    const notes = [987.8, 1318.5, 1760];
    notes.forEach((freq, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "triangle";
      o.frequency.setValueAtTime(freq, now + i * 0.06);
      g.gain.setValueAtTime(0.0001, now);
      g.gain.exponentialRampToValueAtTime(0.14, now + 0.015 + i * 0.06);
      g.gain.exponentialRampToValueAtTime(0.0001, now + 0.22 + i * 0.07);
      o.connect(g);
      g.connect(ctx.destination);
      o.start(now + i * 0.06);
      o.stop(now + 0.28 + i * 0.07);
    });
  } catch (e) {}
}

function showAuth() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
}

function showApp() {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
}

// ===== PUB OBLIGATOIRE AVANT CHAQUE TÂCHE =====
const AD_LINKS = [
  "https://www.profitableratecpmnetwork.com/c7qfe4dikr?key=69d1f3bf8ac6de7391cf3eaa1d77e1a1",
  "https://www.profitableratecpmnetwork.com/nfv5bb5tx4?key=f216c6e41e54bde80d762ad61ed53c11",
  "https://www.profitableratecpmnetwork.com/cyrm5fgis?key=517bf4c2047981143f64fe418a024d00",
  "https://www.profitableratecpmnetwork.com/ewpy9gtfrn?key=49586d19186a4f51110d48c141351fa4",
  "https://www.profitableratecpmnetwork.com/z0dfk8jc?key=f1bff217207649b313c23ecaaab0bc1e",
  "https://www.profitableratecpmnetwork.com/xw1r7mp1t8?key=0836c2f424ad47c911b20c8ae6e4e77e",
  "https://www.profitableratecpmnetwork.com/pu5ce9ayg?key=7fa63f6495b6ee7409066dd74d0e1e17",
  "https://www.profitableratecpmnetwork.com/qiwe85grc?key=83226b59982f37eb31bf5efafb1a5a29",
  "https://www.profitableratecpmnetwork.com/b90cx5y3?key=0cb3e87f53b90373a65859342c1ab694",
  "https://www.profitableratecpmnetwork.com/m5fcdbri?key=9fc5e54ac541cee2fdd113a2d518ac8e",
];
const AD_SECONDS = 15;
let adGateBusy = false;
let adLinkI = 0;
function openAdLink() {
  const url = AD_LINKS[adLinkI % AD_LINKS.length];
  adLinkI += 1;
  try { window.open(url, "_blank", "noopener,noreferrer"); } catch (e) {}
}

function waitAd() {
  return new Promise((resolve) => {
    if (currentUser && currentUser.vip) { resolve(true); return; }
    if (adGateBusy) { resolve(false); return; }
    adGateBusy = true;
    const modal = document.getElementById("ad-gate-modal");
    const btn = document.getElementById("ad-gate-continue");
    const timer = document.getElementById("ad-gate-timer");
    const frame = document.getElementById("ad-gate-frame");
    modal.classList.remove("hidden");
    btn.disabled = true;
    btn.textContent = "⏳ Regarde la pub…";
    frame.src = "ad-gate.html?t=" + Date.now();
    openAdLink();
    let left = AD_SECONDS;
    timer.textContent = left + " s";
    const iv = setInterval(() => {
      left -= 1;
      timer.textContent = Math.max(0, left) + " s";
      if (left <= 0) {
        clearInterval(iv);
        btn.disabled = false;
        btn.textContent = "✅ Continuer";
      }
    }, 1000);
    btn.onclick = () => {
      if (btn.disabled) return;
      openAdLink();
      clearInterval(iv);
      frame.src = "about:blank";
      modal.classList.add("hidden");
      adGateBusy = false;
      resolve(true);
    };
  });
}


// ===== AUTH =====
let authMode = "login";
document.querySelectorAll(".auth-tab").forEach((b) => {
  b.addEventListener("click", () => {
    authMode = b.dataset.mode;
    document.querySelectorAll(".auth-tab").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    document.getElementById("email-field").style.display = authMode === "register" ? "block" : "none";
    document.getElementById("auth-submit").textContent = authMode === "register" ? "Créer mon compte" : "Se connecter";
    document.getElementById("auth-error").classList.add("hidden");
  });
});

document.getElementById("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = document.getElementById("auth-error");
  err.classList.add("hidden");
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const email = document.getElementById("email").value.trim();
  try {
    if (authMode === "register") {
      const r = await API.post("register", { username, password, email });
      API.token = r.token;
      localStorage.setItem("rb_token", r.token);
      toast(r.message || "Compte créé !", "gold");
    } else {
      const r = await API.post("login", { username, password });
      API.token = r.token;
      localStorage.setItem("rb_token", r.token);
      toast("Bienvenue, " + username + " !");
    }
    showApp();
    await refresh();
  } catch (ex) {
    err.textContent = ex.message;
    err.classList.remove("hidden");
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  try { await API.post("logout"); } catch (e) {}
  API.logout();
});

// ===== NAVIGATION =====
document.querySelectorAll(".nav-btn").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.getElementById("tab-" + b.dataset.tab).classList.add("active");
    if (b.dataset.tab === "admin") loadAdmin();
    if (b.dataset.tab === "adult") syncAdultGate();
  });
});

// ===== REFRESH =====
let currentUser = null;

async function refresh() {
  const d = await API.get("dashboard");
  currentUser = d.user;
  renderDashboard(d);
}

function renderDashboard(d) {
  const u = d.user;
  document.getElementById("top-username").textContent = u.username;
  document.getElementById("hero-name").textContent = u.username;
  document.getElementById("top-balance").textContent = eur(u.balance);
  document.getElementById("hero-balance").textContent = (u.balance / 100).toFixed(2).replace(".", ",");
  document.getElementById("stat-today").textContent = eur(u.earned_today);
  document.getElementById("stat-total").textContent = eur(u.total_earned);
  document.getElementById("stat-dailycap").textContent = eur(u.daily_cap);

  const pill = document.getElementById("vip-pill");
  const st = document.getElementById("vip-status");
  if (u.vip) {
    pill.classList.remove("hidden");
    const d = new Date(u.vip_until);
    st.textContent = "Sans pub jusqu’au " + d.toLocaleString("fr-FR");
  } else {
    pill.classList.add("hidden");
    st.textContent = "Pas d’abonnement.";
  }

  // progression vers retrait
  const pct = Math.min(100, (u.balance / u.min_withdraw) * 100);
  document.getElementById("progress-fill").style.width = pct + "%";
  document.getElementById("progress-label").textContent =
    eur(u.balance) + " / " + eur(u.min_withdraw) + " pour retirer";

  // leaderboard
  const lb = document.getElementById("leaderboard");
  lb.innerHTML = "";
  d.leaderboard.forEach((r) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="lb-name">${escapeHtml(r.username)}</span><span class="lb-earn">${eur(r.earned)}</span>`;
    lb.appendChild(li);
  });

  // offres
  renderOffers(d.offers);

  if (d.adult) updateAdultUI(d.adult);
  if (d.clicks) updateClickUI(d.clicks);
  if (!d.intro_done) maybeShowIntro();

  // robinet
  if (d.faucet) setupFaucet(d.faucet);
  startFaucetTimer();

  // historique
  renderHistory(d.recent);

  // retrait
  document.getElementById("wd-balance").textContent = eur(u.balance);
  refreshGiftLocks();

  // admin nav
  document.getElementById("admin-nav").style.display = u.is_admin ? "block" : "none";
}

// ===== OFFERS =====
let offers = [];
let offerFilter = "all";

function renderOffers(list) {
  offers = list;
  const grid = document.getElementById("offer-grid");
  grid.innerHTML = "";
  const filtered = list.filter((o) => offerFilter === "all" || o.type === offerFilter);
  if (filtered.length === 0) {
    grid.innerHTML = '<p class="muted">Aucune offre dans cette catégorie.</p>';
    return;
  }
  filtered.forEach((o) => {
    const el = document.createElement("div");
    el.className = "offer" + (o.done ? " done" : "");
    const icon = o.type === "video" ? "🎬" : o.type === "ptc" ? "🖱️" : o.type === "cpa" ? "🤝" : "📝";
    const typeLabel = o.type === "video" ? "Vidéo" : o.type === "ptc" ? "Clic" : o.type === "cpa" ? "Partenaire" : "Sondage";
    el.innerHTML = `
      <div class="offer-icon">${icon}</div>
      <div class="offer-title">${escapeHtml(o.title)}</div>
      <div class="offer-desc">${escapeHtml(o.description)}</div>
      <div class="offer-foot">
        <span class="offer-reward">+${eur(o.reward_cents)}</span>
        <button class="offer-btn" ${o.done ? "disabled" : ""}>${o.done ? "✓ Fait" : "Commencer"}</button>
      </div>
    `;
    el.querySelector(".offer-btn").addEventListener("click", async () => {
      if (!(await waitAd())) return;
      if (o.type === "video") openVideo(o);
      else if (o.type === "ptc") openPtc(o);
      else if (o.type === "cpa") openCpa(o);
      else openSurvey(o);
    });
    grid.appendChild(el);
  });
}

document.querySelectorAll(".chip").forEach((c) => {
  c.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    c.classList.add("active");
    offerFilter = c.dataset.filter;
    renderOffers(offers);
  });
});

// ===== VIDEO =====
let videoTimerInt = null;
function openVideo(o) {
  const m = document.getElementById("video-modal");
  m.classList.remove("hidden");
  document.getElementById("video-brand").textContent = "🎬";
  document.getElementById("video-title").textContent = o.title;
  document.getElementById("video-reward-text").textContent = "Récompense : +" + eur(o.reward_cents);
  const dur = o.duration_seconds || 20;
  const claim = document.getElementById("video-claim");
  const fill = document.getElementById("video-bar-fill");
  const timer = document.getElementById("video-timer");
  let elapsed = 0;
  claim.disabled = true;
  claim.textContent = "⏳ Encore en lecture…";
  fill.style.width = "0%";

  clearInterval(videoTimerInt);
  videoTimerInt = setInterval(() => {
    elapsed += 0.1;
    const pct = Math.min(100, (elapsed / dur) * 100);
    fill.style.width = pct + "%";
    timer.textContent = Math.ceil(Math.max(0, dur - elapsed)) + " s";
    if (elapsed >= dur) {
      clearInterval(videoTimerInt);
      claim.disabled = false;
      claim.textContent = `✅ Valider +${eur(o.reward_cents)}`;
    }
  }, 100);

  claim.onclick = async () => {
    try {
      const r = await API.post("finish_view", { offer_id: o.id });
      closeVideo();
      toast("+" + eur(r.reward) + " gagné ! 🎉", "gold");
      await refresh();
    } catch (ex) {
      closeVideo();
      toast(ex.message, "err");
    }
  };
}
function closeVideo() {
  clearInterval(videoTimerInt);
  document.getElementById("video-modal").classList.add("hidden");
}

// ===== PTC =====
let ptcTimerInt = null;
function openPtc(o) {
  const m = document.getElementById("ptc-modal");
  m.classList.remove("hidden");
  document.getElementById("ptc-title").textContent = o.title;
  document.getElementById("ptc-headline").textContent = o.title;
  document.getElementById("ptc-url").textContent = slug(o.title) + ".com";
  document.getElementById("ptc-banner").textContent = "✨ " + o.title + " ✨";
  const dur = o.duration_seconds || 15;
  const claim = document.getElementById("ptc-claim");
  const t = document.getElementById("ptc-time");
  let remaining = dur;
  claim.disabled = true;
  claim.textContent = "⏳ Patiente encore…";
  t.textContent = dur + " s";

  clearInterval(ptcTimerInt);
  ptcTimerInt = setInterval(() => {
    remaining -= 1;
    t.textContent = remaining + " s";
    if (remaining <= 0) {
      clearInterval(ptcTimerInt);
      claim.disabled = false;
      claim.textContent = `✅ Valider +${eur(o.reward_cents)}`;
    }
  }, 1000);

  claim.onclick = async () => {
    try {
      const r = await API.post("click_ptc", { offer_id: o.id });
      closePtc();
      toast("+" + eur(r.reward) + " gagné ! 🎉", "gold");
      await refresh();
    } catch (ex) {
      closePtc();
      toast(ex.message, "err");
    }
  };
}
function closePtc() {
  clearInterval(ptcTimerInt);
  document.getElementById("ptc-modal").classList.add("hidden");
}

// ===== SURVEY =====
const surveyQuestions = {
  "Sondage rapide — Tes habitudes de consommation": [
    { q: "À quelle fréquence fais-tu des achats en ligne ?", opts: ["Tous les jours", "Chaque semaine", "Chaque mois", "Rarement"] },
    { q: "Quel est ton moyen de paiement préféré ?", opts: ["Carte bancaire", "PayPal", "Espèces", "Mobile"] },
    { q: "Qu'est-ce qui influence le plus tes achats ?", opts: ["Le prix", "Les avis", "La marque", "Les promos"] },
  ],
  "Sondage — La musique que tu écoutes": [
    { q: "Quel genre écoutes-tu le plus ?", opts: ["Pop", "Rap", "Électro", "Autre"] },
    { q: "Où écoutes-tu de la musique ?", opts: ["Spotify", "YouTube", "Radio", "Autre"] },
    { q: "Combien d'heures par jour ?", opts: ["Moins d'1h", "1 à 3h", "Plus de 3h"] },
  ],
};
const DEFAULT_SURVEY = [
  { q: "Es-tu satisfait de ce site ?", opts: ["Oui", "Non", "Moyen"] },
  { q: "Que voudrais-tu améliorer ?", opts: ["Plus d'offres", "Retraits plus rapides", "Bonus", "Rien"] },
  { q: "Recommanderais-tu le site ?", opts: ["Oui", "Non", "Peut-être"] },
];

let currentSurveyOffer = null;
function openSurvey(o) {
  currentSurveyOffer = o;
  const m = document.getElementById("survey-modal");
  m.classList.remove("hidden");
  document.getElementById("survey-title").textContent = o.title;
  const qs = surveyQuestions[o.title] || DEFAULT_SURVEY;
  const box = document.getElementById("survey-questions");
  box.innerHTML = "";
  qs.forEach((q, i) => {
    const d = document.createElement("div");
    d.className = "sq";
    d.innerHTML = `<h4>${i + 1}. ${escapeHtml(q.q)}</h4>` +
      q.opts.map((opt) => `<label><input type="radio" name="q${i}" value="${escapeHtml(opt)}"> ${escapeHtml(opt)}</label>`).join("");
    box.appendChild(d);
  });
  document.getElementById("survey-submit").onclick = async () => {
    const answered = qs.every((_, i) => document.querySelector(`input[name="q${i}"]:checked`));
    if (!answered) { toast("Réponds à toutes les questions.", "err"); return; }
    try {
      const r = await API.post("survey_submit", { survey_id: o.id });
      document.getElementById("survey-modal").classList.add("hidden");
      toast("+" + eur(r.reward) + " gagné ! 🎉", "gold");
      await refresh();
    } catch (ex) {
      document.getElementById("survey-modal").classList.add("hidden");
      toast(ex.message, "err");
    }
  };
}

// ===== ROBINET € =====
let faucetCooldown = 180;      // secondes
let faucetLastClaim = 0;       // timestamp ms du dernier claim
let faucetInterval = null;
let faucetBusy = false;

function fmtSec(s) {
  s = Math.max(0, Math.round(s));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m} min ${String(r).padStart(2, "0")} s` : `${r} s`;
}

function setupFaucet(faucet) {
  faucetCooldown = faucet.cooldown || 30;
  faucetLastClaim = faucet.last_claim || 0;
  const cd = document.getElementById("faucet-cd");
  if (cd) cd.textContent = fmtSec(faucetCooldown);
  updateFaucetUI();
}

function faucetRemaining() {
  const elapsed = (Date.now() - faucetLastClaim) / 1000;
  return faucetCooldown - elapsed;
}

function updateFaucetUI() {
  const btn = document.getElementById("faucet-btn");
  const timer = document.getElementById("faucet-timer");
  const stream = document.getElementById("faucet-stream");
  const remain = faucetRemaining();
  if (remain <= 0) {
    btn.disabled = false;
    btn.textContent = "💧 Ouvrir le robinet";
    timer.textContent = "✅ Le robinet est prêt ! Clique pour gagner.";
    timer.className = "faucet-timer ready";
    stream.classList.add("on");
  } else {
    btn.disabled = true;
    btn.textContent = "⏳ Rechargement…";
    timer.textContent = "Prochaine ouverture dans " + fmtSec(remain) + ".";
    timer.className = "faucet-timer";
    stream.classList.remove("on");
  }
}

function startFaucetTimer() {
  if (faucetInterval) clearInterval(faucetInterval);
  faucetInterval = setInterval(updateFaucetUI, 1000);
}

function spawnCoins() {
  const bowl = document.getElementById("faucet-bowl");
  const rect = bowl.getBoundingClientRect();
  const card = document.querySelector(".faucet-card");
  const emojis = ["🪙", "💶", "💶", "🪙", "✨"];
  for (let i = 0; i < 8; i++) {
    setTimeout(() => {
      const c = document.createElement("span");
      c.className = "coin-fall";
      c.textContent = emojis[Math.floor(Math.random() * emojis.length)];
      c.style.left = (rect.left - card.getBoundingClientRect().left + 20 + Math.random() * 30) + "px";
      c.style.top = (rect.top - card.getBoundingClientRect().top) + "px";
      card.appendChild(c);
      setTimeout(() => c.remove(), 1200);
    }, i * 90);
  }
}

document.getElementById("faucet-btn").addEventListener("click", async () => {
  if (faucetBusy) return;
  if (!(await waitAd())) return;
  if (faucetBusy) return;
  faucetBusy = true;
  const btn = document.getElementById("faucet-btn");
  btn.disabled = true;
  btn.textContent = "💧 Ouverture…";
  try {
    const r = await API.post("claim_faucet");
    faucetLastClaim = Date.now();
    spawnCoins();
    const timer = document.getElementById("faucet-timer");
    timer.textContent = `🎉 Tu as gagné ${eur(r.reward)} ! Reviens dans ${fmtSec(r.cooldown)}.`;
    timer.className = "faucet-timer ready";
    toast("Robinet : +0,002 € (0,2 centime)" + (r.reward ? " → +" + eur(r.reward) + " au solde" : " (en cours vers 0,01 €)"), "gold");
    await refresh();
  } catch (ex) {
    toast(ex.message, "err");
    // re-synchroniser
    await refresh();
  }
  faucetBusy = false;
  updateFaucetUI();
});

// ===== OFFRES PARTENAIRES (CPA) =====
function openCpa(o) {
  const m = document.getElementById("cpa-modal");
  m.classList.remove("hidden");
  document.getElementById("cpa-title").textContent = o.title;
  document.getElementById("cpa-headline").textContent = o.title;
  document.getElementById("cpa-url").textContent = o.link ? hostOf(o.link) : slug(o.title) + ".com";
  document.getElementById("cpa-banner").textContent = "✨ " + o.title + " ✨";
  document.getElementById("cpa-copy").textContent = "Action à réaliser chez le partenaire. Récompense : +" + eur(o.reward_cents);

  const openBtn = document.getElementById("cpa-open");
  if (o.link) {
    openBtn.style.display = "block";
    openBtn.onclick = () => window.open(o.link, "_blank");
    document.getElementById("cpa-note").textContent = "1) Ouvre l'offre partenaire (nouvel onglet) · 2) fais l'action · 3) reviens valider ici.";
  } else {
    openBtn.style.display = "none";
    document.getElementById("cpa-note").textContent = "Clique ci-dessous pour valider (démonstration).";
  }

  document.getElementById("cpa-claim").onclick = async () => {
    try {
      const r = await API.post("complete_cpa", { offer_id: o.id });
      m.classList.add("hidden");
      toast("+" + eur(r.reward) + " gagné via le partenaire ! 🎉", "gold");
      await refresh();
    } catch (ex) {
      m.classList.add("hidden");
      toast(ex.message, "err");
    }
  };
}

// ===== JEUX =====
// --- Clicker ---
let clickerActive = false, clickerClicks = 0, clickerTimer = null;
document.getElementById("clicker-start").addEventListener("click", async () => {
  if (clickerActive) return;
  if (!(await waitAd())) return;
  if (clickerActive) return;
  clickerActive = true; clickerClicks = 0;
  const btn = document.getElementById("clicker-start");
  btn.disabled = true;
  document.getElementById("clicker-count").textContent = "0 clics";
  let time = 15;
  document.getElementById("clicker-time").textContent = time + " s";
  clickerTimer = setInterval(() => {
    time--;
    document.getElementById("clicker-time").textContent = time + " s";
    if (time <= 0) {
      clearInterval(clickerTimer);
      clickerActive = false;
      btn.disabled = false;
      btn.textContent = "▶️ Rejouer";
      finishClicker();
    }
  }, 1000);
});
document.getElementById("clicker-coin").addEventListener("click", () => {
  if (!clickerActive) return;
  clickerClicks++;
  document.getElementById("clicker-count").textContent = clickerClicks + " clics";
});
async function finishClicker() {
  const score = Math.min(clickerClicks, 10);
  try {
    const r = await API.post("play_game", { game: "clicker", score });
    toast("Clicker : +" + eur(r.reward) + " gagné ! 🎉", "gold");
  } catch (ex) { toast(ex.message, "err"); }
  await refresh();
}

// --- Pile ou Face ---
let coinflipBusy = false;
async function playCoinflip(choice) {
  if (coinflipBusy) return;
  if (!(await waitAd())) return;
  if (coinflipBusy) return;
  coinflipBusy = true;
  const coin = document.getElementById("coinflip-coin");
  const result = document.getElementById("coinflip-result");
  const btnPile = document.getElementById("cf-pile");
  const btnFace = document.getElementById("cf-face");
  btnPile.disabled = true;
  btnFace.disabled = true;
  result.className = "coinflip-result";
  result.textContent = "…";
  coin.classList.remove("flip");
  void coin.offsetWidth;
  coin.classList.add("flip");
  try {
    const r = await API.post("play_coinflip", { choice });
    setTimeout(async () => {
      if (r.won) {
        result.textContent = `🎉 C'était ${r.actual === "pile" ? "Pile" : "Face"} ! Tu gagnes ${eur(r.stake)}`;
        result.classList.add("win");
        toast("Pile ou Face : +" + eur(r.stake) + " !", "gold");
      } else {
        result.textContent = `😕 C'était ${r.actual === "pile" ? "Pile" : "Face"}… tu perds ${eur(r.stake)}`;
        result.classList.add("lose");
        toast("Pile ou Face : -" + eur(r.stake), "err");
      }
      await refresh();
      coinflipBusy = false;
      btnPile.disabled = false;
      btnFace.disabled = false;
    }, 850);
  } catch (ex) {
    result.textContent = ex.message;
    result.className = "coinflip-result";
    toast(ex.message, "err");
    await refresh();
    coinflipBusy = false;
    btnPile.disabled = false;
    btnFace.disabled = false;
  }
}
document.getElementById("cf-pile").addEventListener("click", () => playCoinflip("pile"));
document.getElementById("cf-face").addEventListener("click", () => playCoinflip("face"));

// --- Memory ---
const MEMO_EMOJIS = ["🍎","🚗","🌟","🐱","🎵","⚽"];
let memoCards = [], memoFlipped = [], memoMoves = 0, memoPairs = 0;
function buildMemory() {
  memoMoves = 0; memoPairs = 0; memoFlipped = [];
  memoCards = [...MEMO_EMOJIS, ...MEMO_EMOJIS].sort(() => Math.random() - 0.5);
  const grid = document.getElementById("memory-grid");
  grid.innerHTML = "";
  document.getElementById("memory-status").textContent = "Coups : 0";
  memoCards.forEach((emoji, i) => {
    const c = document.createElement("div");
    c.className = "memory-card";
    c.dataset.index = i;
    c.textContent = "❓";
    c.addEventListener("click", () => flipMemory(c, i, emoji));
    grid.appendChild(c);
  });
}
function flipMemory(el, i, emoji) {
  if (memoFlipped.length >= 2 || el.classList.contains("flipped") || el.classList.contains("matched")) return;
  el.textContent = emoji;
  el.classList.add("flipped");
  memoFlipped.push({ el, i, emoji });
  if (memoFlipped.length === 2) {
    memoMoves++;
    document.getElementById("memory-status").textContent = "Coups : " + memoMoves;
    const [a, b] = memoFlipped;
    if (a.emoji === b.emoji) {
      a.el.classList.add("matched");
      b.el.classList.add("matched");
      memoFlipped = [];
      memoPairs++;
      if (memoPairs === MEMO_EMOJIS.length) finishMemory();
    } else {
      setTimeout(() => {
        a.el.textContent = "❓"; a.el.classList.remove("flipped");
        b.el.textContent = "❓"; b.el.classList.remove("flipped");
        memoFlipped = [];
      }, 700);
    }
  }
}
async function finishMemory() {
  // moins de coups = plus de gain : 6 paires => min 6 coups (parfait) = 10 cents, plus de coups = moins
  const perfect = MEMO_EMOJIS.length;
  const score = Math.max(1, Math.min(10, perfect + (perfect + 6) - memoMoves));
  document.getElementById("memory-status").textContent = "✅ Gagné en " + memoMoves + " coups !";
  try {
    const r = await API.post("play_game", { game: "memory", score });
    toast("Memory : +" + eur(r.reward) + " gagné ! 🎉", "gold");
  } catch (ex) { toast(ex.message, "err"); }
  await refresh();
}

document.getElementById("memory-start").addEventListener("click", async () => {
  if (!(await waitAd())) return;
  buildMemory();
});
buildMemory();

// ===== JEUX À MISE =====
function selectedStake(name) {
  const el = document.querySelector(`input[name="${name}"]:checked`);
  return el ? parseInt(el.value, 10) : 5;
}
function setBusy(ids, busy) {
  ids.forEach((id) => { const b = document.getElementById(id); if (b) b.disabled = busy; });
}

async function playStake(game, choice, stakeName, resultId, onResult) {
  const stake = selectedStake(stakeName);
  try {
    const r = await API.post("play_stake", { game, choice, stake_cents: stake });
    onResult(r);
    await refresh();
    return r;
  } catch (ex) {
    const box = document.getElementById(resultId);
    box.textContent = ex.message;
    box.className = "coinflip-result";
    toast(ex.message, "err");
    await refresh();
    return null;
  }
}

// --- Dé ---
const DICE_EMOJI = { 1:"⚀", 2:"⚁", 3:"⚂", 4:"⚃", 5:"⚄", 6:"⚅" };
async function playDice(choice) {
  if (!(await waitAd())) return;
  setBusy(["dice-even","dice-odd"], true);
  const face = document.getElementById("dice-face");
  const box = document.getElementById("dice-result");
  box.className = "coinflip-result";
  box.textContent = "…";
  face.classList.remove("roll");
  void face.offsetWidth;
  face.classList.add("roll");
  const r = await playStake("dice", choice, "stake-dice", "dice-result", (res) => {
    face.textContent = DICE_EMOJI[res.actual] || "🎲";
    if (res.won) {
      box.textContent = `🎉 ${res.actual} (${res.actual % 2 === 0 ? "pair" : "impair"}) — +${eur(res.stake)}`;
      box.classList.add("win");
      toast("Dé : +" + eur(res.stake), "gold");
    } else {
      box.textContent = `😕 ${res.actual} (${res.actual % 2 === 0 ? "pair" : "impair"}) — −${eur(res.stake)}`;
      box.classList.add("lose");
      toast("Dé : −" + eur(res.stake), "err");
    }
  });
  setBusy(["dice-even","dice-odd"], false);
}
document.getElementById("dice-even").addEventListener("click", () => playDice("even"));
document.getElementById("dice-odd").addEventListener("click", () => playDice("odd"));

// --- Chifoumi ---
const RPS_EMOJI = { pierre:"✊", feuille:"✋", ciseaux:"✌️" };
async function playRps(choice) {
  if (!(await waitAd())) return;
  setBusy(["rps-pierre","rps-feuille","rps-ciseaux"], true);
  document.getElementById("rps-you").textContent = RPS_EMOJI[choice];
  document.getElementById("rps-cpu").textContent = "❔";
  const box = document.getElementById("rps-result");
  box.className = "coinflip-result";
  box.textContent = "…";
  const r = await playStake("rps", choice, "stake-rps", "rps-result", (res) => {
    document.getElementById("rps-cpu").textContent = RPS_EMOJI[res.actual] || "❔";
    if (res.draw) {
      box.textContent = "Égalité — mise rendue.";
      toast("Chifoumi : égalité");
    } else if (res.won) {
      box.textContent = `🎉 ${RPS_EMOJI[choice]} bat ${RPS_EMOJI[res.actual]} — +${eur(res.stake)}`;
      box.classList.add("win");
      toast("Chifoumi : +" + eur(res.stake), "gold");
    } else {
      box.textContent = `😕 ${RPS_EMOJI[res.actual]} bat ${RPS_EMOJI[choice]} — −${eur(res.stake)}`;
      box.classList.add("lose");
      toast("Chifoumi : −" + eur(res.stake), "err");
    }
  });
  setBusy(["rps-pierre","rps-feuille","rps-ciseaux"], false);
}
document.getElementById("rps-pierre").addEventListener("click", () => playRps("pierre"));
document.getElementById("rps-feuille").addEventListener("click", () => playRps("feuille"));
document.getElementById("rps-ciseaux").addEventListener("click", () => playRps("ciseaux"));

// --- Slots ---
const SLOT_SYM = ["🍒","🍋","🍇","🔔","⭐","7️⃣"];
let slotsBusy = false;
document.getElementById("slots-spin").addEventListener("click", async () => {
  if (slotsBusy) return;
  if (!(await waitAd())) return;
  if (slotsBusy) return;
  slotsBusy = true;
  const btn = document.getElementById("slots-spin");
  btn.disabled = true;
  const box = document.getElementById("slots-result");
  box.className = "coinflip-result";
  box.textContent = "…";
  ["slot-0","slot-1","slot-2"].forEach((id) => document.getElementById(id).classList.add("spin"));
  const spinInt = setInterval(() => {
    for (let i = 0; i < 3; i++) {
      document.getElementById("slot-" + i).textContent = SLOT_SYM[Math.floor(Math.random() * SLOT_SYM.length)];
    }
  }, 90);
  const r = await playStake("slots", "spin", "stake-slots", "slots-result", () => {});
  clearInterval(spinInt);
  ["slot-0","slot-1","slot-2"].forEach((id) => document.getElementById(id).classList.remove("spin"));
  if (r && r.reels) {
    r.reels.forEach((s, i) => { document.getElementById("slot-" + i).textContent = s; });
    const net = r.payout;
    if (net > 0) {
      box.textContent = (r.kind === "jackpot" ? "💎 Jackpot ! " : "✅ ") + "+" + eur(net);
      box.classList.add("win");
      toast("Machine à sous : +" + eur(net), "gold");
    } else {
      box.textContent = "Pas de combo — −" + eur(r.stake);
      box.classList.add("lose");
      toast("Machine à sous : −" + eur(r.stake), "err");
    }
  }
  btn.disabled = false;
  slotsBusy = false;
});

// --- Rouge / Noir ---
async function playColor(choice) {
  if (!(await waitAd())) return;
  setBusy(["color-rouge","color-noir"], true);
  const ball = document.getElementById("color-ball");
  const box = document.getElementById("color-result");
  box.className = "coinflip-result";
  box.textContent = "…";
  ball.classList.remove("spin");
  void ball.offsetWidth;
  ball.classList.add("spin");
  await playStake("color", choice, "stake-color", "color-result", (res) => {
    ball.textContent = res.actual === "rouge" ? "🔴" : "⚫";
    if (res.won) {
      box.textContent = `🎉 ${res.actual === "rouge" ? "Rouge" : "Noir"} — +${eur(res.stake)}`;
      box.classList.add("win");
      toast("Roulette : +" + eur(res.stake), "gold");
    } else {
      box.textContent = `😕 ${res.actual === "rouge" ? "Rouge" : "Noir"} — −${eur(res.stake)}`;
      box.classList.add("lose");
      toast("Roulette : −" + eur(res.stake), "err");
    }
  });
  setBusy(["color-rouge","color-noir"], false);
}
document.getElementById("color-rouge").addEventListener("click", () => playColor("rouge"));



document.getElementById("color-noir").addEventListener("click", () => playColor("noir"));

// ===== MINES =====
let minesId = null, minesBusy = false;
function minesBuild(revealed, mines, boomTile, playing) {
  const g = document.getElementById("mines-grid");
  g.innerHTML = "";
  const rev = new Set(revealed || []);
  const mn = new Set(mines || []);
  for (let i = 0; i < 25; i++) {
    const b = document.createElement("button");
    b.className = "mine-cell";
    b.type = "button";
    if (rev.has(i) && !(mn.has(i))) { b.textContent = "💎"; b.classList.add("gem"); b.disabled = true; }
    else if (mn.has(i) && (boomTile === i || !playing)) { b.textContent = "💣"; b.classList.add("boom"); b.disabled = true; }
    else if (!playing) { b.textContent = mn.has(i) ? "💣" : ""; b.classList.add("safe"); b.disabled = true; }
    else { b.textContent = ""; b.onclick = () => minesReveal(i); }
    g.appendChild(b);
  }
}
minesBuild([], [], null, false);
async function minesReveal(tile) {
  if (!minesId || minesBusy) return;
  minesBusy = true;
  try {
    const r = await API.post("mines_reveal", { id: minesId, tile });
    if (r.status === "lost") {
      minesId = null;
      minesBuild(r.revealed, r.mines, r.tile, false);
      document.getElementById("mines-msg").textContent = "💣 Mine ! Tu perds " + eur(r.stake);
      document.getElementById("mines-out").disabled = true;
      document.getElementById("mines-go").disabled = false;
      toast("Mines : perdu, −" + eur(r.stake), "err");
      await refresh();
    } else {
      minesBuild(r.revealed, [], null, true);
      document.getElementById("mines-msg").textContent = r.gems + " gemmes · " + r.multiplier.toFixed(2) + "x · " + eur(r.payout);
      document.getElementById("mines-out").disabled = false;
    }
  } catch (ex) { toast(ex.message, "err"); }
  minesBusy = false;
}
document.getElementById("mines-go").addEventListener("click", async () => {
  if (minesBusy) return;
  if (!(await waitAd())) return;
  minesBusy = true;
  document.getElementById("mines-go").disabled = true;
  try {
    const r = await API.post("mines_start", { stake_cents: selectedStake("stake-mines") });
    minesId = r.id;
    minesBuild([], [], null, true);
    document.getElementById("mines-msg").textContent = "4 mines cachées. Avance, ou retire.";
    document.getElementById("mines-out").disabled = true;
    await refresh();
  } catch (ex) {
    toast(ex.message, "err");
    document.getElementById("mines-go").disabled = false;
  }
  minesBusy = false;
});
document.getElementById("mines-out").addEventListener("click", async () => {
  if (!minesId) return;
  document.getElementById("mines-out").disabled = true;
  try {
    const r = await API.post("mines_cashout", { id: minesId });
    minesId = null;
    minesBuild([], r.mines || [], null, false);
    document.getElementById("mines-msg").textContent = "Retiré " + r.multiplier.toFixed(2) + "x → +" + eur(r.payout);
    document.getElementById("mines-go").disabled = false;
    toast("Mines : +" + eur(r.payout), "gold");
    await refresh();
  } catch (ex) {
    toast(ex.message, "err");
    document.getElementById("mines-out").disabled = false;
  }
});
document.getElementById("vip-day").addEventListener("click", () => buyVip("day"));
document.getElementById("vip-week").addEventListener("click", () => buyVip("week"));
async function buyVip(plan) {
  try {
    const r = await API.post("buy_vip", { plan });
    toast(r.message || "Sans pub activé !", "gold");
    await refresh();
  } catch (ex) { toast(ex.message, "err"); }
}


// ===== EXPRESS (avion / crash) =====
let crashId = null, crashRaf = null, crashStartPerf = 0, crashK = 0.07, crashBusy = false, crashPollAt = 0;
function crashSetMsg(t, cls) {
  const el = document.getElementById("crash-msg");
  el.textContent = t;
  el.className = "crash-msg" + (cls ? " " + cls : "");
}
function crashStopAnim() {
  if (crashRaf) cancelAnimationFrame(crashRaf);
  crashRaf = null;
}
function crashFrame() {
  const t = (performance.now() - crashStartPerf) / 1000;
  const m = Math.exp(crashK * Math.max(0, t));
  const el = document.getElementById("crash-mult");
  el.textContent = m.toFixed(2) + "x";
  el.className = "crash-mult" + (m >= 2 ? " hot" : "");
  const plane = document.getElementById("crash-plane");
  const pct = Math.min(78, 8 + t * 7);
  plane.style.left = (8 + t * 4.2) + "%";
  plane.style.bottom = pct + "%";
  const btn = document.getElementById("crash-out");
  btn.textContent = "💸 Retirer " + m.toFixed(2) + "x";
  if (performance.now() - crashPollAt > 180) {
    crashPollAt = performance.now();
    crashPoll();
  }
  crashRaf = requestAnimationFrame(crashFrame);
}
async function crashPoll() {
  if (!crashId) return;
  try {
    const s = await API.post("crash_status", { id: crashId });
    if (s.status === "lost") crashLose(s);
    if (s.status === "won") crashWin(s);
  } catch (e) {}
}
function crashLose(s) {
  crashId = null;
  crashBusy = false;
  crashStopAnim();
  document.getElementById("crash-sky").classList.add("crashed");
  const el = document.getElementById("crash-mult");
  el.textContent = "💥 " + Number(s.crash_at).toFixed(2) + "x";
  el.className = "crash-mult boom";
  crashSetMsg("Crash à " + Number(s.crash_at).toFixed(2) + "x — tu perds " + eur(s.stake));
  document.getElementById("crash-out").disabled = true;
  document.getElementById("crash-go").disabled = false;
  toast("Express : crash, −" + eur(s.stake), "err");
  refresh();
}
function crashWin(s) {
  crashId = null;
  crashBusy = false;
  crashStopAnim();
  document.getElementById("crash-mult").textContent = Number(s.at).toFixed(2) + "x";
  crashSetMsg("Retiré à " + Number(s.at).toFixed(2) + "x → +" + eur(s.payout));
  document.getElementById("crash-out").disabled = true;
  document.getElementById("crash-go").disabled = false;
  toast("Express : +" + eur(s.payout), "gold");
  refresh();
}
document.getElementById("crash-go").addEventListener("click", async () => {
  if (crashBusy) return;
  if (!(await waitAd())) return;
  crashBusy = true;
  document.getElementById("crash-go").disabled = true;
  document.getElementById("crash-sky").classList.remove("crashed");
  document.getElementById("crash-plane").style.left = "8%";
  document.getElementById("crash-plane").style.bottom = "18%";
  document.getElementById("crash-mult").className = "crash-mult";
  crashSetMsg("Décollage…");
  try {
    const stake = selectedStake("stake-crash");
    const r = await API.post("crash_start", { stake_cents: stake });
    crashId = r.id;
    crashK = r.k || 0.07;
    crashStartPerf = performance.now();
    crashPollAt = 0;
    document.getElementById("crash-out").disabled = false;
    crashSetMsg("Retire avant le crash !");
    crashStopAnim();
    crashRaf = requestAnimationFrame(crashFrame);
    refresh();
  } catch (ex) {
    crashBusy = false;
    document.getElementById("crash-go").disabled = false;
    crashSetMsg(ex.message);
    toast(ex.message, "err");
  }
});
document.getElementById("crash-out").addEventListener("click", async () => {
  if (!crashId) return;
  document.getElementById("crash-out").disabled = true;
  try {
    const s = await API.post("crash_cashout", { id: crashId });
    if (s.status === "lost") crashLose(s);
    else crashWin(s);
  } catch (ex) {
    toast(ex.message, "err");
    document.getElementById("crash-out").disabled = false;
  }
});


// ===== FUN (pubs → quelques centimes) =====
const FUN_QUIZ = [
  { q: "Combien de centimes dans 1 euro ?", a: ["10", "100", "1000"], ok: 1 },
  { q: "Le koala est-il un ours ?", a: ["Oui", "Non", "Parfois"], ok: 1 },
  { q: "Quelle est la couleur du cheval blanc d'Henri IV ?", a: ["Blanc", "Noir", "Invisible"], ok: 0 },
  { q: "2 + 2 = ?", a: ["3", "4", "22"], ok: 1 },
];
async function claimFun(kind, resId, onWin) {
  if (!(await waitAd())) return null;
  const box = document.getElementById(resId);
  box.className = "coinflip-result";
  box.textContent = "…";
  try {
    const r = await API.post("claim_fun", { kind });
    box.textContent = `+${eur(r.reward)}  (encore ${r.left} aujourd'hui)`;
    box.classList.add("win");
    toast("Fun : +" + eur(r.reward), "gold");
    if (onWin) onWin(r);
    await refresh();
    return r;
  } catch (ex) {
    box.textContent = ex.message;
    toast(ex.message, "err");
    return null;
  }
}
document.getElementById("fun-scratch").addEventListener("click", async () => {
  document.getElementById("scratch-box").textContent = "✨";
  const r = await claimFun("scratch", "fun-scratch-res", (res) => {
    document.getElementById("scratch-box").textContent = res.reward >= 2 ? "💶" : "🪙";
  });
  if (!r) document.getElementById("scratch-box").textContent = "❓";
});
document.getElementById("fun-chest").addEventListener("click", async () => {
  document.getElementById("fun-chest-emoji").textContent = "📦";
  await claimFun("chest", "fun-chest-res", (res) => {
    document.getElementById("fun-chest-emoji").textContent = res.reward >= 2 ? "💎" : "🪙";
  });
});
document.getElementById("fun-balloon").addEventListener("click", async () => {
  const r = await claimFun("balloon", "fun-balloon-res");
  if (!r) return;
  document.querySelectorAll("#balloon-row .balloon").forEach((b, i) => {
    setTimeout(() => { b.classList.add("pop"); b.textContent = i === 2 ? "🪙" : "💥"; }, i * 120);
  });
  setTimeout(() => {
    document.querySelectorAll("#balloon-row .balloon").forEach((b) => { b.classList.remove("pop"); b.textContent = "🎈"; });
  }, 1600);
});
document.getElementById("fun-quiz").addEventListener("click", async () => {
  const item = FUN_QUIZ[Math.floor(Math.random() * FUN_QUIZ.length)];
  document.getElementById("fun-quiz-q").textContent = item.q;
  const opts = document.getElementById("fun-quiz-opts");
  opts.innerHTML = "";
  item.a.forEach((label, i) => {
    const b = document.createElement("button");
    b.className = "game-btn small";
    b.textContent = label;
    b.onclick = async () => {
      opts.querySelectorAll("button").forEach((x) => x.disabled = true);
      await claimFun("quiz", "fun-quiz-res");
    };
    opts.appendChild(b);
  });
});



// ===== −18 (3 pubs → 0,10 €) =====
const ADULT_LINKS = [
  "https://www.profitableratecpmnetwork.com/c7qfe4dikr?key=69d1f3bf8ac6de7391cf3eaa1d77e1a1",
  "https://www.profitableratecpmnetwork.com/nfv5bb5tx4?key=f216c6e41e54bde80d762ad61ed53c11",
  "https://www.profitableratecpmnetwork.com/cyrm5fgis?key=517bf4c2047981143f64fe418a024d00",
  "https://www.profitableratecpmnetwork.com/ewpy9gtfrn?key=49586d19186a4f51110d48c141351fa4",
  "https://www.profitableratecpmnetwork.com/z0dfk8jc?key=f1bff217207649b313c23ecaaab0bc1e",
  "https://www.profitableratecpmnetwork.com/xw1r7mp1t8?key=0836c2f424ad47c911b20c8ae6e4e77e",
  "https://www.profitableratecpmnetwork.com/pu5ce9ayg?key=7fa63f6495b6ee7409066dd74d0e1e17",
  "https://www.profitableratecpmnetwork.com/qiwe85grc?key=83226b59982f37eb31bf5efafb1a5a29",
  "https://www.profitableratecpmnetwork.com/b90cx5y3?key=0cb3e87f53b90373a65859342c1ab694",
  "https://www.profitableratecpmnetwork.com/m5fcdbri?key=9fc5e54ac541cee2fdd113a2d518ac8e",
];
function fillHighPayAds() {
  const els = document.querySelectorAll(".login-hit-ad .ad-accept, a.login-hit-ad");
  if (!els.length) return;
  const pool = ADULT_LINKS.slice();
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    const t = pool[i]; pool[i] = pool[j]; pool[j] = t;
  }
  els.forEach((a, i) => {
    const url = pool[i % pool.length];
    const n = ADULT_LINKS.indexOf(url);
    a.href = "go.html?i=" + (n >= 0 ? n : i % ADULT_LINKS.length);
    a.target = "_blank";
    a.rel = "noopener sponsored nofollow";
  });
}
fillHighPayAds();
document.querySelectorAll(".ad-refuse").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const card = btn.closest(".login-hit-ad");
    if (card) card.remove();
  });
});
document.querySelectorAll(".login-hit-ad").forEach((card) => {
  card.addEventListener("click", (e) => {
    if (e.target.closest(".ad-refuse")) return;
    if (e.target.closest(".ad-accept")) return;
    const a = card.querySelector(".ad-accept");
    if (a) window.open(a.href, "_blank", "noopener,noreferrer");
  });
});

let adultLinkI = 0;
let adultBusy = false;
let adultTimerInt = null;
const ADULT_WAIT = 15;

function syncAdultGate() {
  const ok = localStorage.getItem("rb_age18") === "1";
  document.getElementById("adult-gate").classList.toggle("hidden", ok);
  document.getElementById("adult-room").classList.toggle("hidden", !ok);
}

function updateAdultUI(info) {
  if (!info) return;
  const views = Math.min(info.needed, info.views || 0);
  const prog = document.getElementById("adult-progress");
  const timer = document.getElementById("adult-timer");
  const watch = document.getElementById("adult-watch");
  const claim = document.getElementById("adult-claim");
  const left = document.getElementById("adult-left");
  if (!prog) return;
  for (let i = 1; i <= 3; i++) {
    document.getElementById("adot-" + i).classList.toggle("on", i <= views);
  }
  prog.textContent = "Pub " + views + " / " + info.needed;
  left.textContent = info.left_today > 0
    ? "Encore " + info.left_today + " fois aujourd'hui."
    : "Limite du jour atteinte. Reviens demain.";
  if (info.left_today <= 0) {
    watch.classList.add("hidden");
    claim.classList.add("hidden");
    timer.textContent = "Reviens demain pour la rubrique −18.";
    return;
  }
  if (views >= info.needed) {
    watch.classList.add("hidden");
    claim.classList.remove("hidden");
    timer.textContent = "3 pubs vues. Réclame 0,10 €.";
  } else {
    watch.classList.remove("hidden");
    claim.classList.add("hidden");
    watch.textContent = "🎬 Regarder la pub " + (views + 1) + " / " + info.needed;
    if (!adultBusy) timer.textContent = "Clique pour ouvrir la pub " + (views + 1);
  }
}

document.getElementById("adult-age-check").addEventListener("change", (e) => {
  document.getElementById("adult-age-ok").disabled = !e.target.checked;
});
document.getElementById("adult-age-ok").addEventListener("click", () => {
  if (!document.getElementById("adult-age-check").checked) return;
  localStorage.setItem("rb_age18", "1");
  syncAdultGate();
});

document.getElementById("adult-watch").addEventListener("click", async () => {
  if (adultBusy) return;
  adultBusy = true;
  const btn = document.getElementById("adult-watch");
  const timer = document.getElementById("adult-timer");
  btn.disabled = true;
  const url = ADULT_LINKS[adultLinkI % ADULT_LINKS.length];
  adultLinkI += 1;
  try { window.open(url, "_blank", "noopener,noreferrer"); } catch (e) {}
  let left = ADULT_WAIT;
  timer.textContent = "Regarde la pub… " + left + " s";
  clearInterval(adultTimerInt);
  adultTimerInt = setInterval(() => {
    left -= 1;
    timer.textContent = "Regarde la pub… " + Math.max(0, left) + " s";
    if (left <= 0) {
      clearInterval(adultTimerInt);
      adultTimerInt = null;
    }
  }, 1000);
  await new Promise((r) => setTimeout(r, ADULT_WAIT * 1000));
  try {
    const info = await API.post("adult_view");
    updateAdultUI(info);
    toast("Pub −18 validée (" + info.views + "/" + info.needed + ")");
  } catch (ex) {
    toast(ex.message, "err");
  }
  btn.disabled = false;
  adultBusy = false;
});

document.getElementById("adult-claim").addEventListener("click", async () => {
  if (adultBusy) return;
  adultBusy = true;
  try {
    const r = await API.post("adult_claim");
    toast("−18 : +" + eur(r.reward) + " !", "gold");
    updateAdultUI(r);
    await refresh();
  } catch (ex) {
    toast(ex.message, "err");
  }
  adultBusy = false;
});

syncAdultGate();

function playAdultAd() {
  return new Promise((resolve) => {
    if (adGateBusy) { resolve(false); return; }
    adGateBusy = true;
    const modal = document.getElementById("ad-gate-modal");
    const btn = document.getElementById("ad-gate-continue");
    const timer = document.getElementById("ad-gate-timer");
    const frame = document.getElementById("ad-gate-frame");
    modal.classList.remove("hidden");
    btn.disabled = true;
    btn.textContent = "⏳ Pub −18…";
    frame.src = "ad-gate.html?t=" + Date.now();
    const url = ADULT_LINKS[adultLinkI % ADULT_LINKS.length];
    adultLinkI += 1;
    try { window.open(url, "_blank", "noopener,noreferrer"); } catch (e) {}
    let left = ADULT_WAIT;
    timer.textContent = left + " s";
    const iv = setInterval(() => {
      left -= 1;
      timer.textContent = Math.max(0, left) + " s";
      if (left <= 0) {
        clearInterval(iv);
        btn.disabled = false;
        btn.textContent = "✅ Continuer";
      }
    }, 1000);
    btn.onclick = () => {
      if (btn.disabled) return;
      clearInterval(iv);
      frame.src = "about:blank";
      modal.classList.add("hidden");
      adGateBusy = false;
      resolve(true);
    };
  });
}

let lastClickInfo = { clicks: 0, chests: [] };
function updateClickUI(info) {
  if (!info) return;
  lastClickInfo = info;
  const cc = document.getElementById("click-count");
  if (cc) cc.textContent = (info.clicks || 0) + " clics";
  (info.chests || []).forEach((c) => {
    const btn = document.getElementById("chest-btn-" + c.id);
    const em = document.getElementById("chest-emoji-" + c.id);
    const box = document.getElementById("chest-" + c.id);
    if (!btn || !em || !box) return;
    box.classList.toggle("ready", !!(c.ready && !c.opened));
    box.classList.toggle("open", !!c.opened);
    if (c.opened) {
      em.textContent = "✨";
      btn.disabled = true;
      btn.textContent = "Ouvert · +" + eur(c.reward);
    } else if (c.unlocked) {
      em.textContent = "📦";
      btn.disabled = false;
      btn.textContent = "🎬 Pub −18 + ouvrir";
    } else if (c.ready) {
      em.textContent = "🔐";
      btn.disabled = false;
      btn.textContent = "🎬 Pub −18 + débloquer";
    } else {
      em.textContent = "🔒";
      btn.disabled = true;
      btn.textContent = "🔒 " + c.need + " clics";
    }
  });
  const next = (info.chests || []).find((c) => !c.ready);
  const hint = document.getElementById("click-hint");
  if (hint) {
    hint.textContent = next
      ? (next.need - info.clicks) + " clics pour le coffre " + next.id
      : "Tous les paliers atteints aujourd'hui.";
  }
}

let clickTapBusy = false;
document.getElementById("click-big").addEventListener("click", async () => {
  if (clickTapBusy) return;
  clickTapBusy = true;
  const big = document.getElementById("click-big");
  big.style.transform = "scale(.9)";
  setTimeout(() => { big.style.transform = ""; }, 80);
  try {
    const r = await API.post("click_tap");
    updateClickUI(r);
  } catch (ex) { toast(ex.message, "err"); }
  clickTapBusy = false;
});

async function chestAction(id) {
  const c = (lastClickInfo.chests || []).find((x) => x.id === id);
  if (!c || c.opened) return;
  if (!(await playAdultAd())) return;
  try {
    if (!c.unlocked) {
      const r = await API.post("click_unlock", { chest: id });
      updateClickUI(r);
      toast("Coffre débloqué ! Ouvre-le : encore une pub −18.");
    } else {
      const r = await API.post("click_open", { chest: id });
      updateClickUI(r);
      toast("Coffre : +" + eur(r.reward), "gold");
      await refresh();
    }
  } catch (ex) { toast(ex.message, "err"); }
}
[1, 2, 3].forEach((id) => {
  document.getElementById("chest-btn-" + id).addEventListener("click", () => chestAction(id));
});

// ===== BONUS =====
document.getElementById("claim-bonus-btn").addEventListener("click", async () => {
  if (!(await waitAd())) return;
  try {
    const r = await API.post("claim_bonus");
    toast("Bonus de +" + eur(r.reward) + " réclamé ! 🎁", "gold");
    await refresh();
  } catch (ex) { toast(ex.message, "err"); }
});

// ===== WHEEL =====
const WHEEL_REWARDS = [0, 1, 2, 1, 3, 5, 1, 2, 1, 2, 1, 3];
let spinning = false;
document.getElementById("spin-btn").addEventListener("click", () => {
  document.getElementById("wheel-modal").classList.remove("hidden");
  document.getElementById("wheel-result").textContent = "Lance la roue !";
});
document.getElementById("wheel-spin-btn").addEventListener("click", async () => {
  if (spinning) return;
  if (!(await waitAd())) return;
  if (spinning) return;
  spinning = true;
  document.getElementById("wheel-result").textContent = "…";
  try {
    const r = await API.post("spin_wheel");
    // map reward to segment index (find matching value; default first)
    let idx = WHEEL_REWARDS.indexOf(r.reward);
    if (idx < 0) idx = 0;
    const segAngle = 30;
    // align the winning segment under the pointer (pointer is at top)
    const target = 360 * 5 + (360 - idx * segAngle - segAngle / 2);
    const wheel = document.getElementById("wheel");
    wheel.style.transform = `rotate(${target}deg)`;
    setTimeout(() => {
      document.getElementById("wheel-result").textContent =
        r.reward > 0 ? `Tu as gagné ${eur(r.reward)} ! 🎉` : "Pas de chance, 0 € ! 😕";
      spinning = false;
      if (r.reward > 0) toast("+" + eur(r.reward) + " via la roue !", "gold");
      refresh();
    }, 3300);
  } catch (ex) {
    spinning = false;
    document.getElementById("wheel-result").textContent = ex.message;
    toast(ex.message, "err");
  }
});
document.getElementById("wheel-modal").addEventListener("click", (e) => {
  if (e.target.id === "wheel-modal") document.getElementById("wheel-modal").classList.add("hidden");
});

// ===== HISTORY =====
function renderHistory(recent) {
  const body = document.getElementById("history-body");
  body.innerHTML = "";
  if (recent.length === 0) {
    body.innerHTML = '<tr><td colspan="4" class="muted">Aucune transaction.</td></tr>';
    return;
  }
  recent.forEach((t) => {
    const tr = document.createElement("tr");
    const d = new Date(t.created_at);
    const dateStr = d.toLocaleDateString("fr-FR") + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    const kind = t.kind === "withdraw" ? "💸 Retrait" : (t.amount_cents < 0 ? "🎲 Perte" : "💵 Gain");
    const amt = t.amount_cents > 0
      ? `<span class="amt-pos">+${eur(t.amount_cents)}</span>`
      : `<span class="amt-neg">${eur(Math.abs(t.amount_cents))}</span>`;
    tr.innerHTML = `<td>${dateStr}</td><td>${kind}</td><td>${escapeHtml(t.label)}</td><td>${amt}</td>`;
    body.appendChild(tr);
  });
}

// ===== WITHDRAW =====
function refreshGiftLocks() {
  document.querySelectorAll(".gift-card").forEach((b) => { b.disabled = true; });
}
document.querySelectorAll(".gift-card").forEach((b) => {
  b.addEventListener("click", () => {
    toast("Cette carte arrive bientôt — pas encore disponible.", "err");
  });
});

const WD_METHODS = { paypal: "Email PayPal", virement: "IBAN", crypto: "Adresse USDT (TRC20)" };
document.getElementById("wd-method").addEventListener("change", (e) => {
  document.getElementById("wd-details-label").textContent = WD_METHODS[e.target.value];
  document.getElementById("wd-details").placeholder = WD_PLACEHOLDERS[e.target.value] || "";
});
document.getElementById("wd-submit").addEventListener("click", async () => {
  const amount = parseFloat(document.getElementById("wd-amount").value);
  const method = document.getElementById("wd-method").value;
  const details = document.getElementById("wd-details").value.trim();
  if (!amount || isNaN(amount)) { toast("Indique un montant valide.", "err"); return; }
  const cents = Math.round(amount * 100);
  try {
    const r = await API.post("withdraw", { amount_cents: cents, method, details });
    toast(r.message || "Demande envoyée !");
    document.getElementById("wd-amount").value = "";
    document.getElementById("wd-details").value = "";
    await refresh();
    await loadWithdrawals();
  } catch (ex) { toast(ex.message, "err"); }
});

async function loadWithdrawals() {
  try {
    const r = await API.get("withdrawals");
    const box = document.getElementById("wd-list");
    if (r.withdrawals.length === 0) {
      box.innerHTML = '<p class="muted">Aucune demande pour l\'instant.</p>';
      return;
    }
    box.innerHTML = "";
    r.withdrawals.forEach((w) => {
      const d = new Date(w.created_at).toLocaleDateString("fr-FR");
      const el = document.createElement("div");
      el.className = "wd-item";
      el.innerHTML = `
        <div class="wd-top">
          <span class="wd-amount">${eur(w.amount_cents)}</span>
          <span class="badge ${w.status}">${w.status === "pending" ? "En attente" : w.status === "paid" ? "Payé" : "Refusé"}</span>
        </div>
        <div class="muted">${escapeHtml(w.method)} · ${d}</div>`;
      box.appendChild(el);
    });
  } catch (e) {}
}

// ===== ADMIN =====
async function loadAdmin() {
  try {
    const ov = await API.get("admin/overview");
    document.getElementById("adm-users").textContent = ov.users;
    document.getElementById("adm-pending").textContent = ov.pending_withdrawals;
    document.getElementById("adm-paid").textContent = eur(ov.total_paid);
    document.getElementById("adm-earned").textContent = eur(ov.total_earned);

    const wd = await API.get("admin/withdrawals");
    const wb = document.getElementById("adm-withdrawals");
    wb.innerHTML = "";
    if (wd.withdrawals.length === 0) { wb.innerHTML = '<p class="muted">Aucun retrait.</p>'; }
    wd.withdrawals.forEach((w) => {
      const row = document.createElement("div");
      row.className = "adm-row";
      const d = new Date(w.created_at).toLocaleDateString("fr-FR");
      row.innerHTML = `
        <div class="adm-main">
          <div class="adm-title">${escapeHtml(w.username)} — ${eur(w.amount_cents)} (${escapeHtml(w.method)})</div>
          <div class="adm-sub">${d} · ${escapeHtml(w.details)} · ${w.status}</div>
        </div>`;
      if (w.status === "pending") {
        const pay = document.createElement("button");
        pay.className = "btn-sm green"; pay.textContent = "✓ Payer";
        pay.onclick = async () => { await API.post("admin/withdrawal_status", { id: w.id, status: "paid" }); loadAdmin(); toast("Retrait payé."); };
        const rej = document.createElement("button");
        rej.className = "btn-sm red"; rej.textContent = "✗ Refuser";
        rej.onclick = async () => { await API.post("admin/withdrawal_status", { id: w.id, status: "rejected" }); loadAdmin(); toast("Retrait refusé (remboursé)."); };
        row.appendChild(pay); row.appendChild(rej);
      }
      wb.appendChild(row);
    });

    const users = await API.get("admin/users");
    const ub = document.getElementById("adm-users-body");
    ub.innerHTML = "";
    users.users.forEach((u) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${u.id}</td><td>${escapeHtml(u.username)}</td><td>${eur(u.balance_cents)}</td><td>${eur(u.total_earned_cents)}</td><td></td>`;
      const td = tr.lastElementChild;
      const ban = document.createElement("button");
      ban.className = "btn-sm " + (u.banned ? "green" : "red");
      ban.textContent = u.banned ? "Débannir" : "Bannir";
      ban.onclick = async () => { await API.post("admin/user_toggle_ban", { id: u.id }); loadAdmin(); };
      const add = document.createElement("button");
      add.className = "btn-sm"; add.textContent = "+0,50 €"; add.style.marginLeft = "6px";
      add.onclick = async () => { await API.post("admin/user_adjust", { id: u.id, delta: 50 }); loadAdmin(); toast("+0,50 € ajouté."); };

      const vipb = document.createElement("button");
      vipb.className = "btn-sm"; vipb.textContent = "⭐ VIP 7j"; vipb.style.marginLeft = "6px";
      vipb.onclick = async () => { await API.post("admin/user_vip", { id: u.id, days: 7 }); loadAdmin(); toast("VIP 7 jours."); };
      td.appendChild(ban); td.appendChild(add); td.appendChild(vipb);
      ub.appendChild(tr);
    });

    const of = await API.get("offers");
    const ob = document.getElementById("adm-offers");
    ob.innerHTML = "";
    of.offers.forEach((o) => {
      const row = document.createElement("div");
      row.className = "adm-row";
      const t = o.type === "video" ? "🎬" : o.type === "ptc" ? "🖱️" : "📝";
      row.innerHTML = `
        <div class="adm-main">
          <div class="adm-title">${t} ${escapeHtml(o.title)}</div>
          <div class="adm-sub">+${eur(o.reward_cents)} · ${o.type}${o.done ? " · fait" : ""}</div>
        </div>`;
      const toggle = document.createElement("button");
      toggle.className = "btn-sm " + (o.active ? "red" : "green");
      toggle.textContent = o.active ? "Désactiver" : "Activer";
      toggle.onclick = async () => { await API.post("admin/offer_toggle", { id: o.id }); loadAdmin(); };
      row.appendChild(toggle);
      if (o.type === "cpa") {
        const linkBtn = document.createElement("button");
        linkBtn.className = "btn-sm";
        linkBtn.style.marginLeft = "6px";
        linkBtn.textContent = o.link ? "🔗 Lien ✓" : "🔗 Ajouter lien";
        linkBtn.onclick = async () => {
          const link = prompt("Colle le lien d'affiliation pour :\n" + o.title, o.link || "");
          if (link === null) return;
          try {
            await API.post("admin/offer_set_link", { id: o.id, link: link.trim() });
            toast("Lien enregistré !");
            loadAdmin();
          } catch (ex) { toast(ex.message, "err"); }
        };
        row.appendChild(linkBtn);
      }
      ob.appendChild(row);
    });
  } catch (e) { toast(e.message, "err"); }
}

document.getElementById("of-create").addEventListener("click", async () => {
  const title = document.getElementById("of-title").value.trim();
  const type = document.getElementById("of-type").value;
  const reward = parseInt(document.getElementById("of-reward").value);
  const duration = parseInt(document.getElementById("of-duration").value) || 0;
  if (!title || !reward) { toast("Remplis le titre et la récompense.", "err"); return; }
  try {
    await API.post("admin/offer_create", { title, type, reward_cents: reward, duration_seconds: duration });
    toast("Offre créée !");
    document.getElementById("of-title").value = "";
    document.getElementById("of-reward").value = "";
    loadAdmin();
  } catch (ex) { toast(ex.message, "err"); }
});

// ===== utils =====
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function slug(s) {
  return s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
function hostOf(url) {
  try { return new URL(url).hostname; } catch (e) { return url; }
}

// ===== modal close on backdrop =====
["video-modal", "ptc-modal", "survey-modal", "cpa-modal"].forEach((id) => {
  document.getElementById(id).addEventListener("click", (e) => {
    if (e.target.id === id) document.getElementById(id).classList.add("hidden");
  });
});

// ===== VIDÉO D'ACCUEIL (démo, sans argent, avec son) =====
let introShown = false;
function closeIntro() {
  localStorage.setItem("rb_intro_seen", "1");
  const m = document.getElementById("intro-modal");
  if (m) m.classList.add("hidden");
  const vid = document.getElementById("intro-video");
  try { vid.pause(); } catch (e) {}
}
function maybeShowIntro() {
  if (introShown) return;
  if (localStorage.getItem("rb_intro_seen") === "1") return;
  const m = document.getElementById("intro-modal");
  if (!m) return;
  introShown = true;
  m.classList.remove("hidden");
  const vid = document.getElementById("intro-video");
  vid.muted = false;
  vid.volume = 1;
}
document.getElementById("intro-play").addEventListener("click", async () => {
  const vid = document.getElementById("intro-video");
  vid.muted = false;
  vid.volume = 1;
  try { vid.currentTime = 0; await vid.play(); } catch (e) { toast("Clique sur lecture dans la vidéo pour entendre le son.", "err"); }
  document.getElementById("intro-play").classList.add("hidden");
  document.getElementById("intro-claim").classList.remove("hidden");
});
document.getElementById("intro-video").addEventListener("ended", () => {
  document.getElementById("intro-claim").classList.remove("hidden");
  document.getElementById("intro-play").classList.add("hidden");
});
document.getElementById("intro-claim").addEventListener("click", () => closeIntro());
document.getElementById("intro-skip").addEventListener("click", () => closeIntro());

// ===== boot =====
(async function boot() {
  if (!API.token) { showAuth(); return; }
  try {
    await refresh();
    showApp();
  } catch (e) {
    API.logout();
  }
})();
