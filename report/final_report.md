# Email Generation Assistant: Evaluation Report

*This report is generated automatically by `report.py` from the files in `results/`.*

- **Generator model:** `gemma4:e4b` (Ollama, temperature 0.7, fixed seed)
- **Judge model:** `gemma4:26b` (Ollama, temperature 0, JSON-schema constrained output)
- **Scenarios:** 10

The judge is a different, larger model than the generator, so no model grades its own output.

## 1. Prompting Strategies

### Model A: few-shot-roleplay (advanced)

Role-playing system prompt plus 3 few-shot demonstrations: *Confirm a vendor onboarding schedule* (formal), *Announce a mandatory security patch* (urgent), *Invite the team to a celebration lunch* (casual).
None of the demonstration intents appear in the test scenarios, so the strategy cannot score well by copying an answer.

> You are a senior business communications specialist. You write clear, professional emails that precisely match the requested tone and naturally incorporate every required key fact.
>
> Rules:
> - Match the requested tone exactly (formal, casual, urgent, empathetic, or assertive).
> - Include EVERY key fact, woven into prose rather than copied as bullet points.
> - Start with a specific "Subject:" line.
> - Use a greeting, a focused body, a clear call to action, and a sign-off with a name.
> - Keep the body between 100 and 250 words.
> - Never use placeholders such as [Name], [Date], or [Your Name]; invent plausible names if needed.
> - Output only the email, with no commentary before or after it.

### Model B: simple-prompt (baseline)

A single instruction with no role and no examples:

> Write a professional email based on the given intent, key facts, and tone.

Both strategies receive the same user message: the intent, the key facts as a bulleted list, and the tone.

## 2. Metrics (LLM-as-a-Judge)

| Metric | How it is computed |
|---|---|
| Fact Recall | The judge quotes evidence for **each** key fact and marks it present or absent. Score = present / total. |
| Tone Accuracy | 1-5 rubric score for the requested tone, rescaled to 0-1 as (score - 1) / 4. |
| Clarity & Professionalism | 1-5 rubric score (subject, flow, grammar, length, call to action, sign-off, no placeholders), rescaled the same way. |
| Composite | Mean of the three metrics. |

Deterministic diagnostics are recorded alongside: word count, subject-line presence, and the number of unfilled `[placeholders]`.
The human reference emails in `scenarios.json` are scored with the same judge as a calibration baseline.

<details><summary>Judge system prompt</summary>

> You are a strict, impartial evaluator of business emails. You receive an email's intent, its required key facts, the requested tone, and the email itself.
>
> 1. For EACH key fact, in order, quote the sentence from the email that conveys it (or "none") and decide whether its core meaning is present. Specific details (names, dates, numbers, amounts) must be correct for the fact to count; paraphrasing is fine.
>
> 2. Tone accuracy (1-5) against the requested tone:
>    - formal: courteous salutation, precise professional language, no slang, formal sign-off
>    - casual: warm, conversational, friendly, relaxed phrasing
>    - urgent: time-sensitivity is explicit early, direct language, clear immediate call to action
>    - empathetic: acknowledges impact or feelings, gracious and considerate wording
>    - assertive: confident, direct, firm requests and deadlines, without aggression
>    5 = unmistakably the requested tone throughout; 3 = partly matches or mixed; 1 = wrong tone.
>
> 3. Clarity & professionalism (1-5): specific subject line, logical flow, grammar, concision (roughly 100-250 words), clear call to action, proper sign-off. Unfilled placeholders such as [Name] or [Date], meta-commentary, or multiple alternative drafts are serious defects (score 2 or lower).
>    5 = ready to send unchanged; 3 = usable after edits; 1 = unusable.
>
> Be critical: reserve 5 for genuinely excellent work.

</details>

## 3. Results

### Aggregate

| Metric | few-shot-roleplay | simple-prompt | Delta (A - B) | human-reference |
|---|---:|---:|---:|---:|
| Fact Recall | 1.0000 | 1.0000 | +0.0000 | 1.0000 |
| Tone Accuracy | 1.0000 | 1.0000 | +0.0000 | 1.0000 |
| Clarity & Professionalism | 1.0000 | 0.2500 | +0.7500 | 1.0000 |
| Composite | 1.0000 | 0.7500 | +0.2500 | 1.0000 |
| Placeholders (total) | 0 | 37 | | 0 |
| Avg word count | 117.9 | 180.9 | | 168.9 |

**Winner: few-shot-roleplay** (composite margin +0.2500)

### Model A: few-shot-roleplay

| # | Intent | Tone | Fact Recall | Tone Acc. | Clarity | Composite | Words | Placeholders |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Follow up after a client meeting | formal | 1.00 | 1.00 | 1.00 | 1.000 | 120 | 0 |
| 2 | Request a project deadline extension | empathetic | 1.00 | 1.00 | 1.00 | 1.000 | 147 | 0 |
| 3 | Introduce a new team member | casual | 1.00 | 1.00 | 1.00 | 1.000 | 101 | 0 |
| 4 | Escalate an unresolved support ticket | urgent | 1.00 | 1.00 | 1.00 | 1.000 | 102 | 0 |
| 5 | Send a project status update | formal | 1.00 | 1.00 | 1.00 | 1.000 | 114 | 0 |
| 6 | Decline a vendor proposal politely | empathetic | 1.00 | 1.00 | 1.00 | 1.000 | 144 | 0 |
| 7 | Request budget approval | assertive | 1.00 | 1.00 | 1.00 | 1.000 | 118 | 0 |
| 8 | Apologize for a service disruption | empathetic | 1.00 | 1.00 | 1.00 | 1.000 | 129 | 0 |
| 9 | Invite stakeholders to a product demo | formal | 1.00 | 1.00 | 1.00 | 1.000 | 103 | 0 |
| 10 | Send a performance review reminder to a manager | assertive | 1.00 | 1.00 | 1.00 | 1.000 | 101 | 0 |
| **Avg** | | | **1.000** | **1.000** | **1.000** | **1.000** | 118 | 0 |

### Model B: simple-prompt

| # | Intent | Tone | Fact Recall | Tone Acc. | Clarity | Composite | Words | Placeholders |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Follow up after a client meeting | formal | 1.00 | 1.00 | 0.25 | 0.750 | 191 | 5 |
| 2 | Request a project deadline extension | empathetic | 1.00 | 1.00 | 0.25 | 0.750 | 219 | 5 |
| 3 | Introduce a new team member | casual | 1.00 | 1.00 | 0.25 | 0.750 | 135 | 1 |
| 4 | Escalate an unresolved support ticket | urgent | 1.00 | 1.00 | 0.25 | 0.750 | 175 | 4 |
| 5 | Send a project status update | formal | 1.00 | 1.00 | 0.25 | 0.750 | 161 | 3 |
| 6 | Decline a vendor proposal politely | empathetic | 1.00 | 1.00 | 0.25 | 0.750 | 213 | 5 |
| 7 | Request budget approval | assertive | 1.00 | 1.00 | 0.25 | 0.750 | 176 | 3 |
| 8 | Apologize for a service disruption | empathetic | 1.00 | 1.00 | 0.25 | 0.750 | 195 | 3 |
| 9 | Invite stakeholders to a product demo | formal | 1.00 | 1.00 | 0.25 | 0.750 | 192 | 2 |
| 10 | Send a performance review reminder to a manager | assertive | 1.00 | 1.00 | 0.25 | 0.750 | 152 | 6 |
| **Avg** | | | **1.000** | **1.000** | **0.250** | **0.750** | 181 | 37 |

### Calibration: human reference emails

Scored on the 10 scenario(s) that include a human reference email.

| # | Intent | Tone | Fact Recall | Tone Acc. | Clarity | Composite | Words | Placeholders |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Follow up after a client meeting | formal | 1.00 | 1.00 | 1.00 | 1.000 | 169 | 0 |
| 2 | Request a project deadline extension | empathetic | 1.00 | 1.00 | 1.00 | 1.000 | 180 | 0 |
| 3 | Introduce a new team member | casual | 1.00 | 1.00 | 1.00 | 1.000 | 178 | 0 |
| 4 | Escalate an unresolved support ticket | urgent | 1.00 | 1.00 | 1.00 | 1.000 | 165 | 0 |
| 5 | Send a project status update | formal | 1.00 | 1.00 | 1.00 | 1.000 | 165 | 0 |
| 6 | Decline a vendor proposal politely | empathetic | 1.00 | 1.00 | 1.00 | 1.000 | 175 | 0 |
| 7 | Request budget approval | assertive | 1.00 | 1.00 | 1.00 | 1.000 | 172 | 0 |
| 8 | Apologize for a service disruption | empathetic | 1.00 | 1.00 | 1.00 | 1.000 | 176 | 0 |
| 9 | Invite stakeholders to a product demo | formal | 1.00 | 1.00 | 1.00 | 1.000 | 158 | 0 |
| 10 | Send a performance review reminder to a manager | assertive | 1.00 | 1.00 | 1.00 | 1.000 | 151 | 0 |
| **Avg** | | | **1.000** | **1.000** | **1.000** | **1.000** | 169 | 0 |

## 4. Comparative Analysis

### Failure modes of the lower-scoring strategy

The weakest metric for **simple-prompt** was **Clarity & Professionalism** (0.250).

Lowest-scoring scenarios:

- **Scenario 1** (Follow up after a client meeting, formal), composite 0.750. Contained 5 unfilled placeholder(s). Judge: "Tone: The tone is perfectly formal. It uses a professional salutation, precise language ('comprehensive pilot proposal', 'perfectly aligned'), avoids slang, and concludes with a professional sign-off. Clarity: The email is highly professional, logically structured, and contains a clear call to action. However, the presence of multiple unfilled placeholders ([Client Contact Name], [Link to your scheduling tool], [Your Name], etc.) is a significant defect that prevents a perfect score."
- **Scenario 2** (Request a project deadline extension, empathetic), composite 0.750. Contained 5 unfilled placeholder(s). Judge: "Tone: The tone is highly empathetic. It uses considerate language ('respectfully request', 'apologize for any inconvenience', 'thank you so much for your understanding') and focuses on the shared goal of quality, acknowledging the impact of the delay on the recipient. Clarity: The email is professional, well-structured, and clear. However, it contains multiple unfilled placeholders ([Project Name], [Recipient Name], [Mention Launch Date, if applicable], [Your Name]), which is a serious defect in an evaluation of a ready-to-send draft."
- **Scenario 3** (Introduce a new team member, casual), composite 0.750. Contained 1 unfilled placeholder(s). Judge: "Tone: The tone is perfectly casual. It uses friendly emojis, warm language ('exciting news', 'thrilled', 'fantastic experience'), and a conversational structure that avoids stiff professional jargon. Clarity: The email is highly professional and clear. It features a descriptive subject line, logical flow, and a clear call to action. However, the presence of the unfilled placeholder '[Your Name]' is a technical defect that prevents a perfect score."

### Recommendation

**few-shot-roleplay** is recommended for production. It leads on composite score by 0.2500 (1.0000 vs 0.7500).

- Fact recall, the most costly failure in a business email, is identical for both strategies (1.0000), so the difference comes from tone and clarity.
- Unfilled placeholders: few-shot-roleplay produced 0, simple-prompt produced 37. Any placeholder means the email cannot be sent without manual editing.
- Calibration: the human reference emails scored 1.0000. Generated emails scoring close to or above this suggests the judge is near its ceiling and cannot separate strong outputs well.

### Limitations

- 10 scenario(s) and one judge give a small sample; small score differences are not statistically meaningful.
- LLM judges tend toward lenient scores and can favour longer emails; per-fact evidence and the reference baseline reduce but do not remove this.
- Generation uses a fixed seed, but results can still vary across Ollama versions and hardware.
