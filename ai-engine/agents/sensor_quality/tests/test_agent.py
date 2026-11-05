"""Tests for LangChain tools and CrewAI Agent structure."""
import pytest
import json
from sensor_quality_agent.tools.langchain_tools import (
    inspect_signal_integrity,
    inspect_temporal_integrity,
    analyze_signal_noise,
    detect_signal_artifacts,
    detect_flatline_segments,
    validate_sensor_signal,
    calculate_signal_quality,
    generate_quality_explanation,
    global_tool_store
)
from sensor_quality_agent.schemas.signal_schema import SensorStreamData
from sensor_quality_agent.agent.agent import create_sensor_quality_agent

def test_langchain_tools_execution(clean_ecg_stream: SensorStreamData):
    global_tool_store.store_stream("ECG", clean_ecg_stream)

    raw_integrity = inspect_signal_integrity.invoke({"sensor_name": "ECG"})
    data_integrity = json.loads(raw_integrity)
    assert data_integrity["sensor"] == "ECG"
    assert data_integrity["valid_sample_ratio"] == 1.0

    raw_temporal = inspect_temporal_integrity.invoke({"sensor_name": "ECG"})
    data_temporal = json.loads(raw_temporal)
    assert data_temporal["timestamp_integrity"] >= 0.90

    raw_flatline = detect_flatline_segments.invoke({"sensor_name": "ECG"})
    data_flatline = json.loads(raw_flatline)
    assert data_flatline["flatline_ratio"] == 0.0

    raw_quality = calculate_signal_quality.invoke({"sensor_name": "ECG"})
    data_quality = json.loads(raw_quality)
    assert data_quality["sensor"] == "ECG"
    assert data_quality["quality_score"] >= 0.90
    assert data_quality["status"] == "VALID"

    raw_explanation = generate_quality_explanation.invoke({"sensor_name": "ECG"})
    data_explanation = json.loads(raw_explanation)
    assert "status" in data_explanation
    assert data_explanation["recommendation"] == "ACCEPT"

def test_crewai_agent_instantiation():
    agent = create_sensor_quality_agent(llm=None)
    assert agent.role == "Biomedical Signal Quality Assessment Specialist"
    assert len(agent.tools) == 8
