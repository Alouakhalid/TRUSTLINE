-- ==============================================================================
-- TRUSTLINE Mission Health & Autonomous Medical Multi-Agent Architecture
-- Migration: 001_initial_schema.sql
-- Namespaces: SQA, PHA, RAA, Chatbot, Platform Shared, Storage Buckets, RLS
-- Standards: NASA-STD-3001, Zero-Hallucination Isolation, RBAC (Astronaut, Doctor, Admin)
-- ==============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 1. SHARED PLATFORM DATA & USER PROFILES
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL CHECK (role IN ('ASTRONAUT', 'MEDICAL_OFFICER', 'ADMINISTRATOR')),
    astronaut_id TEXT, -- NULL for Medical Officer or Administrator unless assigned
    avatar_path TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.astronaut_profiles (
    astronaut_id TEXT PRIMARY KEY,
    user_id UUID REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    full_name TEXT NOT NULL,
    callsign TEXT,
    mission_role TEXT NOT NULL DEFAULT 'MISSION_SPECIALIST',
    flight_duration_days INTEGER NOT NULL DEFAULT 0,
    blood_type TEXT,
    medical_clearance_status TEXT NOT NULL DEFAULT 'NOMINAL' CHECK (medical_clearance_status IN ('NOMINAL', 'RESTRICTED', 'GROUNDED', 'MONITORED')),
    emergency_contact_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.doctor_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    astronaut_id TEXT NOT NULL REFERENCES public.astronaut_profiles(astronaut_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    UNIQUE(doctor_user_id, astronaut_id)
);

-- ==============================================================================
-- 2. SENSOR QUALITY AGENT (SQA) NAMESPACE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.sqa_sessions (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'DEGRADED', 'FAILED')),
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.sqa_sensor_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT REFERENCES public.sqa_sessions(id) ON DELETE CASCADE,
    astronaut_id TEXT NOT NULL,
    sensor_type TEXT NOT NULL CHECK (sensor_type IN ('ECG', 'PPG', 'RESPIRATION', 'SKIN_TEMP', 'RADIATION', 'ACCELEROMETER', 'MULTI_MODAL')),
    packet_count INTEGER NOT NULL DEFAULT 0,
    dropped_packets INTEGER NOT NULL DEFAULT 0,
    snr_db DOUBLE PRECISION,
    motion_artifact_index DOUBLE PRECISION DEFAULT 0.0,
    signal_quality_index DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL DEFAULT 'VALID' CHECK (status IN ('VALID', 'SUSPECT', 'CORRUPT', 'DROPPED', 'CALIBRATING')),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.sqa_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT REFERENCES public.sqa_sessions(id) ON DELETE SET NULL,
    astronaut_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    quality_band TEXT NOT NULL CHECK (quality_band IN ('GREEN', 'YELLOW', 'RED')),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.sqa_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT REFERENCES public.sqa_sessions(id) ON DELETE SET NULL,
    astronaut_id TEXT NOT NULL,
    sensor_type TEXT NOT NULL,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MODERATE', 'CRITICAL', 'FATAL')),
    description TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    resolution_status TEXT NOT NULL DEFAULT 'OPEN' CHECK (resolution_status IN ('OPEN', 'INVESTIGATING', 'SUPPRESSED', 'RESOLVED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.sqa_validation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sensor_report_id UUID REFERENCES public.sqa_sensor_reports(id) ON DELETE CASCADE,
    validator TEXT NOT NULL,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    validation_notes TEXT,
    validated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.sqa_agent_memory (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('BASELINE', 'NOISE_PROFILE', 'DRIFT_RECORD', 'CALIBRATION')),
    memory_key TEXT NOT NULL,
    memory_value JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    verification_status TEXT NOT NULL DEFAULT 'LIVE' CHECK (verification_status IN ('LIVE', 'CONFIRMED', 'QUARANTINED', 'ARCHIVED')),
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(astronaut_id, memory_key, is_demo)
);

-- ==============================================================================
-- 3. PHYSIOLOGICAL HEALTH AGENT (PHA) NAMESPACE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.pha_sessions (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'SUSPENDED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.pha_health_assessments (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES public.pha_sessions(id) ON DELETE SET NULL,
    astronaut_id TEXT NOT NULL,
    cardiovascular_status TEXT NOT NULL DEFAULT 'NOMINAL',
    metabolic_status TEXT NOT NULL DEFAULT 'NOMINAL',
    neuromuscular_status TEXT NOT NULL DEFAULT 'NOMINAL',
    thermal_status TEXT NOT NULL DEFAULT 'NOMINAL',
    overall_status TEXT NOT NULL DEFAULT 'NOMINAL',
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    assessment_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.pha_personal_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    astronaut_id TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    baseline_mean DOUBLE PRECISION NOT NULL,
    baseline_std DOUBLE PRECISION NOT NULL,
    baseline_range_low DOUBLE PRECISION NOT NULL,
    baseline_range_high DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    established_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(astronaut_id, parameter_name)
);

CREATE TABLE IF NOT EXISTS public.pha_health_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT REFERENCES public.pha_sessions(id) ON DELETE SET NULL,
    astronaut_id TEXT NOT NULL,
    observation_type TEXT NOT NULL,
    value_json JSONB NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'ALERT', 'CRITICAL')),
    clinical_significance TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.pha_evidence_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id TEXT REFERENCES public.pha_health_assessments(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    description TEXT NOT NULL,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.pha_agent_memory (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('VITALS_TREND', 'STRESS_INDICATOR', 'CIRCADIAN_PHASE', 'MEDICAL_FLAG')),
    memory_key TEXT NOT NULL,
    memory_value JSONB NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'LIVE' CHECK (verification_status IN ('LIVE', 'CONFIRMED', 'QUARANTINED', 'ARCHIVED')),
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(astronaut_id, memory_key, is_demo)
);

-- ==============================================================================
-- 4. RADIATION ADAPTATION AGENT (RAA) NAMESPACE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.raa_sessions (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'WARNING', 'SHELTER_IN_PLACE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.raa_risk_assessments (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES public.raa_sessions(id) ON DELETE SET NULL,
    astronaut_id TEXT NOT NULL,
    spe_alert_level TEXT NOT NULL DEFAULT 'NOMINAL' CHECK (spe_alert_level IN ('NOMINAL', 'ADVISORY', 'WATCH', 'WARNING', 'EMERGENCY')),
    acute_risk_level TEXT NOT NULL DEFAULT 'GREEN' CHECK (acute_risk_level IN ('GREEN', 'YELLOW', 'ORANGE', 'RED')),
    cumulative_risk_level TEXT NOT NULL DEFAULT 'GREEN' CHECK (cumulative_risk_level IN ('GREEN', 'YELLOW', 'ORANGE', 'RED')),
    recommended_action TEXT NOT NULL DEFAULT 'CONTINUE_NOMINAL_ACTIVITIES',
    rationale TEXT NOT NULL,
    assessment_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.raa_risk_factors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id TEXT REFERENCES public.raa_risk_assessments(id) ON DELETE CASCADE,
    astronaut_id TEXT NOT NULL,
    factor_type TEXT NOT NULL,
    factor_value DOUBLE PRECISION NOT NULL,
    risk_weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.raa_decision_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id TEXT REFERENCES public.raa_risk_assessments(id) ON DELETE CASCADE,
    decision_type TEXT NOT NULL,
    recommended_by TEXT NOT NULL DEFAULT 'RAA',
    override_by TEXT,
    status TEXT NOT NULL DEFAULT 'RECOMMENDED' CHECK (status IN ('RECOMMENDED', 'ACCEPTED', 'OVERRIDDEN', 'SUPERSEDED')),
    rationale TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.raa_evidence_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id TEXT REFERENCES public.raa_risk_assessments(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    description TEXT NOT NULL,
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.raa_agent_memory (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('CUMULATIVE_DOSE', 'SPE_PROFILE', 'SHIELDING_EVAL', 'TISSUE_RISK')),
    memory_key TEXT NOT NULL,
    memory_value JSONB NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'LIVE' CHECK (verification_status IN ('LIVE', 'CONFIRMED', 'QUARANTINED', 'ARCHIVED')),
    provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(astronaut_id, memory_key, is_demo)
);

-- ==============================================================================
-- 5. CHATBOT NAMESPACE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id TEXT PRIMARY KEY,
    user_id UUID,
    astronaut_id TEXT, -- Invariant: NEVER default to AST-001 if unknown
    title TEXT NOT NULL DEFAULT 'Mission Health Briefing',
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED', 'CLOSED')),
    summary_ref TEXT,
    memory_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    sender TEXT NOT NULL CHECK (sender IN ('USER', 'AGENT', 'SYSTEM')),
    content TEXT NOT NULL,
    agent TEXT, -- e.g. 'supervisor', 'groq-cloud', 'ollama-edge'
    processing_status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (processing_status IN ('RECEIVED', 'PROCESSING', 'COMPLETED', 'FAILED')),
    citations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.chat_short_term_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    astronaut_id TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value JSONB NOT NULL,
    ttl_expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.chat_long_term_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    astronaut_id TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value JSONB NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('PREFERENCE', 'ALLERGY', 'MEDICAL_HISTORY', 'PSYCHOSOCIAL', 'HABIT')),
    importance_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(astronaut_id, memory_key)
);

CREATE TABLE IF NOT EXISTS public.chat_memory_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    astronaut_id TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.chat_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    message_id TEXT REFERENCES public.chat_messages(id) ON DELETE SET NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    ocr_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (ocr_status IN ('PENDING', 'PROCESSED', 'FAILED', 'BYPASSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.chat_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT NOT NULL REFERENCES public.chat_messages(id) ON DELETE CASCADE,
    user_id UUID,
    rating INTEGER NOT NULL CHECK (rating IN (1, -1)),
    feedback_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- ==============================================================================
-- 6. MEDICAL DOCUMENTS & EVIDENCE REGISTRY (WITH QUARANTINE GUARD)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.medical_documents (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    uploaded_by_user_id UUID,
    title TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'LAB_REPORT' CHECK (document_type IN ('LAB_REPORT', 'CLINICAL_NOTE', 'IMAGING_REPORT', 'GENOMIC', 'MISSION_CLEARANCE', 'OTHER')),
    storage_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (processing_status IN ('PENDING', 'PROCESSING', 'EXTRACTED', 'ERROR', 'QUARANTINED', 'VERIFIED')),
    error_message TEXT,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.medical_document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT NOT NULL REFERENCES public.medical_documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    storage_path TEXT NOT NULL,
    changes_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.medical_extracted_text (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id TEXT NOT NULL REFERENCES public.medical_documents(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    ocr_confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    extraction_method TEXT NOT NULL CHECK (extraction_method IN ('GROQ_VISION', 'PYMUPDF', 'DOCX', 'FALLBACK')),
    page_count INTEGER NOT NULL DEFAULT 1,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.medical_evidence (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES public.medical_documents(id) ON DELETE SET NULL,
    astronaut_id TEXT NOT NULL,
    clinical_domain TEXT NOT NULL CHECK (clinical_domain IN ('HEMATOLOGY', 'METABOLIC', 'RENAL', 'CARDIOVASCULAR', 'RADIATION', 'GENERAL')),
    parameter_name TEXT NOT NULL,
    parameter_value DOUBLE PRECISION,
    value_text TEXT,
    unit TEXT,
    reference_range_low DOUBLE PRECISION,
    reference_range_high DOUBLE PRECISION,
    is_abnormal BOOLEAN NOT NULL DEFAULT FALSE,
    -- Invariant: Medical document evidence is ALWAYS historical evidence, never live telemetry.
    -- Verification status must start QUARANTINED or PENDING until flight surgeon validates.
    verification_status TEXT NOT NULL DEFAULT 'QUARANTINED' CHECK (verification_status IN ('PENDING', 'QUARANTINED', 'VERIFIED', 'REJECTED')),
    verified_by_doctor_id UUID,
    verified_at TIMESTAMPTZ,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- ==============================================================================
-- 7. TELEMETRY, ASSESSMENTS & SYSTEM AUDIT
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.telemetry_packets (
    id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL,
    astronaut_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    sensor_type TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    sample_rate_hz DOUBLE PRECISION NOT NULL,
    channels_json JSONB NOT NULL,
    checksum_crc32 BIGINT NOT NULL,
    checksum_ok BOOLEAN NOT NULL DEFAULT TRUE,
    sequence_state TEXT NOT NULL DEFAULT 'NOMINAL',
    timestamp_epoch_ms BIGINT NOT NULL,
    hardware_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    received_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE(packet_id, astronaut_id, is_demo)
);

CREATE TABLE IF NOT EXISTS public.radiation_packets (
    id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL,
    timestamp_epoch_ms BIGINT NOT NULL,
    dose_rate_microgy_h DOUBLE PRECISION NOT NULL,
    equivalent_dose_rate_msv_h DOUBLE PRECISION NOT NULL,
    cumulative_mission_dose_msv DOUBLE PRECISION NOT NULL,
    spe_active BOOLEAN NOT NULL DEFAULT FALSE,
    spe_flux_pfu DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    shielding_thickness_g_cm2 DOUBLE PRECISION NOT NULL DEFAULT 20.0,
    alert_level TEXT NOT NULL DEFAULT 'NOMINAL',
    received_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE(packet_id, is_demo)
);

CREATE TABLE IF NOT EXISTS public.assessments (
    id TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    session_id TEXT,
    workflow_id TEXT,
    completion_status TEXT NOT NULL,
    overall_risk TEXT NOT NULL,
    overall_confidence TEXT,
    astronaut_response TEXT NOT NULL,
    assessment_json JSONB NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.system_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    component TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.agent_execution_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT,
    workflow_id TEXT,
    agent_name TEXT NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    duration_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'TIMED_OUT', 'SKIPPED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.provider_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    reason TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.application_settings (
    key TEXT PRIMARY KEY,
    value_json JSONB NOT NULL,
    description TEXT,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.sync_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'IN_FLIGHT', 'DELIVERED', 'FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.sync_checkpoints (
    id TEXT PRIMARY KEY,
    partition TEXT NOT NULL,
    last_event_id TEXT,
    last_success_at TIMESTAMPTZ,
    events_processed INTEGER NOT NULL DEFAULT 0,
    delivered_total INTEGER NOT NULL DEFAULT 0,
    failed_total INTEGER NOT NULL DEFAULT 0,
    provider TEXT,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(partition, is_demo)
);

-- ==============================================================================
-- 8. INDEXES FOR HIGH-THROUGHPUT MISSION QUERYING
-- ==============================================================================

CREATE INDEX IF NOT EXISTS idx_telemetry_astronaut_sensor ON public.telemetry_packets(astronaut_id, sensor_type, timestamp_epoch_ms DESC);
CREATE INDEX IF NOT EXISTS idx_radiation_timestamp ON public.radiation_packets(timestamp_epoch_ms DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON public.chat_messages(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_astronaut ON public.chat_sessions(astronaut_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessments_astronaut ON public.assessments(astronaut_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sqa_reports_astronaut ON public.sqa_sensor_reports(astronaut_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pha_assessments_astronaut ON public.pha_health_assessments(astronaut_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_raa_assessments_astronaut ON public.raa_risk_assessments(astronaut_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_medical_evidence_astronaut ON public.medical_evidence(astronaut_id, verification_status);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON public.audit_logs(resource_type, resource_id);

-- ==============================================================================
-- 9. ROW LEVEL SECURITY (RLS) & ACCESS CONTROL
-- ==============================================================================

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.astronaut_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctor_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sqa_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sqa_sensor_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sqa_quality_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sqa_anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sqa_validation_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sqa_agent_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pha_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pha_health_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pha_personal_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pha_health_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pha_evidence_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pha_agent_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raa_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raa_risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raa_risk_factors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raa_decision_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raa_evidence_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raa_agent_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_short_term_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_long_term_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_memory_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_extracted_text ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telemetry_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radiation_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_execution_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_checkpoints ENABLE ROW LEVEL SECURITY;

-- Helper functions for RLS checks
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS TEXT LANGUAGE sql STABLE AS $$
  SELECT COALESCE(
    (SELECT role FROM public.user_profiles WHERE id = auth.uid()),
    'ASTRONAUT'
  );
$$;

CREATE OR REPLACE FUNCTION public.current_user_astronaut_id()
RETURNS TEXT LANGUAGE sql STABLE AS $$
  SELECT astronaut_id FROM public.user_profiles WHERE id = auth.uid();
$$;

-- RLS Policies: Service role bypasses RLS automatically in Supabase
-- RLS Policy: Users can view their own profile; Doctors & Admins can view all profiles
CREATE POLICY user_profiles_select ON public.user_profiles
    FOR SELECT TO authenticated
    USING (id = auth.uid() OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR'));

CREATE POLICY user_profiles_admin ON public.user_profiles
    FOR ALL TO authenticated
    USING (public.current_user_role() = 'ADMINISTRATOR');

-- RLS Policy: Chat Sessions & Messages
CREATE POLICY chat_sessions_access ON public.chat_sessions
    FOR ALL TO authenticated
    USING (
        user_id = auth.uid()
        OR astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

CREATE POLICY chat_messages_access ON public.chat_messages
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.chat_sessions s
            WHERE s.id = session_id
            AND (s.user_id = auth.uid() OR s.astronaut_id = public.current_user_astronaut_id() OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR'))
        )
    );

-- RLS Policy: Telemetry & Radiation
CREATE POLICY telemetry_packets_select ON public.telemetry_packets
    FOR SELECT TO authenticated
    USING (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

CREATE POLICY radiation_packets_select ON public.radiation_packets
    FOR SELECT TO authenticated
    USING (TRUE); -- Radiation is shared environmental spacecraft telemetry

-- RLS Policy: Assessments
CREATE POLICY assessments_access ON public.assessments
    FOR SELECT TO authenticated
    USING (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

-- RLS Policy: Medical Documents & Evidence
CREATE POLICY medical_documents_access ON public.medical_documents
    FOR SELECT TO authenticated
    USING (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

CREATE POLICY medical_documents_insert ON public.medical_documents
    FOR INSERT TO authenticated
    WITH CHECK (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

CREATE POLICY medical_evidence_access ON public.medical_evidence
    FOR SELECT TO authenticated
    USING (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

CREATE POLICY medical_evidence_update ON public.medical_evidence
    FOR UPDATE TO authenticated
    USING (public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR'));

-- RLS Policy: Agent Namespaces (SQA, PHA, RAA)
CREATE POLICY sqa_access ON public.sqa_sensor_reports
    FOR SELECT TO authenticated
    USING (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

CREATE POLICY pha_access ON public.pha_health_assessments
    FOR SELECT TO authenticated
    USING (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

CREATE POLICY raa_access ON public.raa_risk_assessments
    FOR SELECT TO authenticated
    USING (
        astronaut_id = public.current_user_astronaut_id()
        OR public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR')
    );

-- ==============================================================================
-- 10. SUPABASE STORAGE BUCKETS PROVISIONING
-- ==============================================================================

INSERT INTO storage.buckets (id, name, public)
VALUES 
    ('astronaut-documents', 'astronaut-documents', false),
    ('medical-reports', 'medical-reports', false),
    ('chat-attachments', 'chat-attachments', false),
    ('processed-document-artifacts', 'processed-document-artifacts', false)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: Restrict read and write access to authenticated users
CREATE POLICY storage_astronaut_documents_select ON storage.objects
    FOR SELECT TO authenticated
    USING (bucket_id = 'astronaut-documents');

CREATE POLICY storage_astronaut_documents_insert ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (bucket_id = 'astronaut-documents');

CREATE POLICY storage_chat_attachments_access ON storage.objects
    FOR ALL TO authenticated
    USING (bucket_id = 'chat-attachments');

CREATE POLICY storage_medical_reports_access ON storage.objects
    FOR ALL TO authenticated
    USING (bucket_id IN ('medical-reports', 'processed-document-artifacts') AND public.current_user_role() IN ('MEDICAL_OFFICER', 'ADMINISTRATOR'));
