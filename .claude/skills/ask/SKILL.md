---
name: ask
description: Answer a robotics or robot-learning question grounded in this library first, then primary sources, with paragraph addresses and an honest confidence statement. Use for any "how does X work", "what should I use for Y", "what is the number for Z" question.
user-invocable: true
argument-hint: "<question>"
---

Answer the question in `$ARGUMENTS` the way a principal engineer would answer a colleague: the answer first, then the evidence, then what is uncertain.

Procedure:
1. Search the library before the web: `grep -ril` over `library/`, `sops/`, `experiments/` for the key terms; read the matching paragraphs. Cite them by manual address (entry and paragraph number, e.g. 2-5.3) so the user can jump there in the site. The address of a heading is the `pnum` the site generator assigns; when unsure, cite the file and heading.
2. If the library does not settle it, fetch primary sources (docs, papers, vendor manuals). Never answer a numeric question from memory.
3. If the answer contradicts a note, say so and fix the note in the same turn (set `status: stale` or correct the text, tag anything unverified).
4. If the question reveals a gap worth a note, add a row to `library/topics/00-study-path.md` under a "Backlog" table or write the note if it is small.
5. Reply format: answer in one to three sentences; evidence as a short list with addresses or links; numbers in a table with units, conditions, and source; a final line stating what is verified and what is not. No preamble.

Follow `~/.claude/CLAUDE.md` writing rules. Never fabricate.
