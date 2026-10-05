"""Write ../Bayan_Presenter_Script.md from script_data.py (edit the data, not the markdown)."""
from pathlib import Path

from script_data import CHECKLIST, CUTS, DONT_SAY, QA, SPEAKERS, SPEECH, WPM, words

OUT = Path(__file__).parent.parent / "Bayan_Presenter_Script.md"


def clock(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def main():
    rows, blocks, t = [], [], 0.0
    prev_speaker = None
    for n, s in enumerate(SPEECH, 1):
        w = sum(words(x) for _, x in s["steps"])
        dur = w / WPM * 60
        if prev_speaker and s["speaker"] != prev_speaker:
            blocks.append(f"\n**— HANDOFF: {SPEAKERS[prev_speaker]} to {SPEAKERS[s['speaker']]} —**\n")
        prev_speaker = s["speaker"]
        rows.append(f"| {n} | {s['title']} | {SPEAKERS[s['speaker']]} | {len(s['steps'])} | {w} | {dur:.0f} s | {clock(t + dur)} |")
        blocks.append(f"### {n} · {s['title']}  ·  {SPEAKERS[s['speaker']]}  ·  {clock(t)} to {clock(t + dur)}\n")
        for k, (cue, text) in enumerate(s["steps"], 1):
            when = "on arrival" if k == 1 else f"click {k - 1}"
            blocks.append(f"**Step {k}** ({when}) · *on screen: {cue}*\n\n> {text}\n")
        t += dur
    total_w = sum(sum(words(x) for _, x in s["steps"]) for s in SPEECH)

    md = f"""# Bayan pitch: presenter script

Four minutes, one speaker (Sanad), problem → data → models → measuring → results → phone → close. **{total_w} words, about {clock(t)} at {WPM} words a minute**
(one speaker), which leaves about {clock(240 - t)} of the four minutes for clicks, the demo video and breathing.
Generated from `build/script_data.py`; the same text is in the speaker notes of both decks.

## Run sheet

| # | Beat | Who | Steps | Words | Time | Clock |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

## How the beats work

- **Every step waits for a click.** Each step plays once and holds on its last frame; start talking as it starts.
  (`make_html.py --auto` and `manim-slides present` flow steps on automatically instead.)
- In the presenting deck each step is its own slide, so a transition looks like the same animation continuing.
  In the native deck the steps stay on one slide. The numbering above is the same in both.
- Numbers are spoken as words on purpose ("seventy-four percent"). تبسيط is said *tabseet*.

## Script

{chr(10).join(blocks)}

## If you run long

Cut in this order:

{chr(10).join(f"{i}. {c}" for i, c in enumerate(CUTS, 1))}

## Say carefully: what the report does not support

| Do not say | Because |
|---|---|
{chr(10).join(f"| {a} | {b} |" for a, b in DONT_SAY)}

## Questions you may get

Short answers, each about 20 seconds. The last column says where to look if asked for more.

{chr(10).join(f"**{q}**  {a}  *({src})*" + chr(10) for q, a, src in QA)}

## Day-of checklist

{chr(10).join(f"- [ ] {c}" for c in CHECKLIST)}
"""
    OUT.write_text(md, encoding="utf8")
    print(f"{OUT.name}: {total_w} words, {clock(t)}")


if __name__ == "__main__":
    main()
