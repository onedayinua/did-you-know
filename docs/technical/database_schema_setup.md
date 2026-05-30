# Database Schema Setup

## 1. Feature Overview
**Purpose**: Create PostgreSQL database schema for Pinterest Food Channel application
**Business Value**: Provide structured storage for trend data, content, visual assets, and scheduled posts
**Scope**: Define all tables, indexes, constraints, and initial data
**Success Criteria**: All tables created with proper indexes, foreign keys, and validation rules

## 2. Service Ownership
**Primary Service**: Database infrastructure (shared by all services)
**Dependent Services**: All services (Trend Collector, Content Pipeline, Quality Assurance, Scheduler)
**Interface Changes**: None - this is foundational schema

## 3. Detailed Implementation

### Database Changes

**Location**: `./migrations/0001_create_pinterest_food_channel_schema.sql`

**Full Schema**:
```sql
-- Pinterest Food Channel Database Schema
-- Migration: 0001_create_pinterest_food_channel_schema.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Trend Data Table
CREATE TABLE trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query VARCHAR(255) NOT NULL,
    trend_score DECIMAL(5,2) NOT NULL DEFAULT 0.0,
    date_collected TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    region VARCHAR(50) NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Content Items Table
CREATE TABLE content_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trend_id UUID NOT NULL,
    food_topic VARCHAR(100) NOT NULL,
    content_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'approved', 'rejected')),
    safety_score DECIMAL(5,2) DEFAULT NULL,
    grammar_score DECIMAL(5,2) DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Visual Assets Table
CREATE TABLE visual_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL,
    image_url TEXT NOT NULL,
    prompt_used TEXT NOT NULL,
    generation_model VARCHAR(100) NOT NULL,
    quality_score DECIMAL(5,2) DEFAULT NULL,
    file_path TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    file_size_bytes INTEGER DEFAULT NULL,
    mime_type VARCHAR(50) DEFAULT 'image/jpeg',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Scheduled Posts Table
CREATE TABLE scheduled_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL,
    visual_id UUID NOT NULL,
    scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
    posted_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'posted', 'failed', 'cancelled')),
    pinterest_post_id VARCHAR(100) DEFAULT NULL,
    pinterest_board_id VARCHAR(100) DEFAULT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Content Processing History Table (audit trail)
CREATE TABLE processing_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    status_before VARCHAR(20),
    status_after VARCHAR(20),
    details JSONB DEFAULT '{}',
    processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
-- Trends Table
CREATE INDEX idx_trends_date_collected ON trends(date_collected DESC);
CREATE INDEX idx_trends_processed ON trends(processed) WHERE NOT processed;
CREATE INDEX idx_trends_trend_score ON trends(trend_score DESC);

-- Content Items Table
CREATE INDEX idx_content_items_trend_id ON content_items(trend_id);
CREATE INDEX idx_content_items_status ON content_items(status);
CREATE INDEX idx_content_items_created_at ON content_items(created_at DESC);
CREATE INDEX idx_content_items_food_topic ON content_items(food_topic);

-- Visual Assets Table
CREATE INDEX idx_visual_assets_content_id ON visual_assets(content_id);
CREATE INDEX idx_visual_assets_quality_score ON visual_assets(quality_score DESC);
CREATE INDEX idx_visual_assets_created_at ON visual_assets(created_at DESC);

-- Scheduled Posts Table
CREATE INDEX idx_scheduled_posts_content_id ON scheduled_posts(content_id);
CREATE INDEX idx_scheduled_posts_visual_id ON scheduled_posts(visual_id);
CREATE INDEX idx_scheduled_posts_status ON scheduled_posts(status);
CREATE INDEX idx_scheduled_posts_scheduled_time ON scheduled_posts(scheduled_time);
CREATE INDEX idx_scheduled_posts_posted_time ON scheduled_posts(posted_time DESC);

-- Processing History Table
CREATE INDEX idx_processing_history_content_id ON processing_history(content_id);
CREATE INDEX idx_processing_history_processed_at ON processing_history(processed_at DESC);
CREATE INDEX idx_processing_history_action ON processing_history(action);

-- Foreign Key Constraints
ALTER TABLE content_items 
ADD CONSTRAINT fk_content_items_trend_id 
FOREIGN KEY (trend_id) REFERENCES trends(id) ON DELETE CASCADE;

ALTER TABLE visual_assets 
ADD CONSTRAINT fk_visual_assets_content_id 
FOREIGN KEY (content_id) REFERENCES content_items(id) ON DELETE CASCADE;

ALTER TABLE scheduled_posts 
ADD CONSTRAINT fk_scheduled_posts_content_id 
FOREIGN KEY (content_id) REFERENCES content_items(id) ON DELETE CASCADE;

ALTER TABLE scheduled_posts 
ADD CONSTRAINT fk_scheduled_posts_visual_id 
FOREIGN KEY (visual_id) REFERENCES visual_assets(id) ON DELETE CASCADE;

ALTER TABLE processing_history 
ADD CONSTRAINT fk_processing_history_content_id 
FOREIGN KEY (content_id) REFERENCES content_items(id) ON DELETE CASCADE;

-- Updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_trends_updated_at 
BEFORE UPDATE ON trends 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_items_updated_at 
BEFORE UPDATE ON content_items 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_visual_assets_updated_at 
BEFORE UPDATE ON visual_assets 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scheduled_posts_updated_at 
BEFORE UPDATE ON scheduled_posts 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial configuration
INSERT INTO trends (query, trend_score, region, processed) VALUES
    ('food trends 2024', 85.50, 'US', true),
    ('easy dinner recipes', 92.30, 'US', true),
    ('healthy snacks', 78.90, 'US', true);
```

**API Endpoints**: None (database migration only)

**Message Formats**: None

## 4. Error Handling
**Expected Failures**:
- Duplicate migration execution
- Missing UUID extension
- Insufficient permissions for table creation
- Foreign key constraint violations during inserts

**Recovery Strategies**:
- Migration should be idempotent with `IF NOT EXISTS` clauses
- Check for UUID extension before use
- Validate permissions before running migration
- Use transactions for atomic schema changes

**Error Responses**: Migration runner will return specific error codes

**Logging Requirements**: Log each successful table creation and index creation

## 5. Input/Output Specifications
**Input Validation**:
- Migration must be sequentially numbered
- SQL must be valid PostgreSQL syntax
- All table names must be lowercase with underscores
- All constraints must have explicit names

**Output Formats**: Migration success/failure with detailed logs

**Data Types**: 
- UUID for all primary keys
- TIMESTAMP WITH TIME ZONE for all dates
- DECIMAL(5,2) for scores (0.00 to 100.00)
- VARCHAR with appropriate length limits

## 6. Edge Cases
- Running migration on existing database with different schema
- Concurrent migration execution attempts
- Database connection failures mid-migration
- Insufficient disk space for index creation
- Timezone inconsistencies in timestamp columns

## 7. Dependencies
- PostgreSQL 13+ with UUID extension support
- Python migration runner script
- Sufficient disk space for indexes
- Database user with CREATE TABLE privileges

## 8. Testing Requirements
- Unit test: Verify SQL syntax is valid
- Integration test: Run migration on test database
- Rollback test: Test migration failure rollback
- Performance test: Verify index creation doesn't timeout
- Data test: Insert sample data and validate constraints

## 9. Deployment Considerations
- **Migration**: Must be first deployment step before any services start
- **Rollback Strategy**: Create separate rollback migration if needed
- **Monitoring**: Monitor database size growth and index performance
- **Performance**: Initial migration expected to complete within 60 seconds
- **Backup**: Take database backup before running migration in production