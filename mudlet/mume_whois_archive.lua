mha = mha or {}

mha.version = "0.1.2"

mha.fileName = "mume_whois_archive.json"
mha.db = mha.db or {
  version = mha.version,
  records = {},
  captures = {},
}

mha.captureState = nil
mha.triggerId = nil
mha.timeoutTimer = nil
mha.idleTimer = nil
mha.aliasIds = mha.aliasIds or {}
mha.windowReady = false
mha.enabled = mha.enabled ~= false

mha.contributorName = mha.contributorName or "Bladorfat"
mha.playingCharacter = mha.playingCharacter or nil

mha.repoPath = mha.repoPath or "/Users/Lewis/mume-character-archive"

mha.queue = mha.queue or {
  items = {},
  index = 1,
  loaded_from = nil,
  loaded_at = nil,
}

mha.queueBatch = mha.queueBatch or {
  running = false,
  stop_requested = false,
  remaining = 0,
  delay_seconds = 10,
  timer = nil,
}

------------------------------------------------------------
-- File handling
------------------------------------------------------------

function mha.filePath()
  return getMudletHomeDir() .. "/" .. mha.fileName
end

function mha.save()
  local path = mha.filePath()
  local tmpPath = path .. ".tmp"

  local f, err = io.open(tmpPath, "w")

  if not f then
    cecho("<red>[mha] Could not save whois archive temp file: " .. tostring(err) .. "\n")
    return false
  end

  if yajl and yajl.to_string then
    f:write(yajl.to_string(mha.db))
  else
    cecho("<red>[mha] JSON support not available. Mudlet yajl module is required.\n")
    f:close()
    return false
  end

  f:close()

  local ok, renameErr = os.rename(tmpPath, path)

  if not ok then
    cecho("<red>[mha] Could not replace whois archive with temp file: " .. tostring(renameErr) .. "\n")
    return false
  end

  return true
end

function mha.load()
  local path = mha.filePath()
  local f = io.open(path, "r")

  if not f then
    mha.db = {
      version = mha.version,
      records = {},
      captures = {},
    }
    return
  end

  local content = f:read("*a")
  f:close()

  if content and content ~= "" and yajl and yajl.to_value then
    local ok, data = pcall(yajl.to_value, content)
    if ok and type(data) == "table" then
      mha.db = data
      mha.db.version = mha.version
      mha.db.records = mha.db.records or {}
      mha.db.captures = mha.db.captures or {}
      return
    end
  end

  cecho("<yellow>[mha] Existing archive could not be read. Starting with an empty archive.\n")
  mha.db = {
    version = mha.version,
    records = {},
    captures = {},
  }
end

------------------------------------------------------------
-- Utility helpers
------------------------------------------------------------

function mha.trim(s)
  if not s then return "" end
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

function mha.normaliseSpaces(s)
  if not s then return "" end
  return mha.trim(s:gsub("%s+", " "))
end

function mha.safeKey(name)
  name = tostring(name or ""):lower()
  name = name:gsub("^%s+", ""):gsub("%s+$", "")
  return name
end

function mha.now()
  return os.date("%Y-%m-%d %H:%M:%S")
end

function mha.today()
  return os.date("%Y-%m-%d")
end

function mha.dateFromEpoch(epoch)
  return os.date("%Y-%m-%d", epoch or os.time())
end

function mha.datetimeFromEpoch(epoch)
  return os.date("%Y-%m-%d %H:%M:%S", epoch or os.time())
end

function mha.isPromptLine(line)
  line = tostring(line or "")
  local compact = mha.normaliseSpaces(line)

  if compact == "" then
    return false
  end

  -- MUME prompts end with >.
  if not compact:match(">%s*$") then
    return false
  end

  -- Avoid treating ordinary whois/body lines as prompts.
  -- A real whois line usually contains prose punctuation or " is a ".
  local lower = compact:lower()

  if lower:find(" is a ", 1, true) or lower:find(" is an ", 1, true) then
    return false
  end

  if lower:match("^last login ") then
    return false
  end

  if lower:match("^is playing from ") then
    return false
  end

  if lower:match("^no one by that name%.?$") then
    return false
  end

  -- Strong prompt signs seen in MUME:
  -- [INS] ...>
  -- ![ ...>
  -- !# ...>
  -- XP:...>
  -- HP/move/mana/state style prompts may vary, so this remains broad.
  if compact:match("^%[[^%]]+%].*>%s*$") then
    return true
  end

  if compact:match("^![%[%#]?.*>%s*$") then
    return true
  end

  if compact:find("XP:", 1, true) then
    return true
  end

  -- Final fallback: a short status-like line ending in >.
  -- This catches changed prompts without swallowing long ASCII-art lines.
  if #compact <= 120 and not compact:match("%.%s*$") then
    return true
  end

  return false
end

function mha.isAmbientStatusLine(line)
  local compact = mha.normaliseSpaces(tostring(line or "")):lower()

  if compact == "you are hungry." then
    return true
  end

  if compact == "you are thirsty." then
    return true
  end

  return false
end

function mha.isFailedWhoisLine(line)
  line = mha.normaliseSpaces(tostring(line or "")):lower()

  if line == "no one by that name." then
    return true
  end

  if line == "no one by that name" then
    return true
  end

  return false
end

function mha.captureContainsFailedWhois(lines)
  for _, line in ipairs(lines or {}) do
    if mha.isFailedWhoisLine(line) then
      return true
    end
  end

  return false
end

function mha.parseAgoText(agoText)
  if not agoText then return nil end

  local result = {
    years = 0,
    months = 0,
    weeks = 0,
    days = 0,
    hours = 0,
    minutes = 0,
  }

  local s = agoText:lower()
  s = s:gsub(",", " ")
  s = s:gsub("%band%s+", " ")
  s = mha.normaliseSpaces(s)

  for number, unit in s:gmatch("(%d+)%s+([%a]+)") do
    number = tonumber(number) or 0

    if unit:match("^year") then
      result.years = number
    elseif unit:match("^month") then
      result.months = number
    elseif unit:match("^week") then
      result.weeks = number
    elseif unit:match("^day") then
      result.days = number
    elseif unit:match("^hour") then
      result.hours = number
    elseif unit:match("^minute") then
      result.minutes = number
    end
  end

  return result
end

function mha.estimateDateFromAgo(agoText, captureEpoch)
  local parts = mha.parseAgoText(agoText)

  if not parts then return nil end

  local d = os.date("*t", captureEpoch or os.time())

  d.year = d.year - (parts.years or 0)
  d.month = d.month - (parts.months or 0)
  d.day = d.day - ((parts.weeks or 0) * 7) - (parts.days or 0)
  d.hour = d.hour - (parts.hours or 0)
  d.min = d.min - (parts.minutes or 0)

  local estimatedEpoch = os.time(d)

  if not estimatedEpoch then return nil end

  return {
    date = os.date("%Y-%m-%d", estimatedEpoch),
    datetime = os.date("%Y-%m-%d %H:%M:%S", estimatedEpoch),
    epoch = estimatedEpoch,
    precision = "estimated_from_relative_mume_whois",
  }
end

function mha.firstWord(s)
  if not s then return nil end
  return s:match("^([%aÀ-ÖØ-öø-ÿ%-']+)")
end

function mha.wordLevelToNumber(levelText)
  if not levelText then return nil end

  local units = {
    one = 1, two = 2, three = 3, four = 4, five = 5,
    six = 6, seven = 7, eight = 8, nine = 9,
  }

  local teens = {
    ten = 10, eleven = 11, twelve = 12, thirteen = 13,
    fourteen = 14, fifteen = 15, sixteen = 16, seventeen = 17,
    eighteen = 18, nineteen = 19,
  }

  local tens = {
    twenty = 20, thirty = 30, forty = 40, fifty = 50,
    sixty = 60, seventy = 70, eighty = 80, ninety = 90,
  }

  local s = tostring(levelText):lower()
  s = s:gsub("%-", " ")
  s = mha.normaliseSpaces(s)

  -- Numeric fallback, in case a future whois ever gives "100".
  local numeric = tonumber(s)
  if numeric then
    return numeric
  end

  -- Explicit MUME corner case:
  -- "one hundred"
  if s == "one hundred" or s == "hundred" then
    return 100
  end

  if teens[s] then return teens[s] end
  if tens[s] then return tens[s] end
  if units[s] then return units[s] end

  local a, b = s:match("^(%a+)%s+(%a+)$")

  if a and b then
    if a == "one" and b == "hundred" then
      return 100
    end

    if tens[a] and units[b] then
      return tens[a] + units[b]
    end
  end

  return nil
end

function mha.splitRaceClass(text)
  if not text then return nil, nil end

  local s = mha.normaliseSpaces(text)
  s = s:gsub("%.$", "")

    local knownRacePrefixes = {
    -- Multi-word races / subraces first
    "Black Númenórean",
    "Black Numenorean",
    "Half%-elven",
    "Half%-Elven",
    "Half%-elf",
    "Half%-Elf",
    "Half Elf",
    "Half elf",

    -- Troll strains
    "Mountain Troll",
    "Cave Troll",
    "Hill Troll",

    -- Orc tribes and non-playable Uruk tribes
    "Uruk%-Burzruth",
    "Uruk%-Durbûk",
    "Uruk%-Durbuk",
    "Uruk%-Durghash",
    "Uruk%-Moragog",
    "Uruk%-Morgundul",
    "Uruk%-Ohurk",
    "Uruk%-Urughash",
    "Tarkhnarb",
    "Morruhk",
    "Zaugurz",

    -- Dwarf clans
    "Longbeard",
    "Firebeard",
    "Broadbeam",

    -- Hobbit breeds
    "Fallohide",
    "Harfoot",
    "Stoor",

    -- Elven peoples
    "Noldorin",
    "Noldo",
    "Sindarin",
    "Sinda",
    "Silvan",

    -- Men / Mannish subraces
    "Dúnedain",
    "Dunedain",
    "Eriadoran",
    "Rohirrim",
    "Beorning",

    -- Main race forms / older whois wording
    "Dwarven",
    "Dwarf",
    "Hobbit",
    "Orcish",
    "Orkish",
    "Orc",
    "Troll",
    "Man",
    "Human",
    "Maia",
    "Bear",
  }

  for _, race in ipairs(knownRacePrefixes) do
    local pattern = "^(" .. race .. ")%s+(.+)$"
    local r, c = s:match(pattern)
    if r and c then
      return r, c
    end
  end

  return s, nil
end

function mha.stripStatus(s)
  if not s then return s, nil end

  local status = s:match("%[([^%]]+)%]")
  s = s:gsub("%s*%[[^%]]+%]", "")
  s = mha.normaliseSpaces(s)

  return s, status
end

function mha.extractCountryOrSource(s)
  if not s then return nil end

  local from = s:match("from%s+(.+)%.?$")
  if not from then return nil end

  from = mha.trim(from)
  from = from:gsub("%.$", "")

  local domain = from:match("%*%.([%a][%a])$")
  if domain then
    return {
      source = from,
      country_code = domain,
    }
  end

  return {
    source = from,
    country_code = nil,
  }
end

function mha.simpleHash(s)
  s = tostring(s or "")

  local hash = 5381

  for i = 1, #s do
    hash = ((hash * 33) + string.byte(s, i)) % 4294967296
  end

  return string.format("%08x", hash)
end

function mha.makeCaptureId(queryName, capturedEpoch, rawText)
  local key = table.concat({
    "mha",
    mha.safeKey(queryName or ""),
    tostring(capturedEpoch or ""),
    mha.simpleHash(rawText or ""),
  }, ":")

  return key
end

function mha.assessCaptureQuality(parsed, rawText)
  rawText = rawText or ""

  if parsed and parsed.result == "not_found" then
    return "not_found"
  end

  if rawText:find("MUME.Client protocol error", 1, true) then
    return "corrupt"
  end

  if parsed and parsed.display_name and parsed.descriptor then
    if parsed.level or parsed.race or parsed.status or parsed.role or parsed.is_playing then
      return "high"
    end

    return "medium"
  end

  if rawText ~= "" then
    return "low"
  end

  return "corrupt"
end

function mha.makeNotFoundParsed(queryName, captureEpoch)
  return {
    query_name = queryName,
    result = "not_found",
    not_found_message = "Character information no longer extant in MUME.",
    parsed_at = mha.now(),
    captured_date = mha.dateFromEpoch(captureEpoch),
    captured_datetime = mha.datetimeFromEpoch(captureEpoch),
    captured_epoch = captureEpoch,
    raw_preserved = true,
  }
end

function mha.extractMentionedCharactersFromBody(bodyText)
  local results = {}

  if not bodyText or bodyText == "" then
    return results
  end

  local lines = mha.rawLines(bodyText)
  local collecting = false
  local buffer = {}

  for _, line in ipairs(lines) do
    local compact = mha.normaliseSpaces(line)
    local lower = compact:lower()

    if lower:match("^other%s+legends?%s*:") then
      collecting = true
      local afterColon = compact:gsub("^[Oo]ther%s+legends?%s*:%s*", "")
      table.insert(buffer, afterColon)
    elseif collecting then
      -- Continue while the next line looks like a wrapped list of names.
      -- Stop if it looks like a URL, heading, or unrelated sentence.
      if compact == "" then
        collecting = false
      elseif lower:find("http", 1, true) or lower:find("site:", 1, true) then
        collecting = false
      elseif compact:find(",") or compact:match("^[%aÀ-ÖØ-öø-ÿ%-']+%.?$") then
        table.insert(buffer, compact)
      else
        collecting = false
      end
    end
  end

  local joined = table.concat(buffer, " ")
  joined = joined:gsub("%.$", "")

  for part in joined:gmatch("([^,]+)") do
    local name = mha.trim(part)
    name = name:gsub("%.$", "")
    name = mha.trim(name)

    if name ~= "" and name:match("^[%aÀ-ÖØ-öø-ÿ%-']+$") then
      table.insert(results, {
        name = name,
        source_phrase = "other legends",
        confidence = "high",
        evidence_type = "whois_self_reported_related_character",
      })
    end
  end

  return results
end

function mha.extractMentionedGroups(parsed)
  local results = {}

  local textParts = {
    parsed.display_name or "",
    parsed.epithet_or_title or "",
    parsed.body_text or "",
  }

  local text = table.concat(textParts, "\n")

  if text == "" then
    return results
  end

  local patterns = {
    {
      phrase = "member of",
      pattern = "[Mm]ember%s+of%s+([^%.\n]+)",
      confidence = "medium",
    },
    {
      phrase = "soldier of",
      pattern = "[Ss]oldier%s+of%s+([^%.\n]+)",
      confidence = "medium",
    },
    {
      phrase = "servant of",
      pattern = "[Ss]ervant%s+of%s+([^%.\n]+)",
      confidence = "medium",
    },
    {
      phrase = "battalion",
      pattern = "([%w%s'%-À-ÖØ-öø-ÿ]+%s+[Bb]attalion)",
      confidence = "medium",
    },
    {
      phrase = "army",
      pattern = "([%w%s'%-À-ÖØ-öø-ÿ]+%s+[Aa]rmy)",
      confidence = "medium",
    },
    {
      phrase = "order",
      pattern = "([%w%s'%-À-ÖØ-öø-ÿ]+%s+[Oo]rder)",
      confidence = "medium",
    },
    {
      phrase = "company",
      pattern = "([%w%s'%-À-ÖØ-öø-ÿ]+%s+[Cc]ompany)",
      confidence = "medium",
    },
    {
      phrase = "clan",
      pattern = "([%w%s'%-À-ÖØ-öø-ÿ]+%s+[Cc]lan)",
      confidence = "medium",
    },
  }

  local seen = {}

  for _, spec in ipairs(patterns) do
    for match in text:gmatch(spec.pattern) do
      local name = mha.normaliseSpaces(match)
      name = name:gsub("^,%s*", "")
      name = name:gsub("%.$", "")
      name = mha.trim(name)

      if name ~= "" and not seen[name:lower()] then
        seen[name:lower()] = true
        table.insert(results, {
          name = name,
          matched_as = name,
          source_phrase = spec.phrase,
          confidence = spec.confidence,
          evidence_type = "possible_clan_or_group_mention",
        })
      end
    end
  end

  return results
end

function mha.truncateAtFirstPrompt(lines, dechoLines, htmlLines)
  local cleanedLines = {}
  local cleanedDecho = {}
  local cleanedHtml = {}

  for i, line in ipairs(lines or {}) do
    if mha.isPromptLine(line) then
      break
    end

    table.insert(cleanedLines, line)
    table.insert(cleanedDecho, dechoLines and dechoLines[i] or line)
    table.insert(cleanedHtml, htmlLines and htmlLines[i] or line)
  end

  return cleanedLines, cleanedDecho, cleanedHtml
end

------------------------------------------------------------
-- Display window
------------------------------------------------------------

function mha.ensureWindow()
  -- Use a normal Mudlet user window rather than a raw mini-console or Geyser.
  -- This should give normal Mudlet window controls: close, move, resize/dock.
  local ok = pcall(function()
    openUserWindow("mhaWindow")
    clearWindow("mhaWindow")
    echo("mhaWindow", "MUME Whois Archive window ready.\n")
  end)

  if ok then
    mha.windowReady = true
    return true
  end

  cecho("<red>[mha] Could not open Mudlet user window.\n")
  cecho("<yellow>[mha] The archive itself is still working; only the display window failed.\n")
  return false
end

function mha.hideWindow()
  -- Prefer closing the user window. If closeUserWindow is unavailable in this
  -- Mudlet version, fall back to hideWindow.
  local ok = false

  if closeUserWindow then
    ok = pcall(function()
      closeUserWindow("mhaWindow")
    end)
  end

  if not ok then
    ok = pcall(function()
      hideWindow("mhaWindow")
    end)
  end

  if ok then
    mha.windowReady = false
    cecho("<green>[mha] Archive window closed/hidden.\n")
  else
    cecho("<yellow>[mha] Could not close archive window. You may need to reload the Mudlet profile to remove an old stuck mini-console.\n")
  end
end

function mha.windowLine(text)
  echo("mhaWindow", tostring(text or "") .. "\n")
end

function mha.renderLatestToWindow(capture)
  if not capture then
    return false
  end

  if not mha.ensureWindow() then
    return false
  end

  local p = capture.parsed or {}

  clearWindow("mhaWindow")

  mha.windowLine("MUME Whois Archive")
  mha.windowLine("==================")
  mha.windowLine("")
  mha.windowLine("Captured: " .. tostring(capture.captured_at or ""))
  mha.windowLine("Query: " .. tostring(capture.query_name or ""))
  mha.windowLine("")

  mha.windowLine("Parsed fields")
  mha.windowLine("-------------")
  mha.windowLine("Display name: " .. tostring(p.display_name or ""))
  mha.windowLine("Character: " .. tostring(p.character_name or ""))
  mha.windowLine("Epithet/title: " .. tostring(p.epithet_or_title or ""))
  mha.windowLine("Descriptor: " .. tostring(p.descriptor or ""))

  if p.level then
    mha.windowLine("Level: " .. tostring(p.level))
  else
    mha.windowLine("Level: ")
  end

  mha.windowLine("Race/type: " .. tostring(p.race or ""))
  mha.windowLine("Class: " .. tostring(p.class or ""))
  mha.windowLine("Role: " .. tostring(p.role or ""))
  mha.windowLine("Status: " .. tostring(p.status or ""))

  if p.status and p.status:lower() == "retired" then
    mha.windowLine("Retirement evidence: yes")
  end

  mha.windowLine("")

  mha.windowLine("Login information")
  mha.windowLine("-----------------")
  mha.windowLine("Captured date: " .. tostring(p.captured_date or capture.captured_date or ""))
  mha.windowLine("Last login text: " .. tostring(p.last_login_text or ""))
  mha.windowLine("Last login ago: " .. tostring(p.last_login_ago or ""))
  mha.windowLine("Estimated login date: " .. tostring(p.last_login_estimated_date or ""))
  mha.windowLine("Login source: " .. tostring(p.last_login_source or p.playing_from or ""))
  mha.windowLine("Country/domain: " .. tostring(p.country_code or ""))
  mha.windowLine("Currently playing: " .. tostring(p.is_playing and "yes" or "no"))
  mha.windowLine("")

  if p.body_text and p.body_text ~= "" then
    mha.windowLine("Body / motto / preserved text")
    mha.windowLine("-----------------------------")
    echo("mhaWindow", p.body_text .. "\n")
    mha.windowLine("")
  end

  mha.windowLine("Raw whois")
  mha.windowLine("---------")
  mha.echoColouredOrPlain("mhaWindow", capture)

  return true
end

function mha.echoColouredOrPlain(windowName, capture)
  if not capture then
    return
  end

  if capture.raw_decho and capture.raw_decho ~= "" and capture.raw_decho ~= capture.raw_text then
    decho(windowName, capture.raw_decho .. "\n")
  else
    echo(windowName, capture.raw_text or "")
    echo(windowName, "\n")
  end
end

------------------------------------------------------------
-- Parser
------------------------------------------------------------

function mha.rawLines(raw)
  local lines = {}

  raw = raw or ""

  for line in raw:gmatch("([^\n]*)\n?") do
    if line == "" and #lines > 0 and raw:sub(-1) ~= "\n" then
      -- avoid artificial final empty line
    else
      table.insert(lines, line)
    end
  end

  return lines
end

function mha.findLatestCaptureByName(name)
  local wanted = mha.safeKey(name or "")

  if wanted == "" then
    return nil, nil
  end

  for i = #(mha.db.captures or {}), 1, -1 do
    local capture = mha.db.captures[i]
    local parsed = capture.parsed or {}

    local candidates = {
      capture.query_name,
      parsed.query_name,
      parsed.character_name,
      parsed.display_name,
    }

    for _, candidate in ipairs(candidates) do
      if candidate and mha.safeKey(candidate) == wanted then
        return capture, i
      end
    end
  end

  -- Fallback: allow substring match on display/raw names.
  -- This helps with accented returned names where safeKey() strips the first letter.
  local wantedLower = tostring(name or ""):lower()

  for i = #(mha.db.captures or {}), 1, -1 do
    local capture = mha.db.captures[i]
    local parsed = capture.parsed or {}

    local haystack = table.concat({
      tostring(capture.query_name or ""),
      tostring(parsed.query_name or ""),
      tostring(parsed.character_name or ""),
      tostring(parsed.display_name or ""),
      tostring(capture.raw_text or ""),
    }, "\n"):lower()

    if haystack:find(wantedLower, 1, true) then
      return capture, i
    end
  end

  return nil, nil
end

function mha.looksLikeWhoisHeaderLine(line)
  local compact = mha.normaliseSpaces(line)
  local lower = compact:lower()

  if mha.isFailedWhoisLine(line) then
    return true
  end

  -- Normal complete whois headers:
  -- Name is a level forty ...
  -- Name is a Black Númenórean ...
  -- Name is a Maia ...
  if lower:find("%sis%s+a%s+") ~= nil or lower:find("%sis%s+an%s+") ~= nil then
    return true
  end

  -- Wrapped header corner case:
  -- Ëárand Cataract, Sorcerer of Lothlórien is a
  --     Half-Elf [Retired].
  if lower:match("%sis%s+a%s*$") or lower:match("%sis%s+an%s*$") then
    return true
  end

  return false
end

function mha.findWhoisHeaderStart(lines)
  for i, line in ipairs(lines or {}) do
    if mha.looksLikeWhoisHeaderLine(line) then
      return i
    end
  end

  return 1
end

function mha.collectWhoisHeader(lines, startIndex)
  local headerLines = {}
  local i = startIndex or 1

  if not lines[i] then
    return "", i
  end

  table.insert(headerLines, lines[i])

  -- Continue joining indented wrapped header lines until the header sentence
  -- ends with a period. This is needed for cases like:
  --
  -- Candid ... is a level
  --     thirty-five Noldorin Scout [Retired].
  while i + 1 <= #lines do
    local currentHeader = mha.normaliseSpaces(table.concat(headerLines, " "))

    if currentHeader:match("%.%s*$") then
      break
    end

    local nextLine = lines[i + 1]

    -- Only consume continuation lines. This avoids pulling Last login into
    -- the character header.
    if nextLine:match("^%s+") and mha.trim(nextLine) ~= "" then
      table.insert(headerLines, nextLine)
      i = i + 1
    else
      break
    end
  end

  local header = mha.normaliseSpaces(table.concat(headerLines, " "))
  return header, i
end

function mha.parseDescriptor(descriptor)
  local parsed = {}

  descriptor = mha.normaliseSpaces(descriptor or "")
  descriptor = descriptor:gsub("%.$", "")

  local descriptorWithoutStatus, status = mha.stripStatus(descriptor)
  parsed.status = status
  parsed.descriptor = descriptorWithoutStatus

  -- Case-insensitive check for "a level ..." / "an level ..."
  local lowerDescriptor = descriptorWithoutStatus:lower()

  if lowerDescriptor:match("^a%s+level%s+") or lowerDescriptor:match("^an%s+level%s+") then
    local afterLevelPrefix = descriptorWithoutStatus:gsub("^[Aa][Nn]?%s+[Ll][Ee][Vv][Ee][Ll]%s+", "")
    afterLevelPrefix = mha.normaliseSpaces(afterLevelPrefix)

    local levelWords, afterLevel = afterLevelPrefix:match("^(one%s+hundred)%s+(.+)$")

if not levelWords then
  levelWords, afterLevel = afterLevelPrefix:match("^([%a%-]+)%s+(.+)$")
end

if levelWords and afterLevel then
  parsed.level_text = levelWords:lower()
  parsed.level = mha.wordLevelToNumber(levelWords)

  local race, class = mha.splitRaceClass(afterLevel)
  parsed.race = race
  parsed.class = class
  parsed.race_class_text = afterLevel
  return parsed
end

    -- If it says "a level" but still cannot parse the rest, do not treat
    -- the word "level" as the race.
    parsed.race = nil
    parsed.class = nil
    parsed.race_class_text = nil
    return parsed
  end

  -- Non-level examples:
  -- Bladorfat is a Maia (Cartographer).
  -- Woland is a Black Númenórean [Retired].
  local role = descriptorWithoutStatus:match("%((.-)%)")
  local noRole = descriptorWithoutStatus:gsub("%s*%([^%)]+%)", "")
  noRole = noRole:gsub("^[Aa][Nn]?%s+", "")
  noRole = mha.normaliseSpaces(noRole)

  parsed.race = noRole
  parsed.role = role
  parsed.race_class_text = noRole

  return parsed
end

function mha.removeAdjacentDuplicateLines(lines)
  local cleaned = {}

  for _, line in ipairs(lines or {}) do
    local previous = cleaned[#cleaned]

    if not previous or line ~= previous then
      table.insert(cleaned, line)
    end
  end

  return cleaned
end

function mha.parseWhois(rawText, queryName, captureEpoch)
  captureEpoch = captureEpoch or os.time()

  local parsed = {
    query_name = queryName,
    parsed_at = mha.now(),
    captured_date = mha.dateFromEpoch(captureEpoch),
    captured_datetime = mha.datetimeFromEpoch(captureEpoch),
    captured_epoch = captureEpoch,
    raw_preserved = true,
  }

  local raw = rawText or ""
  local lines = mha.rawLines(raw)

  -- Remove leading/trailing empty lines for parsing only.
  while #lines > 0 and mha.trim(lines[1]) == "" do
    table.remove(lines, 1)
  end

  while #lines > 0 and mha.trim(lines[#lines]) == "" do
    table.remove(lines, #lines)
  end

  -- Remove immediate duplicate lines before parsing.
  -- This fixes cases where the first whois header line is captured twice:
  --
  -- Ulairy ... is a level thirty-two
  -- Ulairy ... is a level thirty-two
  --     Black Númenórean Mercenary [Retired].
  --
  -- The raw saved text is still preserved separately.
  lines = mha.removeAdjacentDuplicateLines(lines)

  -- Remove any prompt lines that slipped into parsing.
  while #lines > 0 and mha.isPromptLine(lines[#lines]) do
    table.remove(lines, #lines)
  end

  if #lines == 0 then
    return parsed
  end

  -- Locate the first real whois header if unrelated noise slipped in before it.
  -- The raw_text remains preserved; this only affects parsing.
  local headerStart = mha.findWhoisHeaderStart(lines)

  if headerStart > 1 then
    for _ = 1, headerStart - 1 do
      table.remove(lines, 1)
    end
  end

  if #lines == 0 then
    return parsed
  end

  local header, bodyStart = mha.collectWhoisHeader(lines, 1)

  parsed.header = header

  local displayName, descriptor = header:match("^(.-)%s+[Ii][Ss]%s+(.+)$")

  if displayName and descriptor then
    displayName = mha.normaliseSpaces(displayName)
    descriptor = mha.normaliseSpaces(descriptor)

    parsed.display_name = displayName

    local first = mha.firstWord(displayName)
    if first then
      parsed.character_name = first
      local epithet = mha.trim(displayName:gsub("^" .. first, ""))
      if epithet ~= "" then
        parsed.epithet_or_title = epithet
      end
    end

    local descriptorFields = mha.parseDescriptor(descriptor)

    for k, v in pairs(descriptorFields) do
      parsed[k] = v
    end
  end

  -- Build a parsing-friendly version of the whois with wrapped continuation lines joined.
  local flatLines = {}
  local i = 1

  while i <= #lines do
    local current = lines[i]

    while i + 1 <= #lines and lines[i + 1]:match("^%s+") and current:match("[a-zA-Z,%[]$") do
      current = current .. " " .. mha.trim(lines[i + 1])
      i = i + 1
    end

    table.insert(flatLines, mha.normaliseSpaces(current))
    i = i + 1
  end

  for _, l in ipairs(flatLines) do
    if l:match("^Last login ") then
      parsed.last_login_text = l

      local ago = l:match("^Last login%s+(.+)%s+ago%s+from%s+.+%.?$")
      if ago then
        parsed.last_login_ago = ago

        local estimated = mha.estimateDateFromAgo(ago, captureEpoch)
        if estimated then
          parsed.last_login_estimated_date = estimated.date
          parsed.last_login_estimated_datetime = estimated.datetime
          parsed.last_login_estimated_epoch = estimated.epoch
          parsed.last_login_estimate_precision = estimated.precision
        end
      end

      local source = mha.extractCountryOrSource(l)
      if source then
        parsed.last_login_source = source.source
        parsed.country_code = source.country_code
      end
    elseif l:match("^Is playing from ") then
      parsed.is_playing = true
      parsed.playing_text = l

      local source = mha.extractCountryOrSource(l)
      if source then
        parsed.playing_from = source.source
        parsed.country_code = source.country_code
      end
    end
  end

  -- Body/motto: everything after the header, excluding login/current-playing metadata
  -- and their wrapped continuation lines.
  local bodyLines = {}
  local idx = bodyStart + 1

  while idx <= #lines do
    local l = lines[idx]
    local compact = mha.normaliseSpaces(l)

    if compact:match("^Last login ") or compact:match("^Is playing from ") then
      idx = idx + 1

      -- Skip wrapped continuation lines of login/current-playing information.
      while idx <= #lines and lines[idx]:match("^%s+") and mha.trim(lines[idx]) ~= "" do
        idx = idx + 1
      end
    else
      table.insert(bodyLines, l)
      idx = idx + 1
    end
  end

  -- Remove leading/trailing blank lines from body, but preserve internal spacing.
  while #bodyLines > 0 and mha.trim(bodyLines[1]) == "" do
    table.remove(bodyLines, 1)
  end

  while #bodyLines > 0 and mha.trim(bodyLines[#bodyLines]) == "" do
    table.remove(bodyLines, #bodyLines)
  end

  if #bodyLines > 0 then
    parsed.body_text = table.concat(bodyLines, "\n")

  local mentioned = mha.extractMentionedCharactersFromBody(parsed.body_text)
  if mentioned and #mentioned > 0 then
    parsed.mentioned_characters = mentioned
  end
end

local groups = mha.extractMentionedGroups(parsed)
if groups and #groups > 0 then
  parsed.mentioned_groups = groups
end

  return parsed
end

------------------------------------------------------------
-- Capture lifecycle
------------------------------------------------------------
function mha.handleWhoisCommand(name)
  name = mha.trim(name or "")

  if name == "" then
    cecho("<yellow>[mha] Usage: whois <character>\n")
    return
  end

  if mha.enabled == false then
    -- Pass the command through to MUME without archiving.
    send("whois " .. name)
    return
  end

  mha.start(name)
end

function mha.start(name, sourceQueue)
  name = mha.trim(name or "")

  if name == "" then
    cecho("<yellow>[mha] Usage: whois <character>\n")
    return
  end

  if mha.captureState then
    cecho("<yellow>[mha] Already capturing a whois. Finishing previous capture first.\n")
    mha.finish()
  end

  local captureEpoch = os.time()

    mha.captureState = {
    query_name = name,
    started_at = mha.now(),
    capture_date = mha.dateFromEpoch(captureEpoch),
    capture_datetime = mha.datetimeFromEpoch(captureEpoch),
    capture_epoch = captureEpoch,
    source_queue = sourceQueue,
    lines = {},
    decho_lines = {},
    html_lines = {},
    sawOutput = false,
    started_capture_output = false,
  }

  if mha.triggerId then
    killTrigger(mha.triggerId)
    mha.triggerId = nil
  end

  if mha.timeoutTimer then
    killTimer(mha.timeoutTimer)
    mha.timeoutTimer = nil
  end

  if mha.idleTimer then
    killTimer(mha.idleTimer)
    mha.idleTimer = nil
  end

  if mha.ensureWindow() then
    clearWindow("mhaWindow")
    echo("mhaWindow", "Capturing whois for " .. name .. "...\n")
  end

  mha.triggerId = tempRegexTrigger("^(.*)$", [[mha.captureLine(line)]])

  -- Safety timeout: this should rarely be used.
  mha.timeoutTimer = tempTimer(15, [[mha.timeoutCapture()]])

  send("whois " .. name)
end

function mha.captureColourLine(plainLine)
  local result = {
    decho = nil,
    html = nil,
  }

  -- Mudlet 4.8+ supports copy2decho/copy2html.
  -- They copy the current trigger line with colour information.
  if copy2decho then
    local ok, coloured = pcall(function()
      return copy2decho()
    end)

    if ok and coloured and coloured ~= "" then
      result.decho = coloured
    end
  end

  if copy2html then
    local ok, coloured = pcall(function()
      return copy2html()
    end)

    if ok and coloured and coloured ~= "" then
      result.html = coloured
    end
  end

  -- Fallback: if colour capture fails, keep the plain line in these fields
  -- so line counts remain aligned with raw_text.
  if not result.decho then
    result.decho = plainLine or ""
  end

  if not result.html then
    result.html = plainLine or ""
  end

  return result
end

function mha.captureLine(lineText)
  if not mha.captureState then
    return
  end

  local line = lineText or ""
  local q = mha.captureState.query_name or ""

  -- Do not record the command echo.
  if line:lower():match("^%s*whois%s+" .. q:lower() .. "%s*$") then
    return
  end

  -- Do not begin recording until we see a plausible whois response.
  -- This prevents unrelated protocol/client noise from being saved,
  -- but is deliberately loose enough to allow wrapped/oddly displayed
  -- whois headers.
  if not mha.captureState.started_capture_output then
    local cleanLine = mha.normaliseSpaces(line)
    local cleanLower = cleanLine:lower()
    local expected = mha.safeKey(q)

    local startsWithName = false
    local containsNameNearStart = false
    local looksLikeWhoisHeader = false

    if expected ~= "" then
      startsWithName = cleanLower:match("^" .. expected) ~= nil
      containsNameNearStart = cleanLower:sub(1, 40):find(expected, 1, true) ~= nil
    end

    -- Common MUME whois header forms, including wrapped headers ending:
    --   "is a"
    --   "is an"
    looksLikeWhoisHeader = mha.looksLikeWhoisHeaderLine(line)

    if mha.isFailedWhoisLine(line) then
      mha.captureState.started_capture_output = true
    elseif startsWithName or containsNameNearStart or looksLikeWhoisHeader then
      mha.captureState.started_capture_output = true
    else
      return
    end
  end

  -- If the prompt is visible to the trigger, finish immediately.
  if mha.isPromptLine(line) then
    mha.finish()
    return
  end

  -- Ignore ambient standalone status messages that can appear during
  -- long queue batches and are not part of whois output.
  if mha.isAmbientStatusLine(line) then
    return
  end

  local colour = mha.captureColourLine(line)

  table.insert(mha.captureState.lines, line)
  table.insert(mha.captureState.decho_lines, colour.decho or line)
  table.insert(mha.captureState.html_lines, colour.html or line)
  mha.captureState.sawOutput = true

  -- Finish after a short pause with no more whois lines.
  -- This avoids depending entirely on prompt detection.
  if mha.idleTimer then
    killTimer(mha.idleTimer)
    mha.idleTimer = nil
  end

  mha.idleTimer = tempTimer(1.5, [[mha.finish()]])
end

function mha.timeoutCapture()
  if not mha.captureState then
    return
  end

  cecho("<yellow>[mha] Whois capture timed out; saving what was captured.\n")
  mha.finish()
end

function mha.updateStatusHistory(rec, parsed, captureIndex)
  rec.status_history = rec.status_history or {}

  local status = parsed.status
  local observedDate = parsed.captured_date or mha.today()

  if status and status ~= "" then
    table.insert(rec.status_history, {
      status = status,
      observed_date = observedDate,
      observed_datetime = parsed.captured_datetime,
      estimated_last_login_date = parsed.last_login_estimated_date,
      last_login_ago = parsed.last_login_ago,
      capture_index = captureIndex,
    })
  end

  if status and status:lower() == "retired" then
    rec.retirement = rec.retirement or {}

    rec.retirement.ever_observed_retired = true

    if not rec.retirement.first_observed_retired_date then
      rec.retirement.first_observed_retired_date = observedDate
      rec.retirement.first_retired_capture_index = captureIndex
      rec.retirement.first_retired_last_login_estimated_date = parsed.last_login_estimated_date
    end

    rec.retirement.latest_observed_retired_date = observedDate
    rec.retirement.latest_retired_capture_index = captureIndex
    rec.retirement.latest_retired_last_login_estimated_date = parsed.last_login_estimated_date
    rec.retirement.latest_retired_last_login_ago = parsed.last_login_ago
  end
end

function mha.updateNotFoundRecord(queryName, parsed, captureIndex)
  local key = mha.safeKey(queryName)

  if key == "" then
    return
  end

  mha.db.records[key] = mha.db.records[key] or {
    key = key,
    record_kind = "name_evidence",
    query_names = {},
    captures = {},
  }

  local rec = mha.db.records[key]

  rec.query_names = rec.query_names or {}
  rec.captures = rec.captures or {}
  rec.not_found_history = rec.not_found_history or {}

  rec.query_names[mha.safeKey(queryName)] = true

  table.insert(rec.captures, captureIndex)

  -- Do not overwrite a good character latest record with a not_found result.
  -- Store not_found separately.
  rec.latest_result = "not_found"
  rec.latest_not_found = parsed

  table.insert(rec.not_found_history, {
    query_name = queryName,
    observed_date = parsed.captured_date,
    observed_datetime = parsed.captured_datetime,
    captured_epoch = parsed.captured_epoch,
    capture_index = captureIndex,
    result = "not_found",
    message = parsed.not_found_message or "Character information no longer extant in MUME.",
  })
end

function mha.finish()
  if not mha.captureState then
    return
  end

  if mha.triggerId then
    killTrigger(mha.triggerId)
    mha.triggerId = nil
  end

  if mha.timeoutTimer then
    killTimer(mha.timeoutTimer)
    mha.timeoutTimer = nil
  end

  if mha.idleTimer then
    killTimer(mha.idleTimer)
    mha.idleTimer = nil
  end

  local state = mha.captureState
  mha.captureState = nil

  -- If a prompt slipped into the capture, discard the prompt and anything
  -- after it. This prevents room-arrival/combat/weather lines after the whois
  -- from being saved as part of the whois evidence.
  state.lines, state.decho_lines, state.html_lines =
    mha.truncateAtFirstPrompt(state.lines, state.decho_lines, state.html_lines)
    
      -- Remove ambient standalone status messages that are not part of whois.
  local noAmbientLines = {}
  local noAmbientDecho = {}
  local noAmbientHtml = {}

  for i, plain in ipairs(state.lines or {}) do
    if not mha.isAmbientStatusLine(plain) then
      table.insert(noAmbientLines, plain)
      table.insert(noAmbientDecho, state.decho_lines and state.decho_lines[i] or plain)
      table.insert(noAmbientHtml, state.html_lines and state.html_lines[i] or plain)
    end
  end

  state.lines = noAmbientLines
  state.decho_lines = noAmbientDecho
  state.html_lines = noAmbientHtml

  -- Remove any trailing prompt lines that slipped into the capture.
  while #state.lines > 0 and mha.isPromptLine(state.lines[#state.lines]) do
    table.remove(state.lines, #state.lines)
    if state.decho_lines then table.remove(state.decho_lines, #state.decho_lines) end
    if state.html_lines then table.remove(state.html_lines, #state.html_lines) end
  end

  -- Remove immediate duplicate capture lines before saving, keeping colour
  -- arrays aligned with plain-text lines.
  local cleanedLines = {}
  local cleanedDecho = {}
  local cleanedHtml = {}

  for i, plain in ipairs(state.lines or {}) do
    local previous = cleanedLines[#cleanedLines]

    if not previous or plain ~= previous then
      table.insert(cleanedLines, plain)
      table.insert(cleanedDecho, state.decho_lines and state.decho_lines[i] or plain)
      table.insert(cleanedHtml, state.html_lines and state.html_lines[i] or plain)
    end
  end

  state.lines = cleanedLines
  state.decho_lines = cleanedDecho
  state.html_lines = cleanedHtml

  -- Failed whois lookups are still useful queue evidence.
  -- Save them as captures, but do not create/update a character record.
  if mha.captureContainsFailedWhois(state.lines) then
    local raw = table.concat(state.lines, "\n")
    local rawDecho = table.concat(state.decho_lines or {}, "\n")
    local rawHtml = table.concat(state.html_lines or {}, "\n")
    local parsed = mha.makeNotFoundParsed(state.query_name, state.capture_epoch)

    local capture = {
      capture_id = mha.makeCaptureId(state.query_name, state.capture_epoch, raw),
      capture_quality = "not_found",

      query_name = state.query_name,
      captured_at = mha.now(),
      captured_date = state.capture_date or mha.today(),
      captured_datetime = state.capture_datetime or mha.now(),
      captured_epoch = state.capture_epoch or os.time(),

      contributor_name = mha.contributorName,
      playing_character = mha.playingCharacter,

      raw_text = raw,
      raw_colour_format = "plain+decho+html",
      raw_decho = rawDecho,
      raw_html = rawHtml,

      parsed = parsed,
    }

    if state.source_queue then
      capture.source_queue = state.source_queue
    end

    table.insert(mha.db.captures, capture)
    
    local captureIndex = #mha.db.captures
    mha.updateNotFoundRecord(state.query_name, parsed, captureIndex)
    
    mha.save()
    mha.queueCompleteFromCapture(capture)

    if mha.ensureWindow() then
      clearWindow("mhaWindow")
      echo("mhaWindow", "MUME Whois Archive\n")
      echo("mhaWindow", "==================\n\n")
      echo("mhaWindow", "No current whois information found for: " .. tostring(state.query_name) .. "\n")
      echo("mhaWindow", "Character information no longer extant in MUME.\n\n")
      echo("mhaWindow", "This was saved as a not_found capture and name-evidence record.\n\n")
      echo("mhaWindow", "Raw response:\n")
      echo("mhaWindow", "-------------\n")
      echo("mhaWindow", raw .. "\n")
    end

    cecho("<yellow>[mha] Character information no longer extant in MUME for '" .. tostring(state.query_name) .. "'. Saved as not_found capture.\n")
    return
  end

  local raw = table.concat(state.lines, "\n")
  local rawDecho = table.concat(state.decho_lines or {}, "\n")
  local rawHtml = table.concat(state.html_lines or {}, "\n")

  local parsed = mha.parseWhois(raw, state.query_name, state.capture_epoch)

  -- Safety: if the parser could not find a proper whois header,
  -- do not save this as a character record.
  if not parsed.display_name or not parsed.descriptor then
    cecho("<yellow>[mha] Could not recognise a valid whois for '" .. tostring(state.query_name) .. "'. Whois not saved.\n")

    if mha.ensureWindow() then
      clearWindow("mhaWindow")
      echo("mhaWindow", "MUME Whois Archive\n")
      echo("mhaWindow", "==================\n\n")
      echo("mhaWindow", "Could not recognise a valid whois for: " .. tostring(state.query_name) .. "\n")
      echo("mhaWindow", "Whois was not saved.\n\n")
      echo("mhaWindow", "Raw response:\n")
      echo("mhaWindow", "-------------\n")
      echo("mhaWindow", raw .. "\n")
    end

    mha.queueCompleteFromFailure(state, "unrecognised_whois", raw)
    return
  end
  
  local captureQuality = mha.assessCaptureQuality(parsed, raw)

  local capture = {
    capture_id = mha.makeCaptureId(state.query_name, state.capture_epoch, raw),
    capture_quality = captureQuality,

    query_name = state.query_name,
    captured_at = mha.now(),
    captured_date = state.capture_date or mha.today(),
    captured_datetime = state.capture_datetime or mha.now(),
    captured_epoch = state.capture_epoch or os.time(),

    contributor_name = mha.contributorName,
    playing_character = mha.playingCharacter,

    raw_text = raw,
    raw_colour_format = "plain+decho+html",
    raw_decho = rawDecho,
    raw_html = rawHtml,

    parsed = parsed,
  }

  if state.source_queue then
    capture.source_queue = state.source_queue
  end
  
  -- Preserve questionable captures as evidence, but do not let them update
  -- the per-character latest record.
  local canUpdateCharacterRecord =
    capture.capture_quality == "high" or
    capture.capture_quality == "medium"

    table.insert(mha.db.captures, capture)

  local captureIndex = #mha.db.captures
  local key = mha.safeKey(parsed.character_name or parsed.query_name or state.query_name)

  if canUpdateCharacterRecord then
    mha.db.records[key] = mha.db.records[key] or {
      key = key,
      query_names = {},
      captures = {},
    }

    local rec = mha.db.records[key]

    rec.query_names = rec.query_names or {}
    rec.captures = rec.captures or {}

    rec.record_kind = "character"
    rec.latest_result = "found"

    table.insert(rec.captures, captureIndex)

    -- "latest" is only the latest observed whois.
    -- It must not erase older historical evidence such as retirement.
    rec.latest = parsed

    if mha.updateStatusHistory then
      mha.updateStatusHistory(rec, parsed, captureIndex)
    end

    local qkey = mha.safeKey(state.query_name)
    rec.query_names[qkey] = true
  else
    cecho("<yellow>[mha] Capture saved as evidence, but character summary was not updated because quality is: " .. tostring(capture.capture_quality) .. "\n")
  end

  mha.save()
  mha.queueCompleteFromCapture(capture)
  
  local rendered = mha.renderLatestToWindow(capture)

  local display = parsed.display_name or state.query_name
  cecho("<green>[mha] Saved whois for " .. display .. ".\n")

  if not rendered then
    cecho("<yellow>[mha] Saved successfully, but could not update the archive window.\n")
  end
end

function mha.timeout()
  mha.timeoutCapture()
end

------------------------------------------------------------
-- Queue support
------------------------------------------------------------

function mha.setRepoPath(path)
  path = mha.trim(path or "")

  if path == "" then
    cecho("<yellow>[mha] Usage: mha setrepo /path/to/mume-character-archive\n")
    return
  end

  -- Basic ~/ expansion for convenience.
  if path:sub(1, 2) == "~/" then
    local home = os.getenv("HOME") or ""
    path = home .. path:sub(2)
  end

  -- Remove trailing slash.
  path = path:gsub("/+$", "")

  mha.repoPath = path
  cecho("<green>[mha] Repository path set to: " .. mha.repoPath .. "\n")
  cecho("<cyan>[mha] Queue file will be: " .. mha.queueFilePath() .. "\n")
end

function mha.queueFilePath()
  return tostring(mha.repoPath or "") .. "/exports/mudlet/whois_queue.txt"
end

function mha.queueStatePath()
  return getMudletHomeDir() .. "/mume_whois_queue_state.json"
end

function mha.queueLoad()
  local path = mha.queueFilePath()
  local f, err = io.open(path, "r")

  if not f then
    cecho("<red>[mha] Could not open queue file: " .. tostring(path) .. "\n")
    cecho("<red>[mha] Error: " .. tostring(err) .. "\n")
    cecho("<yellow>[mha] Use: mha setrepo /Users/Lewis/mume-character-archive\n")
    return
  end

  local items = {}
  local lineNumber = 0

  for line in f:lines() do
    lineNumber = lineNumber + 1

    -- Handle Windows-style CRLF if present.
    line = tostring(line or ""):gsub("\r$", "")

    local name = mha.trim(line)

    -- Skip blanks and comments.
    if name ~= "" and not name:match("^#") then
      table.insert(items, {
        name = name,
        line_number = lineNumber,
        status = "pending",
      })
    end
  end

  f:close()

  mha.queue = {
    items = items,
    index = 1,
    loaded_from = path,
    loaded_at = mha.now(),
  }

  cecho("<green>[mha] Loaded " .. tostring(#items) .. " queued whois names.\n")
  cecho("<cyan>[mha] Queue file: " .. path .. "\n")

  if #items > 0 then
    cecho("<cyan>[mha] Next: " .. tostring(items[1].name) .. "\n")
  end
  
      mha.queueReconcile()
  
end

function mha.queueCounts()
  local total = #(mha.queue.items or {})
  local pending = 0
  local inProgress = 0
  local done = 0
  local failed = 0

  for _, item in ipairs(mha.queue.items or {}) do
    local status = item.status or "pending"

    if status == "pending" then
      pending = pending + 1
    elseif status == "in_progress" then
      inProgress = inProgress + 1
    elseif status:match("^done") then
      done = done + 1
    elseif status:match("^failed") then
      failed = failed + 1
    else
      pending = pending + 1
    end
  end

  return total, pending, done, inProgress, failed
end

function mha.queueNextIndex()
  local items = mha.queue.items or {}
  local startIndex = mha.queue.index or 1

  for i = startIndex, #items do
    local status = items[i].status or "pending"

    if status == "pending" then
      return i
    end
  end

  -- Safety fallback: if index has moved beyond an earlier pending item,
  -- find the first pending item anywhere.
  for i = 1, #items do
    local status = items[i].status or "pending"

    if status == "pending" then
      return i
    end
  end

  return nil
end

function mha.queueStatus()
  local total, pending, done, inProgress, failed = mha.queueCounts()
  local nextIndex = mha.queueNextIndex()

  cecho("<cyan>[mha] Queue status\n")
  cecho("<cyan>[mha] Repository: " .. tostring(mha.repoPath or "") .. "\n")
  cecho("<cyan>[mha] Queue file: " .. tostring(mha.queue.loaded_from or mha.queueFilePath()) .. "\n")
  cecho("<cyan>[mha] Queue state: " .. tostring(mha.queueStatePath()) .. "\n")
  cecho("<cyan>[mha] Loaded at: " .. tostring(mha.queue.loaded_at or "") .. "\n")
  cecho("<cyan>[mha] Total: " .. tostring(total) .. "\n")
  cecho("<cyan>[mha] Done this session/state: " .. tostring(done) .. "\n")
  cecho("<cyan>[mha] In progress: " .. tostring(inProgress) .. "\n")
  cecho("<cyan>[mha] Failed: " .. tostring(failed) .. "\n")
  cecho("<cyan>[mha] Pending: " .. tostring(pending) .. "\n")
  cecho("<cyan>[mha] Batch running: " .. tostring(mha.queueBatch.running and "yes" or "no") .. "\n")
  cecho("<cyan>[mha] Batch delay: " .. tostring(mha.queueBatch.delay_seconds or 10) .. " seconds\n")

  if nextIndex then
    local item = mha.queue.items[nextIndex]
    cecho("<cyan>[mha] Next #" .. tostring(nextIndex) .. ": " .. tostring(item.name) .. "\n")
  else
    cecho("<yellow>[mha] No pending queue items loaded.\n")
  end
end

function mha.queueReset()
  for _, item in ipairs(mha.queue.items or {}) do
    item.status = "pending"
    item.sent_at = nil
    item.completed_at = nil
    item.capture_id = nil
    item.capture_quality = nil
    item.result = nil
    item.retry_note = nil
  end

  mha.queue.index = 1
  mha.queueSaveState()

  cecho("<green>[mha] Queue session progress reset.\n")
  mha.queueStatus()
end

function mha.queueNext()
  if mha.enabled == false then
    cecho("<yellow>[mha] Whois archiving is disabled. Use: mha on\n")
    return false
  end

  if mha.captureState then
    cecho("<yellow>[mha] A whois capture is already active. Wait for it to finish first.\n")
    return false
  end

  if not mha.queue.items or #mha.queue.items == 0 then
    cecho("<yellow>[mha] No queue loaded. Use: mha queue load or mha queue resume\n")
    return false
  end

  local nextIndex = mha.queueNextIndex()

  if not nextIndex then
    cecho("<green>[mha] Queue complete for this session/state.\n")
    return false
  end

  local item = mha.queue.items[nextIndex]
  item.status = "in_progress"
  item.sent_at = mha.now()

  mha.queue.index = nextIndex + 1

  local sourceQueue = {
    queue_file = mha.queue.loaded_from or mha.queueFilePath(),
    queue_position = nextIndex,
    queue_line_number = item.line_number,
    queue_name = item.name,
    sent_at = item.sent_at,
  }

  mha.queueSaveState()

  cecho("<cyan>[mha] Queue whois #" .. tostring(nextIndex) .. ": " .. tostring(item.name) .. "\n")

  mha.start(item.name, sourceQueue)
  return true
end

function mha.queueCommand(raw)
  raw = mha.trim(raw or "")

  local subcmd, rest = raw:match("^(%S+)%s*(.*)$")
  subcmd = subcmd and subcmd:lower() or ""

  if subcmd == "load" then
    mha.queueLoad()
  elseif subcmd == "save" then
    if mha.queueSaveState() then
      cecho("<green>[mha] Queue state saved.\n")
    end
  elseif subcmd == "resume" then
    mha.queueLoadState()
  elseif subcmd == "reconcile" then
    mha.queueReconcile()
  elseif subcmd == "status" or subcmd == "" then
    mha.queueStatus()
  elseif subcmd == "next" then
    mha.queueNext()
  elseif subcmd == "reset" then
    mha.queueReset()
  elseif subcmd == "delay" then
    mha.queueSetDelay(rest)
  elseif subcmd == "batch" then
    mha.queueBatchStart(rest)
  elseif subcmd == "stop" then
    mha.queueBatchStop("Queue batch stop requested.")
  elseif subcmd == "peek" then
    mha.queuePeek(rest)
  else
    cecho("<yellow>[mha] Unknown queue command.\n")
    cecho("<white>  mha queue load\n")
    cecho("<white>  mha queue save\n")
    cecho("<white>  mha queue resume\n")
    cecho("<white>  mha queue status\n")
    cecho("<white>  mha queue peek [count]\n")
    cecho("<white>  mha queue next\n")
    cecho("<white>  mha queue reset\n")
    cecho("<white>  mha queue delay <seconds>\n")
    cecho("<white>  mha queue batch <count>\n")
    cecho("<white>  mha queue stop\n")
  end
end

function mha.queueSaveState()
  local path = mha.queueStatePath()
  local tmpPath = path .. ".tmp"

  local state = {
    version = mha.version,
    saved_at = mha.now(),
    repo_path = mha.repoPath,
    queue = mha.queue,
  }

  local f, err = io.open(tmpPath, "w")

  if not f then
    cecho("<red>[mha] Could not save queue state temp file: " .. tostring(err) .. "\n")
    return false
  end

  if yajl and yajl.to_string then
    f:write(yajl.to_string(state))
  else
    cecho("<red>[mha] JSON support not available. Mudlet yajl module is required.\n")
    f:close()
    return false
  end

  f:close()

  local ok, renameErr = os.rename(tmpPath, path)

  if not ok then
    cecho("<red>[mha] Could not replace queue state file: " .. tostring(renameErr) .. "\n")
    return false
  end

  return true
end

function mha.queueLoadState()
  local path = mha.queueStatePath()
  local f, err = io.open(path, "r")

  if not f then
    cecho("<yellow>[mha] No saved queue state found at: " .. path .. "\n")
    cecho("<yellow>[mha] Use: mha queue load\n")
    return false
  end

  local content = f:read("*a")
  f:close()

  if not content or content == "" then
    cecho("<yellow>[mha] Queue state file is empty.\n")
    return false
  end

  if not yajl or not yajl.to_value then
    cecho("<red>[mha] JSON support not available. Mudlet yajl module is required.\n")
    return false
  end

  local ok, data = pcall(yajl.to_value, content)

  if not ok or type(data) ~= "table" or type(data.queue) ~= "table" then
    cecho("<red>[mha] Could not read queue state file.\n")
    return false
  end

  if data.repo_path and data.repo_path ~= "" then
    mha.repoPath = data.repo_path
  end

  mha.queue = data.queue
  mha.queue.items = mha.queue.items or {}
  mha.queue.index = mha.queue.index or 1

  -- If Mudlet crashed or was closed mid-capture, do not skip that name.
  for _, item in ipairs(mha.queue.items or {}) do
    if item.status == "in_progress" then
      item.status = "pending"
      item.retry_note = "Reset from in_progress during queue resume."
      item.sent_at = nil
    end
  end

  cecho("<green>[mha] Loaded saved queue state.\n")
  cecho("<cyan>[mha] State file: " .. path .. "\n")

  mha.queueStatus()
  return true
end

function mha.queueStatusFromCapture(capture)
  if not capture then
    return "failed_no_capture"
  end

  local quality = capture.capture_quality or ""

  if quality == "not_found" then
    return "done_not_found"
  elseif quality == "high" or quality == "medium" then
    return "done_found"
  elseif quality == "low" then
    return "done_low_quality"
  elseif quality == "corrupt" then
    return "done_corrupt"
  end

  return "done_unknown"
end

function mha.queueCompleteFromCapture(capture)
  if not capture or not capture.source_queue then
    return
  end

  local pos = tonumber(capture.source_queue.queue_position or 0)

  if not pos or pos <= 0 then
    return
  end

  local item = mha.queue.items and mha.queue.items[pos]

  if not item then
    return
  end

  item.status = mha.queueStatusFromCapture(capture)
  item.completed_at = mha.now()
  item.capture_id = capture.capture_id
  item.capture_quality = capture.capture_quality
  item.result = capture.parsed and capture.parsed.result or "found"

  mha.queueSaveState()

  cecho("<green>[mha] Queue item #" .. tostring(pos) .. " completed: " .. tostring(item.status) .. "\n")

  mha.queueBatchAfterCapture()
end

function mha.queueCompleteFromFailure(state, reason, raw)
  if not state or not state.source_queue then
    return
  end

  local pos = tonumber(state.source_queue.queue_position or 0)

  if not pos or pos <= 0 then
    return
  end

  local item = mha.queue.items and mha.queue.items[pos]

  if not item then
    return
  end

  item.status = "failed_capture"
  item.completed_at = mha.now()
  item.failure_reason = reason or "unknown"
  item.raw_failure = raw or ""

  mha.queueSaveState()

  cecho("<yellow>[mha] Queue item #" .. tostring(pos) .. " marked failed: " .. tostring(reason or "unknown") .. "\n")

  mha.queueBatchStop("Stopping batch because a capture failed.")
end

function mha.queueSetDelay(seconds)
  seconds = tonumber(seconds)

  if not seconds then
    cecho("<yellow>[mha] Usage: mha queue delay <seconds>\n")
    return
  end

  if seconds < 5 then
    cecho("<yellow>[mha] Minimum queue delay is 5 seconds for safety.\n")
    seconds = 5
  end

  mha.queueBatch.delay_seconds = seconds
  cecho("<green>[mha] Queue batch delay set to " .. tostring(seconds) .. " seconds.\n")
end

function mha.queueBatchStart(count)
  count = tonumber(count)

  if not count or count <= 0 then
    count = 25
  end

  if mha.queueBatch.running then
    cecho("<yellow>[mha] Queue batch is already running. Use: mha queue stop\n")
    return
  end

  if mha.captureState then
    cecho("<yellow>[mha] A whois capture is already active. Wait for it to finish first.\n")
    return
  end

  if not mha.queue.items or #mha.queue.items == 0 then
    cecho("<yellow>[mha] No queue loaded. Use: mha queue load or mha queue resume\n")
    return
  end

  mha.queueBatch.running = true
  mha.queueBatch.stop_requested = false
  mha.queueBatch.remaining = count

  cecho("<green>[mha] Starting queue batch of " .. tostring(count) .. " with " .. tostring(mha.queueBatch.delay_seconds or 10) .. " second delay.\n")

  mha.queueBatchStep()
end

function mha.queueBatchStep()
  if not mha.queueBatch.running then
    return
  end

  if mha.queueBatch.stop_requested then
    mha.queueBatch.running = false
    cecho("<yellow>[mha] Queue batch stopped.\n")
    return
  end

  if mha.captureState then
    -- A capture is still active; completion will schedule the next step.
    return
  end

  if (mha.queueBatch.remaining or 0) <= 0 then
    mha.queueBatch.running = false
    cecho("<green>[mha] Queue batch complete.\n")
    mha.queueStatus()
    return
  end

  local started = mha.queueNext()

  if started then
    mha.queueBatch.remaining = mha.queueBatch.remaining - 1
  else
    mha.queueBatch.running = false
    cecho("<yellow>[mha] Queue batch stopped because no next item could be started.\n")
    mha.queueStatus()
  end
end

function mha.queueBatchAfterCapture()
  if not mha.queueBatch.running then
    return
  end

  if mha.queueBatch.stop_requested then
    mha.queueBatch.running = false
    cecho("<yellow>[mha] Queue batch stopped after current capture.\n")
    return
  end

  local delay = tonumber(mha.queueBatch.delay_seconds or 10) or 10

  if delay < 5 then
    delay = 5
  end

  if mha.queueBatch.timer then
    killTimer(mha.queueBatch.timer)
    mha.queueBatch.timer = nil
  end

  if (mha.queueBatch.remaining or 0) <= 0 then
    mha.queueBatch.running = false
    cecho("<green>[mha] Queue batch complete.\n")
    mha.queueStatus()
    return
  end

  cecho("<cyan>[mha] Next queued whois in " .. tostring(delay) .. " seconds. Remaining in batch: " .. tostring(mha.queueBatch.remaining) .. "\n")

  mha.queueBatch.timer = tempTimer(delay, [[mha.queueBatchStep()]])
end

function mha.queueBatchStop(reason)
  mha.queueBatch.stop_requested = true

  if mha.queueBatch.timer then
    killTimer(mha.queueBatch.timer)
    mha.queueBatch.timer = nil
  end

  if reason and reason ~= "" then
    cecho("<yellow>[mha] " .. tostring(reason) .. "\n")
  end

  if not mha.captureState then
    mha.queueBatch.running = false
    cecho("<yellow>[mha] Queue batch stopped.\n")
  else
    cecho("<yellow>[mha] Queue batch will stop after the current capture finishes.\n")
  end
end

function mha.queuePeek(count)
  count = tonumber(count) or 10

  if count < 1 then count = 1 end
  if count > 50 then count = 50 end

  local items = mha.queue.items or {}
  local idx = mha.queueNextIndex()

  if not idx then
    cecho("<yellow>[mha] No pending queue items.\n")
    return
  end

  cecho("<cyan>[mha] Next queued names:\n")

  local shown = 0
  for i = idx, #items do
    local item = items[i]
    local status = item.status or "pending"

    if status == "pending" then
      shown = shown + 1
      cecho("<white>  #" .. tostring(i) .. " " .. tostring(item.name) .. "\n")

      if shown >= count then
        break
      end
    end
  end
end


function mha.queueStatusFromExistingCapture(capture)
  if not capture then
    return nil
  end

  local quality = capture.capture_quality or ""

  if quality == "not_found" then
    return "done_not_found"
  elseif quality == "high" or quality == "medium" then
    return "done_found"
  elseif quality == "low" then
    return "done_low_quality"
  elseif quality == "corrupt" then
    return "done_corrupt"
  end

  return nil
end

function mha.buildCaptureLookup()
  local lookup = {}

  for index, capture in ipairs(mha.db.captures or {}) do
    local quality = capture.capture_quality or ""
    local status = mha.queueStatusFromExistingCapture(capture)

    -- Only treat these as completed queue checks.
    -- Low/corrupt are evidence, but should probably be reviewed or recaptured.
    if status == "done_found" or status == "done_not_found" then
      local keys = {}

      if capture.query_name and capture.query_name ~= "" then
        table.insert(keys, mha.safeKey(capture.query_name))
      end

      local parsed = capture.parsed or {}

      if parsed.character_name and parsed.character_name ~= "" then
        table.insert(keys, mha.safeKey(parsed.character_name))
      end

      for _, key in ipairs(keys) do
        if key ~= "" then
          -- Later captures overwrite earlier ones, which is what we want.
          lookup[key] = {
            capture_index = index,
            capture_id = capture.capture_id,
            capture_quality = quality,
            status = status,
            result = parsed.result or "found",
            query_name = capture.query_name,
            captured_at = capture.captured_at,
          }
        end
      end
    end
  end

  return lookup
end

function mha.queueReconcile()
  if not mha.queue.items or #mha.queue.items == 0 then
    cecho("<yellow>[mha] No queue loaded to reconcile.\n")
    return 0
  end

  local lookup = mha.buildCaptureLookup()
  local reconciled = 0

  for _, item in ipairs(mha.queue.items or {}) do
    local key = mha.safeKey(item.name)
    local found = lookup[key]

    if found then
      local status = item.status or "pending"

      -- Do not overwrite a current in-progress capture.
      if status ~= "in_progress" then
        item.status = found.status
        item.completed_at = found.captured_at or mha.now()
        item.capture_id = found.capture_id
        item.capture_quality = found.capture_quality
        item.result = found.result
        item.capture_index = found.capture_index
        item.reconciled_from_archive = true

        reconciled = reconciled + 1
      end
    end
  end

  local nextIndex = mha.queueNextIndex()

  if nextIndex then
    mha.queue.index = nextIndex
  else
    mha.queue.index = #(mha.queue.items or {}) + 1
  end

  mha.queueSaveState()

  cecho("<green>[mha] Reconciled queue with archive captures: " .. tostring(reconciled) .. " item(s) marked complete.\n")

  local nextPending = mha.queueNextIndex()
  if nextPending then
    cecho("<cyan>[mha] Next pending #" .. tostring(nextPending) .. ": " .. tostring(mha.queue.items[nextPending].name) .. "\n")
  else
    cecho("<green>[mha] No pending queue items remain.\n")
  end

  return reconciled
end

------------------------------------------------------------
-- Commands
------------------------------------------------------------

function mha.enable()
  mha.enabled = true
  cecho("<green>[mha] Whois archiving enabled.\n")
end

function mha.disable()
  mha.enabled = false

  if mha.captureState then
    cecho("<yellow>[mha] Stopping active whois capture.\n")
    mha.finish()
  end

  if mha.triggerId then
    killTrigger(mha.triggerId)
    mha.triggerId = nil
  end

  if mha.timeoutTimer then
    killTimer(mha.timeoutTimer)
    mha.timeoutTimer = nil
  end

  if mha.idleTimer then
    killTimer(mha.idleTimer)
    mha.idleTimer = nil
  end

  cecho("<yellow>[mha] Whois archiving disabled. Normal whois commands will pass through unsaved.\n")
end

function mha.status()
  local recordCount = 0
  for _, _ in pairs(mha.db.records or {}) do
    recordCount = recordCount + 1
  end

  cecho("<cyan>[mha] MUME Whois Archive " .. mha.version .. "\n")
  cecho("<cyan>[mha] Contributor: " .. tostring(mha.contributorName or "") .. "\n")
  cecho("<cyan>[mha] Playing character: " .. tostring(mha.playingCharacter or "") .. "\n")
  cecho("<cyan>[mha] Archiving: " .. tostring(mha.enabled ~= false and "enabled" or "disabled") .. "\n")
  cecho("<cyan>[mha] Records: " .. recordCount .. "\n")
  cecho("<cyan>[mha] Captures: " .. #(mha.db.captures or {}) .. "\n")
  cecho("<cyan>[mha] File: " .. mha.filePath() .. "\n")
  cecho("<cyan>[mha] Repository: " .. tostring(mha.repoPath or "") .. "\n")
  cecho("<cyan>[mha] Queue file: " .. tostring(mha.queueFilePath()) .. "\n")
end

function mha.show(name)
  name = mha.safeKey(name or "")

  if name == "" then
    cecho("<yellow>[mha] Usage: mha show <name>\n")
    return
  end

  local rec = mha.db.records[name]

  if not rec then
    cecho("<yellow>[mha] No record found for " .. name .. ".\n")
    return
  end

  local latest = rec.latest or {}

  cecho("<cyan>--- " .. (latest.display_name or name) .. " ---\n")

  if latest.level then
    cecho("<white>Level: " .. tostring(latest.level) .. "\n")
  end

  if latest.race then
    cecho("<white>Race/type: " .. tostring(latest.race) .. "\n")
  end

  if latest.class then
    cecho("<white>Class: " .. tostring(latest.class) .. "\n")
  end

  if latest.role then
    cecho("<white>Role: " .. tostring(latest.role) .. "\n")
  end

  if latest.status then
    cecho("<white>Status: " .. tostring(latest.status) .. "\n")
  end

  if rec.retirement and rec.retirement.ever_observed_retired then
    cecho("<white>Previously observed retired: yes\n")

    if rec.retirement.first_observed_retired_date then
      cecho("<white>First observed retired: " .. tostring(rec.retirement.first_observed_retired_date) .. "\n")
    end

    if rec.retirement.latest_observed_retired_date then
      cecho("<white>Latest observed retired: " .. tostring(rec.retirement.latest_observed_retired_date) .. "\n")
    end

    if rec.retirement.latest_retired_last_login_estimated_date then
      cecho("<white>Estimated last login while retired: " .. tostring(rec.retirement.latest_retired_last_login_estimated_date) .. "\n")
    end
  end

  if latest.last_login_ago then
    cecho("<white>Last login: " .. tostring(latest.last_login_ago) .. " ago\n")
  end

  if latest.last_login_estimated_date then
    cecho("<white>Estimated login date: " .. tostring(latest.last_login_estimated_date) .. "\n")
  end

  if latest.country_code then
    cecho("<white>Country/domain: " .. tostring(latest.country_code) .. "\n")
  end

  if latest.is_playing then
    cecho("<white>Currently playing: yes\n")
  end

  if latest.body_text then
    cecho("<white>\nBody/motto:\n")
    echo(latest.body_text .. "\n")
  end
end

function mha.findLatestCaptureByName(name)
  local wanted = mha.safeKey(name or "")

  if wanted == "" then
    return nil, nil
  end

  -- First pass: exact archive-key match against the useful capture fields.
  for i = #(mha.db.captures or {}), 1, -1 do
    local capture = mha.db.captures[i]
    local parsed = capture.parsed or {}

    local candidates = {
      capture.query_name,
      parsed.query_name,
      parsed.character_name,
      parsed.display_name,
    }

    for _, candidate in ipairs(candidates) do
      if candidate and mha.safeKey(candidate) == wanted then
        return capture, i
      end
    end
  end

  -- Second pass: record-key fallback, preserving old behaviour.
  local rec = mha.db.records and mha.db.records[wanted] or nil

  if rec and rec.captures and #rec.captures > 0 then
    local captureIndex = rec.captures[#rec.captures]
    local capture = mha.db.captures and mha.db.captures[captureIndex] or nil

    if capture then
      return capture, captureIndex
    end
  end

  -- Third pass: loose substring fallback.
  -- This helps when MUME returns an accented display name, e.g. Ëárand,
  -- while the typed query was plain "earand".
  local wantedLower = tostring(name or ""):lower()

  for i = #(mha.db.captures or {}), 1, -1 do
    local capture = mha.db.captures[i]
    local parsed = capture.parsed or {}

    local haystack = table.concat({
      tostring(capture.query_name or ""),
      tostring(parsed.query_name or ""),
      tostring(parsed.character_name or ""),
      tostring(parsed.display_name or ""),
      tostring(capture.raw_text or ""),
    }, "\n"):lower()

    if haystack:find(wantedLower, 1, true) then
      return capture, i
    end
  end

  return nil, nil
end

function mha.raw(name)
  local originalName = mha.trim(name or "")

  if originalName == "" then
    cecho("<yellow>[mha] Usage: mha raw <name>\n")
    return
  end

  local capture, captureIndex = mha.findLatestCaptureByName(originalName)

  if not capture then
    cecho("<yellow>[mha] No raw capture found for " .. originalName .. ".\n")
    return
  end

  local parsed = capture.parsed or {}
  local display = parsed.display_name or parsed.character_name or capture.query_name or originalName

  cecho("<cyan>--- Raw whois capture #" .. tostring(captureIndex) .. ": " .. tostring(display) .. " ---\n")
  cecho("<white>Query: " .. tostring(capture.query_name or "") .. "\n")

  if capture.capture_id then
    cecho("<white>Capture ID: " .. tostring(capture.capture_id) .. "\n")
  end

  if capture.capture_quality then
    cecho("<white>Quality: " .. tostring(capture.capture_quality) .. "\n")
  end

  cecho("<white>\n")

  echo((capture.raw_text or "") .. "\n")
end

function mha.rawColour(name)
  name = mha.safeKey(name or "")

  if name == "" then
    cecho("<yellow>[mha] Usage: mha rawcolour <name>\n")
    return
  end

  local rec = mha.db.records[name]

  if not rec or not rec.captures or #rec.captures == 0 then
    cecho("<yellow>[mha] No raw capture found for " .. name .. ".\n")
    return
  end

  local captureIndex = rec.captures[#rec.captures]
  local capture = mha.db.captures[captureIndex]

  cecho("<cyan>--- Coloured raw whois: " .. name .. " ---\n")

  if capture.raw_decho and capture.raw_decho ~= "" and capture.raw_decho ~= capture.raw_text then
    decho(capture.raw_decho .. "\n")
  else
    echo((capture.raw_text or "") .. "\n")
  end
end

function mha.window(name)
  name = mha.safeKey(name or "")

  if name == "" then
    cecho("<yellow>[mha] Usage: mha window <name>\n")
    return
  end

  local rec = mha.db.records[name]

  if not rec or not rec.captures or #rec.captures == 0 then
    cecho("<yellow>[mha] No capture found for " .. name .. ".\n")
    return
  end

  local captureIndex = rec.captures[#rec.captures]
  local capture = mha.db.captures[captureIndex]

  if mha.renderLatestToWindow(capture) then
    cecho("<green>[mha] Rendered window for " .. name .. ".\n")
  else
    cecho("<red>[mha] Could not render window for " .. name .. ".\n")
  end
end

function mha.find(term)
  term = mha.safeKey(term or "")

  if term == "" then
    cecho("<yellow>[mha] Usage: mha find <text>\n")
    return
  end

  cecho("<cyan>[mha] Search results for: " .. term .. "\n")

  local found = 0

  for key, rec in pairs(mha.db.records or {}) do
    local latest = rec.latest or {}
    local haystack = table.concat({
      key,
      latest.display_name or "",
      latest.epithet_or_title or "",
      latest.race or "",
      latest.class or "",
      latest.status or "",
      latest.country_code or "",
      latest.body_text or "",
    }, "\n"):lower()

    if haystack:find(term, 1, true) then
      found = found + 1
      cecho("<white>  " .. key .. " - " .. tostring(latest.display_name or "") .. "\n")
    end
  end

  if found == 0 then
    cecho("<yellow>[mha] No matches.\n")
  end
end

function mha.help()
  cecho("<cyan>MUME Whois Archive commands:\n")
  cecho("<white>  whois <name>        Capture and archive a normal MUME whois.\n")
  cecho("<white>  mha whois <name>    Same as above.\n")
  cecho("<white>  mha on              Enable automatic whois archiving.\n")
  cecho("<white>  mha off             Disable automatic whois archiving.\n")
  cecho("<white>  mha status          Show archive size and file path.\n")
  cecho("<white>  mha show <name>     Show parsed latest record.\n")
  cecho("<white>  mha raw <name>      Show preserved raw whois text.\n")
  cecho("<white>  mha rawcolour <name> Show preserved raw whois with Mudlet colours.\n")
  cecho("<white>  mha window <name>   Show latest record in the archive window.\n")
  cecho("<white>  mha hidewindow      Hide the archive window.\n")
  cecho("<white>  mha find <text>     Search parsed records.\n")
  cecho("<white>  mha colourtest <name> Test whether colour data was captured.\n")
  cecho("<white>  mha contributor <name> Set public contributor name.\n")
  cecho("<white>  mha playing <name>     Set current playing character for captures.\n")
  cecho("<white>  mha setrepo <path>  Set local GitHub repository path.\n")
  cecho("<white>  mha queue load      Load exports/mudlet/whois_queue.txt.\n")
  cecho("<white>  mha queue status    Show loaded queue progress.\n")
  cecho("<white>  mha queue next      Capture the next queued whois.\n")
  cecho("<white>  mha queue reset     Reset queue progress for this session.\n")
  cecho("<white>  mha queue save      Save queue progress state.\n")
  cecho("<white>  mha queue resume    Resume saved queue progress.\n")
  cecho("<white>  mha queue peek [n]  Show next queued names.\n")
  cecho("<white>  mha queue delay <s> Set batch delay, minimum 5 seconds.\n")
  cecho("<white>  mha queue batch <n> Run a safe batch of queued whois commands.\n")
  cecho("<white>  mha queue stop      Stop batch after current capture.\n")
  cecho("<white>  mha queue reconcile Reconcile loaded queue against existing archive captures.\n")
  cecho("<white>  mha help            Show this help.\n")
end

function mha.colourtest(name)
  name = mha.safeKey(name or "")

  if name == "" then
    cecho("<yellow>[mha] Usage: mha colourtest <name>\n")
    return
  end

  local rec = mha.db.records[name]

  if not rec or not rec.captures or #rec.captures == 0 then
    cecho("<yellow>[mha] No capture found for " .. name .. ".\n")
    return
  end

  local captureIndex = rec.captures[#rec.captures]
  local capture = mha.db.captures[captureIndex]

  cecho("<cyan>[mha] Colour capture test for " .. name .. "\n")

  if capture.raw_decho and capture.raw_decho ~= "" and capture.raw_decho ~= capture.raw_text then
    cecho("<green>[mha] raw_decho differs from raw_text: colour data probably captured.\n")
  else
    cecho("<yellow>[mha] raw_decho is missing or same as raw_text.\n")
  end

  if capture.raw_html and capture.raw_html ~= "" and capture.raw_html ~= capture.raw_text then
    cecho("<green>[mha] raw_html differs from raw_text: colour data probably captured.\n")
  else
    cecho("<yellow>[mha] raw_html is missing or same as raw_text.\n")
  end

  cecho("<white>\n--- First 1000 chars of raw_decho ---\n")
  echo(string.sub(capture.raw_decho or "", 1, 1000) .. "\n")

  cecho("<white>\n--- First 1000 chars of raw_html ---\n")
  echo(string.sub(capture.raw_html or "", 1, 1000) .. "\n")
end

function mha.setContributor(name)
  name = mha.trim(name or "")

  if name == "" then
    cecho("<yellow>[mha] Usage: mha contributor <name>\n")
    return
  end

  mha.contributorName = name
  cecho("<green>[mha] Contributor set to: " .. name .. "\n")
end

function mha.setPlayingCharacter(name)
  name = mha.trim(name or "")

  if name == "" then
    mha.playingCharacter = nil
    cecho("<yellow>[mha] Playing character cleared.\n")
    return
  end

  mha.playingCharacter = name
  cecho("<green>[mha] Playing character set to: " .. name .. "\n")
end

function mha.command(raw)
  raw = mha.trim(raw or "")

  local cmd, rest = raw:match("^(%S+)%s*(.*)$")
  cmd = cmd and cmd:lower() or ""

  if cmd == "whois" then
    mha.handleWhoisCommand(rest)
  elseif cmd == "on" or cmd == "start" or cmd == "enable" then
    mha.enable()
  elseif cmd == "off" or cmd == "stop" or cmd == "disable" then
    mha.disable()
  elseif cmd == "status" then
    mha.status()
  elseif cmd == "setrepo" or cmd == "repo" then
    mha.setRepoPath(rest)
  elseif cmd == "queue" then
    mha.queueCommand(rest)
  elseif cmd == "contributor" then
    mha.setContributor(rest)
  elseif cmd == "playing" then
    mha.setPlayingCharacter(rest)
  elseif cmd == "show" then
    mha.show(rest)
  elseif cmd == "raw" then
    mha.raw(rest)
  elseif cmd == "rawcolour" or cmd == "rawcolor" then
    mha.rawColour(rest)
  elseif cmd == "window" then
    mha.window(rest)
  elseif cmd == "colourtest" or cmd == "colortest" then
    mha.colourtest(rest)
  elseif cmd == "hidewindow" or cmd == "closewindow" then
    mha.hideWindow()
  elseif cmd == "find" then
    mha.find(rest)
  elseif cmd == "help" or cmd == "" then
    mha.help()
  else
    cecho("<yellow>[mha] Unknown command. Try: mha help\n")
  end
end

------------------------------------------------------------
-- Setup
------------------------------------------------------------

function mha.setup()
  mha.load()

  for _, id in pairs(mha.aliasIds or {}) do
    if id then
      killAlias(id)
    end
  end

  mha.aliasIds = {}

  -- Intercept normal whois commands so they are archived automatically.
  mha.aliasIds.whois = tempAlias("^whois\\s+(.+)$", [[mha.handleWhoisCommand(matches[2])]])

  -- Management command.
  mha.aliasIds.mha = tempAlias("^mha\\s*(.*)$", [[mha.command(matches[2] or "")]])

  cecho("<green>[mha] MUME Whois Archive loaded. Type: mha help\n")
end

mha.setup()
