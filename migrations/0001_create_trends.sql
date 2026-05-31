-- migrations/0001_create_trends.sql
CREATE TABLE IF NOT EXISTS trends (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    score DECIMAL(5,2) NOT NULL DEFAULT 0.0,
    source VARCHAR(50) NOT NULL DEFAULT 'google_trends',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trends_keyword ON trends(keyword);
CREATE INDEX idx_trends_created_at ON trends(created_at DESC);
CREATE INDEX idx_trends_score ON trends(score DESC);