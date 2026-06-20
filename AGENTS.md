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

## Codebase Navigation

Whenever you need to explore the project structure, locate where a feature is implemented, or trace execution paths (e.g., checking if a scheduler starts), you MUST load the exploration skill.

Invoke the `skill` tool with `skill: "explore"` before executing any bash commands.