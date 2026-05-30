# Tool Usage

## write tool

When writing a file always provide both required arguments explicitly:
- `filePath` — the full relative path from the project root (e.g. `data-service/models.py`)
- `content` — the complete file content as a single string

### Rules
- Always provide both arguments explicitly
- Never call with empty or partial arguments
- Never write to shared code without approval
- Never write secrets, credentials, or env files
- Always use exact path from project root
- Verify path before calling the tool
- Always provide complete content
- Never write partial content or placeholder text

### Correct Usage
```json
{
  "content": "# CLI\n\nCLI wrapper script that invokes Python CLI service\n",
  "filePath": "cli"
}
```

### Invalid Usage
- ❌ No arguments
- ❌ Empty arguments
- ❌ Missing required field
- ❌ Wrong data type
- ❌ Secrets/passwords
- ❌ Placeholder text
- ❌ Partial path