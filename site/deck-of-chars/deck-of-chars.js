
const DATA = window.DECK_CHARS || { characters: [], players: [], asciiRecords: [] };
const rawCharacters = Array.isArray(DATA.characters) ? DATA.characters : [];
const characters = deduplicateAccentedCharacters(rawCharacters);
const rawPlayers = Array.isArray(DATA.players) ? DATA.players : [];
const players = refreshPlayerSummaries(rawPlayers, characters);
const asciiRecords = Array.isArray(DATA.asciiRecords) ? DATA.asciiRecords : [];
const portraitFiles = new Set(Array.isArray(DATA.portraitFiles) ? DATA.portraitFiles : []);

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

function stripPronunciationMarks(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/Æ/g, "AE").replace(/æ/g, "ae")
    .replace(/Œ/g, "OE").replace(/œ/g, "oe")
    .replace(/[ÐĐ]/g, "D").replace(/[ðđ]/g, "d")
    .replace(/Þ/g, "TH").replace(/þ/g, "th")
    .replace(/Ø/g, "O").replace(/ø/g, "o")
    .replace(/Ł/g, "L").replace(/ł/g, "l")
    .replace(/ß/g, "ss");
}

function accentlessNameKey(value) {
  return stripPronunciationMarks(value).toLocaleLowerCase("en");
}

function hasPronunciationMark(value) {
  const name = String(value || "");
  return name !== stripPronunciationMarks(name);
}

function characterRecordQuality(c) {
  return (c?.hasWhois ? 100000 : 0)
    + (typeof c?.level === "number" ? 10000 : 0)
    + Number(c?.mentionCount || 0)
    + Number(c?.sources?.length || 0);
}

function deduplicateAccentedCharacters(source) {
  const groups = new Map();
  source.forEach(c => {
    const key = accentlessNameKey(c?.name);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(c);
  });

  const results = [];
  groups.forEach(group => {
    if (new Set(group.map(c => c.name)).size < 2) {
      results.push(...group);
      return;
    }
    const preferred = group.slice().sort((a, b) => {
      const markDifference = Number(hasPronunciationMark(b.name)) - Number(hasPronunciationMark(a.name));
      return markDifference || characterRecordQuality(b) - characterRecordQuality(a);
    })[0];
    results.push(preferred);
  });
  return results;
}

function refreshPlayerSummaries(source, characterList) {
  const byPlayer = new Map();
  characterList.forEach(c => {
    const playerId = c.playerId || "unknown";
    if (!byPlayer.has(playerId)) byPlayer.set(playerId, []);
    byPlayer.get(playerId).push(c);
  });
  return source.map(player => {
    const playerCharacters = byPlayer.get(player.playerId || "unknown") || [];
    const levels = playerCharacters.map(c => c.level).filter(Number.isInteger);
    const highestLevel = levels.length ? Math.max(...levels) : null;
    return {
      ...player,
      characterCount: playerCharacters.length,
      knownWhoisCount: playerCharacters.filter(c => c.hasWhois).length,
      highestLevel,
      highestLevelCharacters: highestLevel === null
        ? []
        : playerCharacters.filter(c => c.level === highestLevel).map(c => c.name)
    };
  });
}

function byId(id) {
  return characters.find(c => c.id === id) || null;
}

function factionClass(c) {
  return c && c.faction ? c.faction : "unknown";
}

function displayClass(c) {
  const klass = String(c?.klass || "").trim();
  if (portraitRace(c) === "Orc" && normal(klass) === "cleric") return "Shaman";
  if (normal(klass) === "magic-user") return "Mage";
  return klass;
}

const PORTRAIT_ASSET_PATH = "assets/cards/";

function portraitToken(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join("_");
}

function portraitRace(c) {
  const raw = String(c?.raceRaw || c?.race || "").trim();
  if (normal(raw) === "man") return "Human";
  return portraitToken(raw);
}

function portraitSubrace(c) {
  let raw = String(c?.subrace || "").trim();
  if (portraitRace(c) === "Troll") raw = raw.replace(/\s+Troll$/i, "");
  return portraitToken(raw);
}

function knownPortraitClass(c) {
  const raw = normal(c?.classRaw || c?.klass);
  const knownClasses = {
    "warrior": "Warrior",
    "magic-user": "Mage",
    "mage": "Mage",
    "cleric": "Cleric",
    "ranger": "Scout",
    "scout": "Scout",
    "thief": "Scout"
  };
  return knownClasses[raw] || "";
}

function defaultPortraitClass(c) {
  const race = portraitRace(c);
  const subrace = portraitSubrace(c);
  if (subrace === "Black_Numenorean") return "Mage";
  if (["Elf", "Half_Elf", "Hobbit"].includes(race)) return "Scout";
  return "Warrior";
}

function portraitClassPriorities(c) {
  return Array.from(new Set([knownPortraitClass(c), defaultPortraitClass(c)].filter(Boolean)));
}

function portraitClassGroup(value) {
  const token = portraitToken(value);
  if (["Scout", "Thief", "Ranger"].includes(token)) return "Scout";
  if (["Mage", "Magic_User"].includes(token)) return "Mage";
  return token;
}

function parsePortraitFile(filename) {
  const stem = String(filename || "").replace(/\.png$/i, "");
  const parts = stem.split("-");
  if (!parts[0]) return null;
  return {
    filename,
    race: parts[0] || "",
    klass: parts[1] || "",
    gender: parts[2] || "",
    subrace: parts.slice(3).join("-")
  };
}

const portraitCatalog = Array.from(portraitFiles).map(parsePortraitFile).filter(Boolean);
const portraitFileLookup = new Map(
  Array.from(portraitFiles).map(filename => [normal(filename), filename])
);

function stablePortraitHash(value) {
  let hash = 2166136261;
  for (const character of String(value || "")) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

const IMMORTAL_RANK_ALIASES = Object.freeze({
  Implementor: "Implementor",
  Implementors: "Implementor",
  Creators_Of_Arda: "Implementor",
  Arata: "Arata",
  Aratar: "Arata",
  Vala: "Vala",
  Valar: "Vala",
  Maia: "Maia",
  Maiar: "Maia",
  Boardreader: "Boardreader",
  Boardreaders: "Boardreader"
});

const IMMORTAL_MAIA_LEVELS = Object.freeze([
  "Boardreader",
  "Cartographer",
  "Builder",
  "Wright",
  "Shaper"
]);

function normaliseImmortalRank(value) {
  const token = portraitToken(value);
  return IMMORTAL_RANK_ALIASES[token] || token;
}

function normaliseImmortalRole(value) {
  const token = portraitToken(value);
  if (token === "Mudller") return "Mudller";
  if (["Architect", ...IMMORTAL_MAIA_LEVELS].includes(token)) return token;
  return "";
}

function immortalPortraitProfile(c) {
  const rankValues = [
    c?.derivedImmortalRank,
    c?.raceRaw,
    c?.race,
    c?.immortalListCategory
  ];
  const knownRanks = new Set(["Implementor", "Arata", "Vala", "Maia", "Boardreader"]);
  const rank = rankValues
    .map(normaliseImmortalRank)
    .find(value => knownRanks.has(value)) || "";
  const role = normaliseImmortalRole(c?.derivedImmortalRole || c?.subrace);

  if (rank === "Boardreader") return { rank: "Maia", level: "Boardreader" };
  if (rank === "Maia") {
    return {
      rank,
      level: IMMORTAL_MAIA_LEVELS.includes(role) ? role : "Boardreader"
    };
  }
  if (rank === "Vala") {
    return {
      rank,
      level: ["Architect", "Mudller"].includes(role) ? role : ""
    };
  }
  return { rank, level: "" };
}

function maiaPortraitFilenameGroup(level) {
  if (level === "Boardreader") {
    return [
      "Maia-Boardreader.png",
      "Maia.png",
      "Boardreader.png",
      "Maiar-Boardreader.png",
      "Maiar.png"
    ];
  }
  return [`Maia-${level}.png`, `Maiar-${level}.png`];
}

function maiaPortraitLevelOrder(level) {
  const targetIndex = IMMORTAL_MAIA_LEVELS.indexOf(level);
  if (targetIndex < 0) return IMMORTAL_MAIA_LEVELS.slice();
  if (level === "Boardreader") return ["Boardreader"];
  return [
    level,
    ...IMMORTAL_MAIA_LEVELS.slice(1, targetIndex).reverse(),
    ...IMMORTAL_MAIA_LEVELS.slice(targetIndex + 1),
    "Boardreader"
  ];
}

function immortalPortraitFilenameGroups(c) {
  const { rank, level } = immortalPortraitProfile(c);
  const groups = [];
  const addMaiaFallbacks = startLevel => {
    maiaPortraitLevelOrder(startLevel).forEach(maiaLevel => {
      groups.push(maiaPortraitFilenameGroup(maiaLevel));
    });
  };
  const valaGeneric = ["Vala.png", "Valar.png"];
  const valaArchitect = ["Vala-Architect.png", "Valar-Architect.png"];
  const valaMudller = [
    "Vala-Mudller.png",
    "Valar-Mudller.png"
  ];

  if (rank === "Implementor") {
    groups.push(["Implementor.png", "Implementors.png"]);
    groups.push(["Arata.png", "Aratar.png"]);
    groups.push(valaGeneric, valaArchitect, valaMudller);
    addMaiaFallbacks("Shaper");
  } else if (rank === "Arata") {
    groups.push(["Arata.png", "Aratar.png"]);
    groups.push(valaGeneric, valaArchitect, valaMudller);
    addMaiaFallbacks("Shaper");
  } else if (rank === "Vala") {
    if (level === "Architect") groups.push(valaArchitect);
    if (level === "Mudller") groups.push(valaMudller);
    groups.push(valaGeneric);
    if (level === "Architect") groups.push(valaMudller);
    else if (level === "Mudller") groups.push(valaArchitect);
    else groups.push(valaArchitect, valaMudller);
    addMaiaFallbacks("Shaper");
  } else if (rank === "Maia") {
    addMaiaFallbacks(level || "Boardreader");
  } else {
    groups.push(maiaPortraitFilenameGroup("Boardreader"));
  }

  return groups;
}

function immortalPortraitFilenames(c) {
  const filenames = [];
  immortalPortraitFilenameGroups(c).forEach(group => {
    group.forEach(candidate => {
      const filename = portraitFiles.size
        ? portraitFileLookup.get(normal(candidate))
        : candidate;
      if (filename && !filenames.includes(filename)) filenames.push(filename);
    });
  });
  return filenames;
}

function portraitMatchScore(portrait, c, raceChoices, gender, subrace) {
  const raceRank = raceChoices.indexOf(portrait.race);
  let subraceRank = 0;
  if (subrace) {
    if (portrait.subrace === subrace) subraceRank = 0;
    else if (!portrait.subrace) subraceRank = 1;
    else subraceRank = 2;
  } else {
    subraceRank = portrait.subrace ? 1 : 0;
  }

  let genderRank = 0;
  if (portrait.gender === gender) genderRank = 0;
  else if (portrait.gender === "Male") genderRank = 1;
  else if (!portrait.gender) genderRank = 2;
  else genderRank = 3;

  return raceRank * 100 + subraceRank * 10 + genderRank;
}

function chooseBestPortrait(options, c, raceChoices, gender, subrace, salt) {
  if (!options.length) return null;
  const scored = options.map(portrait => ({
    portrait,
    score: portraitMatchScore(portrait, c, raceChoices, gender, subrace)
  }));
  const bestScore = Math.min(...scored.map(item => item.score));
  const tied = scored
    .filter(item => item.score === bestScore)
    .map(item => item.portrait)
    .sort((a, b) => a.filename.localeCompare(b.filename));
  const seed = c?.id || c?.name || `${portraitRace(c)}-${portraitSubrace(c)}`;
  return tied[stablePortraitHash(`${seed}:${salt}`) % tied.length];
}

function selectPortrait(c) {
  const race = portraitRace(c);
  const raceChoices = race === "Half_Elf" ? ["Half_Elf", "Elf"] : [race];
  const gender = normal(c?.gender) && normal(c?.gender) !== "unknown"
    ? portraitToken(c?.gender)
    : "Male";
  const subrace = portraitSubrace(c);
  const raceMatches = portraitCatalog.filter(portrait => raceChoices.includes(portrait.race));
  if (!raceMatches.length) return null;

  for (const klass of portraitClassPriorities(c)) {
    const classMatches = raceMatches.filter(portrait => portraitClassGroup(portrait.klass) === klass);
    const selected = chooseBestPortrait(classMatches, c, raceChoices, gender, subrace, klass);
    if (selected) return selected;
  }

  const genericMatches = raceMatches.filter(portrait => !portrait.klass);
  return chooseBestPortrait(genericMatches, c, raceChoices, gender, subrace, "generic")
    || chooseBestPortrait(raceMatches, c, raceChoices, gender, subrace, "any");
}

function unmanifestedPortraitCandidates(c) {
  const race = portraitRace(c);
  const raceChoices = race === "Half_Elf" ? ["Half_Elf", "Elf"] : [race];
  const gender = normal(c?.gender) && normal(c?.gender) !== "unknown"
    ? portraitToken(c?.gender)
    : "Male";
  const subrace = portraitSubrace(c);
  const filenames = [];
  const classNames = klass => klass === "Scout" ? ["Scout", "Thief", "Ranger"] : [klass];
  const add = (...parts) => {
    if (!parts[0] || parts.some(part => !part)) return;
    const filename = `${parts.join("-")}.png`;
    if (!filenames.includes(filename)) filenames.push(filename);
  };

  raceChoices.forEach(raceName => {
    portraitClassPriorities(c).forEach(klass => classNames(klass).forEach(className => {
      add(raceName, className, gender, subrace);
      add(raceName, className, gender);
      add(raceName, className, subrace);
      add(raceName, className);
    }));
    add(raceName, subrace);
    add(raceName);
  });
  add("Unknown");
  return filenames;
}

function portraitCandidates(c) {
  if (normal(c?.faction) === "immortal") {
    return immortalPortraitFilenames(c).map(filename => `${PORTRAIT_ASSET_PATH}${filename}`);
  }
  if (portraitCatalog.length) {
    const selected = selectPortrait(c);
    return selected ? [`${PORTRAIT_ASSET_PATH}${selected.filename}`] : [];
  }
  return unmanifestedPortraitCandidates(c).map(filename => `${PORTRAIT_ASSET_PATH}${filename}`);
}

function advancePortraitFallback(image) {
  const candidates = String(image.dataset.portraitCandidates || "").split("|").filter(Boolean);
  const nextIndex = Number(image.dataset.portraitIndex || 0) + 1;
  if (nextIndex >= candidates.length) {
    image.hidden = true;
    image.removeAttribute("src");
    return;
  }
  image.dataset.portraitIndex = String(nextIndex);
  image.src = candidates[nextIndex];
}

function portraitOverlayHtml(c) {
  const candidates = portraitCandidates(c);
  if (!candidates.length) return "";
  return `<img class="character-card-overlay" src="${escapeHtml(candidates[0])}" data-portrait-candidates="${escapeHtml(candidates.join("|"))}" data-portrait-index="0" onerror="advancePortraitFallback(this)" alt="">`;
}

function setCardPortrait(card, c) {
  if (!card) return;
  let image = card.querySelector(".character-card-overlay");
  const candidates = portraitCandidates(c);

  if (!candidates.length) {
    if (image) {
      image.hidden = true;
      image.removeAttribute("src");
    }
    return;
  }

  if (!image) {
    image = document.createElement("img");
    image.className = "character-card-overlay";
    image.alt = "";
    image.onerror = () => advancePortraitFallback(image);
    card.prepend(image);
  }

  image.hidden = false;
  image.dataset.portraitCandidates = candidates.join("|");
  image.dataset.portraitIndex = "0";
  image.src = candidates[0];
}

function displayLevel(c) {
  if (!c) return "";
  if (c.faction === "immortal") return "";
  if (c.levelLabel) return c.levelLabel;
  if (typeof c.level === "number") return `Level ${c.level}`;
  return "Level ?";
}

function displayIdentitySecondLine(c) {
  if (!c) return "";
  if (c.faction === "immortal") return c.subrace || "";
  return displayClass(c);
}

function displayIdentityLevelLine(c) {
  if (!c) return "Level ?";
  if (c.faction === "immortal" && !c.levelLabel) return "";
  return displayLevel(c);
}

function identityCardLines(c) {
  const skip = new Set(["", "Unknown", "unknown", "Level ?", "—", "-"]);
  const values = [
    c?.raceRaw || c?.race || "",
    c?.subrace || "",
    displayClass(c),
    displayLevel(c) || ""
  ];

  return values
    .map(v => String(v || "").trim())
    .filter(v => !skip.has(v))
    .map(v => `<p>${escapeHtml(v)}</p>`)
    .join("");
}

function hasHeroLegend(c) {
  return typeof c.level === "number" && c.level >= 26;
}

function miniStack(c) {
  return `<div class="mini-stack ${escapeHtml(factionClass(c))}" onclick="openCharacterById('${escapeAttr(c.id)}')">
    <article class="mini-card">
      ${portraitOverlayHtml(c)}
      <h3>${escapeHtml(c.name)}</h3>
      <div class="mini-art"></div>
      ${identityCardLines(c)}
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
      const haystack = [c.name, c.player, c.race, c.subrace, c.klass, displayClass(c), c.factionLabel, c.clan, c.active, c.classificationStatus].join(" ").toLowerCase();
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

function setOptionalText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  const text = String(value || "").trim();
  el.textContent = text;
  el.style.display = text ? "" : "none";
}

function renderTerminalContent(pre, c) {
  if (!pre || !c) return;
  pre.classList.toggle("has-colour-whois", Boolean(c.whoisHtml));
  if (c.whoisHtml) pre.innerHTML = c.whoisHtml;
  else if (c.whoisText) pre.textContent = c.whoisText;
  else pre.textContent = `WHOIS: ${c.name}

No preserved whois display is available yet for this character.`;
}

function setCharacterPanel(c) {
  setText("filter-player-name", c.player || "Unknown");
  setText("player-card-name", c.player || "Unknown");
  setText("identity-name", c.name);
  setOptionalText("identity-race", c.raceRaw || c.race || "Unknown");
  setOptionalText("identity-class", displayIdentitySecondLine(c));
  setOptionalText("identity-level", displayIdentityLevelLine(c));
  setText("strip-player", c.player || "Unknown");
  setText("strip-name", c.name);
  setText("strip-race", c.race || "Unknown");
  setText("strip-class", displayClass(c) || "—");
  setText("strip-level", displayIdentityLevelLine(c) || "—");
  setText("strip-clan", c.clan || "—");
  setText("strip-active", c.active || "unknown");
  const mainCard = document.getElementById("main-identity-card");
  if (mainCard) {
    mainCard.className = `char-card identity-card ${factionClass(c)}`;
    setCardPortrait(mainCard, c);
  }
  const parked = document.getElementById("parked-player-deck");
  if (parked) parked.className = `parked-player-deck player-back-${c.playerCardFaction || "free"}`;
  const terminal = document.getElementById("whois-terminal");
  if (terminal) renderTerminalContent(terminal.querySelector("pre"), c);
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
    ${portraitOverlayHtml(c)}
    <div class="card-name">${escapeHtml(c.name)}</div><div class="portrait"></div>
    ${identityCardLines(c)}
  </article>`);

  parts.push(`<article class="char-card info-card"><h3>Facts</h3><div class="card-symbol">✺</div>
    <ul>
      <li>Race: ${escapeHtml(c.raceRaw || c.race || "Unknown")}</li>
      ${c.subrace ? `<li>Subrace: ${escapeHtml(c.subrace)}</li>` : ""}
      <li>Class: ${escapeHtml(displayClass(c) || "Unknown")}</li>
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
      const haystack = [c.name, c.race, c.klass, displayClass(c), c.factionLabel, c.clan, c.active, c.classificationStatus].join(" ").toLowerCase();
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
    <article class="char-card info-card player-info-card"><h3>Player</h3><div class="card-symbol">♜</div><p class="player-info-name">${escapeHtml(summary.name || "Unknown")}</p><p>${escapeHtml(currentCharacter.playerConfidence || "unknown")} confidence</p>${summary.realFirstName ? `<p>Known first name: ${escapeHtml(summary.realFirstName)}</p>` : ""}</article>
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
  if (pre) {
    if (record.html) { pre.classList.add("has-colour-whois"); pre.innerHTML = record.html; }
    else { pre.classList.remove("has-colour-whois"); pre.textContent = record.text || ""; }
  }
  if (card) {
    card.disabled = false;
    card.onclick = () => openCharacter(record.player || "", record.name || "");
  }
  if (card) card.onclick = () => openCharacterById(record.characterId);
}

function clearSearch(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.value = "";
  if (inputId === "archive-search") filterArchive();
  if (inputId === "player-search") filterPlayerCharacters();
  input.focus();
}

function renderSourceSection(source) {
  const raw = String(source || "").trim();
  if (!raw) return "";

  const colonIndex = raw.indexOf(":");

  let heading = "Source";
  let detail = raw;

  if (colonIndex > 0) {
    heading = raw.slice(0, colonIndex).trim();
    detail = raw.slice(colonIndex + 1).trim();
  }

  return `<section class="scroll-source-section">
    <h3>${escapeHtml(heading)}</h3>
    <div class="scroll-source-detail">${escapeHtml(detail)}</div>
  </section>`;
}

function openScroll(kind) {
  const overlay = document.getElementById("scroll-overlay");
  const title = document.getElementById("scroll-title");
  const body = document.getElementById("scroll-body");
  if (!overlay || !title || !body || !currentCharacter) return;

  const c = currentCharacter;

  if (kind === "player-sources") {
    title.textContent = "Player Sources";
    body.innerHTML = [
      renderSourceSection(`Player: ${c.player || "Unknown"}`),
      renderSourceSection(`Player link confidence: ${c.playerConfidence || "unknown"}`),
      renderSourceSection(`Player ID: ${c.playerId || "unknown"}`)
    ].join("");
  } else if (kind === "logs") {
    title.textContent = "Archive Mentions";
    body.innerHTML = `<div class="scroll-row source">${escapeHtml(c.name)} has ${c.mentionCount.toLocaleString()} mention(s) in the current archive manifest.</div>
      <div class="scroll-row source">Detailed log references are a later data join.</div>`;
  } else if (kind === "whois") {
    title.textContent = "Whois Evidence";
    body.innerHTML = `<pre class="scroll-whois ${c.whoisHtml ? "has-colour-whois" : ""}">${c.whoisHtml || escapeHtml(c.whoisText || "No whois text available.")}</pre>`;
  } else {
    title.textContent = "Sources";
    body.innerHTML = (c.sources || [])
      .map(renderSourceSection)
      .join("") || `<section class="scroll-source-section">
        <h3>Sources</h3>
        <div class="scroll-source-detail">No source records are currently available.</div>
      </section>`;
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
