"""Fixtures for BeamSearchTest: Hugging Face transformers' own beam search (4.57.6) run on a toy model whose logits are
plain integer arithmetic, so the Kotlin test can rebuild the same model and must produce the same tokens.

torch's float32 log_softmax cannot be reproduced bit for bit, and the toy's logits sit on a grid, so some selections
are decided by a one-step float difference. Every top-k call inside generate is watched: a case where two candidates
at a decision boundary (or in the kept order) are within 1e-5 is marked `near_tie`, and the test does not require
those to match.

    python tools/beam_fixtures.py > app/src/test/resources/beam_fixtures.json
"""
import itertools, json, sys
import numpy as np
import torch
import transformers
from transformers import GenerationMixin, PretrainedConfig, PreTrainedModel
from transformers.modeling_outputs import CausalLMOutput

assert transformers.__version__ == "4.57.6", transformers.__version__
EOS, START = 1, 0


def toy_logits(seed, prefix, vocab, pull):
    """Next-token logits after [prefix]: a hash of the prefix mixed with each token id, plus a pull toward EOS that
    grows with length. Mirrored exactly in BeamSearchTest.toyLogits."""
    h = seed
    for t in prefix:
        h = (h * 1_000_003 + t + 1) % 2_147_483_647
    k = np.array([(h * 2_654_435_761 + v * 40_503 + v * v * 97) % 1_000_003 for v in range(vocab)], dtype=np.float32)
    out = k / np.float32(250_000)
    out[EOS] += np.float32(len(prefix)) * np.float32(pull)
    return out


class Cfg(PretrainedConfig):
    model_type = "bayan-toy"


class Toy(PreTrainedModel, GenerationMixin):
    config_class = Cfg

    def __init__(self, config):
        super().__init__(config)
        self.dummy = torch.nn.Parameter(torch.zeros(1))

    def forward(self, input_ids, **kwargs):
        rows = [torch.from_numpy(toy_logits(self.config.seed, r.tolist(), self.config.vocab_size, self.config.pull)) for r in input_ids]
        logits = torch.stack(rows)[:, None, :].expand(-1, input_ids.shape[1], -1)
        return CausalLMOutput(logits=logits)

    def prepare_inputs_for_generation(self, input_ids, **kwargs):
        return {"input_ids": input_ids}


NEAR = 1e-5
_topk = torch.topk
_gap = [float("inf")]


def watched_topk(input, k, *args, **kwargs):
    """torch.topk, recording the smallest gap between neighbours among the k+1 best real (non-filler) values."""
    v = torch.sort(input.reshape(-1) if input.dim() == 1 else input[0], descending=True).values[: k + 1]
    real = v[v > -1e8]
    if real.numel() > 1:
        _gap[0] = min(_gap[0], float((real[:-1] - real[1:]).min()))
    return _topk(input, k, *args, **kwargs)


torch.topk = watched_topk
cases = []
grid = itertools.product([11, 29, 64], [6, 13, 30], [2, 4, 5], [1.0, 0.6, 1.5], [False, True, "never"], [0, 2, 3])
for i, (vocab, max_length, beams, lp, es, ngram) in enumerate(grid):
    if i % 3:            # a third of the grid, spread over every axis
        continue
    for seed, pull in ((7, 0.35), (1234, 0.15), (99991, 0.05)):
        cfg = Cfg(vocab_size=vocab, seed=seed, pull=pull, eos_token_id=EOS, pad_token_id=EOS, bos_token_id=START)
        model = Toy(cfg).eval()
        _gap[0] = float("inf")
        with torch.no_grad():
            out = model.generate(torch.tensor([[START]]), num_beams=beams, max_length=max_length, do_sample=False,
                                 no_repeat_ngram_size=ngram, length_penalty=lp, early_stopping=es, use_cache=False,
                                 eos_token_id=EOS, pad_token_id=EOS, num_return_sequences=1)
        cases.append({"seed": seed, "pull": pull, "vocab": vocab, "max_length": max_length, "beams": beams, "length_penalty": lp,
                      "early_stopping": {False: "Heuristic", True: "WhenFull", "never": "Never"}[es],
                      "no_repeat_ngram": ngram, "near_tie": _gap[0] < NEAR, "output": out[0].tolist()})
json.dump({"transformers": transformers.__version__, "eos": EOS, "start": START, "cases": cases}, sys.stdout)
print(f"{len(cases)} cases, {sum(c['near_tie'] for c in cases)} with a near tie", file=sys.stderr)
