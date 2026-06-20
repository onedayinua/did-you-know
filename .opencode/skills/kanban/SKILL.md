---
name: kanban
description: Kanban Board Workflow
license: MIT
compatibility: opencode
---

# Kanban Board Workflow

⚠️ **TECHLEAD ONLY** ⚠️

This document contains the Kanban board ticket workflow for **techlead only**.

## Quick Start

### Bootstrap Board
```bash
mkdir -p board/{todo,development,review,qa,documentation,done}
```

## Ticket Movement Commands

### Start Development

* YAML Validation: Check if the ticket in board/todo/ has valid YAML frontmatter. If it is plain Markdown, the Techlead must wrap the metadata into the YAML block defined in the Ticket Format section below.
* Branch Creation: Create a new branch for the task.
* Command: git checkout -b "{ticket_id}_$(date +%Y%m%d_%H%M)"
* Link Branch: Update the pr.branch field in the ticket YAML.

```bash
mv board/todo/{ticket} board/development/{ticket}
```
*When*: Assigning ticket to developer

### Ready for Code Review  
Developer Responsibilities:

* Commit Progress: Before moving the ticket, the developer must commit all changes.
* Command: git add . && git commit -m "feat({ticket_id}): implementation complete"

Techlead Responsibilities:

```bash
mv board/development/{ticket} board/review/{ticket}
```
*When*: Developer completes implementation

### Code Review Process
Reviewer Responsibilities:

* Diff-Only Review: To save tokens and time, the reviewer must not read the entire codebase.
* Comparison: Review only the delta between the feature branch and the main branch.
* Command: git diff {start_commit_hash} {end_commit_hash}

Scope: Do not review files outside the diff unless a global refactor was explicitly requested in the tech_spec.

### Review Approved - Ready for Testing
```bash
mv board/review/{ticket} board/qa/{ticket}
```
*When*: Reviewer approves code

### Review Needs Changes
```bash
mv board/review/{ticket} board/development/{ticket}
```
*When*: Reviewer requests changes

### Tests Pass - No Documentation Needed
```bash
mv board/qa/{ticket} board/done/{ticket}
```
*When*: QA tests pass, no docs needed

### Tests Pass - Documentation Needed
```bash
mv board/qa/{ticket} board/documentation/{ticket}
```
*When*: QA tests pass, docs need updating

### Tests Fail - Bugs Found
```bash
mv board/qa/{ticket} board/development/{ticket}
```
*When*: QA finds bugs

### Documentation Complete
```bash
mv board/documentation/{ticket} board/done/{ticket}
```
*When*: Writer completes documentation

### Documentation-Only Ticket
```bash
mv board/todo/{ticket} board/documentation/{ticket}
```
*When*: Ticket only requires documentation work

## Ticket Operations

### Read Ticket
```python
read(filePath="board/todo/ticket_name.md")
```

### Add Comment to Ticket
**Format:**
```yaml
comments:
  - timestamp: "2024-01-15T10:30:00Z"
    author: "developer"
    type: "summary"
    content: "Implementation completed"
```

### Update Ticket History
**Format:**
```yaml
history:
  - timestamp: "2024-01-15T10:00:00Z"
    action: "assigned"
    agent: "developer"
    status: "development"
```

### Add PR Information
**Format:**
```yaml
pr:
  url: "https://github.com/owner/repo/pull/123"
  branch: "feature_name"
  created: "2024-01-15T14:45:00Z"
```

## Common Workflows

### New Feature
```
todo → development → review → qa → documentation → done
                    or
todo → development → review → qa → done
```

### Bug Fix with Review
```
qa → development → review → qa → done
```

### Simple Bug Fix
```
todo → development → qa → done
```

## Ticket Format

```markdown
---
status: todo
service: data-service
type: feature
ticket_id: TKT-001
created: "2024-01-15T10:00:00Z"
tech_spec: docs/technical/data_service_feature.md
pr:
  url: ""
  branch: ""
tasks:
  - "Task 1"
  - "Task 2"
history: []
comments: []
---

# [TKT-001] Feature Name

## Description
Feature description...

## Technical Specification
See [docs/technical/data_service_feature.md](docs/technical/data_service_feature.md)
```

## Rules

1. **Techlead orchestrates**: Only techlead moves tickets
2. **No direct code changes**: Techlead/architect never write code
3. **All work through tickets**: No bypassing the workflow
4. **Update history**: Add entry for every status change
5. **Use ISO timestamps**: `date -u +"%Y-%m-%dT%H:%M:%SZ"`
6. **Mandatory Quality Gates**: Every implementation MUST pass through both @reviewer and @qa agents. Bypassing these gates is a critical workflow violation.
7. **Sequential flow**: Implementations must follow: `development` $\to$ `review` $\to$ `qa` $\to$ (`documentation`) $\to$ `done`.
