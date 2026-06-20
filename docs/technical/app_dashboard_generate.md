# app_dashboard_generate.md

## 1. Feature Overview
**Purpose**: Allow users to manually trigger the content generation pipeline from the Dashboard UI.
**Business Value**: Eliminates the need for developers to manually run `python main.py generate` to create new content.
**Scope**: 
- Add a "Generate" button to the Dashboard page.
- Implement a backend endpoint to trigger the generation pipeline.
- Implement a progress tracking mechanism (polling or WebSocket) to show the current status of the pipeline in a single text line.
- Ensure state persistence so that reloading the page recovers the "generating" state and progress.
- Automatically update the UI when posts are ready.
**Success Criteria**: 
- "Generate" button is visible and correctly aligned.
- Clicking the button starts the pipeline.
- Progress is displayed in real-time (or near real-time) in a single line.
- Page reload does not lose the generation status.
- New content appears on the dashboard immediately after completion without a manual refresh.

## 2. Service Ownership
**Primary Service**: `app` (FastAPI)
**Dependent Services**: `modules/content_generator`, `modules/visual_generator`, `shared/db`, `shared/openrouter_client`
**Interface Changes**: 
- New endpoint `POST /generate` to start the pipeline.
- New endpoint `GET /generate/status` to poll for progress.
- New endpoint `POST /generate/reset` to reset a stuck generation state.
- New WebSocket endpoint `GET /generate/ws` for real-time status updates.

## 3. Detailed Implementation

### Backend Logic
- **Pipeline Trigger**: The `POST /generate` endpoint will invoke the logic currently found in `main.py generate`, specifically `app.scheduler.run_pipeline`.
- **Asynchronous Execution**: Since the pipeline takes time, it must be run in a background task (using `asyncio.create_task`).
- **State Management**:
    - A dedicated `generation_state` table is used to track the current generation status. It is a **singleton table** (always exactly 1 row), enforced by a unique partial index `idx_generation_state_singleton ON generation_state((TRUE))`.
    - Schema: `generation_state (id SERIAL PRIMARY KEY, status VARCHAR(20), progress_message TEXT, error_message TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)`.
    - Statuses: `idle`, `running`, `completed`, `failed` (enforced via `CHECK` constraint).
    - A trigger (`trigger_generation_state_updated_at`) automatically updates `updated_at` on every row modification.
    - The table is seeded with a single idle row on creation.
- **Progress Tracking**: 
    - The `run_pipeline` function updates the `generation_state` table at each major step (e.g., "Selecting trend...", "Creating theme...", "Generating content...", "Generating images...").
    - The `run_pipeline` function now accepts an optional `progress_callback` parameter for reporting progress. When provided, the callback is invoked at each major step with the current progress message, allowing alternative progress reporting mechanisms beyond the database table.

### API Endpoints
1. `POST /generate`:
    - Validates if a generation is already in progress by checking the `generation_state` table.
    - If not, sets state to `running` and triggers `run_pipeline` in the background via `asyncio.create_task`.
    - Returns `202 Accepted` with `{"status": "started"}`.
    - If a generation is already running, returns `409 Conflict` with `{"detail": "Generation already in progress"}`.
2. `GET /generate/status`:
    - Returns the current `status`, `progress_message`, `error_message`, and `updated_at` from the `generation_state` table.
    - Returns `200 OK` with JSON: `{"status": "running", "message": "Generating images...", "error_message": "", "updated_at": "2025-01-01T12:00:00+00:00"}`.
3. `POST /generate/reset`:
    - Resets the generation state back to `idle` with message "No generation running".
    - Useful for recovery if a pipeline crashes in a way that leaves the state stuck in `running` (e.g., SIGKILL).
    - Returns `200 OK` with JSON: `{"status": "idle", "message": "No generation running", "updated_at": "..."}`.
4. `WebSocket /generate/ws`:
    - Pushes real-time status updates to the client every 1 second while the generation is running.
    - Sends JSON: `{"status": "idle|running|completed|failed", "message": "...", "error_message": "...", "updated_at": "..."}`.
    - Closes automatically when status transitions to `completed` or `failed`.
    - The frontend only opens this WebSocket during an active generation; initial page load uses `GET /generate/status`.

### Frontend Implementation
- **UI Placement**: Add a button with a distinct color (e.g., primary blue or green) aligned to the right, on the same line as the platform filters.
- **Interaction**:
    - On click, call `POST /generate`.
    - While status is `running`, show the `progress_message` in a single line of text below the button.
    - After triggering, open a **WebSocket** connection to `/generate/ws` for real-time updates.
    - WebSocket pushes JSON `{"status", "message", "error_message", "updated_at"}` every 1 second while running.
    - On WebSocket error, fall back to HTTP polling every 5 seconds.
- **State Recovery**: On page load (`DOMContentLoaded`), the frontend calls `GET /generate/status` to determine if it needs to show the progress line and disable the Generate button. If status is `running`, it opens a WebSocket connection. If `completed`, it shows the completion message without reloading.
- **Auto-Update**: When the WebSocket sends `completed`, the frontend automatically reloads the page once after **2 seconds** (`setTimeout(() => location.reload(), 2000)`) to display the newly generated content. The reload happens only once — subsequent page loads see `completed` via `GET /generate/status` and show the message without triggering another reload.

## 4. Error Handling
- **Concurrent Requests**: If `POST /generate` is called while status is `running`, return `409 Conflict` with detail "Generation already in progress".
- **Pipeline Failure**: If the pipeline crashes, the background task catches the exception and updates the state to `failed` with the error message.
- **Recovery**: The `POST /generate/reset` endpoint resets the state to `idle` if it gets stuck in `running` (e.g., after a SIGKILL or unexpected crash). This is a manual recovery mechanism available to administrators.

## 5. Input/Output Specifications
- **POST /generate**:
    - Input: None.
    - Output (202): `{"status": "started"}`.
    - Output (409): `{"detail": "Generation already in progress"}`.
- **GET /generate/status**:
    - Output: `{"status": "idle|running|completed|failed", "message": "...", "error_message": "...", "updated_at": "..."}`.
- **POST /generate/reset**:
    - Input: None.
    - Output: `{"status": "idle", "message": "No generation running", "updated_at": "..."}`.

## 6. Edge Cases
- **Page Reload during Generation**: The `GET /generate/status` call on load ensures the user sees the current progress.
- **Network Timeout during Polling**: Frontend should handle failed status checks gracefully without stopping the pipeline.
- **Pipeline taking too long**: Ensure the background task doesn't get killed by the server (use a robust background worker if necessary, though `BackgroundTasks` might suffice for this scale).

## 7. Dependencies
- `app.scheduler.run_pipeline` (adapted to update state via `update_generation_state`).
- `app.scheduler.update_generation_state` — UPSERTs the generation state singleton row.
- `app.scheduler.get_generation_state` — reads current state; returns an idle default if the table doesn't exist.
- `app.scheduler.reset_generation_state` — wrapper that sets state to `idle`.
- Database migration `0005_create_generation_state.sql` for creating the `generation_state` table, unique partial index, seed row, and updated-at trigger.

## 8. Testing Requirements
- **Unit Tests**: Test the state transition logic (`idle` -> `running` -> `completed` / `failed`).
- **Unit Tests**: Test the reset endpoint transitions `running` -> `idle`.
- **Integration Tests**: Trigger generation via API and verify that `content_options` are actually created.
- **UI Tests**: Verify button alignment and that the progress message updates.
- **Persistence Test**: Start generation, reload page, verify progress is still visible.
- **WebSocket Test**: Verify that the WebSocket sends status updates and closes on completion/failure.
- **Polling Test**: Verify that the frontend falls back to polling on WebSocket error.

## 9. Deployment Considerations
- **Migration**: Run `migrations/0005_create_generation_state.sql` to create the `generation_state` table, unique partial index, seed row, and updated-at trigger.
- **Monitoring**: Log the start and end of manual generation triggers.
