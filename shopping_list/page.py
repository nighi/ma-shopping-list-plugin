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
        "open": "Offen ({0})",
        "back": "Zurück",
        "empty": "Die Liste ist leer.",
        "player": "Player: {0}",
        "no_player": "Kein Player gewählt: in den Einstellungen des Plugins auswählen.",
        "error": "Keine Verbindung zum Plugin.",
        "not_started": "Die Einkaufsliste ist leer: Einkaufsmodus nicht gestartet.",
        "start_failed": "Der Einkaufsmodus konnte nicht gestartet werden.",
        "action_failed": "Das hat nicht geklappt.",
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
        "open": "Open ({0})",
        "back": "Back",
        "empty": "The list is empty.",
        "player": "Player: {0}",
        "no_player": "No player chosen: choose one in the settings of the plugin.",
        "error": "No connection to the plugin.",
        "not_started": "The shopping list is empty: shopping mode not started.",
        "start_failed": "Shopping mode could not be started.",
        "action_failed": "That did not work.",
    },
}

PAGE = """<!doctype html>
<html lang="__LANG__" data-theme="__THEME__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  /* the colours of the Music Assistant app: dark by default, light where the system is light */
  /* the theme the user chose in Music Assistant; "auto" follows the device like the app does */
  :root { color-scheme: dark; --bg: #181818; --panel: #232323; --fg: #ffffff;
          --muted: #ffffffb3; --line: #ffffff1f; --primary: #03a9f4; --tonal: #03a9f42e;
          --error: #cf6679; }
  @media (prefers-color-scheme: light) {
    :root[data-theme="auto"] { color-scheme: light; --bg: #f5f5f5; --panel: #ffffff;
      --fg: #000000; --muted: #00000099; --line: #0000001f; --tonal: #03a9f424;
      --error: #b00020; }
  }
  :root[data-theme="light"] { color-scheme: light; --bg: #f5f5f5; --panel: #ffffff;
    --fg: #000000; --muted: #00000099; --line: #0000001f; --tonal: #03a9f424;
    --error: #b00020; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg);
         font: 400 15px/1.45 Roboto, system-ui, -apple-system, "Segoe UI", sans-serif; }
  svg { width: 24px; height: 24px; fill: currentColor; flex: none; }
  header { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; gap: 8px;
           height: 56px; padding: 0 8px; background: var(--panel);
           box-shadow: 0 2px 4px #0000003d; }
  header h1 { margin: 0; font-size: 20px; font-weight: 500; }
  main { max-width: 640px; margin: 0 auto; padding: 16px; }
  .icon-button { display: grid; place-items: center; width: 40px; height: 40px; border: 0;
                 border-radius: 50%; background: none; color: inherit; cursor: pointer; }
  .icon-button:hover { background: var(--line); }
  .card { background: var(--panel); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  .status { display: flex; align-items: center; gap: 12px; }
  .status .title { font-size: 16px; font-weight: 500; }
  .status .subtitle { color: var(--muted); font-size: 13px; }
  .status.on svg.cart { color: var(--primary); }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
  .button { display: inline-flex; align-items: center; gap: 8px; height: 40px; padding: 0 16px;
            border: 0; border-radius: 20px; font: 500 14px/1 inherit; letter-spacing: .02em;
            cursor: pointer; background: var(--tonal); color: var(--primary); }
  .button.filled { background: var(--primary); color: #fff; }
  .button svg { width: 20px; height: 20px; }
  .button:disabled { opacity: .38; cursor: default; }
  .card.list { padding: 8px 0; }
  .list h2 { margin: 8px 16px; color: var(--muted); font-size: 13px; font-weight: 500;
             text-transform: uppercase; letter-spacing: .06em; }
  ul { list-style: none; margin: 0; padding: 0; }
  li { display: flex; align-items: center; gap: 12px; min-height: 56px; padding: 0 8px 0 16px;
       border-top: 1px solid var(--line); }
  li .name { flex: 1; }
  li.current { box-shadow: inset 3px 0 var(--primary); }
  li.current .name { font-weight: 500; font-size: 17px; }
  li.empty { color: var(--muted); }
  li .icon-button { color: var(--primary); }
  #message { display: none; margin: 0 0 16px; padding: 12px 16px; border-radius: 8px;
             background: var(--panel); color: var(--error); box-shadow: inset 3px 0 var(--error); }
  #message.shown { display: block; }
</style>
</head>
<body>
<header>
  <button id="back" class="icon-button" aria-label="__BACK__">
    <svg viewBox="0 0 24 24"><path d="M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z"/></svg>
  </button>
  <h1>__TITLE__</h1>
</header>
<main>
  <p id="message" role="alert"></p>
  <section id="status" class="card">
    <div class="status">
      <svg class="cart" viewBox="0 0 24 24"><path d="M17,18A2,2 0 0,1 19,20A2,2 0 0,1 17,22C15.89,22 15,21.1 15,20C15,18.89 15.89,18 17,18M1,2H4.27L5.21,4H20A1,1 0 0,1 21,5C21,5.17 20.95,5.34 20.88,5.5L17.3,11.97C16.96,12.58 16.3,13 15.55,13H8.1L7.2,14.63L7.17,14.75A0.25,0.25 0 0,0 7.42,15H19V17H7C5.89,17 5,16.1 5,15C5,14.65 5.09,14.32 5.24,14.04L6.6,11.59L3,4H1V2M7,18A2,2 0 0,1 9,20A2,2 0 0,1 7,22C5.89,22 5,21.1 5,20C5,18.89 5.89,18 7,18Z"/></svg>
      <div><div id="mode" class="title"></div><div id="meta" class="subtitle"></div></div>
    </div>
    <div class="actions">
      <button id="toggle" class="button filled"><svg viewBox="0 0 24 24"><path id="toggle-icon"/></svg><span></span></button>
      <button id="read" class="button"><svg viewBox="0 0 24 24"><path d="M14,3.23V5.29C16.89,6.15 19,8.83 19,12C19,15.17 16.89,17.84 14,18.7V20.77C18,19.86 21,16.28 21,12C21,7.72 18,4.14 14,3.23M16.5,12C16.5,10.23 15.5,8.71 14,7.97V16C15.5,15.29 16.5,13.76 16.5,12M3,9V15H7L12,20V4L7,9H3Z"/></svg><span></span></button>
      <button id="skip" class="button"><svg viewBox="0 0 24 24"><path d="M16,18H18V6H16M6,18L14.5,12L6,6V18Z"/></svg><span></span></button>
    </div>
  </section>
  <section class="card list">
    <h2 id="list-title"></h2>
    <ul id="items"></ul>
  </section>
</main>
<script>
const T = __TEXTS__;
const APP = __APP__;
const PLAY = "M8,5.14V19.14L19,12.14L8,5.14Z";
const STOP = "M18,18H6V6H18V18Z";
const CHECK = "M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2M12 20C7.59 20 4 16.41 4 12S7.59 4 12 4 20 7.59 20 12 16.41 20 12 20M16.59 7.58L10 14.17L7.41 11.59L6 13L10 17L18 9L16.59 7.58Z";
const base = location.pathname.replace(/\\/?$/, "/");
const fill = (text, value) => text.replace("{0}", value);
const $ = (id) => document.getElementById(id);
const label = (id, text) => { $(id).querySelector("span").textContent = text; };
let state = null;

function icon(path) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
  shape.setAttribute("d", path);
  svg.append(shape);
  return svg;
}

async function call(path, body) {
  const options = body ? { method: "POST", headers: { "Content-Type": "application/json" },
                           body: JSON.stringify(body) } : {};
  try {
    const response = await fetch(base + path, options);
    if (!response.ok) throw new Error(response.status);
    render(await response.json());
  } catch (err) {
    show(T.error);
  }
}

let shownAt = 0;
function show(text) {
  // a message stays for a few seconds, also when the next poll brings none
  if (!text && Date.now() - shownAt < 6000) return;
  if (text) shownAt = Date.now();
  $("message").textContent = text || "";
  $("message").classList.toggle("shown", Boolean(text));
}

function render(next) {
  state = next;
  show(state.message ? T[state.message] || T.action_failed : "");
  $("status").querySelector(".status").classList.toggle("on", state.on);
  $("mode").textContent = state.on ? (state.zone ? fill(T.on_zone, state.zone) : T.on_manual) : T.off;
  $("meta").textContent = state.player ? fill(T.player, state.player) : T.no_player;
  label("toggle", state.on ? T.stop : T.start);
  $("toggle-icon").setAttribute("d", state.on ? STOP : PLAY);
  label("read", T.read);
  label("skip", T.skip);
  $("read").disabled = $("skip").disabled = !state.player || !state.items.length;
  $("list-title").textContent = fill(T.open, state.items.length);
  const list = $("items");
  list.replaceChildren();
  if (!state.items.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = T.empty;
    list.append(empty);
  }
  state.items.forEach((item, index) => {
    const row = document.createElement("li");
    if (index === 0) row.className = "current";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = item.summary;
    const done = document.createElement("button");
    done.className = "icon-button";
    done.setAttribute("aria-label", T.done);
    done.title = T.done;
    done.append(icon(CHECK));
    done.onclick = () => call("action", { action: "complete", key: item.key });
    row.append(name, done);
    list.append(row);
  });
}

$("back").onclick = () => {
  // the app opened the page in a tab of its own: close it, or else go to the app
  window.close();
  setTimeout(() => { if (APP) location.href = APP; }, 300);
};
$("toggle").onclick = () => call("action", { action: state && state.on ? "stop" : "start" });
$("read").onclick = () => call("action", { action: "read" });
$("skip").onclick = () => call("action", { action: "skip" });
call("state");
setInterval(() => { if (!document.hidden) call("state"); }, 5000);
</script>
</body>
</html>
"""


def render_page(language: str, app_url: str = "", theme: str = "auto") -> str:
    """
    Return the HTML of the page in a language, English when the language is unknown.

    :param language: The language code from the settings, such as ``de``.
    :param app_url: The address of the Music Assistant app, where the back button leads.
    :param theme: The theme the user chose in Music Assistant: ``auto``, ``light`` or ``dark``.
    """
    texts = TEXTS.get(language, TEXTS["en"])

    def script_json(value: object) -> str:
        # "</" can not end the script early inside the JSON
        return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

    return (
        PAGE.replace("__LANG__", language if language in TEXTS else "en")
        .replace("__TITLE__", texts["title"])
        .replace("__THEME__", theme if theme in {"light", "dark"} else "auto")
        .replace("__BACK__", texts["back"])
        .replace("__TEXTS__", script_json(texts))
        .replace("__APP__", script_json(app_url))
    )
