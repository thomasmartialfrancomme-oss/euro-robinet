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
}

function showAuth() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
}
function showApp() {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
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

  // robinet
  if (d.faucet) setupFaucet(d.faucet);
  startFaucetTimer();

  // historique
  renderHistory(d.recent);

  // retrait
  document.getElementById("wd-balance").textContent = eur(u.balance);

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
    el.querySelector(".offer-btn").addEventListener("click", () => {
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
  faucetCooldown = faucet.cooldown || 180;
  faucetLastClaim = faucet.last_claim || 0;
  document.getElementById("faucet-min").textContent = eur(faucet.min || 1);
  document.getElementById("faucet-max").textContent = eur(faucet.max || 5);
  document.getElementById("faucet-cd").textContent = fmtSec(faucetCooldown);
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
    toast("Robinet : +" + eur(r.reward) + " gagné ! 🎉", "gold");
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
document.getElementById("clicker-start").addEventListener("click", () => {
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
document.getElementById("memory-start").addEventListener("click", buildMemory);
buildMemory();

// ===== BONUS =====
document.getElementById("claim-bonus-btn").addEventListener("click", async () => {
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
const WD_METHODS = { paypal: "Email PayPal", virement: "IBAN", crypto: "Adresse USDT (TRC20)" };
document.getElementById("wd-method").addEventListener("change", (e) => {
  document.getElementById("wd-details-label").textContent = WD_METHODS[e.target.value];
});
document.getElementById("wd-submit").addEventListener("click", async () => {
  const amount = parseFloat(document.getElementById("wd-amount").value);
  const method = document.getElementById("wd-method").value;
  const details = document.getElementById("wd-details").value.trim();
  if (!amount || isNaN(amount)) { toast("Indique un montant valide.", "err"); return; }
  const cents = Math.round(amount * 100);
  try {
    const r = await API.post("withdraw", { amount_cents: cents, method, details });
    toast(r.message || "Demande envoyée !", "gold");
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
      td.appendChild(ban); td.appendChild(add);
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
