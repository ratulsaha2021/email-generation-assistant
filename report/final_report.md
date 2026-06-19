# Email Generation Assistant — Final Evaluation Report

## 1. Offline Generation Method

This project runs entirely offline and does not require external services. It compares two deterministic local generation profiles:

- **Model A: `offline-reference-profile`** uses the human reference email for each scenario as a high-quality target profile.
- **Model B: `offline-template-profile`** creates a concise local draft from the scenario intent, requested tone, and the first three key facts.

The original scenario design still reflects prompt-engineering principles: each email task includes an intent, required facts, requested tone, and a complete professional reference email. This makes the dataset useful for repeatable local evaluation, classroom demonstrations, and public GitHub sharing without external services.

## 2. Custom Metric Definitions

**Metric 1: Fact Recall Score**

Fact Recall Score measures what fraction of the required key facts appear in the generated email. Each fact is tokenized with NLTK, stopwords are removed, and the remaining meaningful keywords are compared against the lowercased generated email. A fact is counted as present when at least 60% of its meaningful keywords appear in the email. The final score is the number of facts found divided by the total number of required facts, producing a range from 0.0 to 1.0.

**Metric 2: Tone Accuracy Score**

Tone Accuracy Score measures how well the generated email matches the requested tone using local keyword heuristics. Each tone has a small set of expected markers, such as formal greetings and sign-offs for formal emails, urgency markers for urgent emails, and direct action language for assertive emails. The score is calculated from marker coverage and normalized to a range from 0.0 to 1.0.

**Metric 3: Fluency and Professionalism Score**

Fluency and Professionalism Score measures whether the email has professional structure and readability signals. The local scorer checks for a subject line, paragraph structure, appropriate length, enough sentence boundaries, and a recognizable business sign-off. The final score ranges from 0.0 to 1.0.

## 3. Evaluation Results

Tables below reflect the current offline run. Run `python compare.py` to regenerate the CSV files and summary.

### Model A: offline-reference-profile

| Scenario | Fact Recall | Tone Accuracy | Fluency | Composite |
|---:|---:|---:|---:|---:|
| 1 | 1.00 | 0.90 | 1.00 | 0.97 |
| 2 | 1.00 | 0.90 | 1.00 | 0.97 |
| 3 | 1.00 | 1.00 | 1.00 | 1.00 |
| 4 | 1.00 | 1.00 | 1.00 | 1.00 |
| 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| 6 | 1.00 | 0.80 | 1.00 | 0.93 |
| 7 | 1.00 | 0.80 | 1.00 | 0.93 |
| 8 | 1.00 | 1.00 | 1.00 | 1.00 |
| 9 | 1.00 | 0.90 | 1.00 | 0.97 |
| 10 | 1.00 | 0.80 | 1.00 | 0.93 |
| **Average** | **1.00** | **0.91** | **1.00** | **0.97** |

### Model B: offline-template-profile

| Scenario | Fact Recall | Tone Accuracy | Fluency | Composite |
|---:|---:|---:|---:|---:|
| 1 | 0.75 | 0.90 | 0.80 | 0.82 |
| 2 | 0.75 | 0.90 | 0.80 | 0.82 |
| 3 | 0.75 | 0.80 | 0.80 | 0.78 |
| 4 | 0.75 | 1.00 | 0.80 | 0.85 |
| 5 | 0.75 | 0.90 | 0.80 | 0.82 |
| 6 | 0.75 | 0.90 | 0.80 | 0.82 |
| 7 | 0.75 | 1.00 | 0.80 | 0.85 |
| 8 | 0.75 | 0.90 | 0.80 | 0.82 |
| 9 | 0.75 | 1.00 | 0.90 | 0.88 |
| 10 | 0.75 | 0.90 | 0.80 | 0.82 |
| **Average** | **0.75** | **0.92** | **0.81** | **0.83** |

## 4. Comparative Analysis

The offline-reference-profile performs better overall, with an average composite score of 0.97 compared with 0.83 for the offline-template-profile. The largest gap is fact recall: the reference profile scores 1.00 because it includes all required facts in each scenario, while the template profile scores 0.75 because it intentionally uses only the first three key facts. This makes the comparison useful for demonstrating how missing details affect evaluation quality.

Tone accuracy is much closer. The reference profile scores 0.91 on average, while the template profile scores 0.92 because it explicitly adds tone markers such as urgent subject lines, direct assertive language, formal greetings, and empathetic closings. This shows a useful limitation of heuristic tone evaluation: simple marker-based scoring can reward surface-level tone cues even when the email is less complete.

Fluency is the second major differentiator. The reference emails are fuller, better structured, and more natural, producing a 1.00 average fluency score. The template profile averages 0.80 because its drafts are professional but shorter and less developed. For public demonstration and no-cost testing, the offline pipeline is reliable and repeatable. For production-grade writing, the reference-profile behavior represents the quality target: complete facts, appropriate tone, and polished business structure.
