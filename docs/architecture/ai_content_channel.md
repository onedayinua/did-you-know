# AI Content Channel - Architecture

## Overview
AI-driven social media channel featuring "Did you know?" style culinary entertainment content. The system automates content creation from trend discovery to scheduled posting across multiple platforms.

## Architectural Principles
1. **Platform Agnostic**: Content creation independent of posting destination
2. **Configurable Output**: Generate multiple options, select best
3. **Template Driven**: Content requirements defined in templates
4. **Human in the Loop**: User selects final post from options
5. **Extensible**: Easy to add new platforms and content types

## Service Architecture

### Service 1: Trend Selector
**Purpose**: Identify suitable food-related trends for content creation
**Input**: Google Trends API
**Output**: Exactly one selected trend per execution (guaranteed)
**Frequency**: Configurable (default: every 2 hours)
**Key Decisions**:
- Fetch fresh trends on each execution
- Compare with recently used trends to avoid repetition
- Filter non-food trends using configurable keyword list
- **Always returns exactly one trend** using fallback strategies

**Fallback Strategies** (in order of preference):
1. **Primary**: Select highest-scoring unused food trend
2. **Secondary**: If no unused food trends, select highest-scoring food trend regardless of recent use
3. **Tertiary**: If no food trends at all, select highest-scoring trend from any category
4. **Emergency**: If Google Trends API fails, use pre-defined backup trends from configuration

**Quality Degradation Awareness**:
- System tracks which fallback strategy was used
- Lower-quality selections may trigger alerts or different handling
- Historical analysis to improve trend selection algorithm

### Service 2: Theme Associator
**Purpose**: Create theme from trend, categorized for content variety control
**Input**: Selected trend from Service 1
**Output**: Theme with category assignment
**Process**: 
1. **AI Analysis**: Determine which configured category the trend best fits
2. **Category Deduplication**: Check if category used recently (configurable timeframe)
3. **Theme Creation**: AI creates appropriate theme based on trend and category
4. **Output**: Theme with category metadata

**Simple Configuration**:
```yaml
# categories.yaml
categories:
  - cooking_techniques
  - kitchen_tools
  - ingredients
  - recipes
  - food_science
  - cultural_foods
```

**Category Deduplication**:
- `MIN_HOURS_BETWEEN_CATEGORY`: Don't repeat same category within X hours (default: 12)
- If preferred category used recently, use next best fitting category
- Track category usage for rotation awareness

**Output Example**:
```json
{
  "trend": "air fryer recipes",
  "theme": "Air Fryer Cooking",
  "category": "cooking_techniques",
  "alternative_categories": ["kitchen_tools", "recipes"]
}
```

**Output Structure**:
- Multiple content options (configurable count, default: 3)
- Each option includes: topic, fact, platform-specific formatting
- Quality scores for each option
- User selects single option for posting

### Service 3: Content Generator
**Purpose**: Create multiple content options from selected theme using templates
**Input**: Theme with category from Service 2
**Output**: Multiple (configurable) content options for user selection
**Components**:
1. **Template Engine**: Uses YAML templates to define content requirements
2. **Content Creator**: Generates multiple variations based on templates
3. **Content Reviewer**: Ensures safety, quality, and template compliance

**Template System**:
```yaml
# content_template.yaml
requirements:
  topic_length: "≤3 words"
  fact_style: "Did you know?"
  tone: "engaging, educational, fun"
  platforms:
    - name: "pinterest"
      character_limit: 500
      hashtag_count: 5-10
    - name: "instagram"
      character_limit: 2200
      hashtag_count: 10-30
  variations: 3  # Number of options to generate
```

**Output Structure**:
- Multiple content options (configurable count, default: 3)
- Each option includes: topic, fact, platform-specific formatting
- Quality scores for each option
- User selects single option for posting

### Service 4: Visual Generator
**Purpose**: Create visual assets for selected content
**Input**: User-selected content from Service 3
**Output**: Visual assets ready for posting
**Technology**: AI image generation (OpenRouter with models like DALL-E, Stable Diffusion, Midjourney)
**Components**:
1. **Prompt Engineer**: Creates detailed image prompts from content
2. **Image Generator**: Uses AI models to create images
3. **Visual QA**: Validates image quality and relevance

### Service 5: Content Selector (Human)
**Purpose**: Choose final post from generated options
**Input**: Multiple content options from Service 3
**Output**: Single selected content for posting
**Interface**: Simple web interface or CLI for selection
**Decision Support**:
- Shows all generated options with quality scores
- Allows preview of content with visual assets
- Records selection reason for improvement

## Data Flow
```
Google Trends API (with fallback to configured trends)
    ↓
[Service 1: Trend Selector] → Exactly One Trend (guaranteed)
    ↓
[Service 2: Theme Associator] → Unique Food Theme (deduplicated)
    ↓
[Service 3: Content Generator] → Multiple Content Options (configurable)
    ↓
[Service 4: Content Selector] → User selects single option
    ↓  
[Service 5: Visual Generator] → Visual assets for selected content
    ↓
[Service 6: Scheduler] → Multi-platform posts
```

## Configuration Boundaries

### Category Configuration
- `CATEGORY_LIST`: Available categories (default: cooking_techniques,kitchen_tools,ingredients,recipes)
- `MIN_HOURS_BETWEEN_CATEGORY`: Don't repeat category within X hours (default: 12)
- `CATEGORY_ROTATION_ENABLED`: Ensure category variety (default: true)
- `CATEGORY_IDENTIFICATION_MODEL`: AI model for category detection

### Platform Configuration
- `PLATFORMS_ENABLED`: Which platforms to post to
- `PLATFORM_SCHEDULES`: Optimal posting times per platform
- `CROSS_POST_DELAY`: Time between posting to different platforms

### Visual Generation
- `IMAGE_MODELS`: Prioritized list of AI image models
- `IMAGE_DIMENSIONS`: Platform-specific image sizes
- `QUALITY_THRESHOLD`: Minimum image quality score

## Selection Process Architecture

### User Interface Options
1. **Web Dashboard**: View options, preview, select
2. **CLI Interface**: List options, select by ID
3. **API Endpoint**: Programmatic selection

### Selection Workflow
```
1. Content Generator creates N options
2. Options displayed with scores and previews
3. User reviews and selects one
4. Selection triggers Visual Generator
5. Selected content moves to Scheduler
```

## Extensibility Patterns

### Adding New Platforms
1. Add platform template
2. Configure scheduler for new platform
3. Update content templates to include platform

### Adding Content Types
1. Create new content template
2. Update Trend Selector filters if needed
3. Configure Content Generator to use new template

### Scaling Options Generation
1. Increase `CONTENT_VARIATIONS` for more options
2. Parallel content generation
3. A/B testing of different templates

## Monitoring & Analytics

### Content Generation Metrics
- Option generation success rate
- User selection patterns
- Quality score distribution

### Platform Performance
- Engagement rates per platform
- Optimal posting times analysis
- Cross-platform performance comparison

### Improvement Loop
- Track which options users select
- Use feedback to improve templates
- A/B test template variations

## Deployment Strategy

### Environment Configuration
- Development: Local selection interface, mock platforms
- Staging: Real platforms with test accounts
- Production: Full platform integration, monitoring

### Selection Interface Deployment
- Simple web app for user selection
- Can run locally or as microservice
- Secure access for authorized users

## Status
Proposed

## Date
2025-05-30