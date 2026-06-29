"""
FastAPI backend for AI-powered GD and HR interview simulations
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import json
from datetime import datetime

from models import (
    GDStartRequest, GDStartResponse, GDTurnRequest, GDTurnResponse,
    GDEndRequest, GDEndResponse, GDParticipantResult,
    HRStartRequest, HRStartResponse, HRAnswerRequest, HRAnswerResponse,
    HREndRequest, HREndResponse
)
from database import db_manager
from evaluation import evaluator

app = FastAPI(
    title="AI Interviewer API",
    description="AI-powered Group Discussion and HR Interview Simulation API",
    version="1.0.0"
)

# CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sample GD topics and HR questions for fallback
SAMPLE_GD_TOPICS = [
    "Should social media platforms be regulated more strictly?",
    "Impact of artificial intelligence on employment",
    "Should cryptocurrency replace traditional banking?",
    "Remote work vs office work: Future of workspaces",
    "Should electric vehicles be mandatory by 2030?"
]

SAMPLE_HR_QUESTIONS = {
    "behavioral": [
        "Tell me about a time when you faced a challenging problem at work/school. How did you solve it?",
        "Describe a situation where you had to work with a difficult team member. How did you handle it?",
        "Give an example of a project where you took initiative. What was the outcome?"
    ],
    "technical": [
        "Explain how you would approach debugging a complex software issue.",
        "How do you stay updated with the latest technologies in your field?",
        "Describe your experience with version control systems like Git."
    ],
    "situational": [
        "How would you handle a situation where a project deadline is approaching but requirements keep changing?",
        "If you discovered a colleague was not following company policy, what would you do?",
        "How would you prioritize tasks when you have multiple urgent deadlines?"
    ]
}

# GD Endpoints


@app.post("/api/gd/start", response_model=GDStartResponse)
def start_gd_session(request: GDStartRequest):
    """Start a new group discussion session"""
    try:
        # Input validation
        if not request.participants or not all(p.strip() for p in request.participants):
            raise HTTPException(status_code=400, detail="At least one non-empty participant name is required")

        participants = [p.strip() for p in request.participants]
        session_id = str(uuid.uuid4())
        topic = (request.topic or SAMPLE_GD_TOPICS[0]).strip()

        # Create session in database
        success = db_manager.create_gd_session(session_id, topic, participants)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create GD session")

        # Generate moderator prompt using LLM
        from ai_prompts import get_gd_start_prompt
        try:
            # Try to get LLM-generated prompt
            llm_prompt = get_gd_start_prompt(topic, request.participants, request.time_limit or 90)
            # Here you would call your LLM with GD_SYSTEM_PROMPT + llm_prompt
            # For now, use structured prompt
            moderator_prompt = f"Welcome to GD on '{topic}'. {len(request.participants)} participants: {', '.join(request.participants)}. Time per turn: {request.time_limit or 90} seconds. First speaker: {request.participants[0]}."
        except BaseException:
            moderator_prompt = f"Welcome to GD on '{topic}'. {len(request.participants)} participants: {', '.join(request.participants)}. Time per turn: {request.time_limit or 90} seconds. First speaker: {request.participants[0]}."

        return GDStartResponse(
            session_id=session_id,
            topic=topic,
            participants=participants,
            current_turn=0,
            time_limit=request.time_limit or 90,
            moderator_prompt=moderator_prompt,
            started_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting GD session: {str(e)}")


@app.post("/api/gd/turn", response_model=GDTurnResponse)
def process_gd_turn(request: GDTurnRequest):
    """Process a participant's turn in the GD"""
    try:
        # Get session data
        session = db_manager.get_gd_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="GD session not found")

        # Evaluate the turn
        evaluation = evaluator.evaluate_gd_turn(
            session['topic'],
            request.participant,
            request.transcript,
            request.duration
        )

        # Save turn to database
        turn_number = len(db_manager.get_gd_turns(request.session_id)) + 1
        success = db_manager.save_gd_turn(
            request.session_id,
            request.participant,
            request.transcript,
            request.duration,
            evaluation,
            evaluation.get('feedback', 'Turn completed'),
            turn_number
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save GD turn")

        # Determine next participant and round status
        participants = json.loads(session['participants'])
        if request.participant not in participants:
            raise HTTPException(status_code=400, detail=f"Participant {request.participant} not in session")

        current_index = participants.index(request.participant)
        next_index = (current_index + 1) % len(participants)
        next_participant = participants[next_index] if turn_number < len(participants) * 2 else None  # 2 rounds
        round_complete = turn_number % len(participants) == 0

        # Simple round-robin logic for next participant
        if next_participant is None and turn_number < len(participants) * 2:
            next_participant = participants[turn_number % len(participants)]

        return GDTurnResponse(
            session_id=request.session_id,
            participant=request.participant,
            scores=evaluation,
            feedback=evaluation.get('feedback', 'Turn evaluated'),
            next_participant=next_participant,
            round_complete=round_complete
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid participant: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing GD turn: {str(e)}")


@app.post("/api/gd/end", response_model=GDEndResponse)
def end_gd_session(request: GDEndRequest):
    """End the GD session and provide final results"""
    try:
        # Get session data
        session = db_manager.get_gd_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="GD session not found")

        # Get all turns
        turns = db_manager.get_gd_turns(request.session_id)
        participants = json.loads(session['participants'])

        # Convert turns to transcript format for LLM evaluation
        transcript = []
        for turn in turns:
            transcript.append({
                "session_id": request.session_id,
                "participant": turn['participant'],
                "text": turn['transcript'],
                "time_taken_sec": turn.get('duration', 0)
            })

        # Use LLM for final evaluation
        final_evaluation = evaluator.evaluate_gd_session_final(
            session['topic'], participants, transcript
        )

        # Generate participant results from LLM evaluation
        results = []
        participants_metrics = final_evaluation.get('participants_metrics', {})

        for participant in participants:
            metrics = participants_metrics.get(participant, {})
            scores = {
                "clarity_score": metrics.get('clarity_score', 3.0),
                "relevance_score": metrics.get('relevance_score', 3.0),
                "teamwork_score": metrics.get('teamwork_score', 3.0),
                "leadership_score": metrics.get('leadership_score', 3.0),
                "final_score": (metrics.get('clarity_score', 3.0) + metrics.get('relevance_score', 3.0) +
                                metrics.get('teamwork_score', 3.0) + metrics.get('leadership_score', 3.0)) / 4
            }

            results.append(GDParticipantResult(
                name=participant,
                scores=scores,
                feedback=metrics.get('comments', ["Evaluation completed"]),
                recommendation=metrics.get('final_recommendation', 'hold')
            ))

        # Generate full transcript
        full_transcript = "\n\n".join([
            f"{turn['participant']}: {turn['transcript']}"
            for turn in turns
        ])

        # Use LLM summary or fallback
        summary = final_evaluation.get(
            'overall_topic_summary',
            f"Group discussion on '{session['topic']}' completed with {len(participants)} participants.")

        # End session
        db_manager.end_gd_session(request.session_id)

        return GDEndResponse(
            session_id=request.session_id,
            transcript=full_transcript,
            participants=results,
            summary=summary
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ending GD session: {str(e)}")

# HR Endpoints


@app.post("/api/hr/start", response_model=HRStartResponse)
def start_hr_interview(request: HRStartRequest):
    """Start a new HR interview session"""
    try:
        session_id = str(uuid.uuid4())

        # Create session in database
        success = db_manager.create_hr_session(session_id, request.candidate_name, request.skills)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create HR session")

        # Generate first question using LLM or fallback
        from ai_prompts import get_hr_start_prompt
        try:
            # Try to get LLM-generated start
            llm_prompt = get_hr_start_prompt(request.candidate_name, "Software Engineer", 2, request.skills)
            # Here you would call your LLM with HR_SYSTEM_PROMPT + llm_prompt
            # For now, use structured first question
            first_question = "Tell me about yourself in 60 seconds."
        except BaseException:
            first_question = "Tell me about yourself in 60 seconds."

        return HRStartResponse(
            session_id=session_id,
            candidate_name=request.candidate_name,
            question=first_question,
            question_type="behavioral"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting HR interview: {str(e)}")


@app.post("/api/hr/answer", response_model=HRAnswerResponse)
def process_hr_answer(request: HRAnswerRequest):
    """Process an HR interview answer"""
    try:
        # Input validation
        if not request.answer or not request.answer.strip():
            raise HTTPException(status_code=400, detail="Answer cannot be empty")

        # Get session data
        session = db_manager.get_hr_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="HR session not found")

        # Determine question type and current question text
        answers_count = len(db_manager.get_hr_answers(request.session_id))
        question_types = ["behavioral", "technical", "situational"]
        current_type = question_types[min(answers_count, len(question_types) - 1)]

        # Get the actual current question text
        if answers_count == 0:
            current_question_text = "Tell me about yourself in 60 seconds."
        else:
            current_question_text = SAMPLE_HR_QUESTIONS[current_type][0]

        # Generate next question or mark as last
        if answers_count < 2:  # 3 questions total
            next_type = question_types[answers_count + 1]
            next_question = SAMPLE_HR_QUESTIONS[next_type][0]
            interview_complete = False
        else:
            next_question = None
            next_type = None
            interview_complete = True

        # Evaluate the answer using the actual question
        evaluation = evaluator.evaluate_hr_answer(
            current_question_text,
            current_type,
            session['candidate_name'],
            request.answer
        )

        # Save answer to database with actual question text
        success = db_manager.save_hr_answer(
            request.session_id,
            current_question_text,
            request.answer,
            evaluation,
            evaluation.get('feedback', 'Answer evaluated'),
            current_type
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save HR answer")

        return HRAnswerResponse(
            session_id=request.session_id,
            scores=evaluation,
            feedback="Answer evaluated successfully",
            next_question=next_question,
            question_type=next_type,
            interview_complete=interview_complete
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing HR answer: {str(e)}")


@app.post("/api/hr/end", response_model=HREndResponse)
def end_hr_interview(request: HREndRequest):
    """End the HR interview and provide final results"""
    try:
        # Get session data
        session = db_manager.get_hr_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="HR session not found")

        # Get all answers
        answers = db_manager.get_hr_answers(request.session_id)

        # Calculate overall scores (0-5 scale)
        if answers:
            overall_scores = {}
            score_keys = ['content_richness', 'clarity', 'problem_solving', 'honesty']

            for key in score_keys:
                scores = [json.loads(ans['scores']).get(key, 0) for ans in answers]
                overall_scores[key] = sum(scores) / len(scores) if scores else 0
        else:
            overall_scores = {key: 0 for key in ['content_richness', 'clarity', 'problem_solving', 'honesty']}

        # Generate interview summary
        interview_summary = "\n".join([
            f"Q{ans['id']}: {ans['question']}\nA: {ans['answer'][:100]}..."
            for ans in answers
        ])

        # Generate final report using LLM
        feedback_report = evaluator.generate_hr_final_report(
            session['candidate_name'],
            interview_summary,
            overall_scores
        )

        # End session
        db_manager.end_hr_session(request.session_id)

        return HREndResponse(
            session_id=request.session_id,
            overall_scores=overall_scores,
            feedback_report=feedback_report
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ending HR interview: {str(e)}")

# Health check endpoint


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
