
const DATA = window.DECK_CHARS || { characters: [], players: [], asciiRecords: [] };
const characters = Array.isArray(DATA.characters) ? DATA.characters : [];
const players = Array.isArray(DATA.players) ? DATA.players : [];
const asciiRecords = Array.isArray(DATA.asciiRecords) ? DATA.asciiRecords : [];

let currentCharacter = characters[0] || null;
let selectedCharacterActive = Boolean(currentCharacter);
let currentPlayerId = currentCharacter ? currentCharacter.playerId : "unknown";
let carouselOffset = 0;
let playerCarouselOffset = 0;
let currentArchiveList = characters.slice();

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

function escapeAttr(value) {
  return String(value ?? "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function normal(value) {
  return String(value ?? "").trim().toLowerCase();
}

function byId(id) {
  return characters.find(c => c.id === id) || null;
}

function factionClass(c) {
  return c && c.faction ? c.faction : "unknown";
}

function displayLevel(c) {
  return c && c.levelLabel ? c.levelLabel : "Level ?";
}

function hasHeroLegend(c) {
  return typeof c.level === "number" && c.level >= 26;
}

function miniStack(c) {
  return `<div class="mini-stack ${escapeHtml(factionClass(c))}" onclick="openCharacterById('${escapeAttr(c.id)}')">
    <article class="mini-card">
      <h3>${escapeHtml(c.name)}</h3>
      <div class="mini-art"></div>
      <p>${escapeHtml(c.race || "Unknown")}</p>
      <p>${escapeHtml(c.klass || "Unknown")}</p>
      <p>${escapeHtml(displayLevel(c))}</p>
    </article>
  </div>`;
}

function renderArchive(list = characters) {
  const grid = document.getElementById("archive-grid");
  if (!grid) return;
  currentArchiveList = list.slice();
  grid.innerHTML = list.map(miniStack).join("");
  const headerNote = document.querySelector("#archive-view .section-header p");
  if (headerNote) {
    headerNote.textContent = `Showing ${list.length.toLocaleString()} of ${characters.length.toLocaleString()} characters from the archive.`;
  }
  fitCardText();
}

function distinctValues(field, source = characters) {
  return Array.from(new Set(source.map(c => c[field]).filter(v => String(v || "").trim()))).sort((a, b) => String(a).localeCompare(String(b)));
}

function populateSelect(id, values, allLabel) {
  const select = document.getElementById(id);
  if (!select) return;
  const current = select.value;
  select.innerHTML = `<option value="">${escapeHtml(allLabel)}</option>` + values.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
  if (values.includes(current)) select.value = current;
}

function populateFilters() {
  populateSelect("archive-race", distinctValues("race"), "All races");
  populateSelect("archive-subrace", distinctValues("subrace"), "All subraces");
  populateSelect("archive-class", distinctValues("klass"), "All classes");
  populateSelect("archive-faction", distinctValues("factionLabel"), "All factions");
  populateSelect("archive-clan", distinctValues("clan"), "All clans");

  const playerChars = currentPlayerCharacters(true);
  populateSelect("player-race", distinctValues("race", playerChars), "All races");
  populateSelect("player-class", distinctValues("klass", playerChars), "All classes");
  populateSelect("player-clan", distinctValues("clan", playerChars), "All clans");
}

function filterArchive() {
  const race = document.getElementById("archive-race")?.value || "";
  const subrace = document.getElementById("archive-subrace")?.value || "";
  const klass = document.getElementById("archive-class")?.value || "";
  const faction = document.getElementById("archive-faction")?.value || "";
  const clan = document.getElementById("archive-clan")?.value || "";
  const sort = document.getElementById("archive-sort")?.value || "name";
  const q = normal(document.getElementById("archive-search")?.value || "");

  let filtered = characters.filter(c => {
    if (race && c.race !== race) return false;
    if (subrace && c.subrace !== subrace) return false;
    if (klass && c.klass !== klass) return false;
    if (faction && c.factionLabel !== faction) return false;
    if (clan && c.clan !== clan) return false;
    if (q) {
      const haystack = [c.name, c.player, c.race, c.subrace, c.klass, c.factionLabel, c.clan, c.active, c.classificationStatus].join(" ").toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    if (sort === "level_desc") return (b.level || -1) - (a.level || -1) || a.name.localeCompare(b.name);
    if (sort === "active") return String(a.active).localeCompare(String(b.active)) || a.name.localeCompare(b.name);
    return a.name.localeCompare(b.name);
  });

  renderArchive(filtered);
}

function scrollToPanel() {
  const panel = document.getElementById("character-panel");
  if (panel) panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showArchive() {
  const archive = document.getElementById("archive-view");
  const character = document.getElementById("character-view");
  const panel = document.getElementById("character-panel");

  if (archive) archive.classList.add("is-visible");
  if (character) character.classList.remove("is-visible");
  if (panel) panel.classList.remove("is-spread", "is-player-info");

  closeScroll();
  filterArchive();
}

function openCharacter(name, player = "") {
  const target = characters.find(c => c.name === name && (!player || c.player === player))
    || characters.find(c => c.name === name)
    || characters[0];
  if (target) openCharacterById(target.id);
}

function openCharacterById(id) {
  const target = byId(id);
  if (!target) return;

  currentCharacter = target;
  currentPlayerId = target.playerId || "unknown";
  selectedCharacterActive = true;

  const archive = document.getElementById("archive-view");
  const character = document.getElementById("character-view");
  const panel = document.getElementById("character-panel");

  if (archive) archive.classList.remove("is-visible");
  if (character) character.classList.add("is-visible");
  if (panel) panel.classList.remove("is-spread", "is-player-info");

  setCharacterPanel(target);
  renderRelated();
  renderCarouselCards();
  renderPlayerCarousel();
  populateFilters();

  setTimeout(() => {
    scrollToPanel();
    fitCardText();
  }, 0);
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value || "—";
}

function setCharacterPanel(c) {
  setText("filter-player-name", c.player || "Unknown");
  setText("player-card-name", c.player || "Unknown");

  setText("identity-name", c.name);
  setText("identity-race", c.race || "Unknown");
  setText("identity-class", c.klass || "Unknown");
  setText("identity-level", displayLevel(c));

  setText("strip-player", c.player || "Unknown");
  setText("strip-name", c.name);
  setText("strip-race", c.race || "Unknown");
  setText("strip-class", c.klass || "Unknown");
  setText("strip-level", displayLevel(c));
  setText("strip-clan", c.clan || "—");
  setText("strip-active", c.active || "unknown");

  const mainCard = document.getElementById("main-identity-card");
  if (mainCard) mainCard.className = `char-card identity-card ${factionClass(c)}`;

  const parked = document.getElementById("parked-player-deck");
  if (parked) parked.className = `parked-player-deck ${factionClass(c)}`;

  const terminal = document.getElementById("whois-terminal");
  if (terminal) {
    const pre = terminal.querySelector("pre");
    if (pre) {
      pre.textContent = c.whoisText
        ? c.whoisText
        : `WHOIS: ${c.name}\n\nNo preserved whois display is available yet for this character.`;
    }
  }

  renderStackEdges();
}

function availableCards(c) {
  const cards = ["Facts"];
  if (c.hasWhois) cards.push("Whois");
  if (c.clan) cards.push("Clan");
  if (c.mentionCount > 0) cards.push("Logs");
  if (hasHeroLegend(c) || c.faction === "immortal") cards.push("Deeds");
  // Trophy data is not wired to the archive yet.
  cards.push("Sources");
  return cards;
}

function renderStackEdges() {
  const stack = document.querySelector("#character-view .stack-unspread");
  if (!stack || !currentCharacter) return;
  const existingIdentity = stack.querySelector("#main-identity-card");
  const cards = availableCards(currentCharacter);
  stack.querySelectorAll(".stack-card-edge").forEach(el => el.remove());
  cards.forEach((label, idx) => {
    const edge = document.createElement("article");
    edge.className = "card-edge stack-card-edge";
    edge.dataset.label = label;
    edge.textContent = label;
    edge.onclick = () => openStackCard(idx + 1);
    stack.appendChild(edge);
  });
}

function renderCarouselCards() {
  const track = document.getElementById("carousel-track");
  if (!track || !currentCharacter) return;
  const c = currentCharacter;
  const parts = [];

  parts.push(`<article class="char-card identity-card ${escapeHtml(factionClass(c))}" onclick="pileCards()">
    <div class="card-name">${escapeHtml(c.name)}</div><div class="portrait"></div>
    <p>${escapeHtml(c.race || "Unknown")}</p><p>${escapeHtml(c.klass || "Unknown")}</p><p>${escapeHtml(displayLevel(c))}</p>
  </article>`);

  parts.push(`<article class="char-card info-card"><h3>Facts</h3><div class="card-symbol">✺</div>
    <ul>
      <li>Race: ${escapeHtml(c.race || "Unknown")}</li>
      <li>Class: ${escapeHtml(c.klass || "Unknown")}</li>
      <li>Faction: ${escapeHtml(c.factionLabel || "Unknown")}</li>
      <li>Active: ${escapeHtml(c.active || "unknown")}</li>
    </ul></article>`);

  if (c.hasWhois) {
    parts.push(`<article class="char-card info-card"><h3>Whois</h3><div class="card-symbol">⌁</div>
      <p>Preserved terminal evidence exists.</p><p>${escapeHtml(c.captureQuality || "")}</p>
      <button onclick="openScroll('whois')">Open whois</button></article>`);
  }

  if (c.clan) {
    parts.push(`<article class="char-card info-card special-card"><h3>Clan</h3><div class="card-symbol">⚑</div><p>${escapeHtml(c.clan)}</p></article>`);
  }

  if (c.mentionCount > 0) {
    parts.push(`<article class="char-card info-card"><h3>Logs</h3><div class="card-symbol">✒</div>
      <p>${c.mentionCount.toLocaleString()} archive mentions</p><button onclick="openScroll('logs')">more…</button></article>`);
  }

  if (hasHeroLegend(c) || c.faction === "immortal") {
    const deedText = c.faction === "immortal" ? displayLevel(c) : "Hero / Legend";
    parts.push(`<article class="char-card info-card"><h3>Deeds</h3><div class="card-symbol">♕</div><p>${escapeHtml(deedText)}</p><p>${escapeHtml(c.classificationStatus || "")}</p></article>`);
  }

  parts.push(`<article class="char-card info-card"><h3>Sources</h3><div class="card-symbol">▣</div>
    <p>${escapeHtml(c.playerConfidence || "unknown")} player link confidence</p>
    <button onclick="openScroll('sources')">Open sources</button></article>`);

  track.innerHTML = parts.join("");
  carouselOffset = 0;
  updateCarousel();
}

function openStackCard(index) {
  selectedCharacterActive = true;
  spreadCards();
  carouselOffset = Math.max(0, index);
  updateCarousel();
}

function spreadCards() {
  const panel = document.getElementById("character-panel");
  if (!panel) return;
  panel.classList.remove("is-player-info");
  panel.classList.add("is-spread");
}

function pileCards() {
  const panel = document.getElementById("character-panel");
  if (panel) panel.classList.remove("is-spread", "is-player-info");
  carouselOffset = 0;
  playerCarouselOffset = 0;
  updateCarousel();
  updatePlayerCarousel();
}

function openPlayerDeck() {
  const panel = document.getElementById("character-panel");
  if (!panel) return;

  if (panel.classList.contains("is-spread")) {
    pileCards();
    return;
  }

  selectedCharacterActive = false;
  panel.classList.remove("is-spread");
  panel.classList.add("is-player-info");
  playerCarouselOffset = 0;
  renderPlayerCarousel();
  updatePlayerCarousel();
}

function carouselNudge(direction) {
  const track = document.getElementById("carousel-track");
  if (!track) return;
  const max = Math.max(0, track.children.length - 4);
  carouselOffset = Math.min(max, Math.max(0, carouselOffset + direction));
  updateCarousel();
}

function updateCarousel() {
  const track = document.getElementById("carousel-track");
  if (!track) return;
  track.style.transform = `translateX(${-carouselOffset * 276}px)`;
}

function playerCarouselNudge(direction) {
  const track = document.getElementById("player-carousel-track");
  if (!track) return;
  const max = Math.max(0, track.children.length - 4);
  playerCarouselOffset = Math.min(max, Math.max(0, playerCarouselOffset + direction));
  updatePlayerCarousel();
}

function updatePlayerCarousel() {
  const track = document.getElementById("player-carousel-track");
  if (!track) return;
  track.style.transform = `translateX(${-playerCarouselOffset * 276}px)`;
}

function currentPlayerCharacters(includeCurrent = false) {
  if (!currentCharacter) return [];
  return characters.filter(c => c.playerId === currentCharacter.playerId && (includeCurrent || c.id !== currentCharacter.id));
}

function renderRelated(list = null) {
  const grid = document.getElementById("related-grid");
  if (!grid || !currentCharacter) return;

  const related = list || currentPlayerCharacters(false);
  grid.className = "character-grid compact";
  grid.innerHTML = related.map(miniStack).join("");

  const title = currentCharacter.player === "Unknown" ? "Related Archive Candidates" : `Other Characters Played by ${currentCharacter.player}`;
  setText("related-title", title);
  fitCardText();
}

function filterPlayerCharacters() {
  if (!currentCharacter) return;
  const race = document.getElementById("player-race")?.value || "";
  const klass = document.getElementById("player-class")?.value || "";
  const clan = document.getElementById("player-clan")?.value || "";
  const status = document.getElementById("player-status")?.value || "";
  const q = normal(document.getElementById("player-search")?.value || "");

  let list = currentPlayerCharacters(false).filter(c => {
    if (race && c.race !== race) return false;
    if (klass && c.klass !== klass) return false;
    if (clan && c.clan !== clan) return false;
    if (status === "hero_legend" && !hasHeroLegend(c)) return false;
    if (status === "has_whois" && !c.hasWhois) return false;
    if (status === "needs_review" && !c.reviewNeeded) return false;
    if (q) {
      const haystack = [c.name, c.race, c.klass, c.factionLabel, c.clan, c.active, c.classificationStatus].join(" ").toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  renderRelated(list);
}

function renderPlayerCarousel() {
  const track = document.getElementById("player-carousel-track");
  if (!track || !currentCharacter) return;
  const summary = players.find(p => p.playerId === currentCharacter.playerId) || {
    name: currentCharacter.player,
    characterCount: currentPlayerCharacters(true).length,
    knownWhoisCount: currentPlayerCharacters(true).filter(c => c.hasWhois).length,
    highestLevel: null,
    highestLevelCharacters: [],
    factions: [],
    activeSummary: "unknown"
  };

  track.innerHTML = `
    <article class="char-card info-card player-info-card"><h3>Player</h3><div class="card-symbol">♜</div><p class="player-info-name">${escapeHtml(summary.name || "Unknown")}</p><p>${escapeHtml(currentCharacter.playerConfidence || "unknown")} confidence</p></article>
    <article class="char-card info-card player-info-card"><h3>Characters</h3><div class="card-symbol">☷</div><p>${summary.characterCount || 0} known characters</p><p>${summary.knownWhoisCount || 0} with whois evidence</p></article>
    <article class="char-card info-card player-info-card"><h3>Highest</h3><div class="card-symbol">▲</div><p>${summary.highestLevel ? "Level " + summary.highestLevel : "unknown"}</p><p>${escapeHtml((summary.highestLevelCharacters || []).join(", "))}</p></article>
    <article class="char-card info-card player-info-card"><h3>Active</h3><div class="card-symbol">◷</div><p>${escapeHtml(summary.activeSummary || "unknown")}</p><p>Refined as evidence grows</p></article>
    <article class="char-card info-card player-info-card"><h3>Factions</h3><div class="card-symbol">⚖</div><p>${escapeHtml((summary.factions || []).join(", ") || "Unknown")}</p></article>
    <article class="char-card info-card player-info-card"><h3>Sources</h3><div class="card-symbol">▣</div><p>Whois archive</p><p>Historical lists</p><button onclick="openScroll('player-sources')">Open sources</button></article>
  `;
}

function drawRandomAscii() {
  if (!asciiRecords.length) return;
  const record = asciiRecords[Math.floor(Math.random() * asciiRecords.length)];
  const pre = document.getElementById("ascii-pre");
  const card = document.getElementById("ascii-card");
  if (pre) pre.textContent = record.text;
  if (card) card.onclick = () => openCharacterById(record.characterId);
}

function openScroll(kind) {
  const overlay = document.getElementById("scroll-overlay");
  const title = document.getElementById("scroll-title");
  const body = document.getElementById("scroll-body");
  if (!overlay || !title || !body || !currentCharacter) return;

  const c = currentCharacter;

  if (kind === "player-sources") {
    title.textContent = "Player Sources";
    body.innerHTML = `<div class="scroll-row source">Player: ${escapeHtml(c.player || "Unknown")}</div>
      <div class="scroll-row source">Player link confidence: ${escapeHtml(c.playerConfidence || "unknown")}</div>
      <div class="scroll-row source">Player ID: ${escapeHtml(c.playerId || "unknown")}</div>`;
  } else if (kind === "logs") {
    title.textContent = "Archive Mentions";
    body.innerHTML = `<div class="scroll-row source">${escapeHtml(c.name)} has ${c.mentionCount.toLocaleString()} mention(s) in the current archive manifest.</div>
      <div class="scroll-row source">Detailed log references are a later data join.</div>`;
  } else if (kind === "whois") {
    title.textContent = "Whois Evidence";
    body.innerHTML = `<pre>${escapeHtml(c.whoisText || "No whois text available.")}</pre>`;
  } else {
    title.textContent = "Sources";
    body.innerHTML = (c.sources || []).map(s => `<div class="scroll-row source">${escapeHtml(s)}</div>`).join("");
  }

  overlay.hidden = false;
}

function closeScroll() {
  const overlay = document.getElementById("scroll-overlay");
  if (overlay) overlay.hidden = true;
}

function showTrophies(scope = "auto") {
  const grid = document.getElementById("related-grid");
  if (!grid) return;
  setText("related-title", "Trophy Kills — data not yet connected");
  grid.className = "trophy-grid";
  grid.innerHTML = `<article class="char-card info-card"><h3>Trophies</h3><div class="card-symbol">♕</div><p>Trophy data is not yet wired to the real archive.</p></article>`;
}

function fitCardText() {
  document.querySelectorAll("#character-view .card-name, #character-view .info-card h3, .mini-card h3").forEach(el => {
    el.style.fontSize = "";
    const max = el.clientWidth;
    let size = parseFloat(getComputedStyle(el).fontSize);
    let guard = 0;
    while (el.scrollWidth > max && size > 10 && guard < 36) {
      size -= 1;
      el.style.fontSize = `${size}px`;
      guard += 1;
    }
  });
}

// Backwards compatibility with earlier CSS/JS hooks.
const fitCardTextV12 = fitCardText;

function initialiseDeckOfChars() {
  populateFilters();
  renderArchive(characters);
  if (characters.length) {
    currentCharacter = characters[0];
    currentPlayerId = currentCharacter.playerId;
    setCharacterPanel(currentCharacter);
    renderRelated();
    renderCarouselCards();
    renderPlayerCarousel();
  }
  drawRandomAscii();
  fitCardText();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialiseDeckOfChars);
} else {
  initialiseDeckOfChars();
}
window.addEventListener("resize", fitCardText);
