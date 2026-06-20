---
name: explore
description: Explore folder and files
compatibility: opencode
---

# Skill: Explore Folders and Files

When navigating the codebase, locating features, or tracing execution paths, your primary goal is to minimize context token usage. 

**CRITICAL ANTI-PATTERNS:** 
* NEVER use `ls -R`, unbounded `tree`, or generic `grep -r` across the whole project. 
* Do not manually browse source files aimlessly.

### Primary Strategy: Graphify
This project uses a knowledge graph (`graphify-out/`) for context-efficient navigation. You MUST use it as your first step:
1. **Initial Discovery:** Run `graphify query "<question>"` to find relevant files.
2. **Deep Dives:** Use `graphify path "<A>" "<B>"` to see how components connect, or `graphify explain "<concept>"` for focused context.
3. **Architecture Review:** Read `graphify-out/GRAPH_REPORT.md` ONLY if the queries fail to provide enough context.
4. **Maintenance:** If you modify code, run `graphify update .` to keep the graph current.

### Secondary Strategy: Direct Inspection (Fallback)
If Graphify is unavailable, broken, or you already know the exact entrypoint:
* Use `cat <exact_file_path>` to read specific entrypoints (e.g., `main.py`).
* Use highly targeted searches only (e.g., `grep -rn "def serve" ./src`).