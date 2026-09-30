---
title: BayanBench
emoji: 📖
colorFrom: indigo
colorTo: green
sdk: gradio
sdk_version: 6.28.0
app_file: app.py
hf_oauth: true
pinned: false
short_description: Leaderboard and human rating for Bayan rewriting models
---
BayanBench leaderboard, submissions and blind human rating. Needs the Space secret `HF_TOKEN` (read access to
Congi-libya/bayanbench-data, write access to Congi-libya/bayanbench-submissions). Built from `bayanbench/space` in the
team repo with `make_space.sh`.

> **v1 only.** This app reads the v1 scorecard (code and judge tiers). It was never deployed (Gradio Spaces need a
> paid plan in an organisation) and has not been ported to v2.
