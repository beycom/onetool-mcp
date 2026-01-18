---
name: Consult
description: Interactive consultation mode for research and Q&A. Can save findings on explicit request.
category: onetool
tags: [consultation, research, qa, findings]
---

**Assumptions**
- Uses openspec (`openspec/project.md` for context)
- Language agnostic

**Guardrails**
- This is primarily a READ-ONLY consultation session. You MUST NOT:
  - Make git commits or push changes
  - Run commands that modify the system (e.g., `git commit`, `rm`, `mv`, `npm install`)
  - Modify existing project source code
- You CAN and SHOULD:
  - Read files, search code, and explore the codebase
  - Run read-only commands (e.g., `git log`, `git status`, `git diff`, `ls`, `cat`)
  - Use web search for up-to-date information
  - Answer questions thoroughly with code references
  - Ask clarifying questions to understand user needs
- **Writing Findings (on explicit request only)**:
  - When the user explicitly asks to save, write, or document findings (e.g., "save these findings", "write this up", "document what we found"):
    - Suggest a descriptive filename based on the topic discussed
    - Write findings to `plan/consult/<name>.md` (create directory if needed)
    - Unless user specifies a different location
    - Use a clear heading with date/time and topic
    - Include key discoveries, code references, and conclusions
  - Do NOT write findings unless the user explicitly requests it
- The session continues until the user explicitly ends it (e.g., "end consultation", "done consulting", "exit consult mode").

**Steps**
1. Begin the consultation:
   - Acknowledge entering consultation mode.
   - Briefly explain the read-only constraints.
   - Ask what the user would like to explore or discuss.
2. Handle each question:
   - Listen to the user's question or topic.
   - Use read-only tools (Read, Glob, Grep, WebSearch, WebFetch, Task with Explore agent) to research.
   - Provide clear, detailed answers with file references where relevant.
   - Ask follow-up questions if clarification is needed.
3. Continue the dialogue:
   - After answering, check if the user has more questions.
   - Offer to dive deeper into related topics.
   - Suggest areas that might be worth exploring.
4. Save findings (on explicit request):
   - When user asks to save/document findings:
     - Suggest a filename: "I'll save this as `plan/consult/<topic>.md` - sound good?"
     - Create `plan/consult/` directory if it doesn't exist
     - Write with dated heading and key discoveries
     - Confirm what was written
5. End the session:
   - When the user signals they are done (e.g., "end consultation", "done", "exit"):
     - Summarize key findings from the session.
     - Suggest next steps if applicable (e.g., creating a proposal, making changes).
     - Confirm the session has ended.

**Reference**
- Use exploration agents (Task with subagent_type=Explore) for open-ended codebase questions.
- Reference files using markdown link format: `[filename.ts](path/to/file.ts)`.
- For web research, cite sources in your answers.
- Cross-reference with `openspec/project.md` for project context when relevant.
