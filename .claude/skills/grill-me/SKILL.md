---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview the user relentlessly about every aspect of their plan until you reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

## How to ask questions

Use the AskUserQuestion tool for every question. If it is not available, ask in plain text with the options listed.

Ask one question at a time and wait for the answer. Give 2–4 concrete options per question, with your recommendation first. The user can always write their own answer.

## Flow

1. After each answer, acknowledge the decision in one sentence, then ask the next question.
2. If a file in the repo can answer a question, read it instead of asking.
3. Continue until every branch is resolved or the user says stop.
4. Finish with a numbered list of decisions and a list of anything still open.
