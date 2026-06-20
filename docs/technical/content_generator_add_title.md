# content_generator_add_title.md

## 1. Feature Overview
**Purpose**: Introduce an `img_title` field to the content generation process to be used as a text overlay on generated images.
**Business Value**: Improves visual engagement by allowing short, punchy image titles to be overlaid on images, making them more "Pinterest-style" and readable.
**Scope**: 
- Update `content_template.yaml` to request an `img_title` from the LLM.
- Update database schema to store the `img_title`.
- Update Pydantic models to include `img_title`.
- Update `ContentGenerator` to parse and save `img_title`.
- Update `VisualGenerator` to pass `img_title` to the image generation prompt.
**Success Criteria**:
- LLM generates an `img_title` along with the fact and hashtags.
- `img_title` is correctly stored in the `content_options` table.
- `img_title` is included in the prompt sent to the image generation model.

## 2. Service Ownership
**Primary Service**: `content-generator` (Module 3)
**Dependent Services**: `visual-generator` (Module 3)
**Interface Changes**: 
- Database: `content_options` table gets a new column `img_title`.
- Model: `ContentOption` Pydantic model updated.

## 3. Detailed Implementation

### Database Changes
Add an `img_title` column to the `content_options` table.
```sql
ALTER TABLE content_options ADD COLUMN img_title VARCHAR(255);
```
*Note: A new migration file `migrations/0005_add_img_title_to_content.sql` should be created.*

### API/Model Changes
Update `shared/models.py`:
- `ContentOption` class: Add `img_title: Optional[str] = None`.
- `content_option_from_record` helper: Include `img_title=record.get("img_title")`.
- `ContentOptionResponse` class: Add `img_title: Optional[str] = None`.

### Prompt Changes
Update `config/content_template.yaml`:
- `text_prompt`: Update the instructions to generate a short, engaging `img_title`.
- Update the JSON return format: `{{ "img_title": "...", "fact": "...", "hashtags": ["...", "..."] }}`.
- `image_prompt`: Update the prompt to explicitly mention that the `img_title` should be the text overlay. Replace the generic "short text overlay" instruction with the specific `{img_title}` variable.

### Logic Changes
**`modules/content_generator.py`**:
- Update the parsing logic to extract the `img_title` from the LLM's JSON response.
- Update the database `INSERT` query to include the `img_title` field.

**`modules/visual_generator.py`**:
- Update `_get_pending_options` to select the `img_title` column.
- Update `_generate_and_save` to incorporate `option.img_title` into the final prompt sent to the image generation client.

## 4. Error Handling
**Expected Failures**:
- LLM fails to provide the `img_title` field in JSON.
- `img_title` exceeds 255 characters.

**Recovery Strategies**:
- If `img_title` is missing from JSON, fallback to using the `theme` as the image title.
- Truncate `img_title` to 255 characters before database insertion.

## 5. Input/Output Specifications
**Input Validation**:
- `img_title`: String, max 255 characters.

**Output Formats**:
- JSON from `text_prompt`: `{"img_title": "...", "fact": "...", "hashtags": [...]}`.

## 6. Edge Cases
- **Empty img_title**: If the LLM returns an empty string for the img_title, fallback to the theme.
- **Very Long img_title**: Ensure the image generation prompt handles long img_titles gracefully or that the LLM is instructed to keep them short.

## 7. Dependencies
- `config/content_template.yaml`
- `shared/models.py`
- `modules/content_generator.py`
- `modules/visual_generator.py`
- PostgreSQL database

## 8. Testing Requirements
- **Unit Tests**:
    - Verify `ContentGenerator` correctly parses the new JSON format with `img_title`.
    - Verify `ContentOption` model handles the `img_title` field.
- **Integration Tests**:
    - Run a full generation cycle: Trend -> Theme -> Content (with img_title) -> Image.
    - Verify the `img_title` is present in the database and passed to the image generator.
- **Database Test**: Verify migration `0005` applies correctly.

## 9. Deployment Considerations
- **Migration**: Run the new SQL migration before deploying the updated code.
- **Rollback**: `ALTER TABLE content_options DROP COLUMN img_title;`
