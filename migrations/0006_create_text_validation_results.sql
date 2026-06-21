-- migrations/0006_create_text_validation_results.sql
-- Creates the text_validation_results table for storing per-option validation scores.
-- 
-- Each content option gets one row with scores for:
-- - Toxicity, politeness, grammar, sentiment, readability, img_title quality
-- - Plus metadata: model_used, validation_prompt, raw_response
-- - Plus derived stats: fact_length, hashtag_count, img_title_length
--
-- Uses ON DELETE CASCADE from content_options so deleting an option cleans up.

CREATE TABLE IF NOT EXISTS text_validation_results (
    id SERIAL PRIMARY KEY,
    content_option_id INTEGER NOT NULL REFERENCES content_options(id) ON DELETE CASCADE,
    toxicity_score FLOAT,
    politeness_score FLOAT,
    grammar_score FLOAT,
    sentiment_score FLOAT,
    readability_score FLOAT,
    img_title_score FLOAT,
    fact_length INTEGER,
    hashtag_count INTEGER,
    img_title_length INTEGER,
    model_used VARCHAR(100) NOT NULL,
    validation_prompt TEXT,
    raw_response TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_text_validation_content_option_id ON text_validation_results(content_option_id);
CREATE INDEX idx_text_validation_created_at ON text_validation_results(created_at DESC);

-- Add a unique constraint on content_option_id for upsert support
-- (used by TextValidator._save_results for re-runnable validation)
ALTER TABLE text_validation_results ADD CONSTRAINT text_validation_results_content_option_id_key UNIQUE (content_option_id);