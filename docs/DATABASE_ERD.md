# 🗄️ Database Entity Relationship Diagram (ERD)

> **Versión:** v2.1.0 (Planificación)
> **Última actualización:** 7 de Enero de 2026
> **Base de datos:** PostgreSQL 15+

---

## 📊 Diagrama Completo

```mermaid
erDiagram
    %% ========================================
    %% SHARED DOMAIN
    %% ========================================

    countries {
        CHAR(2) code PK "ISO 3166-1 alpha-2"
        VARCHAR(100) name_en
        VARCHAR(100) name_es
        BOOLEAN active
    }

    country_adjacencies {
        CHAR(2) country_code_1 PK,FK
        CHAR(2) country_code_2 PK,FK
    }

    %% ========================================
    %% USER MODULE (v1.0.0 - v1.12.1)
    %% ========================================

    users {
        UUID id PK
        VARCHAR(50) first_name
        VARCHAR(50) last_name
        VARCHAR(255) email UK
        VARCHAR(255) password
        FLOAT handicap "nullable"
        TIMESTAMP handicap_updated_at "nullable"
        BOOLEAN email_verified
        VARCHAR(255) verification_token "nullable"
        VARCHAR(255) password_reset_token "nullable - v1.11.0"
        TIMESTAMP password_reset_expires_at "nullable - v1.11.0"
        CHAR(2) country_code FK "nullable"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    refresh_tokens {
        UUID id PK
        UUID user_id FK
        VARCHAR(64) token_hash UK "SHA256"
        TIMESTAMP expires_at
        BOOLEAN revoked
        TIMESTAMP created_at
        TIMESTAMP revoked_at "nullable"
    }

    %% ========================================
    %% ROLES & PERMISSIONS (v2.1.0 - NEW)
    %% ========================================

    roles {
        UUID id PK
        VARCHAR(50) name UK "ADMIN, CREATOR, PLAYER"
        VARCHAR(255) description
        TIMESTAMP created_at
    }

    user_roles {
        UUID user_id PK,FK
        UUID role_id PK,FK
        TIMESTAMP assigned_at
    }

    %% ========================================
    %% GOLF COURSES (v2.1.0 - NEW)
    %% ========================================

    golf_courses {
        UUID id PK
        VARCHAR(200) name
        CHAR(2) country_code FK
        VARCHAR(20) course_type "STANDARD_18 | PITCH_AND_PUTT | EXECUTIVE"
        INT number_of_holes "9 or 18"
        VARCHAR(20) approval_status "PENDING_APPROVAL | APPROVED | REJECTED"
        UUID creator_id FK "Usuario que lo creó"
        UUID approved_by FK "nullable - Admin que aprobó"
        TIMESTAMP approved_at "nullable"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    tees {
        UUID id PK
        UUID golf_course_id FK
        VARCHAR(50) identifier "60 | Blancas | Championship | etc"
        VARCHAR(30) category "CHAMPIONSHIP_MALE | AMATEUR_MALE | etc"
        FLOAT slope_rating "55-155"
        FLOAT course_rating
        VARCHAR(10) gender "MALE | FEMALE | UNISEX"
        TIMESTAMP created_at
    }

    holes {
        UUID id PK
        UUID golf_course_id FK
        INT hole_number "1-18"
        INT par "3-6"
        INT stroke_index "1-18, unique per course"
        TIMESTAMP created_at
    }

    %% ========================================
    %% COMPETITION MODULE (v1.3.0 - v1.7.0)
    %% ========================================

    competitions {
        UUID id PK
        UUID creator_id FK
        VARCHAR(200) name
        DATE start_date
        DATE end_date
        CHAR(2) country_code FK
        CHAR(2) secondary_country_code FK "nullable"
        CHAR(2) tertiary_country_code FK "nullable"
        VARCHAR(100) team_1_name
        VARCHAR(100) team_2_name
        VARCHAR(20) handicap_type "SCRATCH | PERCENTAGE"
        INT handicap_value "nullable - 90/95/100"
        INT max_players
        VARCHAR(20) team_assignment "MANUAL | AUTOMATIC"
        VARCHAR(20) status "DRAFT | ACTIVE | CLOSED | IN_PROGRESS | COMPLETED | CANCELLED"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    enrollments {
        UUID id PK
        UUID competition_id FK
        UUID user_id FK
        VARCHAR(20) status "REQUESTED | INVITED | APPROVED | REJECTED | CANCELLED | WITHDRAWN"
        VARCHAR(10) team_id "nullable - team_1 or team_2"
        DECIMAL(4_1) custom_handicap "nullable - override"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    %% ========================================
    %% ROUNDS & MATCHES (v2.1.0 - NEW)
    %% ========================================

    rounds {
        UUID id PK
        UUID competition_id FK
        UUID golf_course_id FK
        DATE date
        VARCHAR(20) session_type "MORNING | AFTERNOON | FULL_DAY"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    matches {
        UUID id PK
        UUID round_id FK
        VARCHAR(20) format "FOURBALL | FOURSOMES | SINGLES | GREENSOME"
        VARCHAR(20) status "SCHEDULED | IN_PROGRESS | COMPLETED | CANCELLED | WALKOVER_TEAM_A | WALKOVER_TEAM_B"
        INT starting_hole "1-18 para shotgun start"
        UUID team_a_player_1_id FK
        UUID team_a_player_1_tee_id FK
        INT team_a_player_1_playing_handicap "Pre-calculado WHS"
        UUID team_a_player_2_id FK "nullable para SINGLES"
        UUID team_a_player_2_tee_id FK "nullable"
        INT team_a_player_2_playing_handicap "nullable"
        UUID team_b_player_1_id FK
        UUID team_b_player_1_tee_id FK
        INT team_b_player_1_playing_handicap
        UUID team_b_player_2_id FK "nullable para SINGLES"
        UUID team_b_player_2_tee_id FK "nullable"
        INT team_b_player_2_playing_handicap "nullable"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    %% ========================================
    %% INVITATIONS (v2.1.0 - NEW)
    %% ========================================

    invitations {
        UUID id PK
        UUID competition_id FK
        UUID inviter_id FK "Creator que invita"
        VARCHAR(255) invitee_email
        UUID invitee_user_id FK "nullable si no registrado"
        VARCHAR(20) status "PENDING | ACCEPTED | REJECTED | EXPIRED"
        VARCHAR(255) token UK "256-bit secure token"
        TEXT personal_message "nullable"
        TIMESTAMP expires_at "7 días"
        TIMESTAMP responded_at "nullable"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    %% ========================================
    %% LIVE SCORING (v2.1.0 - NEW)
    %% ========================================

    hole_scores {
        UUID id PK
        UUID match_id FK
        INT hole_number "1-18"
        UUID player_id FK
        INT gross_score "Golpes brutos"
        INT net_score "Golpes netos calculado"
        INT strokes_received "Golpes recibidos por handicap"
        VARCHAR(20) status "DRAFT | SUBMITTED | VALIDATED | DISPUTED"
        TIMESTAMP submitted_at "nullable"
        TIMESTAMP validated_at "nullable"
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    %% ========================================
    %% RELATIONSHIPS
    %% ========================================

    %% Shared Domain
    countries ||--o{ country_adjacencies : "adjacent_to"
    countries ||--o{ users : "nationality"
    countries ||--o{ competitions : "location"
    countries ||--o{ golf_courses : "location"

    %% User Module
    users ||--o{ refresh_tokens : "has"
    users ||--o{ competitions : "creates"
    users ||--o{ enrollments : "enrolls_in"
    users ||--o{ user_roles : "has_roles"
    users ||--o{ golf_courses : "creates (pending)"
    users ||--o{ golf_courses : "approves (admin)"
    users ||--o{ invitations : "invites"
    users ||--o{ invitations : "invited"
    users ||--o{ hole_scores : "records"

    %% Roles
    roles ||--o{ user_roles : "assigned_to"

    %% Golf Courses
    golf_courses ||--o{ tees : "has"
    golf_courses ||--o{ holes : "has"
    golf_courses ||--o{ rounds : "used_in"
    tees ||--o{ matches : "player_uses (4x)"

    %% Competition Module
    competitions ||--o{ enrollments : "has"
    competitions ||--o{ rounds : "has"
    competitions ||--o{ invitations : "has"

    %% Rounds & Matches
    rounds ||--o{ matches : "has"
    matches ||--o{ hole_scores : "scored_in"
```

---

## 📋 Tablas Actuales (v1.12.1)

| Tabla | Registros Típicos | Módulo | Versión |
|-------|-------------------|--------|---------|
| `countries` | 166 | Shared | v1.0.0 |
| `country_adjacencies` | 614 | Shared | v1.0.0 |
| `users` | 100-10,000+ | User | v1.0.0 |
| `refresh_tokens` | 100-50,000 | User | v1.8.0 |
| `competitions` | 10-1,000 | Competition | v1.3.0 |
| `enrollments` | 200-50,000 | Competition | v1.3.0 |

**Total tablas actuales:** 6

---

## 🆕 Tablas Nuevas (v2.1.0)

| Tabla | Registros Típicos | Módulo | Sprint |
|-------|-------------------|--------|--------|
| `roles` | 3-10 | User | Sprint 1 |
| `user_roles` | 100-10,000+ | User | Sprint 1 |
| `golf_courses` | 100-5,000 | Golf Courses | Sprint 1 |
| `tees` | 300-25,000 (3-5 por campo) | Golf Courses | Sprint 1 |
| `holes` | 1,800-90,000 (18 por campo) | Golf Courses | Sprint 1 |
| `rounds` | 30-3,000 (3-10 por torneo) | Competition | Sprint 3 |
| `matches` | 100-30,000 (10-30 por round) | Competition | Sprint 3 |
| `invitations` | 500-100,000 | Competition | Sprint 3 |
| `hole_scores` | 5,000-5,000,000 (72 por match singles, 144 fourball) | Scoring | Sprint 4 |

**Total tablas nuevas:** 9

**Total tablas v2.1.0:** 15 tablas

---

## 🔑 Índices Principales

### Índices Actuales
```sql
-- users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_country ON users(country_code);

-- refresh_tokens
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

-- competitions
CREATE INDEX idx_competitions_creator ON competitions(creator_id);
CREATE INDEX idx_competitions_status ON competitions(status);
CREATE INDEX idx_competitions_dates ON competitions(start_date, end_date);

-- enrollments
CREATE INDEX idx_enrollments_competition ON enrollments(competition_id);
CREATE INDEX idx_enrollments_user ON enrollments(user_id);
CREATE INDEX idx_enrollments_status ON enrollments(status);
```

### Índices Nuevos (v2.1.0)
```sql
-- roles & user_roles
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);

-- golf_courses
CREATE INDEX idx_golf_courses_country ON golf_courses(country_code);
CREATE INDEX idx_golf_courses_status ON golf_courses(approval_status);
CREATE INDEX idx_golf_courses_creator ON golf_courses(creator_id);

-- tees
CREATE INDEX idx_tees_course ON tees(golf_course_id);
CREATE INDEX idx_tees_category ON tees(category);

-- holes
CREATE INDEX idx_holes_course ON holes(golf_course_id);
CREATE UNIQUE INDEX idx_holes_course_number ON holes(golf_course_id, hole_number);

-- rounds
CREATE INDEX idx_rounds_competition ON rounds(competition_id);
CREATE INDEX idx_rounds_course ON rounds(golf_course_id);
CREATE INDEX idx_rounds_date ON rounds(date);

-- matches
CREATE INDEX idx_matches_round ON matches(round_id);
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_players ON matches(team_a_player_1_id, team_a_player_2_id, team_b_player_1_id, team_b_player_2_id);

-- invitations
CREATE INDEX idx_invitations_competition ON invitations(competition_id);
CREATE INDEX idx_invitations_email ON invitations(invitee_email);
CREATE INDEX idx_invitations_user ON invitations(invitee_user_id);
CREATE INDEX idx_invitations_status ON invitations(status);
CREATE INDEX idx_invitations_token ON invitations(token);

-- hole_scores
CREATE INDEX idx_hole_scores_match ON hole_scores(match_id);
CREATE INDEX idx_hole_scores_player ON hole_scores(player_id);
CREATE INDEX idx_hole_scores_status ON hole_scores(status);
CREATE UNIQUE INDEX idx_hole_scores_match_hole_player ON hole_scores(match_id, hole_number, player_id);
```

---

## 📐 Estimación de Crecimiento

### Escenario: 1 Competición Típica (20 jugadores, 3 días)

| Tabla | Registros | Cálculo |
|-------|-----------|---------|
| `golf_courses` | +1 | 1 campo |
| `tees` | +4 | 4 tees (60, 56, 52, 47) |
| `holes` | +18 | 18 hoyos |
| `rounds` | +6 | 2 rounds/día x 3 días |
| `matches` | +60 | 10 matches/round x 6 rounds |
| `invitations` | +20 | 20 jugadores invitados |
| `hole_scores` | +2,160 | 60 matches x 18 hoyos x 2 jugadores (singles) |

**Total por competición:** ~2,269 registros

### Escenario: 100 Competiciones Activas

| Tabla | Registros |
|-------|-----------|
| `golf_courses` | 100 |
| `tees` | 400 |
| `holes` | 1,800 |
| `rounds` | 600 |
| `matches` | 6,000 |
| `invitations` | 2,000 |
| `hole_scores` | 216,000 |

**Total estimado:** ~227,000 registros nuevos

---

## 🚀 Estrategia de Optimización

### Particionamiento (Futuro v2.2.0)
```sql
-- Particionar hole_scores por fecha (mensual)
CREATE TABLE hole_scores_2026_01 PARTITION OF hole_scores
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

### Archivado (Futuro v2.2.0)
- Mover `hole_scores` de competiciones completadas a tabla de archivo
- Retención: 2 años en BD activa, 5 años en archivo

### Read Replicas (Futuro v2.2.0)
- Leaderboards consultan read replica
- Escrituras (scoring) en BD principal

---

## 🔗 Referencias

- **ROADMAP.md**: Planificación v2.1.0
- **ADR-025**: Competition Module Evolution
- **Migraciones**: `alembic/versions/`
