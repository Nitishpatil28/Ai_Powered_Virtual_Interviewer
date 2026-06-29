"""
AI prompt templates for GD and HR interview simulations
"""
import json

from typing import List, Dict

# GD Prompts
GD_SYSTEM_PROMPT = """
You are "GD-Moderator-AI", a professional, neutral, and time-aware moderator for a 6-person group discussion. Purpose: evaluate each participant's communication skills, leadership, teamwork, clarity of thought, relevance, and listening. Always:
- Keep tone formal but human.
- Enforce turn-time limits (default 90 seconds per turn).
- Prompt participants to be concise when overrunning.
- Encourage quieter participants after two turns from them.
- Take notes of each participant: contribution_count, interruptions_made, interruptions_suffered, leadership_actions, idea_clarity_score (0-5), relevance_score (0-5), teamwork_score (0-5).
- After discussion end, produce:
  1) transcript (json array)
  2) per-participant metrics (json)
  3) short qualitative feedback (2-3 bullets per participant)
  4) overall topic summary in 3 sentences.
Return output in strict JSON only.
"""

GD_START_PROMPT = """
Start a GD on the topic: "{topic}". Participants: {participants}. Time per turn: {time_per_turn} seconds. Max rounds: {max_rounds}. Behavior profile for participants is optional. If provided, incorporate but don't reveal it.
Return the session id and initial moderator prompt to participants.
"""

GD_PARTICIPANT_MESSAGE_FORMAT = """
{{"session_id":"{session_id}", "participant":"{participant}", "text":"{text}", "time_taken_sec": {time_taken}}}
"""

GD_EVALUATION_PROMPT = """
You are GD-Evaluator-AI. Given the following JSON transcript and participant list, produce participant scores and feedback. Return JSON.

{{"topic": "{topic}", "participants": {participants}, "transcript": {transcript}}}

For each participant, provide:
- clarity_score (0-5)
- relevance_score (0-5)
- teamwork_score (0-5)
- leadership_score (0-5)
- final_recommendation (pass/hold/fail)
- 2 bullet comments
"""

GD_SUMMARY_PROMPT = """
Summarize this group discussion on: "{topic}"

Full transcript:
{transcript}

Participants: {participants}

Provide:
1. Overall discussion quality assessment
2. Key points raised
3. Areas of consensus/disagreement
4. Final participant rankings with brief reasoning
"""

# HR Interview Prompts
HR_SYSTEM_PROMPT = """
You are "HR-Interviewer-AI" playing a professional HR interviewer for campus/entry-level positions. Behavior:
- Ask 6-10 targeted questions: 2 behavioral (STAR-style), 2 technical (job relevant), 2 situational/aptitude.
- After each participant answer, ask 1 follow-up to probe depth.
- Score answers in 0-5 for content_richness, clarity, problem_solving, honesty (0-5 each).
- At session end, produce a concise interview report: strengths (3), weaknesses (3), recommended next step (hire/reject/onsite), suggested role fit, and 3 personalized improvement tips.
Return JSON only.
"""

HR_START_PROMPT = """
Start HR interview for candidate: {{"name":"{name}", "role":"{role}","experience_years":{experience}, "skills":{skills}}}.
Use friendly professional tone. Use dynamic follow-ups. Return interview id and first question.
"""

HR_QUESTION_GENERATION_PROMPT = """
Generate the next interview question for candidate: {candidate_name}

Skills: {skills}
Previous questions asked: {previous_questions}
Question types needed: {question_types}

Generate one question that:
- Is appropriate for engineering placement interview
- Tests relevant skills or experiences
- Hasn't been asked before
- Allows for detailed response (2-3 minutes)

Return question and its type (behavioral/technical/situational/general).
"""

HR_EVALUATION_PROMPT = """
Evaluate this interview answer:

Question: "{question}"
Question Type: {question_type}
Candidate: {candidate_name}
Answer: "{answer}"

Rate on scale of 0-5:

1. Content Richness: Depth, relevance, and completeness (0-5)
2. Clarity: Communication effectiveness and structure (0-5)
3. Problem Solving: Analytical thinking and solution quality (0-5)
4. Honesty: Authenticity and transparency (0-5)

Provide scores as JSON with specific feedback for improvement.
"""

HR_FINAL_REPORT_PROMPT = """
Generate final HR interview report for candidate: {candidate_name}

Interview summary: {interview_summary}
Overall scores: {overall_scores}

Produce JSON with:
- strengths (array of 3 items)
- weaknesses (array of 3 items)
- recommended_action (hire/reject/onsite)
- suggested_role_fit (string)
- improvement_tips (array of 3 items)
"""

HR_FEEDBACK_REPORT_PROMPT = """
Generate a comprehensive feedback report for candidate: {candidate_name}

Interview Summary:
{interview_summary}

Overall Scores:
{overall_scores}

Create a professional report with:
1. Performance Overview
2. Strengths (3-4 points)
3. Areas for Improvement (3-4 points)
4. Specific Recommendations (3-4 actionable tips)
5. Overall Assessment and Interview Outcome
"""

# Utility functions


def get_gd_start_prompt(topic: str, participants: List[str], time_per_turn: int = 90, max_rounds: int = 3) -> str:
    """Generate GD start prompt with specific data"""
    participants_str = '["' + '","'.join(participants) + '"]'
    return GD_START_PROMPT.format(
        topic=topic,
        participants=participants_str,
        time_per_turn=time_per_turn,
        max_rounds=max_rounds
    )


def get_gd_participant_message(session_id: str, participant: str, text: str, time_taken: int) -> str:
    """Generate participant message format"""
    return GD_PARTICIPANT_MESSAGE_FORMAT.format(
        session_id=session_id,
        participant=participant,
        text=text,
        time_taken=time_taken
    )


def get_gd_evaluation_prompt(topic: str, participants: List[str], transcript: List[Dict]) -> str:
    """Generate GD final evaluation prompt with transcript data"""
    participants_json = json.dumps(participants)
    transcript_json = json.dumps(transcript)
    return GD_EVALUATION_PROMPT.format(
        topic=topic,
        participants=participants_json,
        transcript=transcript_json
    )


def get_hr_question_prompt(candidate_name: str, skills: List[str],
                           previous_questions: List[str], question_types: List[str]) -> str:
    """Generate HR question prompt with specific data"""
    return HR_QUESTION_GENERATION_PROMPT.format(
        candidate_name=candidate_name,
        skills=", ".join(skills),
        previous_questions="\n".join(f"- {q}" for q in previous_questions) if previous_questions else "None",
        question_types=", ".join(question_types)
    )


def get_hr_evaluation_prompt(question: str, question_type: str, candidate_name: str, answer: str) -> str:
    """Generate HR evaluation prompt with specific data"""
    return HR_EVALUATION_PROMPT.format(
        question=question,
        question_type=question_type,
        candidate_name=candidate_name,
        answer=answer
    )


def get_gd_summary_prompt(topic: str, transcript: str, participants: List[str]) -> str:
    """Generate GD summary prompt with specific data"""
    return GD_SUMMARY_PROMPT.format(
        topic=topic,
        transcript=transcript,
        participants=", ".join(participants)
    )


def get_hr_start_prompt(name: str, role: str, experience: int, skills: List[str]) -> str:
    """Generate HR interview start prompt"""
    skills_json = json.dumps(skills)
    return HR_START_PROMPT.format(
        name=name,
        role=role,
        experience=experience,
        skills=skills_json
    )


def get_hr_final_report_prompt(candidate_name: str, interview_summary: str, overall_scores: Dict[str, float]) -> str:
    """Generate HR final report prompt with specific data"""
    scores_json = json.dumps(overall_scores)
    return HR_FINAL_REPORT_PROMPT.format(
        candidate_name=candidate_name,
        interview_summary=interview_summary,
        overall_scores=scores_json
    )


def get_hr_feedback_prompt(candidate_name: str, interview_summary: str, overall_scores: Dict[str, float]) -> str:
    """Generate HR feedback report prompt with specific data"""
    scores_json = json.dumps(overall_scores)
    return HR_FEEDBACK_REPORT_PROMPT.format(
        candidate_name=candidate_name,
        interview_summary=interview_summary,
        overall_scores=scores_json
    )
