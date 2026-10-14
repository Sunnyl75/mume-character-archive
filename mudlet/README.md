# MUME Whois Archive for Mudlet

Recovered Lua source for the Deck of Chars / MUME Character Archive whois collector.

## Recovered version

Version 0.1.2, recovered from `Pasted text(85).txt`, saved on 10 June 2026. Lewis confirmed on 15 October 2026 that the later crash report was not followed up, so this is treated as the latest recovered copy. It has not been compared with his installed Mudlet profile. The source is preserved without behavioural changes; a final newline is added.

## Installation

In Mudlet's script editor, create one script and paste the complete contents of `mume_whois_archive.lua`. Save the script. It registers its own aliases and loads the archive from the current Mudlet profile folder. Avoid loading duplicate copies.

Use `mha help` for all commands. Ordinary `whois <name>` commands are intercepted and archived. `mha off` disables archiving; `mha on` enables it.

Set your contributor and local repository path before collecting:

```text
mha contributor <your contributor name>
mha setrepo <absolute path to your local mume-character-archive checkout>
```

The recovered defaults include contributor `Bladorfat` and repository `/Users/Lewis/mume-character-archive`.

## Collection and queue

Captures preserve raw text and, when available, coloured decho/HTML output, plus parsed records. The JSON archive is `mume_whois_archive.json` in the Mudlet profile directory. Saving uses a temporary file followed by rename.

The queue reads `exports/mudlet/whois_queue.txt` from the configured local repository:

```text
mha queue load
mha queue status
mha queue next
```

See `mha help` for batch, resume, delay and stop commands. The repository's existing Python importer handles the resulting JSON archive.

## Unresolved compatibility report

Lewis reported a crash using the collector in the latest Mudlet on 24 September 2026. The earlier discussion identified the capture trigger and `copy2decho()` / `copy2html()` colour-copying calls in Mudlet 5.0 as a suspected path, not a confirmed diagnosis. No fix or successful retest was followed up. This recovered source still contains those calls; archiving it does not resolve the crash.

Validation: the entire recovered file compiles with Lua 5.4. This is a syntax check only; no live Mudlet/MUME runtime testing was performed.
