-- migrations/0004_create_posts.sql
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    content_option_id INTEGER NOT NULL,
    platform VARCHAR(50) NOT NULL,
    image_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'success', 'failed')),
    post_url TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_posts_content_option FOREIGN KEY (content_option_id)
        REFERENCES content_options(id) ON DELETE CASCADE
);

CREATE INDEX idx_posts_content_option_id ON posts(content_option_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_platform ON posts(platform);
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_posts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_posts_updated_at();