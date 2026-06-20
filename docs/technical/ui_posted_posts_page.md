# ui_posted_posts_page.md

## 1. Feature Overview
**Purpose**: Add a "Posted" menu item to the top navigation and a corresponding page to view all posts that have been successfully published.
**Business Value**: Allows users to easily review and preview content that has already been posted without navigating through the full history.
**Scope**: 
- Update top menu navigation.
- Create a new route `/posted`.
- Implement a page listing posts with `status = 'posted'`.
- Implement a "Preview" button for each post that links to the existing preview page.
**Success Criteria**:
- "Posted" link appears in the top menu.
- `/posted` route renders a list of posts with `status = 'posted'`.
- Each post card in the "Posted" list has a "Preview" button.
- Clicking "Preview" redirects to `/preview/{id}`.

## 2. Service Ownership
**Primary Service**: `app` (FastAPI + Jinja2)
**Dependent Services**: None
**Interface Changes**: 
- New GET endpoint `/posted`.
- Modification to `dashboard.html` (or shared layout) to include the menu link.

## 3. Detailed Implementation
**Database Changes**: None (uses existing `content_options` table).

**API Endpoints**:
- `GET /posted`: 
    - Query: `SELECT id, batch_id, platform, theme, fact, hashtags, image_path, status, created_at, updated_at FROM content_options WHERE status = 'posted' ORDER BY created_at DESC`
    - Response: Renders `dashboard.html` with `posted_mode=True`.

**Business Logic**:
- The "Posted" page should reuse the `dashboard.html` template to maintain visual consistency.
- The logic will be similar to the `/approved` route but filtering for `status = 'posted'`.
- The cards should display the theme, fact preview, and image, similar to the dashboard.
- The "Preview" button should link to `/preview/{id}`.

**State Management**:
- The page is read-only (list of posted content).

## 4. Error Handling
**Expected Failures**:
- No posted posts found (empty list).
- Database connection failure.
**Recovery Strategies**:
- If no posts are found, display a "No posted posts yet" message.
- Standard FastAPI error handling for DB failures (500 Internal Server Error).

## 5. Input/Output Specifications
**Input Validation**:
- No user input for the list page.
- `id` in the preview link must be a positive integer.
**Output Formats**:
- HTML rendered via Jinja2.

## 6. Edge Cases
- **Empty State**: No posts have been marked as 'posted'.
- **Platform Filtering**: Ensure that if platform filters are added later, they work consistently with the dashboard.
- **Deleted Images**: If an image path exists in DB but the file is missing from `data/images/`, show a placeholder.

## 7. Dependencies
- **Internal Services**: `shared.db` for queries.
- **Templates**: `app/templates/dashboard.html`.

## 8. Testing Requirements
- **Unit Tests**: Test the `/posted` route returns 200 OK.
- **Integration Tests**: 
    - Create a `content_option` with status `posted`.
    - Verify it appears on the `/posted` page.
    - Verify the "Preview" button leads to the correct preview page.
- **UI Tests**: Verify the "Posted" link is present in the top menu.

## 9. Deployment Considerations
- **Migration**: No SQL migrations needed.
- **Rollback**: Revert the route and template changes.
- **Performance**: Index on `status` in `content_options` table is recommended if the table grows large.
