"""Unit tests for Astronaut Health Profile schemas, persistence, and verification."""
import pytest
from pydantic import ValidationError
from personal_health.schemas.health_profile import (
    AstronautHealthProfile,
    BasicInformation,
    MedicalHistory,
    HealthEvent
)
from personal_health.services.health_profile_service import HealthProfileService
from personal_health.repositories.health_profile_repository import HealthProfileRepository

def test_basic_information_valid():
    """Verify nominal BMI computation and validation boundaries."""
    info = BasicInformation(
        astronaut_id="AST-001",
        age=40,
        height_cm=180.0,
        weight_kg=81.0
    )
    assert info.bmi == 25.0
    assert info.astronaut_id == "AST-001"

def test_basic_information_invalid_bounds():
    """Reject unphysical heights, weights, or negative ages."""
    with pytest.raises(ValidationError):
        BasicInformation(
            astronaut_id="AST-001",
            age=10,
            height_cm=180.0,
            weight_kg=80.0
        )
    with pytest.raises(ValidationError):
        BasicInformation(
            astronaut_id="AST-001",
            height_cm=50.0,
            weight_kg=80.0
        )

def test_health_profile_service_persistence(sample_health_profile):
    """Verify profile round-trip storage and retrieval."""
    repo = HealthProfileRepository()
    svc = HealthProfileService(repository=repo)

    saved = svc.save_profile(sample_health_profile)
    assert saved.astronaut_id == "AST-TEST-01"

    retrieved = svc.get_or_create_profile("AST-TEST-01")
    assert retrieved is not None
    assert retrieved.astronaut_id == "AST-TEST-01"
    assert retrieved.basic_info.height_cm == 178.0

def test_health_profile_nominal_generation():
    """Verify generation of default nominal flight profile."""
    repo = HealthProfileRepository()
    svc = HealthProfileService(repository=repo)

    profile = svc.get_or_create_profile("AST-NOMINAL-99")
    assert profile.astronaut_id == "AST-NOMINAL-99"
    assert profile.physical_fitness.vo2_max_ml_kg_min == 52.4
    assert len(profile.medications) >= 1
