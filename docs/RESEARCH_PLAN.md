# Inside Joke: research plan

CS 85, Fall 2026, Module 7, option B (Explore). Plan written Tue Nov 24 2026. Final homework due Fri Dec 4 2026, 9 pm.

## Summary

Inside Joke turns a person's public professional facts into a small animated GIF with a personalized joke. In sales outreach, a personalized gift has long worked as a signal: it shows the sender spent time on you. Generative AI makes that signal nearly free to produce.

This project asks a social science question with software as the instrument: when a personalized joke costs almost nothing to make, do recipients still read it as effort, and what happens when they are told AI made it?

Disclosure of interest: I run a B2B outbound agency, so I have a commercial reason to hope the answer is yes. The hypotheses, exclusions and analysis below are fixed before data collection for that reason.

## 1. Research questions and hypotheses

### Research questions

- RQ1. Does a personalized humorous GIF signal more sender effort than a generic humorous GIF?
- RQ2. Does telling the recipient that AI made it in seconds reduce that signal?
- RQ3. Does personalization carry a privacy cost, measured as creepiness?
- RQ4. Does the image add anything over the same kind of joke sent as plain text?
- RQ5 (measurement). Do the LLM judge's scores agree with human ratings?

### Hypotheses, fixed before data collection

All ratings use 1 to 7 scales. Conditions A, B and C are defined in section 3.

- H1 (signal). Perceived effort is higher for the personalized GIF (A) than for the generic GIF (C). Test: paired difference A minus C on the effort composite, 2-sided, alpha = .05.
- H2 (disclosure discount). The A minus C difference in perceived effort is smaller for participants who see the AI disclosure label than for those who do not. Test: compare per-participant difference scores between the 2 arms. This test has low power at our sample size (see 3.9). We report it as a direction and an interval estimate.
- H3 (privacy cost). Creepiness is higher for the personalized GIF (A) than for the generic GIF (C). Test: paired difference A minus C on the creepiness composite.
- H4 (medium). Funniness is higher for the personalized GIF (A) than for the personalized text-only message (B). Test: paired difference A minus B on the funny item.

Confirmatory family: H1, H3 and H4, with Holm correction across the 3 tests. H2 is confirmatory in direction and reported with its confidence interval.

### Measurement question, no direction assumed

- M1. For each of 4 dimensions (funny, specific, kind, glance), what is the Spearman correlation between the judge model's score and the mean human rating? Working threshold for "the judge is useful": rho of at least .40 with a 95% interval that excludes 0.

### Exploratory, labeled as such in the write-up

- Reply intent (single item) across A, B and C.
- Whether the number of grounded facts in a joke predicts creepiness.
- Whether creepiness and funniness are negatively related within the personalized conditions, as benign violation theory would predict.

## 2. Approach to knowledge

### The discipline

Experimental social science, at the meeting point of economics (signaling), consumer psychology (humor, privacy) and marketing.

### How this discipline knows things

- It states a prediction before looking at data, so a result cannot be explained after the fact (Simmons, Nelson and Simonsohn 2011).
- It manipulates 1 thing at a time and holds the rest constant.
- It uses random assignment so that groups differ only by chance.
- It measures attitudes with multi-item rating scales and checks that the items agree with each other.
- It includes manipulation checks: a direct test that participants perceived the manipulation.
- It reports effect sizes with confidence intervals, and treats a single small study as an estimate. A p-value alone says little (Lakens 2013).
- It counts a null result as information.

This differs from how the earlier modules knew things. Music theory and art history worked from a fixed corpus. Here the data do not exist until people respond, and the software produces the stimuli.

### Theory behind each hypothesis

- Costly signaling. A signal is credible when it is costly to fake (Spence 1973; Zahavi 1975). In marketing, perceived advertising expense signals seller confidence (Kirmani and Wright 1989; Kirmani and Rao 2000). Gifts work the same way: Camerer (1988) models gifts as signals whose inefficiency is the point. People also use effort as a shortcut for quality and reward visible effort (Kruger et al. 2004; Morales 2005). H1 and H2 follow: personalization should read as effort, and a cue that the effort was near 0 should weaken it.
- Reciprocity. A gift creates a felt obligation to respond (Gouldner 1960; Cialdini 1984). Reply intent is our proxy.
- Humor. Benign violation theory says something is funny when it breaks an expectation and feels safe at the same time (McGraw and Warren 2010). A meta-analysis finds humor in advertising raises attention and liking (Eisend 2009). The guardrails aim to keep the violation benign.
- Personalization and privacy. Highly personalized email can trigger reactance when the personalization is not justified (White et al. 2008). Covert data collection makes personalized ads feel invasive (Aguirre et al. 2015). H3 follows.
- AI-mediated communication. Hancock, Naaman and Levy (2020) define the area and predict that AI involvement changes how senders are judged.

### How the software operationalizes each construct

| Construct | Manipulated or measured | How the software does it |
|---|---|---|
| Personalization | Manipulated, within subjects | Writer prompt receives the participant's facts (A, B) or no personal facts (C). Each personal detail must cite an input field in `grounding`. |
| Dose of personalization | Measured | Count of entries in the chosen concept's `grounding` list. |
| Medium richness | Manipulated, within subjects | Same pipeline; output rendered as GIF (A) or plain text (B). |
| Cost of the signal | Manipulated, between subjects | A label under each stimulus states AI authorship and the 20-second production time, or no label. |
| Perceived effort | Measured | 2 rating items plus an estimate of minutes spent. |
| Benign vs harmful violation | Measured and constrained | Human "creepy" and "in on the joke" items; banned-topic filter; judge "kind" score below 7 blocks a concept. |
| Humor quality | Measured twice | Human "funny" item; judge "funny" score. Agreement between them is M1. |

## 3. Study design

### 3.1 Design at a glance

A 2 x 3 mixed design.

- Between subjects (2 levels): AI disclosure label shown, or no label.
- Within subjects (3 levels): A personalized GIF, B personalized text only, C generic GIF.

Each participant rates 3 stimuli. Target n = 30, acceptable range 24 to 40.

### 3.2 Participants and recruitment

Classmates, friends and housemates, age 18 or older. No agency clients, prospects or employees. No payment. Participation is voluntary and has no connection to anyone's grade.

### 3.3 Procedure, 2 steps

Step 1, intake (about 3 minutes, Google Form). Consent, then 6 facts:

1. First name, or a nickname.
2. Role or title (job, internship, club role or concentration).
3. Field or industry.
4. One thing you are working toward this term.
5. One recurring annoyance in that role (a tool, a meeting, a deadline).
6. Tools you use daily.

Participants may enter a realistic persona instead of themselves, and tick a box saying so.

Step 2, rating (about 6 minutes, 1 to 5 days later). I run the tool in batch, read every output myself, and send each participant a personal link to their 3 stimuli and the rating form.

The 2-step structure has 3 purposes. A human screens every joke before anyone sees it. Generation failures do not waste a participant's time. Participants do not watch the tool run, which keeps the disclosure manipulation meaningful.

### 3.4 Conditions

All participants read the same scenario: "Imagine each of these arrived as the first email from Alex, a salesperson you have never met."

- A, personalized GIF. A concept written from the participant's facts, rendered as an animated GIF.
- B, personalized text only. A different concept written from the same facts, shown as plain text in an email-style box. No image.
- C, generic GIF. A GIF in the same format with a joke about office life in general. No name, no personal facts. Drawn at random from a pool of 6 per format, built in advance with the same writer, judge and renderer.

A and B use 2 different jokes so that nobody rates the same joke twice. The tool keeps the 2 highest-ranked concepts that pass the guardrails, and a seeded coin flip decides which becomes the GIF and which becomes text. Random assignment balances concept quality across A and B.

Format is held constant within a participant. Half get Meme Desk and half get Future Headline. The other 3 formats stay in the prototype but out of the study: Three-Panel Day costs 3 images, Reply Reaction needs a conversation thread, and more formats would add noise.

One art backend is fixed for the whole study (image model or SVG), chosen after the pilot. Any stimulus that falls back to placeholder art is regenerated before sending.

### 3.5 Disclosure manipulation

- Label arm: under each stimulus, "Alex made this with an AI tool in about 20 seconds."
- No-label arm: nothing under the stimulus.

The statement is true, so the study involves no deception. The consent form tells both arms that study materials were produced with generative AI.

Known weakness: participants are in a generative AI course and may assume AI in both arms. The manipulation therefore changes how salient the low cost is. It does not create a belief in human authorship. The manipulation check will show how far apart the arms ended up.

### 3.6 Randomization and counterbalancing

- A script with a recorded random seed assigns everything. I do not choose.
- Disclosure arm: blocked randomization in blocks of 4, in intake order.
- Presentation order: the 6 possible orders of A, B and C are cycled within each arm, so each order appears about equally often per arm.
- Format: alternates within arm.
- Which of the top 2 concepts becomes the GIF: seeded coin flip.
- Generic item: seeded random draw from the pool.
- Assignments are saved to `assignments.csv` before any stimulus is generated.

### 3.7 Rating items

Shown after each stimulus. 1 = strongly disagree, 7 = strongly agree.

1. Funny: "This made me smile or laugh."
2. Effort 1: "The sender put real effort into this."
3. Effort 2: "The sender took time to learn about me."
4. Thoughtful: "This felt thoughtful."
5. Specific: "This could only have been made for me."
6. Creepy 1: "This felt creepy."
7. Creepy 2: "The sender seems to know too much about me."
8. Kind: "I felt in on the joke."
9. Glance: "I understood it within a few seconds."
10. Reply: "If this arrived in a cold email, I would reply."

Composites: effort = mean of items 2 and 3. Creepiness = mean of items 6 and 7. If the 2 items of a composite correlate below .50, I report them separately.

Asked once at the end:

- Manipulation check 1: "How much was AI involved in making what you saw?" (1 = no AI, 7 = entirely AI).
- Manipulation check 2: "About how many minutes did the sender spend on each one?" (number).
- Attention check, placed inside the second stimulus block: "Select 2 for this row."
- Open text: "Did anything cross a line or feel off? What?"
- "Did you enter your real facts or a persona?"

Item 5 doubles as the manipulation check for personalization: A and B should score above C.

### 3.8 Exclusion rules, fixed in advance

Exclude a participant who:

- fails the attention check,
- finishes the rating step in under 90 seconds,
- gives the same answer to all 30 stimulus items,
- submits twice (keep the first submission),
- helped build or test the tool,
- could not be given 2 personalized concepts that passed the guardrails after 3 attempts.

Persona participants stay in the main analysis. A sensitivity analysis repeats each test with real-facts participants only. I report how many people each rule removed.

### 3.9 Analysis

Per hypothesis:

- H1, H3, H4: per-participant paired difference; mean difference with 95% confidence interval; effect size dz; paired t-test; Wilcoxon signed-rank test as a check, because the ratings are ordinal. Holm correction across the 3 tests.
- H2: per-participant A minus C effort difference, compared between arms with a Welch t-test; Hedges g with 95% interval.
- Manipulation checks: label arm vs no-label arm on AI involvement and on estimated minutes (median and Mann-Whitney test for minutes, which will be skewed).
- Mixed model, only if the final n is 30 or more: rating ~ condition x disclosure + position + (1 | participant). Otherwise the paired tests stand alone.
- Order effects: mean rating by position 1, 2, 3, as a descriptive table.

Every confirmatory result is reported whatever its direction or p-value. One figure per hypothesis: individual points, mean and 95% interval.

Power, stated plainly:

- Within subjects, 80% power, 2-sided alpha of .05: n = 24 detects dz of about 0.60, n = 30 about 0.53, n = 40 about 0.46. Smaller effects will likely be missed.
- Between subjects (H2): 15 per arm detects only d of about 1.06, and 20 per arm about 0.91. Real disclosure effects are probably smaller. A null result on H2 will not show that disclosure is harmless.
- If fewer than 16 people complete the study, I report descriptive statistics and plots only, with no significance tests.

### 3.10 Judge vs human agreement (M1)

Unit of analysis: 1 stimulus. Each participant contributes up to 3, so about 90 stimuli.

- Map judge to human: funny to item 1, specific to item 5, kind to item 8, glance to item 9.
- Spearman rho per dimension, with a bootstrap 95% interval that resamples participants, because ratings from 1 person are related.
- Scatter plot per dimension.

3 limits I will state:

- The judge scores the text and never sees the art. Condition B is the cleanest comparison. I report rho for B alone and for all stimuli.
- Range restriction. Participants only see concepts the judge ranked highly and scored 7 or more on kind. That shrinks the correlation.
- With about 30 independent people, a true rho of .40 has an interval of roughly .05 to .66.

Small add-on to address range restriction, if time allows: for 10 fixed personas, 3 raters score all 3 candidate concepts as text (30 concepts), including the ones the judge ranked last. This also tests whether best-of-3 selection picks what humans prefer.

### 3.11 Non-determinism measurements, no participants needed

For 5 fixed personas, run the same input 10 times each (50 runs). Record:

- how many distinct jokes appear,
- the share of concepts that pass the guardrails on the first attempt, and which rule failed,
- the spread of judge totals across runs,
- judge test-retest: score the same concepts twice at temperature 0 and count changes.

### 3.12 Budget

- All model calls are logged with cost by the ledger in `llm.py`.
- Spending cap for the whole study: $25. Stop and switch the art backend to SVG if projected cost passes the cap.
- Expected calls per participant: 1 writer call, 1 judge call, 1 image. The generic pool is built once.

## 4. Ethics and consent

### Consent text, shown before intake

> This is a class project for CS 85 at Harvard. It studies how people react to short humorous images and messages. Some materials were produced with generative AI.
>
> You will enter a few facts about your work or school role, then later rate 3 short items. Total time is about 10 minutes. Enter only facts you would put on a public profile. You may use an invented persona instead of yourself.
>
> What you enter is sent to commercial AI model providers to produce the items. Do not enter anything private or sensitive.
>
> Your ratings are stored under a random code. Your facts are kept on 1 laptop and deleted by Dec 18 2026. Results are reported only as group averages, with no names. A joke made for you will not be shown to anyone else without your separate permission.
>
> Taking part is voluntary. You may stop at any time or ask me to delete your data, with no consequence. This has no connection to any grade. You must be 18 or older.
>
> Questions: [student name and email]. Course staff: Dr. Christopher Thorpe.
>
> [ ] I agree to take part.

### Data minimization

- 6 fields, none sensitive, persona allowed.
- The optional website research step in `research.py` is switched off for the study. Nothing is collected about a participant beyond what they typed.
- Ratings file holds a random code only. The file linking codes to email addresses is separate and deleted after the last reminder.
- No participant-made stimulus appears in the write-up without written permission. Examples in the write-up use invented personas.

### No real prospects

Nobody outside the consented participant pool receives anything. No agency prospects or clients are contacted for this class project.

### No likeness of real people

The art prompts forbid depicting the reader. Characters are generic stylized figures or objects. The SVG path strips embedded images. I check this by eye for every stimulus.

### Guardrails as an ethics mechanism

- The joke targets a shared annoyance of the job, never the person.
- A banned-topic filter in code rejects references to appearance, age, health, family, religion, politics, layoffs and lawsuits.
- Every personal detail must cite the input field it came from, so the tool cannot invent facts about someone.
- The judge's "kind" score must be 7 or higher, or the concept cannot ship.
- For the study, a 5th layer: I read each stimulus before sending it and record any I reject, with the reason.

### After the study

Each participant receives a short note describing both arms and the hypotheses, and an offer to see the results.

### IRB note

Class projects done for teaching, with no intent to publish or generalize, are often not treated as human subjects research that needs IRB review. I will not assume this. On Nov 24 I am asking Dr. Thorpe and the TA to confirm, and I will follow their answer, including contacting the Harvard human subjects office if they advise it. If I later want to publish the results or use them in agency marketing, that would need a new review and new consent.

## 5. Innovations

1. Best-of-N with a cross-family judge. The writer produces 3 concepts at temperature 1.0. A model from a different company scores them at temperature 0. One draw from a non-deterministic system is a gamble; 3 draws plus selection is a process. Using a different model family is meant to reduce a model's preference for its own output (Panickssery et al. 2024; verify venue).
2. Words drawn by code. The image model is told to draw no text. Python draws every letter, so names are always spelled correctly. The non-deterministic part does what it is good at, and the deterministic part does what must be exact.
3. Grounding citations. Each personal detail carries the name of the input field it came from. Code rejects any concept that cites a field that does not exist. This is a cheap, checkable defense against invented facts.
4. Deterministic guardrails before the judge. Word limits, required fields and banned topics are checked by ordinary code, which gives the same answer every time.
5. First-frame-complete GIF. Some desktop versions of Outlook show only the first frame of a GIF (verify current behavior). The first frame is therefore designed to contain the whole joke.
6. SVG fallback. If the image model is unavailable or out of credit, a text model draws the scene as SVG, code sanitizes it, and it is rasterized locally. A gradient placeholder is the last resort, so the pipeline always finishes.
7. Motion grammar. For animation, the model picks from a short list of named primitives (for example `calendar_flip`, `progress_bar`, `stamp`). Code implements each one. The model chooses; it never writes animation code. The choice is validated against the list.
8. A cost and latency ledger on every model call, so the write-up reports measured numbers.

## 6. Success criteria

### Technical

| Criterion | Target | How measured |
|---|---|---|
| Generation time | Median under 20 s per GIF | Ledger timestamps, all study runs |
| File size | Every GIF under 1 MB | File size on disk |
| Guardrail pass rate | At least 70% of concepts pass on first attempt (provisional; reset after pilot) | `rejected` vs `candidates` counts |
| Complete failure rate | Under 5% of runs end with no usable concept | Run log |
| Cost | Under $0.10 per GIF (provisional; reset after pilot) | Ledger |
| Art backend | 0 placeholder images shown to participants | Run log |
| Spelling | 0 misspelled names in on-image text | Manual check of all study stimuli |

### Scientific

- At least 24 valid participants.
- All 4 hypotheses tested as written, with effect sizes and intervals.
- The personalization manipulation check passes (A and B above C on item 5).
- M1 reported for all 4 dimensions.

Success means the study was run as planned and reported in full. It does not require the hypotheses to be supported.

### What I learn even if the hypotheses fail

- H1 fails: personalization from 6 typed facts does not read as effort. That is a useful warning for my own industry.
- H2 shows nothing: I learn the size of the interval, and how many participants a real test would need.
- H3 is supported strongly: the tool has a privacy problem that guardrails did not solve, and the open-text answers say where the line is.
- H4 fails: the image adds cost and latency without adding humor, so text may be enough.
- M1 is low: an LLM judge cannot stand in for people on humor, and best-of-N selection needs a better selector.
- In every case I will have measured how non-deterministic the pipeline is and how much the guardrails remove.

## 7. Timeline

| Day | Work |
|---|---|
| Tue Nov 24 | Finish this plan. Email it to the TA as a time-stamped record and ask the IRB question. Draft consent and intake form. Get 1 format rendering end to end. |
| Wed Nov 25 | Build study mode: generic control, text-only output, disclosure label, top-2 concepts, batch runner, seeded assignment script. Pilot with 2 or 3 people. Send the intake form before people leave for break. |
| Thu Nov 26 | Thanksgiving. Optional. Intake form collects responses on its own. |
| Fri Nov 27 | Optional. If working: run the non-determinism measurements (3.11). |
| Sat Nov 28 | Fix pilot problems. Build the generic pool. Fix the art backend. Freeze prompts and model versions; record them. Build the rating form. |
| Sun Nov 29 | Intake reminder. Write the analysis script and test it on made-up data. Draft the "approach to knowledge" and "innovations" sections. |
| Mon Nov 30 | Intake closes at noon. Batch generation. Read and screen every stimulus. Send rating links by evening. |
| Tue Dec 1 | Class. Ask classmates to complete ratings. Send reminders. Start the methods section. |
| Wed Dec 2 | Ratings close at 9 pm. Apply exclusions. Run the analysis. Make figures. |
| Thu Dec 3 | Class. Write results, limits and learnings. Clean up the process log. Send the note to participants. |
| Fri Dec 4 | Proofread. Package prototype and write-up. Submit by 6 pm; the deadline is 9 pm. |

Fallbacks:

- Fewer than 16 raters by Wed Dec 2: report descriptives only, and say so.
- Image model unavailable: run the whole study on the SVG backend.
- Behind schedule on Sat Nov 28: drop condition B and H4, keep A vs C and the disclosure arm.

The exam is Tue Dec 8. Nothing in this plan runs past Dec 4 except optional resubmission.

## 8. Write-up outline

### Part 1: written plans and descriptions

1. The question in 1 paragraph, and why an economics student who runs an outbound agency cares.
2. Approach to knowledge (section 2 of this plan, shortened).
3. Innovations (section 5).
4. How success is defined and what I hoped to learn (section 6).
5. Method: participants, design, items, randomization, exclusions.
6. Deviations from this plan, listed 1 by 1 with reasons.

### Part 2: the prototype

1. What it does, with 1 example per format using an invented persona.
2. Architecture diagram: facts, writer, guardrails, judge, art, renderer, GIF.
3. Interfaces and APIs: the model API as an interface; the JSON contract between the writer and the code; the format spec in `formats.py` as an interface between the prompt and the renderer.
4. How to run it.

### Part 3: results

1. Participant flow: invited, completed intake, completed ratings, excluded, analyzed.
2. Manipulation checks.
3. H1 to H4: figure, mean difference, interval, effect size, 1 plain sentence each.
4. M1: judge vs human table and scatter plots.
5. Exploratory findings, marked as exploratory.
6. Limits: small convenience sample of students, hypothetical scenario instead of real email, weak disclosure manipulation, single items for some constructs, my commercial interest.

### Part 4: course ideas applied

1. Non-determinism. The same facts and the same prompt give different jokes. Evidence: the 50-run table from 3.11. Why it matters here: a single draw could be unfunny, wrong or unkind. How the system tames it: generate 3, filter with deterministic code, select with a judge at temperature 0, draw words in code.
2. Deterministic vs non-deterministic parts. A table of every stage and which kind it is. The design rule I followed: anything that must be exact is done by code.
3. Stepwise refinement (Wirth 1971). v0: 1 prompt, 1 image, text drawn by the image model. v1: split into concept, guardrail, judge, art and render stages, each testable alone. What each split fixed.
4. Evaluating software. 4 kinds of evaluation used: deterministic checks, an LLM judge, human ratings, and performance measurements. Where they disagreed.

### Part 5: documented process and learnings

1. The process log (section 9), edited.
2. Prompts that worked and prompts that failed, side by side, with the reason.
3. Known flaws I found in my own code, for example: the word-limit check allows 30% over the limit although the prompt says "exactly"; the banned-word list blocks harmless uses such as "old spreadsheet"; the judge cannot see the art.
4. What I would do with 10 times the sample and a real IRB protocol.

### References

Verified to exist; check page numbers before submitting.

- Aguirre, E., Mahr, D., Grewal, D., de Ruyter, K., and Wetzels, M. (2015). Unraveling the personalization paradox. Journal of Retailing, 91(1), 34-49.
- Camerer, C. (1988). Gifts as economic signals and social symbols. American Journal of Sociology, 94 (supplement), S180-S214.
- Cialdini, R. (1984). Influence: The psychology of persuasion.
- Eisend, M. (2009). A meta-analysis of humor in advertising. Journal of the Academy of Marketing Science, 37, 191-203.
- Gouldner, A. (1960). The norm of reciprocity. American Sociological Review, 25(2), 161-178.
- Hancock, J., Naaman, M., and Levy, K. (2020). AI-mediated communication. Journal of Computer-Mediated Communication, 25(1), 89-100.
- Kirmani, A., and Rao, A. (2000). No pain, no gain. Journal of Marketing, 64(2), 66-79.
- Kirmani, A., and Wright, P. (1989). Money talks: Perceived advertising expense and expected product quality. Journal of Consumer Research, 16(3), 344-353.
- Kruger, J., Wirtz, D., Van Boven, L., and Altermatt, T. W. (2004). The effort heuristic. Journal of Experimental Social Psychology, 40(1), 91-98.
- Lakens, D. (2013). Calculating and reporting effect sizes to facilitate cumulative science. Frontiers in Psychology, 4, 863.
- McGraw, A. P., and Warren, C. (2010). Benign violations: Making immoral behavior funny. Psychological Science, 21(8), 1141-1149.
- Morales, A. (2005). Giving firms an "E" for effort. Journal of Consumer Research, 31(4), 806-812.
- Simmons, J., Nelson, L., and Simonsohn, U. (2011). False-positive psychology. Psychological Science, 22(11), 1359-1366.
- Spence, M. (1973). Job market signaling. Quarterly Journal of Economics, 87(3), 355-374.
- White, T., Zahay, D., Thorbjørnsen, H., and Shavitt, S. (2008). Getting too personal: Reactance to highly personalized email solicitations. Marketing Letters, 19, 39-50.
- Wirth, N. (1971). Program development by stepwise refinement. Communications of the ACM, 14(4), 221-227.
- Zahavi, A. (1975). Mate selection: A selection for a handicap. Journal of Theoretical Biology, 53(1), 205-214.
- Zheng, L., et al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. NeurIPS 2023 Datasets and Benchmarks.

Verify before citing:

- Panickssery, A., Bowman, S., and Feng, S. (2024). LLM evaluators recognize and favor their own generations. (Confirm venue.)
- Jakesch, M., et al. (2019). AI-mediated communication: How the perception that profile text was written by AI affects trustworthiness. CHI 2019. (Confirm title and authors.)
- Any study of how disclosed AI authorship of personal messages changes perceived effort. I believe such studies exist from 2023 onward; find and read 1 before citing.

## 9. Process log template

Fill in 1 entry per work session. Short is fine.

### Session entry

- Date and time:
- Goal for this session (1 sentence):
- Tool used (Claude Code, chat, other):
- What I asked for, in my words:
- What I got:
- Did it work? (yes / partly / no)
- How I checked:
- What I changed next and why:
- Time spent:

### Prompts that worked

| Date | Stage (writer, judge, art, code) | Prompt or key sentence | What it produced | Why I think it worked |
|---|---|---|---|---|
| | | | | |

### Prompts that failed

| Date | Stage | Prompt or key sentence | What went wrong | Why (what was ambiguous or missing) | Fix |
|---|---|---|---|---|---|
| | | | | | |

When a prompt fails, ask the model why, and paste its answer here.

### Non-determinism observations

| Date | Same input, how many runs | What varied | What stayed the same | What I did about it |
|---|---|---|---|---|
| | | | | |

### Guardrail log

| Date | Concept (short) | Rule that fired | Correct rejection or false alarm? | Action |
|---|---|---|---|---|
| | | | | |

### Stimulus screening log (study only)

| Participant code | Stimulus | Sent as is / regenerated / withheld | Reason |
|---|---|---|---|
| | | | |

### Version log

| Version | Date | What changed | Why | Evidence it was better |
|---|---|---|---|---|
| v0 | | | | |
| v1 | | | | |

### Deviations from the plan

| Date | Planned | What I did | Reason |
|---|---|---|---|
| | | | |

### Numbers to capture for the write-up

- Median and 90th percentile generation time:
- Mean cost per GIF:
- Largest GIF size:
- First-attempt guardrail pass rate:
- Runs with no usable concept:
- Art backend used, by count:
- Total spend:

## Appendix: study build notes

1. **`render.py` is missing.** `formats.py` says rendering lives there and `art.py` says code draws every letter there, but the package holds only `art.py`, `concept.py`, `config.py`, `formats.py`, `llm.py` and `research.py`. There is no CLI entry point either.
2. **Generic control.** `check()` rejects any concept with empty `grounding`. Add a `generic=True` path that passes a no-facts prospect block, tells the writer not to use a name, and skips the grounding and first-name rules. Pre-build 6 per format for meme and headline, and freeze them.
3. **Top-2 concepts.** `pick()` returns one `chosen`, plus `candidates` holding all passing concepts. Expose the ranked list, and loop up to 3 attempts until at least 2 pass. In non-fast mode the judge runs only when more than 1 concept passes, which this satisfies.
4. **Text-only renderer.** Format the concept's `text` fields plus `email_line` as an HTML email-style box.
5. **Disclosure label.** Render it in the rating page HTML, under the stimulus, so the GIF bytes are identical across arms.
6. **Pin the art backend.** `--art auto` falls through silently from image to svg to placeholder, which would confound the study. Pin `image` or `svg`, and fail loudly on placeholder.
7. **Switch off `research.fetch_site`** for study runs.
8. **Assignment script.** Seeded; writes `assignments.csv` with code, arm, order, format, GIF-concept id and generic item id.
9. **Per-run JSON.** Save chosen and rejected concepts, judge scores, grounding count, backend, and ledger rows. M1 and the technical criteria both read from it.
10. **Rating delivery.** One static HTML page per participant with stimuli as "Item 1, 2, 3" in assigned order, linking to one Google Form prefilled with the participant code. Condition mapping stays in `assignments.csv`.
11. **`analysis.py`.** pandas and scipy: paired tests, dz, bootstrap intervals, Holm correction, Spearman.
