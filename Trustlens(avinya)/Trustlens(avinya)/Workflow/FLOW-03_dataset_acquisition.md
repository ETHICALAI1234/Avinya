# FLOW-03 — Dataset Acquisition

**Folder:** `01_data` · **Time:** 45 min · **Priority:** NICE (needed to *prove*, not to *build*)

---

## 1. Comes from
**FLOW-02** → working venv with `datasets` installed

## 2. Goal
Get one verified, human-annotated, span-level dataset on disk, with its license understood.

## 3. What to use

### PRIMARY — RAGTruth ✅

**This is the recommendation.** It is the only large public corpus with **human-annotated hallucination spans**, which is exactly what TrustLens outputs.

| | |
|---|---|
| Source | `github.com/ParticleMedia/RAGTruth` → `dataset/response.jsonl` + `dataset/source_info.jsonl` |
| License | **MIT** — safe for a hackathon and for commercial use |
| Size | 2,965 prompts → **17,790 responses**, ~15,090 train / 2,700 test |
| Annotations | **14,289 human-annotated hallucination spans** with char `start`/`end`/`text` |
| Models covered | GPT-3.5-Turbo-0613, GPT-4-0613, Llama-2-7B/13B/70B-Chat, Mistral-7B-Instruct |
| Tasks | QA, Data2txt, Summarisation |
| Paper | Niu et al., ACL 2024 |
| Preprocessed? | **Yes** — clean JSONL, two files, one join. No cleaning needed. |

**Why it beats the alternatives for you:** LettuceDetect (your detector) was trained on RAGTruth's train split, so evaluating on RAGTruth's *test* split is a like-for-like comparison against published numbers. You can put "LettuceDetect reports 79.22% example-level F1 on this exact split" next to your own number and the judge can check it.

**Schema:**
```
response.jsonl    : id, source_id, model, temperature, labels[], split, quality, response
                    labels[] = {start, end, text, label_type, ...}
source_info.jsonl : source_id, task_type, source, source_info, prompt
```
Join on `source_id`.

### SECONDARY (eval breadth) — pick at most one

| Dataset | ID / URL | License | Use | Caveat |
|---|---|---|---|---|
| **HaluBench** | `PatronusAI/HaluBench` (split `test`, 14,900 rows) | **cc-by-nc-2.0 — NON-COMMERCIAL** | Binary PASS/FAIL across domains | Repackages RAGTruth/HaluEval/PubmedQA/etc → **contamination risk if you also use RAGTruth**. Non-commercial license must be stated. |
| **LLM-AggreFact** | `lytang/LLM-AggreFact` | — | Benchmark your verifier vs published balanced-accuracy numbers | **GATED** — must log in to HF and accept terms; `load_dataset(..., token=True)` |
| **HaluEval** | `pminervini/HaluEval`, configs `qa`/`dialogue`/`summarization`/`general` | MIT | Broad QA hallucination pairs | No span offsets — response-level only |
| **FEVER** | `load_dataset("fever", "v1.0")` | CC BY-SA 3.0 | 3-way SUPPORTS/REFUTES/NOT ENOUGH INFO — our exact label scheme | ~427k rows, overkill for 24h; known `NonMatchingChecksumError` on some `datasets` versions |
| **TruthfulQA** | `truthfulqa/truthful_qa` | Apache-2.0 | 817 closed-book truthfulness questions, 38 categories | Tiny, tests the *model* not your *verifier* |
| **FaithBench** | `github.com/vectara/FaithBench` | check repo LICENSE | 4-class with spans, "challenging" cases | Deliberately hard cases → **not representative base rates**, will make your numbers look worse than reality |
| **X-Fact** | `utahnlp/x-fact` | MIT | 31,189 claims, 25 languages incl. Hindi, Tamil, Bengali, Marathi, Gujarati, Punjabi | Only if you pitch multilingual — otherwise skip |

### Recommendation, stated plainly
**RAGTruth as primary. HaluBench as one secondary slice *only if* you exclude its RAGTruth-derived rows.** Do not try to use five datasets in 24 hours.

## 4. How to do it

`scripts/download_ragtruth.py`:
```python
import json, subprocess, pathlib

RAW = pathlib.Path("data/raw"); RAW.mkdir(parents=True, exist_ok=True)

# Shallow clone — the repo is small but there is no reason to pull history
if not (RAW / "RAGTruth").exists():
    subprocess.run(
        ["git", "clone", "--depth", "1",
         "https://github.com/ParticleMedia/RAGTruth.git", str(RAW / "RAGTruth")],
        check=True)

base = RAW / "RAGTruth" / "dataset"
responses = [json.loads(l) for l in (base / "response.jsonl").open()]
sources   = {json.loads(l)["source_id"]: json.loads(l)
             for l in (base / "source_info.jsonl").open()}

print(f"responses: {len(responses)}")
print(f"sources:   {len(sources)}")
print("response keys:", sorted(responses[0].keys()))
print("source keys:  ", sorted(next(iter(sources.values())).keys()))
print("example labels:", responses[0].get("labels"))
```

**Run this and read the printed keys before writing FLOW-04.** Do not trust the schema table above over what the file actually contains — that is the entire anti-hallucination principle of this project, applied to your own build.

If git clone is blocked, download the two `.jsonl` files directly from the GitHub web UI and drop them in `data/raw/RAGTruth/dataset/`.

## 5. Output contract → FLOW-04
- `data/raw/RAGTruth/dataset/response.jsonl`
- `data/raw/RAGTruth/dataset/source_info.jsonl`
- A printed confirmation of the actual field names
- `data/raw/LICENSES.md` recording: RAGTruth = MIT, plus any secondary dataset and its terms

## 6. Done when
- [ ] Both JSONL files on disk
- [ ] Row counts printed and plausible (~17.8k responses)
- [ ] Actual field names recorded in `LICENSES.md` alongside the license
- [ ] `data/raw/` is gitignored

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| GitHub blocked on venue network | Download the raw JSONLs via the web UI, or use the HF derivative `jakobsnel/RAGTruth_Xtended` |
| Repo layout differs from the table | Trust the repo. Update FLOW-04 to match what is actually there. |
| FEVER checksum error | `load_dataset("fever","v1.0", verification_mode="no_checks")` or upgrade `datasets` |
| HF gated dataset blocks you | `huggingface-cli login`, accept terms on the dataset page, pass `token=True` |
| Out of time entirely | **Skip this flow.** Hand-build 20 examples in FLOW-04 and report them honestly as a sample. A working demo with 20 honest examples beats a benchmark with no demo. |

## 8. Verify before trusting
- **Exact filenames and field names inside the RAGTruth repo** — the print statements above exist precisely to check this.
- HaluBench's license (cc-by-nc-2.0) and LLM-AggreFact's gating status — confirm on the HF dataset pages; if you use HaluBench, state the non-commercial restriction in your README.
- Row counts cited here come from the papers/dataset cards; verify against what you download.
