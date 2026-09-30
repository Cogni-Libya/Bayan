# 0001 — Product form and where the model runs

**Status:** **Accepted** — decided in the meeting of Sun 20 Sep 2026, 20:00
**Decision:** **Option B — Android plugin (`PROCESS_TEXT`)**
**Deciders:** Marwan (project lead), Mohammed (application)
**Issue:** https://github.com/Cogni-Libya/Bayan/issues/9
**Feeds:** Final Action Plan (due Tue 22 Sep, 23:00)

---

## 1. Context

People with dyslexia meet hard Arabic text **inside other apps and websites**. A separate app that
requires copying and pasting text may not match how the problem is actually encountered. We have to
choose the form the product takes, and separately, whether the model runs on the user's device or on
a server.

The mentor's review of the Action Plan asked us to report on-device speed, size and quality
trade-offs. Those numbers depend on this decision, so it blocks the Action Plan.

### Constraints we already know

| Constraint | Value | Source |
|---|---|---|
| Simplification model | AraT5v2-base-1024, ~368M params | model config |
| Size, full precision (fp32) | ~1.4 GB | 368M × 4 bytes |
| Size, int8, as-is | ~400 MB | 368M × 1 byte + overhead |
| Size, int8 after vocabulary pruning | **~223 MB** | 46% of the model is two embedding matrices (110,208 × 768 × 2 = 169M params) |
| Size, int4 after vocabulary pruning | **~112 MB** | same, 0.5 bytes/param |
| Readability classifier (already built) | int8 ONNX, runs locally, ~16 texts/s on CPU | `scripts/validation.py` |
| Time remaining | Report progress shown at the mentoring sessions Wed 23 and Wed 30 Sep; **final submission Mon 5 Oct, final pitch Tue 6 Oct** | SIC schedule |

> **Latency is being measured, not estimated.** No number is recorded here yet because none has been
> measured on a real phone. The mentor asked for measurements, so this stays blank until we have them
> rather than carrying a guess that later gets quoted as a result.

---

## 2. Options considered

### A — Chrome extension
- **Stack:** Manifest V3; ONNX Runtime Web or transformers.js.
- **Against:** desktop-first, while the reading our users actually struggle with happens on a phone.
  WebAssembly inference for a 368M-parameter seq2seq model in a browser tab is also the least
  predictable of the three.

### B — Android plugin (`PROCESS_TEXT`) — **chosen**
- **Stack:** Kotlin activity registering `android.intent.action.PROCESS_TEXT`; ONNX Runtime Mobile.
- **For:** "تبسيط" appears in the text-selection menu of every app on the phone, so the tool is present
  at the moment the reader meets hard text — no copying, no pasting, no separate app to open.

### C — Standalone app
- **Stack:** ordinary Kotlin app with a text box.
- **Against:** it works, but it requires the reader to copy text out of wherever they were reading and
  paste it somewhere else. That is the friction the project exists to remove.

---

## 3. Why B

The deciding argument is not a score, it is where the problem happens. A reader with dyslexia meets hard
Arabic **inside** an app they are already using — a message, a news page, a PDF. A and C both ask them to
leave that context; B does not.

The three also differ in how much they can be defended in the final pitch. B demos as one gesture inside
a real app. C demos as a text box, which looks like any other model demo. A cannot be demoed on a phone
at all.

Effort is roughly equal: all three need the same ONNX export and the same decode loop, and the surface
around it is small in every case.

---

## 4. Where the model runs

A separate axis from the product form. Decide explicitly — do not let it fall out by default.

| | On the device | On a server |
|---|---|---|
| Privacy | Text never leaves the device | User text sent to us |
| Works offline | Yes | No |
| Size cost to the user | 112–223 MB download | None |
| Latency | Bounded by the user's CPU | Bounded by the network |
| Cost to us | None | Hosting, for as long as the demo must stay up |
| Risk to the final demo | Slow or fails on a weak laptop | Fails if the network fails on pitch day |

**Chosen:** **On the device.**

**Because:** the plugin's whole value is that it works wherever the user is already reading. A server
round-trip breaks that in three ways: it needs a connection the user may not have, it sends the
text they are reading to us, and it puts a hosted service on the critical path of the final pitch.
On-device costs a one-time download and is bounded by the phone's CPU, which we can measure and
control. A server is bounded by a network we cannot.

---

## 5. Decision

**We are building Option B — an Android plugin that registers a `PROCESS_TEXT` intent**, so "Simplify"
appears in the text-selection menu of any app on the phone. This matches how the problem is actually
met: a reader with dyslexia hits hard Arabic text inside an app they are already using, selects it,
and simplifies it in place — with no copying, no pasting, and no separate app to open.

---

## 6. Consequences

**What this commits us to:**
- An Android app in Kotlin registering a `PROCESS_TEXT` intent.
- **ONNX Runtime Mobile** as the inference stack, for every model in the pipeline.
- Shipping the model to the user's phone — either inside the app or downloaded on first run.
- Measuring speed on a real device, not estimating it. The mentor asked for numbers.

**What this rules out:**
- A Chrome extension and a standalone app, for this deliverable.
- Any model that cannot be exported to ONNX, or that needs a GPU.
- Python at runtime — which decides the diacritization choice: Mishkal is a Python rule engine and
  is now out on architecture grounds, independently of its error rate.

**Changes needed in the Action Plan (due Tue 22):**
- Name the product form and state that inference is on-device.
- Give the size budget and whatever latency numbers we have by then, and say plainly which are
  measured and which are estimated.

**Mohammed's first build tasks:**
1. `PROCESS_TEXT` skeleton — "Simplify" appears in the selection menu of any app, receives the
   selected text and shows it back unchanged. No model. This proves the plumbing.
2. Load an ONNX model in ONNX Runtime Mobile and run one inference, on a real phone.
3. Wire the two together, and report load time and per-sentence latency.

**Effect on the compression work (Marwan, starting Wed 23):**
- Target format: **ONNX Runtime Mobile**, int8 dynamic quantization first.
- Size budget: **≤ 250 MB** for the simplifier. Vocabulary-pruned int8 is ~223 MB, which fits. int4
  (~112 MB) is the fallback if load time or memory on a mid-range phone turns out to be the problem.
- Add to that: the diacritizer (~45 MB) and the read-aloud model, so the total download matters, not
  just the simplifier.
- Distribution: **download on first run**, not bundled in the APK. Keeps the install small and lets
  us replace the model without shipping a new build.

---

## 7. Follow-ups

- [x] Decision posted in Discord
- [x] Issue #9 closed
- [x] Build tasks issued to Mohammed — [issue #14](https://github.com/Cogni-Libya/Bayan/issues/14),
      including the four build decisions: on-device · tokenizer inside the ONNX graph · greedy
      decoding, no beam search · model downloaded on first run
- [x] Action Plan updated (v6)
- [x] Measured load time and per-sentence latency on a real phone (§8)

---

## 8. Outcome (30 Sep 2026)

The decision held: Bayan runs as a `PROCESS_TEXT` plugin with every model on the device. What the build
changed, measured on a Xiaomi Mi 11X (Snapdragon 870, Android 13, 6 GB RAM):

| Decision | As built |
|---|---|
| On-device | Yes. int8 ONNX bundles run by ONNX Runtime; read-aloud through sherpa-onnx |
| Tokenizer inside the ONNX graph | **Changed:** SentencePiece is implemented in Kotlin (`engine/SentencePieceTokenizer.kt`), so the app needs no onnxruntime-extensions and passes strings to the engine either way |
| Greedy decoding | Yes, with a KV cache, a 3-gram repetition block and a 256-token cap; tokens stream to the screen as they are decoded |
| Download on first run | Yes, from `Congi-libya/bayan-onnx`, resumable, every file checked by SHA-256, Wi-Fi-only by default |
| ≤ 250 MB | AraBART int8 **222 MB** fits. AraT5v2 int8 is 471 MB: vocabulary pruning was not needed for AraBART and was not done for AraT5v2 |
| Bottom sheet without the overlay permission | Yes, for the result. An optional floating panel, which does need the permission, keeps reading while the reader returns to the page |

Latency (AraT5v2 bundle, from the app's logs over six runs): cold model load 2.6–7.3 s; first token
177–318 ms for a paragraph's first sentence and 55–85 ms for later ones; whole sentence 0.48–2.24 s. On a
laptop CPU with the same loop AraBART is 1.9× faster than AraT5v2, so its phone latency should be lower.
