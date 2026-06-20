-- migrations/0005_create_generation_state.sql
CREATE TABLE IF NOT EXISTS generation_state (
    id SERIAL PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle', 'running', 'completed', 'failed')),
    progress_message TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_generation_state_singleton ON generation_state((TRUE));
CREATE INDEX idx_generation_state_status ON generation_state(status);

-- Seed initial row
INSERT INTO generation_state (status, progress_message)
VALUES ('idle', 'No generation running')
ON CONFLICT DO NOTHING;

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_generation_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_generation_state_updated_at
    BEFORE UPDATE ON generation_state
    FOR EACH ROW EXECUTE FUNCTION update_generation_state_updated_at();