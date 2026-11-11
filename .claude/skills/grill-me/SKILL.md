---
name: grill-me
description: Discovery phase of the workflow - interview the user relentlessly about an idea, plan or design until reaching shared understanding, resolving each branch of the decision tree, then hand off to planner. Use when the user brings a raw idea ("tenho uma ideia", "vamos pensar em X"), wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

# Grill Me

If a plan or design is provided, interview me relentlessly about every aspect of it until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

If only a raw idea or feature description is provided, first help me shape it into a concrete plan by exploring the codebase to understand conventions and constraints, then interview me about the design decisions.

For each question, provide your recommended answer.

CRITICAL: Ask exactly ONE question per response. Never list multiple questions. Wait for the user's answer before asking the next question.

If a question can be answered by exploring the codebase, explore the codebase instead of asking.

When every branch is resolved:
- Summarize the decisions in a short numbered list.
- Decisions that shape the whole product go to `PRD.md`, and questions left open at project level (architecture, product direction) go to `OPEN_QUESTIONS.md`. Show the exact text and write it only after the user confirms.
- Decisions about this feature stay in the conversation: offer to hand off to `planner` ("vamos planejar"), which turns them into the feature's plan. Don't write the plan yourself.
