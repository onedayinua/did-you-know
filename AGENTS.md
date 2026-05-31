## Kanban Board Workflow - Role-Based Responsibilities

This project uses a ticket-based Kanban board workflow for managing development tasks with clear role separation.

### Role-Based Workflow Knowledge

| Role | Workflow Knowledge | Responsibility |
|------|-------------------|----------------|
| **Techlead** | Full workflow | Orchestrates entire process, moves tickets, coordinates all agents |
| **Architect** | Creates tickets only | Plans work, creates tickets in `board/todo/` |
| **Developer** | Zero workflow | Implements features, writes tests |
| **QA** | Zero workflow | Runs tests, reports results |
| **Reviewer** | Zero workflow | Reviews code for service boundaries |
| **Writer** | Zero workflow | Updates documentation |

### Key Principles
1. **Techlead orchestrates**: Only techlead moves tickets and coordinates workflow
2. **Subagents focus**: Developer, QA, reviewer, writer only do their specific tasks
3. **No direct changes**: Techlead/architect never write code directly
4. **Ticket workflow**: All work must go through tickets

### Quick Reference
- **Ticket location**: `board/{todo,development,review,qa,documentation,done}/` (states, not linear flow)
- **Agent coordination**: Techlead decides state transitions based on circumstances

### Environment Configuration

#### Development Environment
Each service should have `.env.test` configuration files for development and testing:

1.
2. **Test Isolation**: Use test database connections and API keys to avoid affecting production
3. **Agent Usage**: All agents should use `.env.test` during development and testing

#### Expected File Structure
```
<service-name>/
  .env          # Production configuration (gitignored, never commit)
  .env.test     # Test configuration (safe to commit with test values)
  .env.example  # Example configuration with placeholders
```

#### Agent Responsibilities
- **Check for `.env.test`**: Before running tests, verify `.env.test` exists in the service directory
- **Create if missing**: If `.env.test` doesn't exist, create it with test configuration
- **Use test configuration**: Always use `.env.test` for development and testing activities
- **Never use production `.env`**: Avoid using production configuration during development

#### Configuration Guidelines for `.env.test`
- Use test database names
- Use test/stub API keys for external services
- Point to sandbox/staging API endpoints
- Include all required environment variables from `.env.example`

## graphify (MANDATORY REPOSITORY NAVIGATION)

This project has a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships. 

**CRITICAL CONSTRAINT:** Do NOT use standard bash commands like `cd`, `ls`, `find`, `tree`, or `grep` for initial codebase discovery or navigation. You MUST use `graphify` as your primary lens for understanding the repo.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

### Mandatory Execution Order:
1. **Initial Discovery:** For any codebase questions, you MUST first run `graphify query "<question>"` (assuming `graphify-out/graph.json` exists). Do not manually browse source files until this is done.
2. **Deep Dives:** Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. 
3. **Broad Navigation:** If `graphify-out/wiki/index.md` exists, read it for broad navigation instead of raw source browsing.
4. **Architecture Review:** Read `graphify-out/GRAPH_REPORT.md` ONLY if the query/path/explain commands do not surface enough context.
5. **Post-Modification:** After modifying any code, you MUST run `graphify update .` to keep the graph current (AST-only, no API cost).

### Exceptions:
- Dirty `graphify-out/` files are expected. Do not skip using `graphify` just because the graph files are dirty.
- Only skip `graphify` if the user explicitly tells you to, or if the current task is specifically to debug stale/incorrect graphify output.