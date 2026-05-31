-- migrations/0002_create_themes.sql
CREATE TABLE IF NOT EXISTS themes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    trend_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_themes_trend_id FOREIGN KEY (trend_id)
        REFERENCES trends(id) ON DELETE CASCADE
);

CREATE INDEX idx_themes_name ON themes(name);
CREATE INDEX idx_themes_created_at ON themes(created_at DESC);
CREATE INDEX idx_themes_trend_id ON themes(trend_id);