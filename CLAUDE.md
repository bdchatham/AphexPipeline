# Documentation Contract for Archon

This repository participates in the **Archon** RAG system. All canonical documentation lives in `.kiro/docs/` and is ingested by Archon for retrieval.

## Documentation Structure

The `.kiro/docs/` directory contains the following files:

- **overview.md**: High-level purpose, features, and getting started guide
- **architecture.md**: System design, components, dependencies, and infrastructure
- **operations.md**: Deployment, monitoring, troubleshooting, and maintenance
- **api.md**: API endpoints, request/response formats, authentication, and error handling
- **data-models.md**: Database schema, data flow, and validation rules
- **faq.md**: Frequently asked questions and common troubleshooting

## Documentation Rules

### 1. Ground in Code
All documentation must be grounded in actual code and infrastructure. Include "Source" sections that reference:
- Source code files
- Infrastructure-as-code files
- Configuration files
- Specs in `.kiro/specs/` if present

### 2. RAG-Friendly Structure
- Keep sections small and focused (400-800 tokens)
- Use clear headings and subheadings
- Write in direct, factual language
- Prefer lists and step-by-step instructions

### 3. Maintain Provenance
Always cite where information comes from. Never document behavior you cannot verify in the codebase.

### 4. Avoid Duplication
Link to other documentation rather than repeating information. Keep a single source of truth.

### 5. Keep Current
Update documentation in the same PR as code changes. Remove or correct stale information immediately.

## Security

- Never include secrets, tokens, or credentials in documentation
- Mark security-sensitive details with TODOs and request human review

## Archon Ingestion

Archon ingests all Markdown files from `.kiro/docs/` in this repository. These docs are used for RAG-based queries about the system.
