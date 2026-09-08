# Architectural Boundary: V1 Compatibility Layer vs. V2 Production Architecture

---

## 1. V1 Protection Freeze

The V1 system represents a stable baseline implementation with verified workflows. Under executive directive:
- **No changes to V1 endpoints**: `/api/v1/auth`, `/api/v1/satellite`, `/api/v1/drone`, `/api/v1/parcel` remain strictly intact.
- **No changes to V1 models**: `app/models/parcel.py` (`parcels` table) and `app/models/user.py` (`users` table) remain unchanged. V2 models will never implicitly mutate or alter V1 tables.
- **No changes to V1 schemas**: `app/schemas/auth.py`, `app/schemas/parcel.py` remain preserved for V1 clients.
- **No changes to V1 services**: `app/services/ai/sam_engine.py`, `app/services/gis/vector_service.py`, `app/services/ulpin_generator.py` remain the frozen fallback layer.

## 2. V2 Target Architecture

V2 is isolated under dedicated directories:
- **Routes**: `app/api/v2/`
- **Domain Services**: `app/services/v2/`
- **Models**: `app/models/v2/`
- **Schemas**: `app/schemas/v2/`
- **Integrations**: `app/integrations/` / `app/services/v2/integrations/`

## 3. Database Separation
- **V1 Tables**:
  - `users`: Authentication and surveyor user profiles.
  - `parcels`: V1 saved parcels (`geom`, `ulpin`, `area_sqm`, `perimeter_m`, `land_use_type`, `owner_name`).
- **V2 Tables**:
  - `processing_jobs`: Durable job lifecycle (`queued`, `running`, `succeeded`, `failed`, `cancelled`).
  - Upcoming: `v2_projects`, `v2_surveys`, `v2_survey_units`, `v2_datasets`, `v2_validation_issues`, `v2_cadastral_features`.

## 4. Shared Utilities Policy
V2 may only reuse pure, side-effect-free utility functions after verifying that reuse cannot alter V1 behavior. If any modification is needed for V2, a dedicated V2 implementation must be authored in `app/services/v2/`.
