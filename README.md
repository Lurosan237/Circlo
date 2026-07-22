# Circlo Safety App

A privacy-first safety application that uses verified Safety Circles to help locate missing persons.

## Overview

Circlo organizes trusted contacts into three concentric circles (Inner, Community, Professional) and uses location-aware check requests based on locally stored route data. When someone goes missing, alerts flow outward through verified relationships with multi-person verification requirements.

## Architecture

- **Mobile App**: Flutter with Material 3, Riverpod state management
- **Backend**: Python FastAPI with PostgreSQL
- **Security**: End-to-end encryption (AES-256-GCM), SHA-256 hashing for PII, Row-Level Security

## Project Structure

```
circlo-safety-app/
├── mobile/                 # Flutter mobile application
│   ├── lib/
│   │   ├── core/          # Core services, models, theme
│   │   └── features/      # Feature modules (auth, circles, alerts)
│   └── test/              # Flutter tests
├── backend/               # Python FastAPI backend
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── core/         # Config, database, security
│   │   └── middleware/   # Rate limiting, auth
│   └── tests/            # Backend tests
├── database/             # PostgreSQL schema and RLS policies
└── docker-compose.yml    # Development environment
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Flutter SDK (for mobile development)
- Python 3.12+ (for local backend development)

### Setup

1. Clone the repository
2. Run the setup script:
   ```powershell
   .\scripts\setup.ps1
   ```

Or manually:

```bash
# Start Docker containers
docker-compose up -d

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install Flutter dependencies
cd mobile
flutter pub get
```

### Running Services

- **Backend API**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Mobile tests
cd mobile
flutter test
```

## Security Features

- Phone numbers hashed with SHA-256 before transmission
- All messages encrypted with AES-256-GCM
- Route data stored only locally (never transmitted)
- Row-Level Security in PostgreSQL for data isolation
- JWT authentication with 24-hour expiry
- Rate limiting to prevent abuse

## Safety Circles

- **Inner Circle**: 3-5 family members and close friends
- **Community Circle**: 15-30 trusted neighbors and local contacts
- **Professional Circle**: Local emergency resources and verified professionals

## Alert Flow

1. User triggers alert
2. 2-of-3 Inner Circle members must verify
3. If unresolved after 30 minutes, escalates to Community Circle
4. If unresolved after 2 hours, escalates to Professional Circle
5. All participants notified when resolved

## Development Process

This project was built using a spec-driven workflow: formal requirements and design documents (`.kiro/specs/`) were written first, then used to guide implementation. Requirements were traced through to acceptance criteria and tests.

## License

MIT License - see [LICENSE](LICENSE) for details.
