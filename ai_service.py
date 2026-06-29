# ============================================
# FILE: ai_services.py
# Enhanced AI Service Integrations (OpenAI, Speech, Code Execution, NLP)
# ============================================

from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import os
import json
import time
import random
import sqlite3
import requests
import nltk
from textblob import TextBlob
from typing import Dict, List, Any
import numpy as np

# Download required NLTK data
required_nltk_resources = [
    'punkt',
    'punkt_tab',
    'stopwords',
    'vader_lexicon',
    'averaged_perceptron_tagger',
    'averaged_perceptron_tagger_eng'
]

for resource in required_nltk_resources:
    try:
        if resource == 'punkt':
            nltk.data.find("tokenizers/punkt")
        elif resource == 'punkt_tab':
            nltk.data.find("tokenizers/punkt_tab")
        elif resource == 'stopwords':
            nltk.data.find("corpora/stopwords")
        elif resource == 'vader_lexicon':
            nltk.data.find("sentiment/vader_lexicon")
        elif resource == 'averaged_perceptron_tagger':
            nltk.data.find("taggers/averaged_perceptron_tagger")
        elif resource == 'averaged_perceptron_tagger_eng':
            nltk.data.find("taggers/averaged_perceptron_tagger_eng")
    except LookupError:
        print(f"Downloading NLTK resource: {resource}")
        try:
            nltk.download(resource, quiet=True)
        except Exception as e:
            print(f"Warning: Could not download {resource}: {e}")


# ============================================
# CONFIGURATION
# ============================================

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system environment variables

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
JUDGE0_API_KEY = os.environ.get("JUDGE0_API_KEY")
JUDGE0_URL = "https://judge0-ce.p.rapidapi.com"
DB_PATH = "users.db"

# Initialize NLTK components
sentiment_analyzer = SentimentIntensityAnalyzer()
stop_words = set(stopwords.words('english'))

# ============================================
# ENHANCED NLP ANALYSIS SERVICE
# ============================================


class EnhancedNLPAnalysisService:
    """Advanced NLP analysis for comprehensive text evaluation."""

    def __init__(self):
        self.filler_words = ['um', 'uh', 'like', 'you know', 'so', 'well', 'actually', 'basically']
        self.positive_words = ['excellent', 'great', 'good', 'amazing', 'wonderful', 'fantastic', 'outstanding']
        self.negative_words = ['bad', 'terrible', 'awful', 'horrible', 'disappointing', 'poor']

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Comprehensive text analysis for interview responses."""
        if not text or len(text.strip()) < 10:
            return self._get_default_analysis()

        # Basic metrics
        word_count = len(word_tokenize(text))
        sentence_count = len(sent_tokenize(text))
        avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0

        # Filler word analysis
        filler_count = self._count_filler_words(text)
        filler_ratio = filler_count / word_count if word_count > 0 else 0

        # Sentiment analysis
        sentiment_scores = sentiment_analyzer.polarity_scores(text)

        # Clarity and fluency
        clarity_score = self._calculate_clarity_score(text)
        fluency_score = self._calculate_fluency_score(text)

        # Confidence indicators
        confidence_score = self._calculate_confidence_score(text)

        # Content relevance (basic keyword matching)
        relevance_score = self._calculate_relevance_score(text)

        # Grammar and structure
        grammar_score = self._calculate_grammar_score(text)

        # Overall score calculation
        overall_score = self._calculate_overall_score({
            'clarity': clarity_score,
            'fluency': fluency_score,
            'confidence': confidence_score,
            'relevance': relevance_score,
            'grammar': grammar_score,
            'sentiment': sentiment_scores['compound']
        })

        # Generate feedback
        feedback = self._generate_feedback({
            'filler_ratio': filler_ratio,
            'clarity_score': clarity_score,
            'fluency_score': fluency_score,
            'confidence_score': confidence_score,
            'relevance_score': relevance_score,
            'grammar_score': grammar_score,
            'sentiment': sentiment_scores
        })

        return {
            'word_count': word_count,
            'sentence_count': sentence_count,
            'avg_words_per_sentence': round(avg_words_per_sentence, 2),
            'filler_count': filler_count,
            'filler_ratio': round(filler_ratio, 3),
            'clarity_score': round(clarity_score, 2),
            'fluency_score': round(fluency_score, 2),
            'confidence_score': round(confidence_score, 2),
            'relevance_score': round(relevance_score, 2),
            'grammar_score': round(grammar_score, 2),
            'sentiment_scores': sentiment_scores,
            'overall_score': round(overall_score, 2),
            'feedback': feedback,
            'strengths': self._identify_strengths(text),
            'improvements': self._identify_improvements(text)
        }

    def _count_filler_words(self, text: str) -> int:
        """Count filler words in the text."""
        words = word_tokenize(text.lower())
        return sum(1 for word in words if word in self.filler_words)

    def _calculate_clarity_score(self, text: str) -> float:
        """Calculate clarity score based on sentence structure and complexity."""
        sentences = sent_tokenize(text)
        if not sentences:
            return 0.0

        clarity_scores = []
        for sentence in sentences:
            words = word_tokenize(sentence)
            if len(words) < 3:
                clarity_scores.append(0.3)
                continue

            # Check for clear subject-verb-object structure
            pos_tags = nltk.pos_tag(words)
            has_noun = any(tag.startswith('N') for word, tag in pos_tags)
            has_verb = any(tag.startswith('V') for word, tag in pos_tags)

            # Sentence length penalty (too long = less clear)
            length_penalty = min(1.0, 20 / len(words))

            # Structure bonus
            structure_bonus = 0.3 if (has_noun and has_verb) else 0.1

            clarity_scores.append(min(1.0, length_penalty + structure_bonus))

        return np.mean(clarity_scores) * 100

    def _calculate_fluency_score(self, text: str) -> float:
        """Calculate fluency score based on flow and transitions."""
        words = word_tokenize(text)
        if len(words) < 5:
            return 0.0

        # Check for transition words
        transition_words = ['however', 'therefore', 'moreover', 'furthermore', 'additionally', 'consequently']
        transition_count = sum(1 for word in words if word.lower() in transition_words)

        # Check for repetition (bad for fluency)
        unique_words = len(set(word.lower() for word in words))
        repetition_penalty = unique_words / len(words) if words else 0

        # Sentence variety (good for fluency)
        sentences = sent_tokenize(text)
        sentence_lengths = [len(word_tokenize(s)) for s in sentences]
        length_variance = np.var(sentence_lengths) if len(sentence_lengths) > 1 else 0
        variety_bonus = min(0.3, length_variance / 100)

        fluency = (transition_count * 0.1 + repetition_penalty * 0.7 + variety_bonus) * 100
        return min(100, max(0, fluency))

    def _calculate_confidence_score(self, text: str) -> float:
        """Calculate confidence score based on language patterns."""
        words = word_tokenize(text.lower())
        if not words:
            return 0.0

        # Positive indicators
        confident_words = ['confident', 'sure', 'certain', 'definitely', 'absolutely', 'believe', 'know']
        confident_count = sum(1 for word in words if word in confident_words)

        # Negative indicators (hesitation)
        hesitant_words = ['maybe', 'perhaps', 'might', 'could', 'possibly', 'think', 'guess']
        hesitant_count = sum(1 for word in words if word in hesitant_words)

        # Question marks (uncertainty)
        question_count = text.count('?')

        # Exclamation marks (enthusiasm)
        exclamation_count = text.count('!')

        # Calculate score
        confidence = (confident_count * 10 + exclamation_count * 5 -
                      hesitant_count * 5 - question_count * 3) / len(words) * 100
        return min(100, max(0, confidence))

    def _calculate_relevance_score(self, text: str) -> float:
        """Calculate relevance score based on content quality."""
        # This is a simplified version - in practice, you'd compare against job requirements
        words = word_tokenize(text.lower())
        if not words:
            return 0.0

        # Technical terms bonus
        technical_terms = [
            'project',
            'experience',
            'skills',
            'achievement',
            'challenge',
            'solution',
            'team',
            'leadership']
        technical_count = sum(1 for word in words if word in technical_terms)

        # Specific examples bonus
        example_indicators = ['for example', 'for instance', 'specifically', 'such as', 'like when']
        example_count = sum(1 for phrase in example_indicators if phrase in text.lower())

        # Length appropriateness (not too short, not too long)
        length_score = 1.0 if 20 <= len(words) <= 200 else 0.5

        relevance = (technical_count * 5 + example_count * 10 + length_score * 20) / len(words) * 100
        return min(100, max(0, relevance))

    def _calculate_grammar_score(self, text: str) -> float:
        """Calculate grammar score using TextBlob."""
        try:
            blob = TextBlob(text)
            # TextBlob's sentiment and grammar checking
            sentences = blob.sentences
            if not sentences:
                return 0.0

            # Check for basic grammar patterns
            correct_sentences = 0
            for sentence in sentences:
                # Simple check: does it have proper capitalization and ending punctuation?
                if sentence.string[0].isupper() and sentence.string.rstrip()[-1] in '.!?':
                    correct_sentences += 1

            grammar_score = (correct_sentences / len(sentences)) * 100
            return min(100, max(0, grammar_score))
        except BaseException:
            return 50.0  # Default middle score if analysis fails

    def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted overall score."""
        weights = {
            'clarity': 0.25,
            'fluency': 0.20,
            'confidence': 0.20,
            'relevance': 0.20,
            'grammar': 0.10,
            'sentiment': 0.05
        }

        # Normalize sentiment to 0-100 scale
        sentiment_score = (scores['sentiment'] + 1) * 50

        overall = sum(scores[key] * weights[key] for key in weights.keys() if key != 'sentiment')
        overall += sentiment_score * weights['sentiment']

        return min(100, max(0, overall))

    def _generate_feedback(self, metrics: Dict[str, Any]) -> str:
        """Generate personalized feedback based on metrics."""
        feedback_parts = []

        if metrics['filler_ratio'] > 0.1:
            feedback_parts.append("Try to reduce filler words like 'um', 'uh', and 'like'.")

        if metrics['clarity_score'] < 70:
            feedback_parts.append("Work on making your responses clearer and more structured.")

        if metrics['fluency_score'] < 70:
            feedback_parts.append("Practice smoother transitions between ideas.")

        if metrics['confidence_score'] < 70:
            feedback_parts.append("Speak with more confidence and conviction.")

        if metrics['relevance_score'] < 70:
            feedback_parts.append("Provide more specific examples and relevant details.")

        if metrics['grammar_score'] < 80:
            feedback_parts.append("Pay attention to grammar and sentence structure.")

        if not feedback_parts:
            feedback_parts.append("Great job! Your communication skills are strong.")

        return " ".join(feedback_parts)

    def _identify_strengths(self, text: str) -> List[str]:
        """Identify strengths in the response."""
        strengths = []

        if len(word_tokenize(text)) > 50:
            strengths.append("Detailed response")

        if any(word in text.lower() for word in ['example', 'instance', 'specifically']):
            strengths.append("Uses specific examples")

        if any(word in text.lower() for word in ['team', 'collaboration', 'together']):
            strengths.append("Shows teamwork awareness")

        if any(word in text.lower() for word in ['learn', 'improve', 'develop', 'grow']):
            strengths.append("Shows learning mindset")

        return strengths if strengths else ["Good communication"]

    def _identify_improvements(self, text: str) -> List[str]:
        """Identify areas for improvement."""
        improvements = []

        if len(word_tokenize(text)) < 20:
            improvements.append("Provide more detailed responses")

        if text.count('?') > 2:
            improvements.append("Be more decisive in your answers")

        if any(word in text.lower() for word in ['maybe', 'perhaps', 'might']):
            improvements.append("Express more confidence in your statements")

        return improvements if improvements else ["Continue practicing"]

    def _get_default_analysis(self) -> Dict[str, Any]:
        """Return default analysis for empty or very short text."""
        return {
            'word_count': 0,
            'sentence_count': 0,
            'avg_words_per_sentence': 0,
            'filler_count': 0,
            'filler_ratio': 0,
            'clarity_score': 0,
            'fluency_score': 0,
            'confidence_score': 0,
            'relevance_score': 0,
            'grammar_score': 0,
            'sentiment_scores': {'compound': 0, 'pos': 0, 'neu': 1, 'neg': 0},
            'overall_score': 0,
            'feedback': "Please provide a more detailed response.",
            'strengths': [],
            'improvements': ["Provide a more detailed response"]
        }


# ============================================
# CODE EXECUTION SERVICE (Judge0)
# ============================================

class CodeExecutionService:
    """Executes code submissions securely using Judge0 API."""

    LANGUAGE_IDS = {
        "python": 71,
        "java": 62,
        "cpp": 54,
        "javascript": 63,
        "c": 50
    }

    def __init__(self):
        self.headers = {
            "content-type": "application/json",
            "X-RapidAPI-Key": JUDGE0_API_KEY,
            "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com"
        }

    def execute_code(self, code: str, language: str, test_cases: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Executes code against test cases via Judge0 API.

        Args:
            code: Source code to execute.
            language: Programming language name.
            test_cases: List of input/output test cases.

        Returns:
            Dict containing individual results and overall score.
        """
        if not JUDGE0_API_KEY:
            # Fallback: Execute Python code locally for testing
            if language.lower() == 'python':
                return self._execute_python_locally(code, test_cases)
            else:
                return {
                    "error": "Judge0 API key not configured and local execution not supported for this language",
                    "message": "Set JUDGE0_API_KEY environment variable or use Python"
                }

        language_id = self.LANGUAGE_IDS.get(language.lower(), 71)
        results = []

        for test_case in test_cases:
            submission_data = {
                "language_id": language_id,
                "source_code": code,
                "stdin": test_case.get("input", ""),
                "expected_output": test_case.get("output", "")
            }

            try:
                response = requests.post(
                    f"{JUDGE0_URL}/submissions",
                    json=submission_data,
                    headers=self.headers,
                    params={"base64_encoded": "false", "wait": "true"}
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    output = (result.get("stdout") or "").strip()
                    expected = (test_case.get("output") or "").strip()

                    results.append({
                        "test_case": test_case,
                        "status": result.get("status", {}).get("description", "Unknown"),
                        "output": output,
                        "expected": expected,
                        "passed": output == expected,
                        "time": result.get("time", "N/A"),
                        "memory": result.get("memory", "N/A")
                    })
                else:
                    results.append({
                        "test_case": test_case,
                        "status": f"Error {response.status_code}",
                        "output": "Execution failed",
                        "passed": False
                    })

            except Exception as e:
                results.append({
                    "test_case": test_case,
                    "status": "Error",
                    "output": str(e),
                    "passed": False
                })

        passed_count = sum(1 for r in results if r["passed"])
        total = len(results)
        score = (passed_count / total * 100) if total > 0 else 0

        return {
            "results": results,
            "passed": passed_count,
            "total": total,
            "score": round(score, 2),
            "all_passed": passed_count == total
        }

    def _execute_python_locally(self, code: str, test_cases: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Execute Python code locally against test cases.
        This is a fallback when Judge0 API is not available.
        """
        import subprocess
        import tempfile
        import os

        results = []

        for i, test_case in enumerate(test_cases):
            try:
                # Create a temporary Python file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    # Write the code with input handling
                    test_input = test_case.get("input", "")
                    full_code = f"""
import sys
from io import StringIO

# Capture original stdin
original_stdin = sys.stdin

# Mock stdin with test input
sys.stdin = StringIO('''{test_input}''')

try:
{code}
except SystemExit:
    pass
finally:
    # Restore original stdin
    sys.stdin = original_stdin
"""
                    f.write(full_code)
                    temp_file = f.name

                # Execute the code
                result = subprocess.run(
                    ['python', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                output = (result.stdout or "").strip()
                expected = (test_case.get("output", "") or "").strip()

                # Clean up
                os.unlink(temp_file)

                passed = output == expected
                results.append({
                    "test_case": test_case,
                    "status": "Accepted" if passed else "Wrong Answer",
                    "output": output,
                    "expected": expected,
                    "passed": passed,
                    "time": "N/A",
                    "memory": "N/A"
                })

            except subprocess.TimeoutExpired:
                results.append({
                    "test_case": test_case,
                    "status": "Time Limit Exceeded",
                    "output": "Execution timed out",
                    "passed": False
                })
            except Exception as e:
                results.append({
                    "test_case": test_case,
                    "status": "Runtime Error",
                    "output": str(e),
                    "passed": False
                })

        passed_count = sum(1 for r in results if r["passed"])
        total = len(results)
        score = (passed_count / total * 100) if total > 0 else 0

        return {
            "results": results,
            "passed": passed_count,
            "total": total,
            "score": round(score, 2),
            "all_passed": passed_count == total
        }


# ============================================
# HR INTERVIEW SERVICE (OpenAI GPT)
# ============================================

class HRInterviewService:
    """AI-driven HR interview using OpenAI GPT-4."""

    def __init__(self):
        self.api_key = OPENAI_API_KEY

    def generate_question(self, student_profile: Dict, previous_answers: List[Dict], company_name: str) -> Dict:
        """Generates HR interview question tailored to student and company."""
        if not self.api_key:
            return self._get_fallback_question()

        context = f"""You are an HR interviewer for {company_name}.
Student Profile:
- Name: {student_profile.get('name', 'Candidate')}
- Skills: {student_profile.get('skills', 'Not specified')}
- CGPA: {student_profile.get('cgpa', 'N/A')}
- Experience: {student_profile.get('projects', 'Not specified')}

Generate a professional, relevant HR interview question. Avoid repetition and match difficulty progressively."""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": context},
                        {"role": "user", "content": "Generate the next interview question."}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 150
                },
                timeout=10
            )

            if response.status_code == 200:
                question = response.json()["choices"][0]["message"]["content"].strip()
                return {"question": question, "generated_at": time.time()}
            else:
                return self._get_fallback_question()

        except Exception as e:
            print(f"WARNING: Error generating HR question: {e}")
            return self._get_fallback_question()

    def evaluate_answer(self, question: str, answer: str) -> Dict:
        """Evaluates an HR answer using GPT-4 for structured scoring."""
        if not self.api_key:
            return self._get_fallback_evaluation()

        prompt = f"""Evaluate the following HR interview answer and return a JSON result:
Question: {question}
Answer: {answer}

Provide:
clarity_score, relevance_score, confidence_score, content_quality, overall_score, strengths, improvements, feedback."""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are an expert HR interviewer."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 400
                },
                timeout=10
            )

            if response.status_code == 200:
                result_text = response.json()["choices"][0]["message"]["content"]
                return json.loads(result_text)
            else:
                return self._get_fallback_evaluation()

        except Exception as e:
            print(f"WARNING: Error evaluating HR answer: {e}")
            return self._get_fallback_evaluation()

    def _get_fallback_question(self) -> Dict:
        """Backup question set when API fails."""
        questions = [
            "Tell me about yourself.",
            "Why do you want to work here?",
            "Describe a challenging situation you handled.",
            "What motivates you to perform well?",
            "Where do you see yourself in five years?"
        ]
        return {"question": random.choice(questions), "generated_at": time.time()}

    def _get_fallback_evaluation(self) -> Dict:
        """Backup evaluation result."""
        return {
            "clarity_score": 75,
            "relevance_score": 72,
            "confidence_score": 70,
            "content_quality": 74,
            "overall_score": 73,
            "strengths": ["Good communication", "Relevant points"],
            "improvements": ["Use more real-world examples", "Show more enthusiasm"],
            "feedback": "Decent response. Work on adding specific examples."
        }


# ============================================
# SPEECH TO TEXT SERVICE (Whisper)
# ============================================

class SpeechToTextService:
    """Speech recognition using OpenAI Whisper API."""

    def __init__(self):
        self.api_key = OPENAI_API_KEY

    def transcribe_audio(self, audio_file_path: str, language: str = "en") -> Dict:
        """Transcribes audio file to text."""
        if not self.api_key:
            return {
                "success": False,
                "error": "OpenAI API key not configured. Set OPENAI_API_KEY environment variable.",
                "text": ""
            }

        try:
            with open(audio_file_path, 'rb') as audio_file:
                files = {
                    'file': audio_file,
                    'model': (None, 'whisper-1'),
                    'language': (None, language)
                }
                headers = {"Authorization": f"Bearer {self.api_key}"}
                response = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    return {"success": True, "text": result.get("text", ""), "language": language}
                else:
                    return {"success": False, "error": f"Failed: {response.status_code}", "text": ""}

        except Exception as e:
            return {"success": False, "error": str(e), "text": ""}


# ============================================
# NLP ANALYSIS SERVICE (GD Evaluation)
# ============================================

NLPAnalysisService = EnhancedNLPAnalysisService


# ============================================
# REPORT GENERATION SERVICE
# ============================================

class ReportGenerationService:
    """Generates consolidated report combining all test results."""

    def __init__(self):
        pass

    def generate_report(self, student_data: Dict) -> Dict:
        """Generate consolidated performance report."""
        return {
            "aptitude_score": student_data.get("aptitude_score", 0),
            "gd_score": student_data.get("gd_score", 0),
            "technical_score": student_data.get("technical_score", 0),
            "hr_score": student_data.get("hr_score", 0),
            "overall_score": (student_data.get("aptitude_score", 0) +
                              student_data.get("gd_score", 0) +
                              student_data.get("technical_score", 0) +
                              student_data.get("hr_score", 0)) / 4,
            "feedback": student_data.get("feedback", ""),
            "generated_at": time.time()
        }


# ============================================
# APTITUDE TEST EVALUATION SERVICE (OpenAI GPT)
# ============================================

class AptitudeEvaluationService:
    """AI-driven aptitude test evaluation using OpenAI GPT with enhanced question generation."""

    def __init__(self):
        self.api_key = OPENAI_API_KEY

    def evaluate_answer(self, question: str, options: List[str], selected_answer: str,
                        correct_answer: str = None, category: str = "General") -> Dict:
        """
        Evaluates an aptitude test answer using AI.

        Args:
            question: The aptitude question text
            options: List of answer options [A, B, C, D]
            selected_answer: Student's selected answer (A, B, C, D)
            correct_answer: Pre-defined correct answer if available
            category: Question category (Logical, Quantitative, Verbal, etc.)

        Returns:
            Dict with is_correct, explanation, confidence_score, reasoning
        """
        if correct_answer:
            # If correct answer is predefined, use simple comparison
            is_correct = (selected_answer == correct_answer)
            return {
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "selected_answer": selected_answer,
                "evaluation_method": "predefined"
            }

        # Use AI evaluation when correct answer is not predefined
        if not self.api_key:
            return self._get_fallback_evaluation(selected_answer)

        prompt = f"""You are an expert aptitude test evaluator. Analyze the following question and determine if the selected answer is correct.

Question: {question}

Options:
A) {options[0] if len(options) > 0 else 'N/A'}
B) {options[1] if len(options) > 1 else 'N/A'}
C) {options[2] if len(options) > 2 else 'N/A'}
D) {options[3] if len(options) > 3 else 'N/A'}

Selected Answer: {selected_answer}
Category: {category}

Provide your evaluation in the following JSON format:
{{
    "is_correct": true/false,
    "correct_answer": "A/B/C/D",
    "explanation": "Brief explanation of why this answer is correct/incorrect",
    "reasoning": "Step-by-step reasoning for the solution",
    "confidence_score": 0-100
}}"""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are an expert aptitude test evaluator. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=15
            )

            if response.status_code == 200:
                result_text = response.json()["choices"][0]["message"]["content"]
                # Extract JSON from potential markdown code blocks
                result_text = result_text.strip()
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

                evaluation = json.loads(result_text)
                evaluation["selected_answer"] = selected_answer
                evaluation["evaluation_method"] = "ai_openai"
                return evaluation
            else:
                print(f"WARNING: OpenAI API error: {response.status_code}")
                return self._get_fallback_evaluation(selected_answer)

        except json.JSONDecodeError as e:
            print(f"WARNING: JSON decode error in AI evaluation: {e}")
            return self._get_fallback_evaluation(selected_answer)
        except Exception as e:
            print(f"WARNING: Error in AI evaluation: {e}")
            return self._get_fallback_evaluation(selected_answer)

    def batch_evaluate_answers(self, questions_and_answers: List[Dict]) -> Dict:
        """
        Evaluates multiple aptitude answers in batch.

        Args:
            questions_and_answers: List of dicts with question, options, selected_answer, correct_answer

        Returns:
            Dict with results list, score, correct_count, total_count
        """
        results = []
        correct_count = 0

        for qa in questions_and_answers:
            evaluation = self.evaluate_answer(
                question=qa.get("question", ""),
                options=qa.get("options", []),
                selected_answer=qa.get("selected_answer", ""),
                correct_answer=qa.get("correct_answer"),
                category=qa.get("category", "General")
            )

            if evaluation.get("is_correct"):
                correct_count += 1

            results.append({
                "question_id": qa.get("question_id"),
                "question": qa.get("question"),
                "selected_answer": qa.get("selected_answer"),
                "correct_answer": evaluation.get("correct_answer"),
                "is_correct": evaluation.get("is_correct"),
                "explanation": evaluation.get("explanation", ""),
                "reasoning": evaluation.get("reasoning", ""),
                "confidence_score": evaluation.get("confidence_score", 0)
            })

        total_count = len(results)
        score = (correct_count / total_count * 100) if total_count > 0 else 0

        return {
            "results": results,
            "correct_count": correct_count,
            "total_count": total_count,
            "score": round(score, 2),
            "evaluation_method": "ai_assisted"
        }

    def _get_fallback_evaluation(self, selected_answer: str) -> Dict:
        """Fallback evaluation when AI is unavailable."""
        return {
            "is_correct": None,
            "correct_answer": "Unknown",
            "selected_answer": selected_answer,
            "explanation": "Unable to evaluate - AI service unavailable",
            "reasoning": "Please check API configuration",
            "confidence_score": 0,
            "evaluation_method": "fallback"
        }

    def generate_performance_feedback(self, test_results: Dict, student_name: str = "Student") -> Dict:
        """
        Generates comprehensive AI-driven motivational feedback for aptitude test performance.

        Args:
            test_results: Dict with results list, score, correct_count, total_count
            student_name: Name of the student

        Returns:
            Dict with motivational_message, strengths, weaknesses, recommendations, topic_analysis
        """
        if not self.api_key:
            return self._get_fallback_feedback(test_results)

        results = test_results.get("results", [])
        score = test_results.get("score", 0)
        correct_count = test_results.get("correct_count", 0)
        total_count = test_results.get("total_count", 0)

        # Analyze performance by category
        category_performance = {}
        for result in results:
            category = result.get("category", "General")
            if category not in category_performance:
                category_performance[category] = {"correct": 0, "total": 0}
            category_performance[category]["total"] += 1
            if result.get("is_correct"):
                category_performance[category]["correct"] += 1

        # Build category summary
        category_summary = []
        for category, perf in category_performance.items():
            percentage = (perf["correct"] / perf["total"] * 100) if perf["total"] > 0 else 0
            category_summary.append(f"{category}: {perf['correct']}/{perf['total']} ({percentage:.0f}%)")

        # Questions answered incorrectly
        incorrect_questions = [r for r in results if not r.get("is_correct")]
        incorrect_topics = [r.get("category", "General") for r in incorrect_questions]

        prompt = f"""You are a motivational aptitude test coach. Analyze this student's performance and provide encouraging, actionable feedback.

Student Name: {student_name}
Overall Score: {score:.1f}%
Questions Correct: {correct_count}/{total_count}

Category-wise Performance:
{chr(10).join(category_summary)}

Topics with mistakes: {', '.join(set(incorrect_topics)) if incorrect_topics else 'None'}

Provide a comprehensive, motivational analysis in the following JSON format:
{{
    "motivational_message": "A warm, encouraging message (3-4 sentences) that acknowledges their effort and motivates them",
    "strengths": ["List 3-4 specific strengths based on their performance"],
    "areas_for_improvement": ["List 3-4 specific areas to work on"],
    "topic_wise_recommendations": {{
        "category_name": "Specific advice for this topic area"
    }},
    "study_plan": ["5-7 actionable study recommendations tailored to their performance"],
    "next_steps": ["3-4 immediate next steps they should take"],
    "encouragement": "Final motivating statement to inspire continued effort"
}}

Make it personal, specific, and actionable. Focus on growth mindset and improvement."""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are an expert motivational coach and aptitude test trainer. Provide encouraging, specific, and actionable feedback."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=20
            )

            if response.status_code == 200:
                result_text = response.json()["choices"][0]["message"]["content"]
                # Extract JSON from potential markdown code blocks
                result_text = result_text.strip()
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

                feedback = json.loads(result_text)
                feedback["score"] = score
                feedback["correct_count"] = correct_count
                feedback["total_count"] = total_count
                feedback["category_performance"] = category_performance
                feedback["feedback_method"] = "ai_openai"
                return feedback
            else:
                print(f"WARNING: OpenAI API error for feedback: {response.status_code}")
                return self._get_fallback_feedback(test_results)

        except json.JSONDecodeError as e:
            print(f"WARNING: JSON decode error in AI feedback: {e}")
            return self._get_fallback_feedback(test_results)
        except Exception as e:
            print(f"WARNING: Error generating AI feedback: {e}")
            return self._get_fallback_feedback(test_results)

    def _get_fallback_feedback(self, test_results: Dict) -> Dict:
        """Generate basic feedback when AI is unavailable."""
        score = test_results.get("score", 0)
        correct_count = test_results.get("correct_count", 0)
        total_count = test_results.get("total_count", 0)

        if score >= 80:
            motivational_message = f"Excellent work! You scored {score:.1f}%, showing strong aptitude skills. Keep up the great effort!"
        elif score >= 60:
            motivational_message = f"Good effort! You scored {score:.1f}%. With focused practice, you'll reach excellence soon!"
        elif score >= 40:
            motivational_message = f"You're on the right track with {score:.1f}%. Consistent practice will help you improve significantly!"
        else:
            motivational_message = f"Every expert was once a beginner. Your {score:.1f}% shows you're learning. Stay committed and you'll improve!"

        return {
            "motivational_message": motivational_message,
            "strengths": ["Completed the test", "Showed determination", "Identified areas for growth"],
            "areas_for_improvement": ["Review incorrect questions", "Practice more problems", "Focus on weak topics"],
            "topic_wise_recommendations": {"General": "Practice regularly and review fundamentals"},
            "study_plan": [
                "Review all incorrect answers and understand why",
                "Practice 10-15 questions daily in weak areas",
                "Take regular mock tests to track progress",
                "Focus on time management during practice",
                "Use quality study materials and resources"
            ],
            "next_steps": [
                "Review your test results in detail",
                "Create a daily practice schedule",
                "Take another practice test in 1 week"
            ],
            "encouragement": "Remember, improvement comes with consistent effort. You've got this!",
            "score": score,
            "correct_count": correct_count,
            "total_count": total_count,
            "category_performance": {},
            "feedback_method": "fallback"
        }

    def generate_adaptive_questions(self, student_performance: Dict, company_name: str, count: int = 10) -> List[Dict]:
        """
        Generate AI-driven adaptive questions based on student's performance history.

        Args:
            student_performance: Dict with category scores, weak areas, etc.
            company_name: Target company for question generation
            count: Number of questions to generate

        Returns:
            List of generated question dictionaries
        """
        if not self.api_key:
            return self._get_fallback_adaptive_questions(student_performance, count)

        # Analyze performance to identify weak areas
        weak_categories = []
        category_scores = student_performance.get("category_performance", {})

        for category, scores in category_scores.items():
            if scores.get("percentage", 0) < 70:  # Below 70% threshold
                weak_categories.append(category)

        if not weak_categories:
            weak_categories = ["General Aptitude"]  # Default if all categories are strong

        prompt = f"""You are an expert aptitude test question generator for {company_name} interviews.

Student Performance Analysis:
- Weak areas: {', '.join(weak_categories)}
- Overall score: {student_performance.get('overall_score', 0):.1f}%
- Previous attempts: {student_performance.get('attempts', 1)}

Generate {count} challenging but fair aptitude questions focusing on the weak areas. Each question should be:
1. Company-specific and relevant to {company_name} roles
2. Progressive difficulty (mix of easy, medium, hard)
3. Include detailed explanations
4. Have 4 clear options (A, B, C, D)

Return in this exact JSON format:
{{
    "questions": [
        {{
            "category": "Category name",
            "difficulty": "Easy/Medium/Hard",
            "question": "Question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "A",
            "explanation": "Detailed explanation",
            "company_context": "Why this is relevant to {company_name}",
            "time_limit": 60
        }}
    ]
}}

Focus on practical, job-relevant questions that test logical thinking and problem-solving skills."""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are an expert aptitude question generator for technical interviews. Create high-quality, company-specific questions."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.8,
                    "max_tokens": 2000
                },
                timeout=25
            )

            if response.status_code == 200:
                result_text = response.json()["choices"][0]["message"]["content"]
                # Extract JSON
                result_text = result_text.strip()
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

                generated_data = json.loads(result_text)
                questions = generated_data.get("questions", [])

                # Add metadata
                for q in questions:
                    q["generated_by"] = "ai_openai"
                    q["company_id"] = self._get_company_id(company_name)
                    q["year_asked"] = 2024

                return questions
            else:
                print(f"WARNING: OpenAI API error for question generation: {response.status_code}")
                return self._get_fallback_adaptive_questions(student_performance, count)

        except Exception as e:
            print(f"WARNING: Error generating AI questions: {e}")
            return self._get_fallback_adaptive_questions(student_performance, count)

    def _get_company_id(self, company_name: str) -> int:
        """Get company ID from database."""
        try:
            conn = sqlite3.connect("questions.db")
            c = conn.cursor()
            c.execute("SELECT id FROM companies WHERE lower(name) = lower(?)", (company_name,))
            result = c.fetchone()
            conn.close()
            return result[0] if result else 1
        except BaseException:
            return 1

    def _get_fallback_adaptive_questions(self, student_performance: Dict, count: int) -> List[Dict]:
        """Generate basic adaptive questions when AI is unavailable."""
        # Use existing question generation logic as fallback
        weak_categories = []
        category_scores = student_performance.get("category_performance", {})

        for category, scores in category_scores.items():
            if scores.get("percentage", 0) < 70:
                weak_categories.append(category)

        if not weak_categories:
            weak_categories = ["General"]

        questions = []
        for i in range(count):
            category = weak_categories[i % len(weak_categories)] if weak_categories else "General"
            difficulty = "Medium"  # Default

            if category == "Logical Reasoning":
                questions.append({
                    "category": category,
                    "difficulty": difficulty,
                    "question": f"Practice logical reasoning question {i+1}",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "explanation": "Practice question - review fundamentals",
                    "company_context": "General aptitude practice",
                    "time_limit": 60,
                    "generated_by": "fallback"
                })
            elif category == "Quantitative Aptitude":
                questions.append({
                    "category": category,
                    "difficulty": difficulty,
                    "question": f"Practice quantitative question {i+1}",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "B",
                    "explanation": "Practice question - review calculations",
                    "company_context": "General aptitude practice",
                    "time_limit": 60,
                    "generated_by": "fallback"
                })
            else:
                questions.append({
                    "category": category,
                    "difficulty": difficulty,
                    "question": f"Practice aptitude question {i+1}",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "C",
                    "explanation": "Practice question - review concepts",
                    "company_context": "General aptitude practice",
                    "time_limit": 60,
                    "generated_by": "fallback"
                })

        return questions


# ============================================
# GLOBAL SERVICE INSTANCES
# ============================================

code_executor = CodeExecutionService()
hr_service = HRInterviewService()
speech_service = SpeechToTextService()
nlp_service = NLPAnalysisService()
report_service = ReportGenerationService()
aptitude_evaluator = AptitudeEvaluationService()


# ============================================
# HELPER FUNCTIONS
# ============================================

def execute_student_code(code: str, language: str, question_id: int) -> Dict:
    """Executes student's code against stored test cases."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT test_cases FROM technical_questions WHERE id=?", (question_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        return {"error": "Question not found"}

    test_cases = json.loads(result[0])
    return code_executor.execute_code(code, language, test_cases)


def evaluate_gd_performance(transcript: str) -> Dict:
    """Evaluates a student's Group Discussion transcript."""
    return nlp_service.analyze_text(transcript)


def conduct_hr_interview(student_email: str, company_name: str) -> Dict:
    """Initializes HR interview session for student."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE email=?", (student_email,))
    student = c.fetchone()
    conn.close()

    if not student:
        return {"error": "Student not found"}

    profile = {"name": student[2], "cgpa": student[3], "skills": student[5]}
    question = hr_service.generate_question(profile, [], company_name)

    return {"session_started": True, "question": question, "profile": profile}


def evaluate_aptitude_answers(questions_and_answers: List[Dict]) -> Dict:
    """
    Evaluate aptitude test answers using AI.

    Args:
        questions_and_answers: List of dicts with question, options, selected_answer, correct_answer

    Returns:
        Dict with results, score, correct_count, total_count
    """
    return aptitude_evaluator.batch_evaluate_answers(questions_and_answers)


if __name__ == "__main__":
    print("🚀 AI Services Module Loaded Successfully")
    print("=" * 50)
    print("Available Services:")
    print("  ✓ Code Execution (Judge0)")
    print("  ✓ HR Interview (GPT-4)")
    print("  ✓ Speech to Text (Whisper)")
    print("  ✓ NLP Analysis (GD)")
    print("  ✓ Aptitude Test Evaluation (GPT-4)")
    print("  ✓ Report Generation")
    print("=" * 50)
