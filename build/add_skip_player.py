#!/usr/bin/env python3
"""Add the full story player to a built My Daily Review page — the
pop-up follow-along form (the admin's design, settled in a voice call
2026-11-10, first directed for the Morning Scroll and then for every
player page): the bar does NOT stand open while anyone is only
reading. Tapping a story's own Listen link starts the player at that
story and pops the bar up as a floating window pinned to the TOP
RIGHT of the screen, where it stays while listening; Stop, or the
last story ending, hides it again.

Road: run AFTER the page is built and its per-story recordings stand
verified (nightly job steps 3-4). The script reads the story listen
links out of the built page in page order — those links stand only
for stories whose recordings verified — checks each recording file
stands beside the page, writes the edition playlist
(daily-review-<date>.playlist.json) beside the page, and inserts the
(one, hidden-at-rest) player block directly under the dateline:

  - the approved seven-button set (the admin's order, 2026-11-10,
    in the admin's own picture — one black rounded bar, all seven in
    one row inside it, plain white SVG shapes with the plain word in
    small white text under each shape):
    "Start of story or story before" (to the start of the story
    playing; pressed while the story stands within its first five
    seconds, to the start of the story before it — the admin's
    five-second rule, 2026-11-10),
    "Back 10 seconds" (10 seconds back, clamped at the start), "Play"
    (its own button), "Pause" (its own button), "Forward 10 seconds"
    (10 seconds forward, stepping into the next story at the end),
    "Next story" (jumps to the next story and keeps playing), and
    "Stop" (stops, resets to the first story at time 0, and hides
    the bar); the Media Session next-track action does the Next
    story work and previous-track does the start-or-before work;
  - a now-playing story TITLE line, a "Story N of M" line, and a
    time line, all inside the floating bar;
  - FOLLOW-ALONG: every story on the page carries its player-order
    number by its headline; while a story plays, its whole article
    is highlighted, and the sentence being read is highlighted
    inside it. Sentence timings are figured HERE, once, at build
    time: the story's narration (its headline, then its bullets as
    plain sentences — the same words step 4 speaks) is split into
    sentences and the recording's measured length (ffprobe) is
    spread across them in proportion to their word counts; the
    timings stand in the page's playlist data, so listening itself
    costs nothing. While playing, the screen keeps the sentence
    being read in view (a gentle scroll); paused or stopped, the
    page stays where the reader left it. A story whose timings
    cannot be figured keeps the article highlight only.

Fallback: fewer than two verified story recordings -> no player, the
page is left exactly as built (the per-story listen links are the
fallback, as they have been since 2026-11-02). Idempotent: a standing
player block is removed whole and rebuilt, standing story numbers
are stripped and re-laid, and each CSS set is added once only.

Usage: python3 add_skip_player.py [page] [date]
  page defaults to ~/workspace/daily-news/index.html
  date defaults to the date in the page's story recording names
Prints one verdict line: PLAYER: <n> tracks ... or FALLBACK: <why>.
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

PAGE_DEFAULT = Path.home() / "workspace" / "daily-news" / "index.html"

PLAYER_JS_TEMPLATE = r"""(function () {
  var TRACKS = __PLAYLIST__;
  var box = document.querySelector('.whole-player');
  var audio = document.getElementById('edition-audio');
  var titleEl = document.getElementById('np-title');
  var nowEl = document.getElementById('now-playing');
  var timeEl = document.getElementById('time-line');
  var idx = 0, done = false, curSent = -1;
  var articles = [], prepared = {}, sentSpans = {};
  function fmt(s) {
    if (!isFinite(s) || s < 0) s = 0;
    s = Math.floor(s);
    return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
  }
  function showBar() {
    box.classList.remove('wp-hidden');
    box.classList.add('wp-float');
  }
  function hideBar() {
    box.classList.add('wp-hidden');
    box.classList.remove('wp-float');
  }
  function showLine() {
    if (done) {
      titleEl.textContent = 'All ' + TRACKS.length + ' stories are done';
      nowEl.textContent = '';
    } else {
      titleEl.textContent = TRACKS[idx].title;
      nowEl.textContent = 'Story ' + (idx + 1) + ' of ' + TRACKS.length;
    }
    timeEl.textContent = fmt(audio.currentTime) + ' of ' + fmt(audio.duration);
    if ('mediaSession' in navigator && !done) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({ title: TRACKS[idx].title, artist: 'My Daily Review' });
      } catch (e) {}
    }
  }
  function clearSent() {
    if (curSent >= 0 && sentSpans[idx] && sentSpans[idx][curSent]) {
      sentSpans[idx][curSent].classList.remove('wp-sent-on');
    }
    curSent = -1;
  }
  function markArticle() {
    articles.forEach(function (a, i) {
      if (a) a.classList.toggle('wp-playing', i === idx && !done);
    });
  }
  var BS = String.fromCharCode(92);
  function escRe(s) { return s.split('').map(function (c) { return ('.*+?^${}()|[]'.indexOf(c) >= 0 || c === BS) ? BS + c : c; }).join(''); }
  function prepare(i) {
    if (prepared[i]) return;
    prepared[i] = true;
    sentSpans[i] = [];
    var art = articles[i];
    var sents = (TRACKS[i].sentences || []);
    if (!art || !sents.length) return;
    var els = [];
    var head = art.querySelector('h3 a');
    if (head) els.push(head);
    art.querySelectorAll('li').forEach(function (li) { els.push(li); });
    var nodes = [], stream = '';
    els.forEach(function (el, ei) {
      if (ei > 0) stream += ' ';
      var tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
      var n;
      while ((n = tw.nextNode())) {
        nodes.push({ node: n, start: stream.length });
        stream += n.nodeValue;
      }
    });
    var cursor = 0;
    sents.forEach(function (sent, si) {
      var words = sent.t.split(new RegExp(BS + 's+')).filter(Boolean).map(escRe);
      if (!words.length) { sentSpans[i][si] = null; return; }
      var re = new RegExp(words.join(BS + 's+'));
      var m = re.exec(stream.slice(cursor));
      if (!m) { sentSpans[i][si] = null; return; }
      var a = cursor + m.index, b = a + m[0].length;
      cursor = b;
      var span = null;
      var segs = [];
      nodes.forEach(function (nd) {
        var ns = nd.start, ne = ns + nd.node.nodeValue.length;
        if (ne > a && ns < b) segs.push({ nd: nd, from: Math.max(a, ns) - ns, to: Math.min(b, ne) - ns });
      });
      for (var k = segs.length - 1; k >= 0; k--) {
        var sg = segs[k], node = sg.nd.node;
        node.splitText(sg.to);
        var mid = node.splitText(sg.from);
        var sp = document.createElement('span');
        sp.className = 'wp-sent';
        mid.parentNode.replaceChild(sp, mid);
        sp.appendChild(mid);
        span = sp;
      }
      sentSpans[i][si] = span;
    });
  }
  function followSent() {
    var sents = TRACKS[idx].sentences || [];
    if (!sents.length) return;
    var t = audio.currentTime, k = -1;
    for (var i = 0; i < sents.length; i++) {
      if (t >= sents[i].s && t < sents[i].e) { k = i; break; }
    }
    if (k === curSent) return;
    clearSent();
    curSent = k;
    if (k < 0) return;
    prepare(idx);
    var sp = sentSpans[idx] && sentSpans[idx][k];
    if (!sp) return;
    sp.classList.add('wp-sent-on');
    if (!audio.paused) {
      var r = sp.getBoundingClientRect();
      if (r.bottom > window.innerHeight - 8 || r.top < 8) {
        sp.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }
  function load(i, autoplay) {
    clearSent();
    idx = i; done = false;
    audio.src = TRACKS[i].href;
    audio.load();
    markArticle();
    showLine();
    if (autoplay) {
      audio.play();
      var art = articles[i];
      if (art) setTimeout(function () { art.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 60);
    }
  }
  function goBegin() {
    if (done) { load(0, false); return; }
    if (audio.currentTime <= 5 && idx > 0) {
      load(idx - 1, !audio.paused);
    } else {
      audio.currentTime = 0; showLine();
    }
  }
  function goNext() {
    if (done) { load(0, true); return; }
    if (idx < TRACKS.length - 1) { load(idx + 1, true); }
  }
  document.getElementById('btn-play').addEventListener('click', function () {
    showBar();
    if (done) { load(0, true); return; }
    markArticle();
    audio.play();
  });
  document.getElementById('btn-pause').addEventListener('click', function () {
    audio.pause();
  });
  document.getElementById('btn-stop').addEventListener('click', function () {
    audio.pause(); load(0, false); clearSent(); markArticle(); hideBar();
  });
  document.getElementById('btn-begin').addEventListener('click', goBegin);
  document.getElementById('btn-back').addEventListener('click', function () {
    audio.currentTime = Math.max(0, audio.currentTime - 10); showLine();
  });
  document.getElementById('btn-fwd').addEventListener('click', function () {
    var d = audio.duration;
    if (isFinite(d) && audio.currentTime + 10 >= d) {
      if (idx < TRACKS.length - 1) { load(idx + 1, !audio.paused); }
      else { audio.currentTime = d; }
    } else {
      audio.currentTime = Math.min(d || 0, audio.currentTime + 10);
    }
    showLine();
  });
  document.getElementById('btn-next').addEventListener('click', goNext);
  audio.addEventListener('timeupdate', function () { showLine(); followSent(); });
  audio.addEventListener('loadedmetadata', showLine);
  audio.addEventListener('ended', function () {
    if (idx < TRACKS.length - 1) { load(idx + 1, true); }
    else {
      done = true; clearSent(); markArticle(); showLine(); hideBar();
    }
  });
  if ('mediaSession' in navigator) {
    try {
      navigator.mediaSession.setActionHandler('nexttrack', function () { showBar(); goNext(); });
      navigator.mediaSession.setActionHandler('previoustrack', function () { showBar(); goBegin(); });
    } catch (e) { /* older browser: buttons still work */ }
  }
  document.addEventListener('DOMContentLoaded', function () {
    var links = document.querySelectorAll('a.story-listen');
    links.forEach(function (link, i) {
      articles[i] = link.closest('article');
      link.addEventListener('click', function (e) {
        e.preventDefault();
        showBar();
        load(i, true);
      });
    });
    load(0, false);
  });
  load(0, false);
})();"""

# The bar look (Clay's picture, 2026-11-10 — the fix after the first
# seven-button build came out as separate boxes in a grid): ONE black
# rounded bar, all seven buttons in ONE row inside it, each button a
# plain white SVG shape with its plain word in small white text under
# the shape, inside the bar. No separate boxes, no grid, no colored or
# emoji icons, no white buttons. The .wp-bar selectors outrank the
# older player rules wherever those still stand in a built page's
# shell, and the block carries its "Story N of M" line and time line
# under the bar.
BAR_CSS = (
    '  .whole-player { text-align:center; margin:14px auto 0; max-width:980px; }\n'
    '  .whole-player .wp-bar { display:flex; flex-wrap:nowrap; '
    'align-items:flex-start; background:#111; border-radius:60px; '
    'padding:12px 14px; }\n'
    '  .whole-player .wp-bar .wp-btn { flex:1 1 0; width:auto; min-width:0; '
    'min-height:0; margin:0; padding:3px 1px; background:transparent; '
    'border:none; border-radius:16px; color:#fff; cursor:pointer; '
    'font-family:Arial, Helvetica, sans-serif; line-height:1.25; }\n'
    '  .whole-player .wp-bar .wp-btn:active { background:#333; }\n'
    '  .whole-player .wp-bar .wp-btn .sym { display:block; line-height:0; }\n'
    '  .whole-player .wp-bar .wp-btn .sym svg { width:32px; height:32px; }\n'
    '  .whole-player .wp-bar .wp-btn .word { display:block; font-size:11px; '
    'font-weight:400; margin-top:3px; color:#fff; }\n'
    '  .whole-player #now-playing { font-weight:700; margin:10px 0 0; '
    'font-size:15.5px; }\n'
    '  .whole-player .wp-time { margin:2px 0 8px; font-size:14px; '
    'color:#333; font-variant-numeric:tabular-nums; }\n'
)
PLAYER_CSS = BAR_CSS
FULL_PLAYER_CSS = BAR_CSS

# The pop-up follow-along set (Clay, 2026-11-10): the player element
# rests hidden; while listening it floats pinned to the TOP RIGHT of
# the screen (the same bar moved, never a second copy); the story
# number by each headline; the playing article's highlight; the
# sentence highlight.
POPUP_CSS = (
    '  .whole-player.wp-hidden { display:none; }\n'
    '  .whole-player.wp-float { position:fixed; top:10px; right:10px; '
    'left:auto; z-index:80; width:450px; max-width:calc(100vw - 20px); '
    'margin:0; background:#fffdf5; border:2px solid #111; '
    'border-radius:14px; padding:10px 10px 2px; '
    'box-shadow:0 8px 28px rgba(0,0,0,.35); }\n'
    '  .whole-player #np-title { font-weight:700; font-size:15.5px; '
    'margin:4px 0 0; }\n'
    '  .whole-player.wp-float #now-playing { margin-top:2px; }\n'
    '  .wp-storynum { font-weight:700; margin-right:6px; }\n'
    '  article.wp-playing { background:#fbeec0; '
    'box-shadow:inset 0 0 0 2px #d9b23a; border-radius:6px; }\n'
    '  .wp-sent-on { background:#ffdf6b; }\n'
)

# A story's headline link followed by its listen link, both inside the
# story's <h3> headline line, in page order. (Anchored to <h3> so the
# doors-line links above the stories can never be taken as a headline.)
# A standing story-number span from an earlier run of this script is
# stripped in main() before this runs; the span is allowed here so a
# stray one can never hide a story.
STORY_RE = re.compile(
    r'<h3>(?:<span class="wp-storynum">\d+\.</span>\s*)?'
    r'<a href="https?://[^"]*"[^>]*>(.*?)</a>\s*'
    r'<a class="story-listen" href="(story-[^"]+\.mp3)">',
    re.S)
ARTICLE_RE = re.compile(r'<article>.*?</article>', re.S)
LISTEN_HREF_RE = re.compile(r'class="story-listen" href="(story-[^"]+\.mp3)"')
LI_RE = re.compile(r'<li>(.*?)</li>', re.S)
STORYNUM_RE = re.compile(r'<span class="wp-storynum">\d+\.</span>\s*')
# A standing player block from an earlier run of this script. The
# block ends with its script and the closing </div> after it — the
# bar inside the block carries its own nested <div>, so the strip
# must run to the script's end, not the first </div>.
PLAYER_BLOCK_RE = re.compile(
    r'\s*<div class="listen whole-player">.*?</script>\s*</div>\s*(?=<section>)',
    re.S)


def strip_tags(fragment):
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(text).strip()


def collect_tracks(page_text, page_dir):
    """The edition's tracks from the page's own listen links, in page
    order — a track stands only when its recording file stands beside
    the page. Returns (tracks, missing) where missing names the hrefs
    whose files did not stand."""
    tracks, missing = [], []
    for title_html, href in STORY_RE.findall(page_text):
        mp3 = page_dir / href
        if mp3.is_file() and mp3.stat().st_size > 0:
            tracks.append({"title": strip_tags(title_html), "href": href,
                           "size_bytes": mp3.stat().st_size})
        else:
            missing.append(href)
    return tracks, missing


def collect_narrations(page_text):
    """href -> the narration step 4 spoke for that story: its headline
    and its bullet texts, read back off the built page itself (the
    headline link and the <li> lines of the story's own article)."""
    narrations = {}
    for block in ARTICLE_RE.findall(page_text):
        m = LISTEN_HREF_RE.search(block)
        if not m:
            continue
        head = STORY_RE.search(block)
        title = strip_tags(head.group(1)) if head else ""
        bullets = [strip_tags(li) for li in LI_RE.findall(block)]
        narrations[m.group(1)] = (title, [b for b in bullets if b])
    return narrations


def split_sentences(title, bullets):
    """The narration as sentences: the headline first (step 4 speaks
    it as its own sentence), then the bullets' text split on sentence
    ends."""
    sentences = []
    if title:
        sentences.append(title)
    text = " ".join(bullets)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9\u201c"\'(])', text)
    sentences.extend(p.strip() for p in parts if p.strip())
    return sentences


def probe_duration(mp3):
    """The recording's measured length in seconds, or None."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", str(mp3)],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return None


def sentence_timings(sentences, duration):
    """Spread the recording's measured length across its sentences in
    proportion to their word counts. Returns [{t, s, e}] or [] when
    the timings cannot be figured."""
    if not sentences or not duration or duration <= 0:
        return []
    weights = [max(1, len(s.split())) for s in sentences]
    total = float(sum(weights))
    out, at = [], 0.0
    for sent, w in zip(sentences, weights):
        end = at + duration * w / total
        out.append({"t": sent, "s": round(at, 2),
                    "e": round(min(end, duration), 2)})
        at = end
    if out:
        out[-1]["e"] = round(duration, 2)
    return out


def _svg(inner):
    return ('<svg viewBox="0 0 48 48" aria-hidden="true" '
            f'focusable="false">{inner}</svg>')


_W = 'fill="#fff"'
# The seven white shapes, drawn exact (Clay's picture, 2026-11-10):
# story jumps carry a bar; the 10-second jumps carry a small "10"
# under the triangles, no bar.
ICON_BEGIN = _svg(
    f'<rect x="5" y="11" width="5" height="26" {_W}/>'
    f'<polygon points="25,11 10,24 25,37" {_W}/>'
    f'<polygon points="41,11 26,24 41,37" {_W}/>')
ICON_BACK = _svg(
    f'<polygon points="23,7 9,20 23,33" {_W}/>'
    f'<polygon points="40,7 26,20 40,33" {_W}/>'
    f'<text x="24" y="45" font-size="11" font-weight="bold" '
    f'font-family="Arial, Helvetica, sans-serif" '
    f'text-anchor="middle" {_W}>10</text>')
ICON_PLAY = _svg(f'<polygon points="17,10 38,24 17,38" {_W}/>')
ICON_PAUSE = _svg(
    f'<rect x="15" y="11" width="6.5" height="26" {_W}/>'
    f'<rect x="26.5" y="11" width="6.5" height="26" {_W}/>')
ICON_FWD = _svg(
    f'<polygon points="8,7 22,20 8,33" {_W}/>'
    f'<polygon points="25,7 39,20 25,33" {_W}/>'
    f'<text x="24" y="45" font-size="11" font-weight="bold" '
    f'font-family="Arial, Helvetica, sans-serif" '
    f'text-anchor="middle" {_W}>10</text>')
ICON_NEXT = _svg(
    f'<polygon points="7,11 22,24 7,37" {_W}/>'
    f'<polygon points="23,11 38,24 23,37" {_W}/>'
    f'<rect x="39" y="11" width="5" height="26" {_W}/>')
ICON_STOP = _svg(f'<rect x="12" y="12" width="24" height="24" {_W}/>')


def _btn(btn_id, icon, word):
    return (f'    <button class="wp-btn" id="{btn_id}" type="button">'
            f'<span class="sym">{icon}</span>'
            f'<span class="word">{word}</span></button>\n')


def player_block(tracks):
    script = PLAYER_JS_TEMPLATE.replace(
        "__PLAYLIST__", json.dumps(tracks, indent=2))
    first_line = f'Story 1 of {len(tracks)}'
    return (
        '\n  <div class="listen whole-player wp-hidden">\n'
        '    <div class="wp-bar">\n'
        + _btn('btn-begin', ICON_BEGIN, 'Start of story or story before')
        + _btn('btn-back', ICON_BACK, 'Back 10 seconds')
        + _btn('btn-play', ICON_PLAY, 'Play')
        + _btn('btn-pause', ICON_PAUSE, 'Pause')
        + _btn('btn-fwd', ICON_FWD, 'Forward 10 seconds')
        + _btn('btn-next', ICON_NEXT, 'Next story')
        + _btn('btn-stop', ICON_STOP, 'Stop')
        + '    </div>\n'
        f'    <p id="np-title">{html.escape(tracks[0]["title"])}</p>\n'
        f'    <p id="now-playing">{first_line}</p>\n'
        '    <p class="wp-time" id="time-line">0:00 of 0:00</p>\n'
        '    <audio id="edition-audio" preload="metadata"></audio>\n'
        f'<script>\n{script}</script>\n'
        '  </div>')


def add_story_numbers(page_text):
    """Lay each story's player-order number by its headline. Runs on
    the success path only, in the same order collect_tracks read."""
    count = [0]

    def repl(m):
        count[0] += 1
        return (f'<h3><span class="wp-storynum">{count[0]}.</span> '
                + m.group(0)[len('<h3>'):])

    return STORY_RE.sub(repl, page_text), count[0]


def main():
    page_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PAGE_DEFAULT
    page_text = page_path.read_text()
    # Idempotent: standing story numbers from an earlier run come off
    # before anything reads the page, and go back on below.
    page_text = STORYNUM_RE.sub("", page_text)
    tracks, missing = collect_tracks(page_text, page_path.parent)
    if missing:
        print(f"FALLBACK: recording file(s) missing beside the page: "
              f"{missing} — page left unchanged")
        return 1
    if len(tracks) < 2:
        print(f"FALLBACK: only {len(tracks)} verified story recording(s) "
              f"— no player, page left unchanged")
        return 0
    narrations = collect_narrations(page_text)
    timed = 0
    for track in tracks:
        title, bullets = narrations.get(
            track["href"], (track["title"], []))
        sentences = split_sentences(title, bullets)
        duration = probe_duration(page_path.parent / track["href"])
        track["sentences"] = sentence_timings(sentences, duration)
        if track["sentences"]:
            timed += 1
    date_str = sys.argv[2] if len(sys.argv) > 2 else None
    if not date_str:
        m = re.search(r"story-(\d{4}-\d{2}-\d{2})-", tracks[0]["href"])
        date_str = m.group(1) if m else "unknown-date"
    playlist_path = page_path.parent / f"daily-review-{date_str}.playlist.json"
    playlist_path.write_text(json.dumps(tracks, indent=2) + "\n")

    # Idempotent: strip a standing player block whole, then re-insert.
    new_text = PLAYER_BLOCK_RE.sub("\n", page_text)
    if ".whole-player" not in new_text:
        new_text = new_text.replace("</style>", PLAYER_CSS + "</style>", 1)
    if ".wp-bar {" not in new_text:
        new_text = new_text.replace(
            "</style>", FULL_PLAYER_CSS + "</style>", 1)
    if ".wp-float" not in new_text:
        new_text = new_text.replace("</style>", POPUP_CSS + "</style>", 1)
    anchor = re.search(r'(<p class="dateline">.*?</p>)', new_text, re.S)
    if not anchor:
        print("FALLBACK: no dateline anchor in the page — page left "
              "unchanged (playlist file was written)")
        return 1
    new_text = (new_text[:anchor.end()] + player_block(tracks)
                + new_text[anchor.end():])
    new_text, numbered = add_story_numbers(new_text)
    page_path.write_text(new_text)
    print(f"PLAYER: {len(tracks)} tracks for {date_str} — pop-up "
          f"follow-along player inserted in {page_path.name} "
          f"({numbered} stories numbered, {timed} with sentence "
          f"timings); playlist at {playlist_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
