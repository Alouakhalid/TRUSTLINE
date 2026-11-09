"""Structured schemas for astronaut health profiles and records."""
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class BasicInformation(BaseModel):
    """Demographic and core anthropometric measurements."""
    astronaut_id: str = Field(..., min_length=1, description="Unique astronaut identifier")
    date_of_birth: Optional[date] = Field(default=None, description="Date of birth")
    age: Optional[int] = Field(default=None, ge=18, le=80, description="Chronological age")
    height_cm: float = Field(..., gt=100.0, lt=250.0, description="Height in centimeters")
    weight_kg: float = Field(..., gt=30.0, lt=200.0, description="Body mass in kilograms")
    body_fat_percentage: Optional[float] = Field(default=None, ge=3.0, le=50.0)
    blood_type: Optional[str] = Field(default=None)
    profile_created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def bmi(self) -> float:
        """Calculate Body Mass Index (BMI)."""
        height_m = self.height_cm / 100.0
        return round(self.weight_kg / (height_m ** 2), 2)

class MedicalCondition(BaseModel):
    """Historical or active clinical condition."""
    condition_name: str
    diagnosed_date: Optional[str] = None
    status: str = Field(default="resolved")
    clinical_notes: Optional[str] = None

class AllergyRecord(BaseModel):
    """Allergic sensitivity record."""
    allergen: str
    reaction_type: str
    severity: str = Field(default="moderate")

class MedicalHistory(BaseModel):
    """Comprehensive medical history record."""
    previous_conditions: List[MedicalCondition] = Field(default_factory=list)
    cardiovascular_history: List[str] = Field(default_factory=list)
    respiratory_history: List[str] = Field(default_factory=list)
    previous_injuries: List[str] = Field(default_factory=list)
    previous_surgeries: List[str] = Field(default_factory=list)
    allergies: List[AllergyRecord] = Field(default_factory=list)
    medical_constraints: List[str] = Field(default_factory=list)

class MedicationRecord(BaseModel):
    """Active or historical pharmacological prescription."""
    medication_id: str
    medication_name: str
    dosage: str
    route: str = Field(default="oral")
    administration_schedule: str
    start_date: str
    end_date: Optional[str] = None
    notes: Optional[str] = None
    verification_status: str = Field(default="verified_flight_surgeon")

class AssessmentScore(BaseModel):
    """Standardized psychological or cognitive test score."""
    instrument_name: str
    instrument_version: Optional[str] = None
    administered_date: str
    raw_score: float
    normative_percentile: Optional[float] = None
    interpretation: str
    evaluator: str = Field(default="flight_surgeon_protocol")

class PsychologicalProfile(BaseModel):
    """Psychological and behavioral adaptation indicators."""
    stress_baseline: Optional[str] = Field(default="normal")
    anxiety_baseline: Optional[str] = Field(default="low")
    mood_stability_index: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sleep_quality_index: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    confinement_adaptation_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    coping_strategies: List[str] = Field(default_factory=list)
    assessments: List[AssessmentScore] = Field(default_factory=list)

class CognitiveProfile(BaseModel):
    """Cognitive performance and vigilance telemetry."""
    attention_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reaction_time_ms: Optional[float] = Field(default=None, gt=50.0, lt=2000.0)
    working_memory_capacity: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    concentration_index: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    decision_making_speed: Optional[str] = Field(default="normal")
    cognitive_workload_index: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    assessments: List[AssessmentScore] = Field(default_factory=list)

class PhysicalFitnessProfile(BaseModel):
    """Physical conditioning and operational endurance profile."""
    vo2_max_ml_kg_min: Optional[float] = Field(default=None, ge=20.0, le=90.0)
    resting_heart_rate_bpm: Optional[float] = Field(default=None, ge=35.0, le=120.0)
    endurance_rating: Optional[str] = Field(default="high")
    weekly_exercise_hours: Optional[float] = Field(default=None, ge=0.0, le=40.0)
    mobility_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    muscle_performance_recovery_rate: Optional[str] = Field(default="nominal")

class HealthEvent(BaseModel):
    """Historical or operational health event with full provenance."""
    event_id: str
    astronaut_id: str
    event_type: str
    description: str
    severity: str = Field(default="nominal")
    event_time: datetime
    reporting_time: datetime = Field(default_factory=datetime.utcnow)
    ingestion_time: datetime = Field(default_factory=datetime.utcnow)
    provenance_source: str = Field(default="astronaut_telemetry")
    medical_officer_verdict: Optional[str] = None
    follow_up_required: bool = Field(default=False)

class AstronautHealthProfile(BaseModel):
    """Complete aggregated astronaut health profile."""
    astronaut_id: str
    basic_info: BasicInformation
    medical_history: MedicalHistory = Field(default_factory=MedicalHistory)
    medications: List[MedicationRecord] = Field(default_factory=list)
    psychological_profile: PsychologicalProfile = Field(default_factory=PsychologicalProfile)
    cognitive_profile: CognitiveProfile = Field(default_factory=CognitiveProfile)
    physical_fitness: PhysicalFitnessProfile = Field(default_factory=PhysicalFitnessProfile)
    recent_health_events: List[HealthEvent] = Field(default_factory=list)
