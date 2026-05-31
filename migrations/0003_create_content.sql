-- migrations/0003_create_content.sql
CREATE TABLE IF NOT EXISTS content_options (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    theme VARCHAR(100) NOT NULL,
    fact TEXT NOT NULL,
    hashtags JSONB NOT NULL DEFAULT '[]',
    image_prompt TEXT,
    image_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'posted', 'expired', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_content_options_status ON content_options(status);
CREATE INDEX idx_content_options_batch_id ON content_options(batch_id);
CREATE INDEX idx_content_options_created_at ON content_options(created_at DESC);
CREATE INDEX idx_content_options_theme ON content_options(theme);
CREATE INDEX idx_content_options_platform ON content_options(platform);
CREATE INDEX idx_content_options_platform_status ON content_options(platform, status);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_content_options_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_content_options_updated_at
    BEFORE UPDATE ON content_options
    FOR EACH ROW EXECUTE FUNCTION update_content_options_updated_at();