-- migrations/0005_add_img_title_to_content.sql
ALTER TABLE content_options ADD COLUMN img_title VARCHAR(255);
