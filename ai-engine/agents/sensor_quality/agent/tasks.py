"""CrewAI task definitions for Sensor Quality Agent."""
from typing import Optional
from crewai import Task, Agent
from .prompts import (
    SENSOR_QUALITY_TASK_DESCRIPTION,
    SENSOR_QUALITY_EXPECTED_OUTPUT
)

def create_sensor_quality_task(
    agent: Agent,
    astronaut_id: str,
    session_id: str
) -> Task:
    description = SENSOR_QUALITY_TASK_DESCRIPTION.format(
        astronaut_id=astronaut_id,
        session_id=session_id
    )
    return Task(
        description=description,
        expected_output=SENSOR_QUALITY_EXPECTED_OUTPUT,
        agent=agent
    )
