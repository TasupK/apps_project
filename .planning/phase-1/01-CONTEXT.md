# Phase 1 Context: Mock Data Layer & Monitor Agent

## Domain Boundary
Precision machine parts data management and rule-based shortage detection.

## Locked Implementation Decisions

### Data Storage & Modeling
- **Storage:** SQLite (`buybee.db`) for structured data with JSON support.
- **Modeling:** Pydantic models in `db/models.py` for strict schema enforcement.
- **Seeding:** Hardcoded mock data in `db/seed_data.py` for PoC stability.

### Data Normalization
- **Technical Specs:** Raw text is parsed into structured JSON in the `spec_attributes` field.
- **Attributes Captured:** Inner Diameter, Outer Diameter, Width, Module, Teeth, **Precision Class**, and **Material**.
- **Regex Parsing:** Attributes are extracted using predefined regex patterns in `tools/dimension_extractor.py`.

### Search Strategy (Query Expansion)
- **Synonyms:** Use a static dictionary (`db/aliases.json`) for category-based synonym expansion.
- **Keyword Priority:** **Dimension-First** strategy.
  - Format: `[Synonym] [Dimensions] [Brand]`
  - Example: `Ball Bearing 20x47x14 NSK`
- **MPN Inclusion:** Manufacturer Part Numbers (MPN) are always included as a backup precise search term.

### Monitoring & Events
- **Detection Logic:** `current_stock < safety_stock`.
- **Output:** `shortage_event_{id}.json` containing all metadata, structured attributes, and generated keywords.

## Code Context & Assets
- `db/models.py`: Data schemas.
- `db/database.py`: DB operations.
- `tools/dimension_extractor.py`: Core logic for parsing and keyword generation.
- `agents/monitor_agent.py`: Scans DB and triggers events.

## Canonical Refs
- [.planning/phase-1/PHASE_1_FORMAT_CONTRACT.md](PHASE_1_FORMAT_CONTRACT.md)
- [db/aliases.json](../../db/aliases.json)
