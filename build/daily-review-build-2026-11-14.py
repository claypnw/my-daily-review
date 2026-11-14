import json, re, html, pathlib
with open("/home/hatch/workspace/daily-news/stories-2026-11-14.json") as f:
    raw=json.load(f)
stories=[tuple(x) for x in raw]
sections=[("New breakthroughs in AI and its uses",5,[]),("What impact AI is having on the economy",5,[]),("What impact AI is having on states (AZ, NV, CA, OR, WA)",5,[]),("Carnivore",5,[]),("Keto",5,[]),("Payson, AZ",5,[]),("Solar",5,["Panels","Battery"])]
def esc(s): return html.escape(s,quote=True)
DATE_LONG="Saturday, November 14, 2026"
WINDOW="November 11–14, 2026"
out=[]
out.append('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">')
out.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
out.append(f'<title>My Daily Review — {DATE_LONG}</title>')
cur=pathlib.Path("/home/hatch/workspace/daily-news/index.html").read_text()
m=re.search(r"<style>.*?</style>",cur,re.S)
out.append(m.group(0)+'</head><body>\n<div class="paper">\n  <header class="masthead">\n    <h1 class="nameplate">My Daily Review</h1>\n'+f'    <div class="mast-meta"><span>{DATE_LONG}</span><span>{DATE_LONG}</span></div>\n  </header>\n  <nav class="doors"><a href="https://claypnw.github.io/menu/admin-menu.html">Admin Menu</a><span class="sep">|</span><a href="https://morning-scroll-53x.pages.dev/?from=admin">Morning Scroll</a><span class="sep">|</span><a href="sources.html">Sources</a></nav>\n  <p class="dateline">{DATE_LONG} — the day\'s news on the subjects on Clay\'s list. Stories are from November 11 to November 14, 2026, from the named source list, and each story is carried once across the four days.</p>\n')
def article_html(s):
    sec,sub,headline,url,source,date,bullets=s
    lis="".join(f"<li>{esc(b)}</li>" for b in bullets)
    return f'<article><h3><a href="{esc(url)}" target="_blank" rel="noopener">{esc(headline)}</a></h3>\n<p class="byline">{esc(source)} — {esc(date)}</p>\n<ul>{lis}</ul></article>'
for sec_name,maxn,subs in sections:
    main=[s for s in stories if s[0]==sec_name and s[1] is None]
    allsec=[s for s in stories if s[0]==sec_name]
    note_extra=", with subsections Panels and Battery" if subs else ""
    note=f"Up to {maxn} stories{note_extra}. {len(allsec)} found today." if allsec else f"Up to {maxn} stories{note_extra}."
    out.append('<section>')
    out.append(f'<div class="section-head"><h2>{esc(sec_name)}</h2><p class="subnote">{esc(note)}</p></div>')
    if main or not subs:
        out.append('<div class="cols">')
        if main:
            for s in main: out.append(article_html(s))
        else:
            out.append(f'<p class="nonews">No real news found for this subject in the named sources for {WINDOW}.</p>')
        out.append('</div>')
    for sub in subs:
        ss=[s for s in stories if s[0]==sec_name and s[1]==sub]
        out.append(f'<div class="subhead-wrap"><h3 class="subhead">{esc(sub)}</h3></div>')
        out.append('<div class="cols">')
        if ss:
            out.append(f'<p class="subnote">Up to 5 stories. {len(ss)} found today.</p>')
            for s in ss: out.append(article_html(s))
        else:
            out.append('<p class="subnote">Up to 5 stories.</p>')
            out.append(f'<p class="nonews">No real news found for this subsection in the named sources for {WINDOW}.</p>')
        out.append('</div>')
    out.append('</section>')
out.append(f'''  <h2 class="about-head">About this page</h2>
  <div class="about">My Daily Review is built from Clay's subjects list. Each subject carries a number — the most stories for that subject that day; a new subject starts at 5. Fewer are shown when fewer real stories are found, and a subject with no real news that day says so. Stories come from the named source list Clay picked on October 23, 2026 — 44 sources; each story was opened and checked before use, and each story names its source and its date, with the headline linking to the full story. No one source carries more than a quarter of the day's stories. This page was built on {DATE_LONG}, for the four days November 11–14, 2026, with each story carried once across those days.</div>
</div>
</body></html>''')
pathlib.Path("/home/hatch/workspace/daily-news/index.html").write_text("\n".join(out))
def slugify(h):
    s=h.lower(); s=re.sub(r"[^a-z0-9]+","-",s); return s.strip("-")[:80].strip("-")
seen={}; recs=[]
for i,s in enumerate(stories,1):
    slug=slugify(s[2])
    if slug in seen: seen[slug]+=1; slug=f"{slug}-{seen[slug]}"
    else: seen[slug]=1
    recs.append({"n":i,"headline":s[2],"source":s[4],"slug":slug,"file":f"story-2026-11-14-{slug}.mp3","narration":s[2]+". "+" ".join(s[6])})
json.dump(recs,open("/home/hatch/workspace/daily-news/tts-list-2026-11-14.json","w"),indent=1)
print(f"built {len(stories)} stories")
for r in recs: print(r["n"],r["file"])
