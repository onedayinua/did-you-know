-- migrations/0005_fix_image_paths.sql
-- Strip the 'data/images/' prefix from existing image_path values
-- to match the new template URLs that use /images/ prefix.
UPDATE content_options
SET image_path = RIGHT(image_path, LENGTH(image_path) - LENGTH('data/images/')),
    updated_at = CURRENT_TIMESTAMP
WHERE image_path LIKE 'data/images/%';