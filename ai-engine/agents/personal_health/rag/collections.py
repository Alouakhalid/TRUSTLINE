"""Aerospace medical knowledge collections and document chunk structures."""
from typing import Dict, List, Optional
from ..schemas.rag_evidence import RAGCollection, EvidenceType, RAGEvidenceItem

COLLECTION_DOMAINS: Dict[RAGCollection, str] = {
    RAGCollection.BIOMEDICAL_KNOWLEDGE: "Terrestrial and human autonomic physiology, cardiovascular dynamics, and allostatic load",
    RAGCollection.SPACE_HEALTH_RESEARCH: "Spaceflight adaptation, microgravity cardiovascular deconditioning, and radiation biology",
    RAGCollection.MISSION_MEDICAL_PROTOCOLS: "Flight surgeon approved clinical intervention protocols, EVA thresholds, and telemetry alert workflows",
    RAGCollection.PSYCHOLOGICAL_COGNITIVE_RESEARCH: "Operational psychology, circadian disruption, cognitive vigilance, and confinement dynamics",
    RAGCollection.PHYSIOLOGICAL_SIGNAL_RESEARCH: "Biomedical sensor physics, artifact morphology, sampling standards, and HRV metric bounds"
}

ROUTING_KEYWORDS: Dict[RAGCollection, List[str]] = {
    RAGCollection.MISSION_MEDICAL_PROTOCOLS: ["protocol", "emergency", "escalation", "procedure", "threshold", "alert", "eva", "medical officer", "red-line"],
    RAGCollection.SPACE_HEALTH_RESEARCH: ["microgravity", "spaceflight", "fluid shift", "space motion sickness", "cosmic radiation", "astronaut", "orbit", "cabin"],
    RAGCollection.PSYCHOLOGICAL_COGNITIVE_RESEARCH: ["psychological", "cognitive", "stress", "anxiety", "isolation", "sleep", "vigilance", "workload", "fatigue"],
    RAGCollection.PHYSIOLOGICAL_SIGNAL_RESEARCH: ["ecg", "hrv", "eda", "emg", "respiration", "sampling rate", "artifact", "rmssd", "sdnn", "skin conductance", "filter"],
    RAGCollection.BIOMEDICAL_KNOWLEDGE: ["heart rate", "blood pressure", "temperature", "autonomic", "parasympathetic", "sympathetic", "vagal", "physiology", "cardiac"]
}
