"""Service managing astronaut health profiles and medical histories."""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from ..repositories.health_profile_repository import HealthProfileRepository
from ..schemas.health_profile import (
    AstronautHealthProfile,
    BasicInformation,
    MedicalHistory,
    MedicationRecord,
    PsychologicalProfile,
    CognitiveProfile,
    PhysicalFitnessProfile,
    HealthEvent
)

class HealthProfileService:
    """Service handling astronaut profile queries and verification."""

    def __init__(self, repository: Optional[HealthProfileRepository] = None):
        self.repository = repository or HealthProfileRepository()

    def get_or_create_profile(self, astronaut_id: str) -> AstronautHealthProfile:
        """Fetch profile or initialize nominal profile if not present."""
        existing = self.repository.get_profile(astronaut_id)
        if existing:
            return existing
        nominal_profile = self.generate_nominal_profile(astronaut_id)
        return self.repository.save_profile(nominal_profile)

    def save_profile(self, profile: AstronautHealthProfile) -> AstronautHealthProfile:
        """Save updated profile to persistence layer."""
        return self.repository.save_profile(profile)

    def record_health_event(self, event: HealthEvent) -> HealthEvent:
        """Persist health event with chronological integrity."""
        return self.repository.record_event(event)

    def get_recent_health_events(self, astronaut_id: str, limit: int = 10) -> List[HealthEvent]:
        """Query recent health events for an astronaut."""
        return self.repository.get_recent_events(astronaut_id, limit=limit)

    def generate_nominal_profile(self, astronaut_id: str) -> AstronautHealthProfile:
        """Generate verified nominal operational profile for spaceflight candidate."""
        basic = BasicInformation(
            astronaut_id=astronaut_id,
            age=38,
            height_cm=180.0,
            weight_kg=78.5,
            body_fat_percentage=14.5,
            blood_type="O_POS"
        )
        med_history = MedicalHistory(
            cardiovascular_history=["Normotensive, no structural heart disease", "Sinus rhythm"],
            respiratory_history=["Clear lung fields, FEV1/FVC nominal"],
            previous_injuries=["Right clavicle fracture (resolved, 2018)"],
            previous_surgeries=["Appendectomy (laparoscopic, 2012)"],
            allergies=[],
            medical_constraints=["Strict hydration schedule during EVA"]
        )
        medications = [
            MedicationRecord(
                medication_id="MED-001",
                medication_name="Multivitamin + Vitamin D3",
                dosage="1 tablet (2000 IU D3)",
                route="oral",
                administration_schedule="Daily with morning meal",
                start_date="2026-01-01",
                verification_status="verified_flight_surgeon"
            )
        ]
        psych = PsychologicalProfile(
            stress_baseline="nominal",
            anxiety_baseline="low",
            mood_stability_index=0.92,
            sleep_quality_index=8.0,
            confinement_adaptation_score=88.5,
            coping_strategies=["Aerobic exercise", "Structured downtime", "Active mindfulness"]
        )
        cog = CognitiveProfile(
            attention_score=94.0,
            reaction_time_ms=225.0,
            working_memory_capacity=91.0,
            concentration_index=0.93,
            cognitive_workload_index=3.2
        )
        fitness = PhysicalFitnessProfile(
            vo2_max_ml_kg_min=52.4,
            resting_heart_rate_bpm=58.0,
            endurance_rating="high",
            weekly_exercise_hours=12.0,
            mobility_score=95.0,
            muscle_performance_recovery_rate="rapid"
        )
        return AstronautHealthProfile(
            astronaut_id=astronaut_id,
            basic_info=basic,
            medical_history=med_history,
            medications=medications,
            psychological_profile=psych,
            cognitive_profile=cog,
            physical_fitness=fitness,
            recent_health_events=[]
        )
