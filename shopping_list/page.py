"""
The page of the plugin, offered in the main menu of the Music Assistant app.

It shows the shopping list and whether shopping mode is on, and starts or ends shopping mode,
reads the current entry, ticks entries off and skips the current one. The page runs sandboxed:
it talks to the plugin through the sub-paths ``state`` (GET) and ``action`` (POST) of its own
address.
"""

from __future__ import annotations

import json

TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "title": "Einkaufsliste",
        "on_zone": "Einkaufsmodus an: {0}",
        "on_manual": "Einkaufsmodus an",
        "off": "Einkaufsmodus aus",
        "start": "Einkaufsmodus starten",
        "stop": "Einkaufsmodus beenden",
        "read": "Vorlesen",
        "skip": "Später",
        "done": "Erledigt",
        "empty": "Die Liste ist leer.",
        "player": "Player: {0}",
        "no_player": "Kein Player gewählt: in den Einstellungen des Plugins auswählen.",
        "error": "Keine Verbindung zum Plugin.",
    },
    "en": {
        "title": "Shopping list",
        "on_zone": "Shopping mode on: {0}",
        "on_manual": "Shopping mode on",
        "off": "Shopping mode off",
        "start": "Start shopping mode",
        "stop": "End shopping mode",
        "read": "Read out",
        "skip": "Later",
        "done": "Done",
        "empty": "The list is empty.",
        "player": "Player: {0}",
        "no_player": "No player chosen: choose one in the settings of the plugin.",
        "error": "No connection to the plugin.",
    },
}

PAGE = """<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: light dark; --accent: #2e7d32; --muted: #8a8a8a; }
  body { font: 16px/1.4 system-ui, sans-serif; margin: 0 auto; max-width: 34rem; padding: 1rem; }
  h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
  #mode { font-weight: 600; margin: 0 0 .25rem; }
  #mode.on { color: var(--accent); }
  #meta { color: var(--muted); font-size: .9rem; margin: 0 0 1rem; }
  .row { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: 1rem; }
  button { font: inherit; border: 0; border-radius: .6rem; padding: .7rem 1rem; cursor: pointer;
           background: #8884; color: inherit; }
  button.primary { background: var(--accent); color: #fff; }
  button:disabled { opacity: .5; cursor: default; }
  ul { list-style: none; margin: 0; padding: 0; }
  li { display: flex; align-items: center; gap: .5rem; padding: .6rem 0;
       border-bottom: 1px solid #8883; }
  li span { flex: 1; }
  li:first-child span { font-weight: 700; font-size: 1.15rem; }
  li button { padding: .4rem .8rem; }
  #message { color: var(--muted); }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<p id="mode"></p>
<p id="meta"></p>
<div class="row">
  <button id="toggle" class="primary"></button>
  <button id="read"></button>
  <button id="skip"></button>
</div>
<ul id="items"></ul>
<p id="message"></p>
<script>
const T = __TEXTS__;
const base = location.pathname.replace(/\\/?$/, "/");
const fill = (text, value) => text.replace("{0}", value);
const $ = (id) => document.getElementById(id);
let state = null;

async function call(path, body) {
  const options = body ? { method: "POST", headers: { "Content-Type": "application/json" },
                           body: JSON.stringify(body) } : {};
  try {
    const response = await fetch(base + path, options);
    if (!response.ok) throw new Error(response.status);
    render(await response.json());
  } catch (err) {
    $("message").textContent = T.error;
  }
}

function render(next) {
  state = next;
  $("message").textContent = "";
  const mode = $("mode");
  mode.className = state.on ? "on" : "";
  mode.textContent = state.on ? (state.zone ? fill(T.on_zone, state.zone) : T.on_manual) : T.off;
  $("meta").textContent = state.player ? fill(T.player, state.player) : T.no_player;
  $("toggle").textContent = state.on ? T.stop : T.start;
  $("read").textContent = T.read;
  $("skip").textContent = T.skip;
  $("read").disabled = $("skip").disabled = !state.player || !state.items.length;
  const list = $("items");
  list.replaceChildren();
  if (!state.items.length) {
    const empty = document.createElement("li");
    empty.textContent = T.empty;
    list.append(empty);
  }
  for (const item of state.items) {
    const row = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = item.summary;
    const done = document.createElement("button");
    done.textContent = T.done;
    done.onclick = () => call("action", { action: "complete", key: item.key });
    row.append(name, done);
    list.append(row);
  }
}

$("toggle").onclick = () => call("action", { action: state && state.on ? "stop" : "start" });
$("read").onclick = () => call("action", { action: "read" });
$("skip").onclick = () => call("action", { action: "skip" });
call("state");
setInterval(() => { if (!document.hidden) call("state"); }, 5000);
</script>
</body>
</html>
"""


def render_page(language: str) -> str:
    """
    Return the HTML of the page in a language, English when the language is unknown.

    :param language: The language code from the settings, such as ``de``.
    """
    texts = TEXTS.get(language, TEXTS["en"])
    # "</" can not end the script early inside the JSON
    texts_json = json.dumps(texts, ensure_ascii=False).replace("</", "<\\/")
    return (
        PAGE.replace("__LANG__", language if language in TEXTS else "en")
        .replace("__TITLE__", texts["title"])
        .replace("__TEXTS__", texts_json)
    )
