"""
Pydantic models for GD and HR interview simulations
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

# GD Models


class GDStartRequest(BaseModel):
    topic: str = Field(..., description="GD topic")
    participants: List[str] = Field(..., description="List of participant names")
    time_limit: Optional[int] = Field(180, description="Time limit in seconds per turn")


class GDStartResponse(BaseModel):
    session_id: str = Field(..., description="Unique session ID")
    topic: str = Field(..., description="GD topic")
    participants: List[str] = Field(..., description="List of participant names")
    current_turn: int = Field(0, description="Current turn number")
    time_limit: int = Field(..., description="Time limit per turn")
    moderator_prompt: Optional[str] = Field(None, description="Initial moderator prompt")
    started_at: Optional[str] = Field(None, description="Session start timestamp")


class GDTurnRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")
    participant: str = Field(..., description="Participant name")
    transcript: str = Field(..., description="Speech transcript")
    duration: float = Field(..., description="Duration in seconds")


class GDTurnResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    participant: str = Field(..., description="Participant name")
    scores: Dict[str, float] = Field(..., description="Individual scores (clarity, relevance, teamwork, leadership)")
    feedback: str = Field(..., description="Short feedback for this turn")
    next_participant: Optional[str] = Field(None, description="Next participant to speak")
    round_complete: bool = Field(False, description="Whether current round is complete")


class GDEndRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")


class GDParticipantResult(BaseModel):
    name: str = Field(..., description="Participant name")
    scores: Dict[str,
                 float] = Field(...,
                                description="Final scores (clarity_score, relevance_score, teamwork_score, leadership_score, final_score)")
    feedback: List[str] = Field(..., description="Feedback bullets")
    recommendation: Optional[str] = Field(None, description="Pass/hold/fail recommendation")


class GDEndResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    transcript: str = Field(..., description="Full discussion transcript")
    participants: List[GDParticipantResult] = Field(..., description="Results for each participant")
    summary: str = Field(..., description="Overall topic summary")

# HR Models


class HRStartRequest(BaseModel):
    candidate_name: str = Field(..., description="Candidate name")
    skills: List[str] = Field(..., description="Candidate skills")


class HRStartResponse(BaseModel):
    session_id: str = Field(..., description="Unique session ID")
    candidate_name: str = Field(..., description="Candidate name")
    question: str = Field(..., description="First question")
    question_type: str = Field(..., description="Type of question (behavioral/technical/situational)")


class HRAnswerRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")
    answer: str = Field(..., description="Candidate's answer")


class HRAnswerResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    scores: Dict[str, float] = Field(...,
                                     description="Answer scores (content_richness, clarity, problem_solving, honesty)")
    feedback: str = Field(..., description="Feedback for this answer")
    next_question: Optional[str] = Field(None, description="Next question")
    question_type: Optional[str] = Field(None, description="Type of next question")
    interview_complete: bool = Field(False, description="Whether interview is complete")
    evaluation_details: Optional[Dict[str, Any]] = Field(None, description="Detailed evaluation information")


class HREndRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")


class HREndResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    overall_scores: Dict[str, float] = Field(..., description="Overall scores (0-5 scale)")
    feedback_report: Dict[str, Any] = Field(
        ..., description="Complete feedback report with strengths, weaknesses, recommended_action, suggested_role_fit, improvement_tips")

# Database Models (for reference)


class GDSession(BaseModel):
    id: str
    topic: str
    participants: List[str]
    current_turn: int
    transcripts: List[Dict[str, Any]]
    status: str
    created_at: datetime


class HRSession(BaseModel):
    id: str
    candidate_name: str
    skills: List[str]
    questions_asked: List[str]
    answers: List[Dict[str, Any]]
    current_question_index: int
    status: str
    created_at: datetime
