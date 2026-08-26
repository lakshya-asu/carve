# Writing standard for this project

Research completed on 2026-08-26.

## Working conclusion

There is no reliable list of words that proves a passage was written by AI. There is also no dependable general-purpose detector for individual passages. The useful question is simpler: does the writing help a reader understand the engineering work?

For this project, good writing has four properties:

1. It states the result first.
2. It names the part, person, or program that performs each action.
3. It ties important claims to a measurement, file, test, or source.
4. It says what is known, what is assumed, what failed, and what happens next.

The project will use those tests instead of trying to imitate a vague idea of human writing.

## What the research says

### Single words are weak evidence

Kobak and colleagues measured changes across more than 15 million biomedical abstracts. After public LLM tools appeared, some style words rose abruptly. The affected words were often verbs and adjectives rather than subject-matter nouns. The authors are careful about the limit of the method: it can estimate change across a large body of writing, but it cannot identify the author of one abstract.

This matters here. Words such as `robust`, `comprehensive`, or `pivotal` can sound inflated, but a word alone does not establish authorship. We should replace it when it is vague. We should keep it when it has a precise technical meaning.

### Repetition and uniform structure are more useful warning signs

Recent linguistic studies found differences in average patterns between human and model-generated text. The exact result changes by model, prompt, genre, and dataset. Two findings recur: model output often uses more elaborate phrase structures, and human writing usually varies more across syntax and meaning.

That does not mean we should force sentence variety or add colorful synonyms. It means each sentence should follow the work. A measured result can be short. A limitation may need a longer explanation. A procedure should use direct commands. Natural variation follows from those different jobs.

### People are poor AI detectors

Research on human judgment found that people often perform near chance when they try to identify generated text. Repetition and nonsense were useful clues in one study, but many popular clues were wrong. Readers sometimes treated long words and unusual word pairs as machine output even when those features were more common in the human samples.

The practical lesson is not to chase a detector score. Edit for accuracy, usefulness, and voice.

### Automated detectors can cause harm

Detector studies report both false positives and easy evasion. One Stanford-led study found a strong bias against writers who use English as an additional language. Another analysis showed that paraphrasing can sharply reduce detector performance. As model and human text distributions become more alike, reliable general detection becomes mathematically harder.

This project will not use an AI detector as a writing gate. The local checker is only a style lint. It finds a small set of phrases and punctuation choices that we have decided not to use. It does not claim to identify who wrote the text.

### Plain language also works for experts

Government and industry style guides agree on the basics. Put the main point first. Prefer short, familiar words. Use active voice when the actor matters. Keep the subject close to the verb. Use one term for one concept. Break long pages into sections that readers can scan.

Research with engineers, scientists, and medical professionals adds an important qualification. Experts still want concise and scannable pages, but they also need evidence and the correct technical terms. Removing every specialist term would make this report less useful. The right approach is to keep terms such as `articulation`, `intrinsics`, and `permissive`, then explain them when the audience may not know them.

## Audit of the current reports

### What already works

- The reports give exact test counts, timing values, paths, and failure codes.
- They state that the robot model, gripper, meat mechanics, and cutter are references where that is true.
- They show the failed Solution B regression instead of hiding it.
- They separate learned perception from deterministic control.
- They link claims to machine-readable output and manufacturer sources.

### What needed editing

- The Scene 2.0 opening used a slogan instead of stating the decision.
- Several headings used magazine-style phrasing rather than telling the reader what the section contains.
- `Baseline` appeared where `first build`, `current model`, or a named sensor set was clearer.
- Some sentences described what the report was doing instead of what the system or team had done.
- A few paragraphs packed too many actions into one sentence.
- The older technical report described the current reference cell as complete without putting the remaining robot and geometry work in the opening paragraph.

## Project writing rules

### Start with the engineering result

Use:

> We selected the FANUC M-10iD/12 Food Grade arm for Scene 2.0. It has not been imported into Isaac Sim yet.

Avoid:

> A credible scene before a clever pipeline.

The first version tells the reader what changed and what remains.

### Name the actor

Use:

> The tracker combines camera timestamps with conveyor encoder data.

Avoid:

> Camera timestamps and conveyor encoder data are combined.

Passive voice is still useful when the outcome matters more than the actor. It is not forbidden.

### Keep technical words and remove display words

Keep `inverse kinematics`, `joint limit`, `camera intrinsics`, `permissive`, and `cut_target_frame`. These terms carry engineering meaning.

Replace vague display words such as `sophisticated`, `seamless`, `transformative`, and `state of the art` with the actual mechanism or test result.

### Use status words consistently

- `Verified` means a named test or artifact supports the claim.
- `Implemented` means the project contains the code or scene element.
- `Proposed` means the design has not been built.
- `Assumed` means the value has no physical measurement yet.
- `Failed` means an acceptance condition did not pass.
- `Blocked` means the team needs external data, hardware, or authority.

### Keep one term for one concept

Use `workpiece` for the simulated item when discussing control and physics. Use `meat cut` when discussing the process. Do not rotate through `object`, `product`, `item`, and `piece` just to vary the prose.

Use `cutter-entry tray` for the stationary handoff location. Use `cutter` for the downstream machine.

### Write numbers with their meaning

Do not write that performance was good or fast. Write the measured result and the gate. For example:

> The p95 intercept timing error was 3.83 ms. The run passed the configured 10 ms gate.

If the gate has not been established from real process data, say so.

### Separate fact, assumption, and next action

A useful engineering paragraph often follows this order:

1. What we observed.
2. What it means for the current simulation.
3. What it does not prove.
4. What we will test next.

### Use headings as labels, not taglines

Use `What 30 ms costs at belt speed` instead of `Timing is a distance problem`.

Use `What Isaac Sim can test` instead of `What the simulation can and cannot represent`.

Use `What passed in Isaac Sim` instead of `Verified snapshot`.

### Do not pad transitions

Remove openings such as `It is important to note`, `In today's landscape`, `Furthermore`, and `In conclusion` unless the transition carries real meaning. Start with the fact.

### Do not manufacture personality

Human writing is not slang, deliberate errors, random sentence lengths, or ornamental metaphors. The report should sound like an engineer explaining work to another person. A small amount of first person is useful when it identifies a decision:

> We chose the fixed camera mount because it keeps calibration stable.

### Keep limitations close to claims

Do not put every caveat in the footer. If a chart uses synthetic data, say that in its caption. If a robot is proposed, label it as proposed beside the robot name.

## Local style lint

`tools/audit_report_language.py` checks the two HTML reports and this guide. It reports sentence length, a short list of canned phrases, and prohibited dash characters. It is intentionally narrow.

The lint does not score authorship. It does not penalize technical terms. A person must still review whether the writing is accurate, specific, and appropriate for the reader.

Run it with:

```powershell
python tools\audit_report_language.py --fail-on-style
```

## Sources

- Dmitry Kobak, Rita Gonzalez-Marquez, Emoke-Agnes Horvat, and Jan Lause, [Delving into LLM-assisted writing in biomedical publications through excess vocabulary](https://pmc.ncbi.nlm.nih.gov/articles/PMC12219543/), Science Advances, 2025.
- Sergio E. Zanotto and Segun Aroyehun, [Linguistic and Embedding-Based Profiling of Texts Generated by Humans and Large Language Models](https://aclanthology.org/2025.emnlp-main.1163/), EMNLP, 2025.
- Julie M. Culda and colleagues, [Like a Human? A Linguistic Analysis of Human-written and Machine-generated Scientific Texts](https://aclanthology.org/2025.lm4dh-1.4/), LM4DH, 2025.
- Maurice Jakesch and colleagues, [Human heuristics for AI-generated language are flawed](https://pmc.ncbi.nlm.nih.gov/articles/PMC10089155/), PNAS, 2023.
- Weixin Liang and colleagues, [GPT detectors are biased against non-native English writers](https://pmc.ncbi.nlm.nih.gov/articles/PMC10382961/), Patterns, 2023.
- Vinu Sankar Sadasivan and colleagues, [Can AI-Generated Text be Reliably Detected?](https://arxiv.org/abs/2303.11156), 2023.
- UK Government Digital Service, [Use clear language](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/).
- Microsoft, [Use simple words, concise sentences](https://learn.microsoft.com/en-us/style-guide/word-choice/use-simple-words-concise-sentences).
- Google, [Second person and first person](https://developers.google.com/style/person).
- Nielsen Norman Group, [Writing Digital Copy for Domain Experts](https://www.nngroup.com/articles/writing-domain-experts/).

## Limits of this research

Most linguistic studies compare groups of texts. Their findings depend on the model, prompt, date, subject, and genre. They do not supply a universal recipe for human prose. English-language style guidance also reflects cultural and institutional preferences. We will treat this standard as an editorial tool and revise it when readers find a rule unhelpful.

## Rerun inputs

Use these questions for the next review:

- Which passages slowed the reader down?
- Which claims lacked a test, file, number, or source?
- Which headings failed to describe their section?
- Which technical terms need one sentence of explanation?
- Which caveats were too far from the claim they qualify?
- Did the opening state the current result and the next step?
