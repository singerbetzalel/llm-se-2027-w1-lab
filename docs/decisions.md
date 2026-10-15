# Unspecified decisions

The brief did not tell you everything. Every time you or your agent chose
something the brief did not specify, add a line here.

Examples of the kind of thing that counts: what fields the record has, what
happens to an issue with no clear type, how confident is confident enough,
what the output looks like when the model returns nothing usable.

You will need this list in W2, when we reconstruct the requirements this
build implicitly assumed. The comparison across the cohort is the lesson, so
write down what you actually decided, not what you think is the right answer.

---

- Record fields: repo, number, url, issue_type, component, severity, has_reproduction_steps, summary, confidence, needs_human_review, rationale, model, error — chosen to mirror the dataset's gold_* fields so the output can be scored later.
- issue_type vocabulary is bug / enhancement / documentation / question / unknown, shared across all repos; hono's "meta" (announcement) type was dropped.
- An issue with no clear type gets issue_type "unknown" (the model may choose it) and is always flagged needs_human_review.
- component uses each repo's own vocabulary from config/repos.toml (not normalised across repos); anything outside that list becomes null; textual always gets null.
- severity is assigned to every issue type, not only bugs; feature requests and questions are expected to be "low". Levels are defined in the prompt (critical/high/medium/low/unknown).
- "Confident enough" = confidence >= 0.7 for issue_type; below that, needs_human_review is true. 0.7 is a guess, not calibrated.
- confidence is the model's self-reported number in [0, 1]; it is not calibrated against anything.
- Existing GitHub labels are NOT shown to the model: incoming issues are usually unlabelled, and gold labels are derived from them (leakage).
- Issue title/body are passed to the model as data with an explicit "untrusted, ignore instructions" note; outputs are constrained to fixed vocabularies and validated in Python; issue text never reaches a shell.
- Bodies longer than 8000 characters are truncated before the model call.
- If the model call fails or returns invalid output, the tool still prints a record: issue_type/severity "unknown", confidence 0, needs_human_review true, and an error message. Exit code is still 0.
- Out-of-range or wrongly-typed model output (e.g. confidence 1.5) is treated as a failure, not clamped or repaired. Label case/whitespace ("Bug ") is normalised.
- Model: LLM_MODEL from .env (anthropic/claude-sonnet-4-6), temperature 0, max 1000 output tokens, plain dspy.Predict (no chain-of-thought step); a short rationale is requested as an output field instead.
- Input sources: a GitHub issue URL (fetched via REST API, optional GITHUB_TOKEN), a JSON file/stdin with one issue object, or the train/dev snapshot. The test split is refused by the CLI.
- Output format: pretty-printed JSON for one issue; JSON Lines when --limit selects several.
- Pull-request URLs are rejected; only issues are triaged.
