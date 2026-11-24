"""One static rating page per approved participant (plan 3.3 step 2, 3.5, 3.7).

study_data/pages/<code>/index.html shows Item 1, 2, 3 in the assigned order
(A as GIF, B as an email-style text box, C as the generic GIF), the disclosure
label under each stimulus in the label arm only, and the rating form.
Stimulus files are copied in under neutral names (item1.gif) so the page
source never reveals the condition.

Answers go out one of 2 ways:
  --form-url TEMPLATE  "Send my answers" opens a Google Forms prefill URL; every
                       {placeholder} in TEMPLATE is replaced (see the runbook).
  (default)            "Download my answers" saves <code>_answers.json, which the
                       participant sends back. The download button exists in both modes.

    .venv/bin/python -m study.pages
    .venv/bin/python -m study.pages --form-url 'https://docs.google.com/forms/d/e/ID/viewform?usp=pp_url&entry.1={code}'
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import shutil

from . import DATA_DIR, DISCLOSURE_LABEL, SCENARIO
from .assign import read_assignments
from .batch import read_log

ITEMS = [
    ("funny", "This made me smile or laugh."),
    ("effort1", "The sender put real effort into this."),
    ("effort2", "The sender took time to learn about me."),
    ("thoughtful", "This felt thoughtful."),
    ("specific", "This could only have been made for me."),
    ("creepy1", "This felt creepy."),
    ("creepy2", "The sender seems to know too much about me."),
    ("kind", "I felt in on the joke."),
    ("glance", "I understood it within a few seconds."),
    ("reply", "If this arrived in a cold email, I would reply."),
]
ITEM_KEYS = [k for k, _ in ITEMS]
ATTENTION = ("attention", "Select 2 for this row.")
ATTENTION_POSITION, ATTENTION_AFTER = 2, 5   # inside the 2nd stimulus block, after item 5
END_KEYS = ["mc_ai", "mc_minutes", "open_text", "facts_type"]


def answer_keys() -> list[str]:
    keys = []
    for p in (1, 2, 3):
        keys += [f"item{p}_{k}" for k in ITEM_KEYS]
        if p == ATTENTION_POSITION:
            keys.append(f"item{p}_attention")
    return keys + END_KEYS


CSS = """
:root{--bg:#f7f5f0;--card:#fff;--ink:#1d1d1f;--muted:#6b6860;--line:#e2ded5;--accent:#2f6fed;--accent-ink:#fff;--sel:#e8effd}
:root[data-theme="dark"]{--bg:#15161a;--card:#1f2026;--ink:#f1efe9;--muted:#a7a39a;--line:#34353d;--accent:#7aa2ff;--accent-ink:#0d1020;--sel:#26304a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:680px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 8px}h2{font-size:20px;margin:0 0 12px}
.lead{color:var(--muted);margin:0 0 20px}
.scenario{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;padding:12px 16px;margin:0 0 28px;font-weight:600}
section.item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 16px;margin:0 0 28px}
.stim{display:flex;flex-direction:column;align-items:center;gap:8px;margin:0 0 20px}
.stim img{max-width:100%;height:auto;border-radius:6px;border:1px solid var(--line)}
.stim .email-box{width:100%}
.label{font-size:14px;color:var(--muted);margin:0;text-align:center}
fieldset{border:0;padding:0;margin:0 0 18px}
legend{padding:0;margin:0 0 6px;font-weight:600}
.scale{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}
.scale label{display:flex;align-items:center;justify-content:center;min-height:44px;border:1px solid var(--line);border-radius:8px;cursor:pointer;user-select:none}
.scale input{position:absolute;opacity:0;width:1px;height:1px}
.scale input:checked+span{font-weight:700}
.scale label:has(input:checked){background:var(--sel);border-color:var(--accent)}
.scale input:focus-visible+span{outline:2px solid var(--accent);outline-offset:4px}
.ends{display:flex;justify-content:space-between;font-size:13px;color:var(--muted);margin-top:4px}
.end input[type=number],.end textarea{width:100%;font:inherit;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
.choice{display:flex;gap:12px;flex-wrap:wrap}.choice label{display:flex;gap:6px;align-items:center;min-height:44px}
.missing legend{color:#c0392b}
.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:8px}
button{font:inherit;font-weight:600;min-height:44px;padding:10px 18px;border-radius:8px;border:1px solid var(--accent);cursor:pointer}
button.primary{background:var(--accent);color:var(--accent-ink)}button.secondary{background:transparent;color:var(--accent)}
#status{margin-top:12px;min-height:24px}
"""

JS = r"""
(function(){
  var cfg = JSON.parse(document.getElementById('cfg').textContent);
  var started = new Date();
  var form = document.getElementById('rate');
  var status = document.getElementById('status');
  function collect(){
    var out = {}, missing = [];
    cfg.keys.forEach(function(k){
      var el = form.elements[k];
      var v = el ? (el.value || '') : '';
      if (k !== 'open_text' && v === '') missing.push(k);
      out[k] = v;
    });
    form.querySelectorAll('fieldset').forEach(function(fs){
      var name = fs.getAttribute('data-key');
      fs.classList.toggle('missing', missing.indexOf(name) >= 0);
    });
    return {answers: out, missing: missing};
  }
  function payload(a){
    var now = new Date();
    return Object.assign({code: cfg.code, started_at: started.toISOString(), submitted_at: now.toISOString(),
      seconds: Math.round((now - started) / 1000)}, a);
  }
  function check(){
    var c = collect();
    if (c.missing.length){
      status.textContent = 'Please answer every row marked in red (' + c.missing.length + ' left).';
      var first = form.querySelector('fieldset.missing'); if (first) first.scrollIntoView({behavior:'smooth', block:'center'});
      return null;
    }
    return payload(c.answers);
  }
  document.getElementById('download').addEventListener('click', function(){
    var p = check(); if (!p) return;
    var blob = new Blob([JSON.stringify(p, null, 2)], {type: 'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = cfg.code + '_answers.json';
    document.body.appendChild(a); a.click(); a.remove();
    status.textContent = 'Saved ' + cfg.code + '_answers.json. Please send that file back to the study contact. Thank you.';
  });
  var send = document.getElementById('send');
  if (send) send.addEventListener('click', function(){
    var p = check(); if (!p) return;
    var url = cfg.formUrl.replace(/\{([a-z0-9_]+)\}/g, function(m, k){
      var v = p[k];
      return v === undefined ? m : encodeURIComponent(String(v));
    });
    window.open(url, '_blank', 'noopener');
    status.textContent = 'The form opened in a new tab with your answers filled in. Press Submit there to finish.';
  });
})();
"""


def _scale(name: str, legend: str) -> str:
    opts = "".join(f'<label><input type="radio" name="{name}" value="{v}"><span>{v}</span></label>'
                   for v in range(1, 8))
    return (f'<fieldset data-key="{name}"><legend>{html.escape(legend)}</legend>'
            f'<div class="scale" role="radiogroup">{opts}</div>'
            f'<div class="ends"><span>1 strongly disagree</span><span>7 strongly agree</span></div></fieldset>')


def _block(p: int) -> str:
    rows = []
    for i, (k, text) in enumerate(ITEMS, 1):
        rows.append(_scale(f"item{p}_{k}", f"{i}. {text}"))
        if p == ATTENTION_POSITION and i == ATTENTION_AFTER:
            rows.append(_scale(f"item{p}_attention", ATTENTION[1]))
    return "\n".join(rows)


def _end_questions() -> str:
    ai = "".join(f'<label><input type="radio" name="mc_ai" value="{v}"><span>{v}</span></label>' for v in range(1, 8))
    return f"""<section class="item end">
<h2>A few last questions</h2>
<fieldset data-key="mc_ai"><legend>How much was AI involved in making what you saw?</legend>
<div class="scale" role="radiogroup">{ai}</div><div class="ends"><span>1 no AI</span><span>7 entirely AI</span></div></fieldset>
<fieldset data-key="mc_minutes"><legend>About how many minutes did the sender spend on each one?</legend>
<input type="number" name="mc_minutes" min="0" max="10000" step="any" inputmode="decimal"></fieldset>
<fieldset data-key="open_text"><legend>Did anything cross a line or feel off? What? (optional)</legend>
<textarea name="open_text" rows="3" maxlength="2000"></textarea></fieldset>
<fieldset data-key="facts_type"><legend>Did you enter your real facts or a persona?</legend>
<div class="choice"><label><input type="radio" name="facts_type" value="real"> My real facts</label>
<label><input type="radio" name="facts_type" value="persona"> A persona</label></div></fieldset>
</section>"""


def stimulus_html(cond: str, p: int, b_snippet: str, label: bool) -> str:
    if cond == "B":
        body = b_snippet
    else:
        body = f'<img src="item{p}.gif" alt="Item {p}" width="480">'
    lab = f'<p class="label">{html.escape(DISCLOSURE_LABEL)}</p>' if label else ""
    return f'<div class="stim">{body}{lab}</div>'


def build_page(a: dict, b_snippet: str, *, form_url: str | None) -> str:
    letters = a["order"].split("-")
    label = a["arm"] == "label"
    sections = []
    for p, cond in enumerate(letters, 1):
        sections.append(f'<section class="item" aria-labelledby="h{p}"><h2 id="h{p}">Item {p}</h2>\n'
                        f'{stimulus_html(cond, p, b_snippet, label)}\n{_block(p)}\n</section>')
    cfg = {"code": a["code"], "keys": answer_keys(), "formUrl": form_url or ""}
    cfg_json = json.dumps(cfg).replace("</", "<\\/")
    send = ('<button type="button" class="primary" id="send">Send my answers</button>'
            '<button type="button" class="secondary" id="download">Download my answers</button>'
            if form_url else '<button type="button" class="primary" id="download">Download my answers</button>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Inside Joke rating</title>
<style>{CSS}</style></head>
<body><main>
<h1>Rate 3 short items</h1>
<p class="lead">This takes about 6 minutes. Answer each row from 1 to 7. Your code is {html.escape(a["code"])}.</p>
<p class="scenario">{html.escape(SCENARIO)}</p>
<form id="rate" onsubmit="return false">
{chr(10).join(sections)}
{_end_questions()}
<div class="actions">{send}</div>
<p id="status" role="status" aria-live="polite"></p>
</form>
</main>
<script type="application/json" id="cfg">{cfg_json}</script>
<script>{JS}</script>
</body></html>
"""


def build_pages(*, data_dir: pathlib.Path, form_url: str | None = None, log=print) -> list[str]:
    if form_url and "{code}" not in form_url:
        raise ValueError("--form-url must contain {code} so the response carries the participant code")
    assignments = read_assignments(data_dir / "assignments.csv")
    screen = read_log(data_dir / "screening_log.csv")
    built = []
    for a in assignments:
        code = a["code"]
        if (screen.get(code) or {}).get("status") != "approved":
            continue
        stim = data_dir / "stimuli" / code
        c_gif = data_dir / "generic" / a["format"] / f"{a['generic_item']}.gif"
        missing = [p for p in (stim / "A.gif", stim / "B.json", c_gif) if not p.exists()]
        if missing:
            log(f"{code}: skipped, missing {[str(m) for m in missing]}")
            continue
        out = data_dir / "pages" / code
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("item*.gif"):
            old.unlink()
        letters = a["order"].split("-")
        for p, cond in enumerate(letters, 1):
            if cond == "A":
                shutil.copyfile(stim / "A.gif", out / f"item{p}.gif")
            elif cond == "C":
                shutil.copyfile(c_gif, out / f"item{p}.gif")
        b = json.loads((stim / "B.json").read_text())
        (out / "index.html").write_text(build_page(a, b["html"], form_url=form_url), encoding="utf-8")
        built.append(code)
    log(f"built {len(built)} page(s) in {data_dir / 'pages'}")
    return built


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build one rating page per approved participant.")
    ap.add_argument("--data-dir", type=pathlib.Path, default=DATA_DIR)
    ap.add_argument("--form-url", default=None, help="Google Forms prefill template containing {code}")
    a = ap.parse_args(argv)
    build_pages(data_dir=a.data_dir, form_url=a.form_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
