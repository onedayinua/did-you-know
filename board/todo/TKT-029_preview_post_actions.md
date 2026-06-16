---
status: todo
service: app
type: feature
ticket_id: TKT-029
created: "2026-06-16T12:00:00Z"
tech_spec: docs/technical/app_preview_post_actions.md
pr:
  url: ""
  branch: ""
tasks:
  - "Add POST /options/{id}/mark-posted endpoint in app/routes.py that creates posts record + updates content_options.status to 'posted'"
  - "Add inline sendPinToExtension JavaScript and fetchImageAsBase64 helper to templates/preview/base.html"
  - "Add 'Post to Pinterest' and 'Mark as Posted' buttons to templates/preview/pinterest.html (and base.html), conditionally shown when option.status == 'approved' and option.platform == 'pinterest'"
  - "Add PINTEREST_EXTENSION_ID env var support in app configuration"
history: []
comments: []
---

# [TKT-029] Preview Page Post Actions (Post to Pinterest / Mark as Posted)

## Description
On the preview page, if the content option status is `approved` and platform is `pinterest`, show two buttons:
1. **Post to Pinterest** — triggers `sendPinToExtension()` from the inject.js Chrome extension code, prefilling the Pinterest pin builder with the post data (title, description, image, URL).
2. **Mark as Posted** — creates a record in the `posts` table and updates `content_options.status` to `'posted'`.

## Technical Specification
See [docs/technical/app_preview_post_actions.md](docs/technical/app_preview_post_actions.md)