"""
AI evaluation and rule-based scoring for GD and HR simulations
"""

import json
import re
from typing import Dict, List, Any, Optional
from ai_prompts import GD_SYSTEM_PROMPT, HR_SYSTEM_PROMPT, get_hr_feedback_prompt

import openai
from ai_prompts import (
    get_hr_evaluation_prompt, get_gd_summary_prompt
)


class AIEvaluator:
    """Handles AI-powered evaluation using LLM calls"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        if api_key:
            openai.api_key = api_key

    def evaluate_gd_turn(self, topic: str, participant: str, transcript: str, duration: float) -> Dict[str, Any]:
        """Evaluate a single GD turn using AI"""
        try:
            # Use rule-based evaluation with heuristics for individual turns
            return self._rule_based_gd_evaluation_with_heuristics(transcript, duration, topic)

        except Exception as e:
            print(f"GD evaluation failed: {e}")
            return self._rule_based_gd_evaluation(transcript, duration)

    def evaluate_gd_session_final(self, topic: str, participants: List[str], transcript: List[Dict]) -> Dict[str, Any]:
        """Evaluate complete GD session using LLM"""
        try:
            from ai_prompts import get_gd_evaluation_prompt
            prompt = get_gd_evaluation_prompt(topic, participants, transcript)

            if not self.api_key:
                # Fallback to rule-based evaluation
                return self._rule_based_gd_final_evaluation(transcript, participants, topic)

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": GD_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            result_text = response.choices[0].message.content.strip()
            # Try to parse JSON response
            try:
                result = json.loads(result_text)
                return result
            except json.JSONDecodeError:
                # Extract scores from text if JSON parsing fails
                return self._parse_gd_final_scores_from_text(result_text, participants)

        except Exception as e:
            print(f"AI GD final evaluation failed: {e}")
            return self._rule_based_gd_final_evaluation(transcript, participants, topic)

    def evaluate_hr_answer(self, question: str, question_type: str, candidate_name: str, answer: str) -> Dict[str, Any]:
        """Evaluate an HR interview answer using AI"""
        try:
            prompt = get_hr_evaluation_prompt(question, question_type, candidate_name, answer)

            if not self.api_key:
                # Fallback to rule-based evaluation
                return self._rule_based_hr_evaluation_with_heuristics(answer, question_type)

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": HR_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400
            )

            result_text = response.choices[0].message.content.strip()
            try:
                result = json.loads(result_text)
                return result
            except json.JSONDecodeError:
                return self._parse_hr_scores_from_text(result_text)

        except Exception as e:
            print(f"AI evaluation failed: {e}")
            return self._rule_based_hr_evaluation_with_heuristics(answer, question_type)

    def generate_hr_final_report(self, candidate_name: str, interview_summary: str,
                                 overall_scores: Dict[str, float]) -> Dict[str, Any]:
        """Generate final HR interview report using LLM"""
        try:
            from ai_prompts import get_hr_final_report_prompt
            prompt = get_hr_final_report_prompt(candidate_name, interview_summary, overall_scores)

            if not self.api_key:
                # Fallback to rule-based report
                return self._rule_based_hr_final_report(overall_scores)

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": HR_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=600
            )

            result_text = response.choices[0].message.content.strip()
            try:
                result = json.loads(result_text)
                return result
            except json.JSONDecodeError:
                return self._parse_hr_final_report_from_text(result_text)

        except Exception as e:
            print(f"AI HR final report failed: {e}")
            return self._rule_based_hr_final_report(overall_scores)

    def generate_gd_summary(self, topic: str, full_transcript: str, participants: List[str]) -> str:
        """Generate overall GD summary"""
        try:
            prompt = get_gd_summary_prompt(topic, full_transcript, participants)

            if not self.api_key:
                return self._rule_based_gd_summary(topic, participants)

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert GD moderator. Provide a comprehensive summary."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=600
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"AI summary failed: {e}")
            return self._rule_based_gd_summary(topic, participants)

    def generate_hr_feedback_report(self, candidate_name: str, interview_summary: str,
                                    overall_scores: Dict[str, float]) -> str:
        """Generate comprehensive HR feedback report"""
        try:
            prompt = get_hr_feedback_prompt(candidate_name, interview_summary, overall_scores)

            if not self.api_key:
                return self._rule_based_hr_feedback(overall_scores)

            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an experienced HR professional. Create a detailed, constructive feedback report."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=800
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"AI feedback generation failed: {e}")
            return self._rule_based_hr_feedback(overall_scores)

    # Rule-based fallback methods with enhanced heuristics
    def _rule_based_gd_evaluation_with_heuristics(self, transcript: str, duration: float, topic: str) -> Dict[str, Any]:
        """Enhanced rule-based GD evaluation with heuristics"""
        word_count = len(transcript.split())
        sentences = len(re.split(r'[.!?]+', transcript))

        # Contribution count: based on word count (higher is better but penalize off-topic)
        contribution_score = min(5.0, max(1.0, word_count / 50))

        # Interruptions: detect phrases like "sorry to interrupt" (penalize)
        interruption_keywords = ['sorry to interrupt', 'excuse me', 'can i add', 'let me interrupt']
        interruptions_made = sum(1 for phrase in interruption_keywords if phrase.lower() in transcript.lower())

        # Semantic relevance: cosine similarity with topic (simplified keyword overlap)
        topic_words = set(topic.lower().split())
        transcript_words = set(transcript.lower().split())
        overlap = len(topic_words & transcript_words)
        relevance = min(5.0, max(1.0, (overlap / max(1, len(topic_words))) * 5))

        # Clarity: count sentence length, structure words
        structure_words = ['first', 'second', 'third', 'however', 'therefore', 'moreover', 'in conclusion']
        structure_count = sum(1 for word in structure_words if word.lower() in transcript.lower())
        avg_sentence_length = word_count / max(1, sentences)
        clarity_penalty = 1.0 if avg_sentence_length < 30 else max(0.5, 30 / avg_sentence_length)
        clarity = min(5.0, max(1.0, (structure_count * 0.5 + clarity_penalty) * 2))

        # Leadership: +1 for proposing plan, +1 for inviting others, +1 for summarizing
        leadership_keywords = [
            'i propose',
            'i suggest',
            'we should',
            'let me summarize',
            'does anyone',
            'what do you think']
        leadership_score = sum(1 for phrase in leadership_keywords if phrase.lower() in transcript.lower())
        leadership = min(5.0, max(1.0, leadership_score * 0.8))

        # Teamwork: collaborative language
        teamwork_keywords = ['we', 'together', 'group', 'team', 'agree', 'support', 'collaborate']
        teamwork_score = sum(1 for word in teamwork_keywords if word.lower() in transcript.lower())
        teamwork = min(5.0, max(1.0, teamwork_score * 0.7))

        # Confidence: based on length and direct statements
        confidence_indicators = ['i believe', 'i think', 'definitely', 'absolutely', 'certainly']
        confidence_score = sum(1 for phrase in confidence_indicators if phrase.lower() in transcript.lower())
        confidence = min(5.0, max(1.0, confidence_score * 0.6 + contribution_score * 0.4))

        # Combine to final score
        final_score = 0.25 * clarity + 0.25 * relevance + 0.2 * teamwork + 0.15 * leadership + 0.15 * confidence
        final_score = min(5.0, max(1.0, final_score))

        return {
            "clarity_score": round(clarity, 1),
            "relevance_score": round(relevance, 1),
            "teamwork_score": round(teamwork, 1),
            "leadership_score": round(leadership, 1),
            "final_score": round(final_score, 1),
            "contribution_count": contribution_score,
            "interruptions_made": interruptions_made,
            "feedback": f"Turn evaluation: {round(final_score, 1)}/5 overall score."
        }

    def _rule_based_gd_final_evaluation(
            self, transcript: List[Dict], participants: List[str], topic: str) -> Dict[str, Any]:
        """Rule-based final GD evaluation"""
        participant_scores = {}

        for participant in participants:
            participant_turns = [t for t in transcript if t.get('participant') == participant]
            if not participant_turns:
                participant_scores[participant] = {
                    "clarity_score": 1.0,
                    "relevance_score": 1.0,
                    "teamwork_score": 1.0,
                    "leadership_score": 1.0,
                    "final_recommendation": "fail",
                    "comments": ["No participation detected"]
                }
                continue

            # Aggregate scores from turns
            total_clarity = total_relevance = total_teamwork = total_leadership = 0
            total_contributions = 0
            total_interruptions = 0

            for turn in participant_turns:
                scores = self._rule_based_gd_evaluation_with_heuristics(
                    turn.get('text', ''), turn.get('time_taken_sec', 0), topic
                )
                total_clarity += scores.get('clarity_score', 0)
                total_relevance += scores.get('relevance_score', 0)
                total_teamwork += scores.get('teamwork_score', 0)
                total_leadership += scores.get('leadership_score', 0)
                total_contributions += scores.get('contribution_count', 0)
                total_interruptions += scores.get('interruptions_made', 0)

            num_turns = len(participant_turns)
            avg_clarity = total_clarity / num_turns
            avg_relevance = total_relevance / num_turns
            avg_teamwork = total_teamwork / num_turns
            avg_leadership = total_leadership / num_turns

            # Penalize excessive interruptions
            interruption_penalty = min(1.0, total_interruptions * 0.2)
            final_score = 0.25 * avg_clarity + 0.25 * avg_relevance + 0.2 * avg_teamwork + \
                0.15 * avg_leadership + 0.15 * total_contributions - interruption_penalty
            final_score = max(1.0, min(5.0, final_score))

            # Determine recommendation
            if final_score >= 4.0:
                recommendation = "pass"
            elif final_score >= 3.0:
                recommendation = "hold"
            else:
                recommendation = "fail"

            participant_scores[participant] = {
                "clarity_score": round(avg_clarity, 1),
                "relevance_score": round(avg_relevance, 1),
                "teamwork_score": round(avg_teamwork, 1),
                "leadership_score": round(avg_leadership, 1),
                "final_recommendation": recommendation,
                "comments": [
                    f"Overall score: {round(final_score, 1)}/5",
                    f"Contributions: {total_contributions:.1f}, Interruptions: {total_interruptions}"
                ]
            }

        return {
            "transcript": transcript,
            "participants_metrics": participant_scores,
            "overall_topic_summary": f"Group discussion on '{topic}' completed with {len(participants)} participants."
        }

    def _rule_based_hr_evaluation_with_heuristics(self, answer: str, question_type: str) -> Dict[str, Any]:
        """Enhanced rule-based HR evaluation with heuristics"""
        word_count = len(answer.split())
        sentences = len(re.split(r'[.!?]+', answer))

        # Content richness: Based on length and detail (0-5 scale)
        content_richness = min(5.0, max(1.0, (word_count / 50) + (sentences / 3)))

        # Clarity: Based on sentence structure and length (0-5 scale)
        avg_sentence_length = word_count / max(1, sentences)
        clarity_penalty = 1.0 if avg_sentence_length < 25 else max(0.5, 25 / avg_sentence_length)
        structure_indicators = ['first', 'second', 'however', 'therefore', 'for example']
        structure_bonus = sum(1 for word in structure_indicators if word.lower() in answer.lower()) * 0.2
        clarity = min(5.0, max(1.0, clarity_penalty * 3 + structure_bonus))

        # Problem solving: Look for analytical words (0-5 scale)
        problem_keywords = ['analyze', 'solution', 'approach', 'strategy', 'method', 'process', 'challenge', 'overcome']
        problem_score = sum(1 for word in problem_keywords if word.lower() in answer.lower())
        problem_solving = min(5.0, max(1.0, problem_score * 0.8 + content_richness * 0.2))

        # Honesty: Look for authentic language vs generic responses (0-5 scale)
        authentic_indicators = ['i experienced', 'i learned', 'i felt', 'personally', 'specifically']
        generic_indicators = ['generally', 'usually', 'typically', 'in general', 'normally']
        authentic_score = sum(1 for phrase in authentic_indicators if phrase.lower() in answer.lower())
        generic_penalty = sum(1 for phrase in generic_indicators if phrase.lower() in answer.lower()) * 0.1
        honesty = min(5.0, max(1.0, authentic_score * 0.5 + 3.0 - generic_penalty))

        # Adjust based on question type
        if question_type == 'behavioral':
            # STAR method check
            star_elements = ['situation', 'task', 'action', 'result']
            star_score = sum(1 for element in star_elements if element.lower() in answer.lower())
            problem_solving = min(5.0, problem_solving + star_score * 0.3)
        elif question_type == 'technical':
            # Technical depth check
            technical_terms = ['code', 'algorithm', 'framework', 'database', 'api', 'debug', 'optimize']
            technical_score = sum(1 for term in technical_terms if term.lower() in answer.lower())
            content_richness = min(5.0, content_richness + technical_score * 0.2)

        return {
            "content_richness": round(content_richness, 1),
            "clarity": round(clarity, 1),
            "problem_solving": round(problem_solving, 1),
            "honesty": round(honesty, 1)
        }

    def _rule_based_hr_final_report(self, overall_scores: Dict[str, float]) -> Dict[str, Any]:
        """Rule-based HR final report generation"""
        avg_score = sum(overall_scores.values()) / len(overall_scores)

        # Determine recommendation
        if avg_score >= 4.0:
            recommendation = "hire"
            action_reason = "Strong overall performance across all evaluation criteria"
        elif avg_score >= 3.0:
            recommendation = "onsite"
            action_reason = "Solid performance with room for in-person assessment"
        else:
            recommendation = "reject"
            action_reason = "Performance below required standards"

        # Generate strengths
        strengths = []
        if overall_scores.get('content_richness', 0) >= 3.5:
            strengths.append("Demonstrates strong content knowledge and depth")
        if overall_scores.get('clarity', 0) >= 3.5:
            strengths.append("Communicates ideas clearly and effectively")
        if overall_scores.get('problem_solving', 0) >= 3.5:
            strengths.append("Shows good analytical and problem-solving skills")
        if overall_scores.get('honesty', 0) >= 3.5:
            strengths.append("Provides authentic and honest responses")
        if not strengths:
            strengths.append("Shows willingness to participate in the interview process")

        # Generate weaknesses
        weaknesses = []
        if overall_scores.get('content_richness', 0) < 3.0:
            weaknesses.append("Could provide more detailed and comprehensive answers")
        if overall_scores.get('clarity', 0) < 3.0:
            weaknesses.append("Communication could be clearer and more structured")
        if overall_scores.get('problem_solving', 0) < 3.0:
            weaknesses.append("Could demonstrate stronger analytical thinking")
        if overall_scores.get('honesty', 0) < 3.0:
            weaknesses.append("Responses could be more authentic and specific")
        if not weaknesses:
            weaknesses.append("Areas for improvement not clearly identified")

        # Suggested role fit
        role_fit = "Entry-level engineering position" if avg_score >= 3.5 else "Internship or training program" if avg_score >= 2.5 else "Not suitable for current openings"

        # Improvement tips
        improvement_tips = [
            "Practice STAR method for behavioral questions",
            "Prepare specific examples from past experiences",
            "Work on clear and concise communication",
            "Research company and role requirements thoroughly"
        ]

        return {
            "strengths": strengths[:3],  # Limit to 3
            "weaknesses": weaknesses[:3],  # Limit to 3
            "recommended_action": recommendation,
            "suggested_role_fit": role_fit,
            "improvement_tips": improvement_tips[:3]  # Limit to 3
        }

    def _rule_based_gd_summary(self, topic: str, participants: List[str]) -> str:
        """Rule-based GD summary fallback"""
        return f"""
Group Discussion Summary: {topic}

Participants: {', '.join(participants)}

Overall Assessment:
- Discussion covered the main aspects of the topic
- Participants showed varying levels of engagement
- Key points were raised about the importance and implications

Key Observations:
- Good participation from all members
- Some strong leadership shown
- Areas for improvement in turn-taking and depth of analysis

Recommendations:
- Practice more structured approaches to complex topics
- Focus on building consensus and collaborative solutions
- Work on clearer articulation of ideas
"""

    def _rule_based_hr_feedback(self, overall_scores: Dict[str, float]) -> str:
        """Rule-based HR feedback fallback"""
        avg_score = sum(overall_scores.values()) / max(1, len(overall_scores))
        # Convert from 0-5 scale to 0-100 scale
        score_100 = avg_score * 20

        performance_level = "Excellent" if score_100 >= 80 else "Good" if score_100 >= 60 else "Needs Improvement"

        return f"""
HR Interview Feedback Report

Performance Overview: {performance_level} performance with an overall score of {score_100:.1f}/100

Strengths:
- Good communication skills demonstrated
- Relevant experience highlighted effectively
- Professional attitude maintained throughout

Areas for Improvement:
- Could provide more specific examples
- Work on structuring responses more clearly
- Practice handling technical questions

Recommendations:
- Prepare STAR method responses for behavioral questions
- Research company-specific technical requirements
- Practice mock interviews regularly
- Focus on concise yet comprehensive answers

Overall Assessment:
A solid candidate who shows potential for growth. Recommended for further consideration with additional preparation.
"""

    def _parse_gd_final_scores_from_text(self, text: str, participants: List[str]) -> Dict[str, Any]:
        """Parse final GD scores from AI text response"""
        participant_scores = {}

        # Try to extract participant scores
        for participant in participants:
            participant_scores[participant] = {
                "clarity_score": 3.0,
                "relevance_score": 3.0,
                "teamwork_score": 3.0,
                "leadership_score": 3.0,
                "final_recommendation": "hold",
                "comments": ["Evaluation completed"]
            }

        return {
            "transcript": [],
            "participants_metrics": participant_scores,
            "overall_topic_summary": "Group discussion evaluation completed."
        }

    def _parse_hr_final_report_from_text(self, text: str) -> Dict[str, Any]:
        """Parse HR final report from AI text response"""
        return {
            "strengths": ["Good communication skills", "Shows potential", "Willing to learn"],
            "weaknesses": ["Could be more specific", "Needs more experience", "Improve technical depth"],
            "recommended_action": "onsite",
            "suggested_role_fit": "Entry-level engineering position",
            "improvement_tips": [
                "Practice technical questions",
                "Prepare specific examples",
                "Research company thoroughly"
            ]
        }


# Global evaluator instance
evaluator = AIEvaluator()
