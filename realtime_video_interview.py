"""
Real-Time AI Video Interview System
- Live facial expression analysis
- Real-time emotion detection
- Speech-to-text transcription
- AI interviewer with adaptive questioning
"""

import cv2
import numpy as np
import base64
import time
from datetime import datetime
from collections import deque

# Try to import advanced libraries (install if needed)
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("! DeepFace not available. Install: pip install deepface")

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("! SpeechRecognition not available. Install: pip install SpeechRecognition")

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("! pyttsx3 not available. Install: pip install pyttsx3")


class RealtimeVideoAnalyzer:
    """Analyzes video frames in real-time for facial expressions and emotions"""

    def __init__(self):
        self.emotion_history = deque(maxlen=30)  # Last 30 frames (1 second at 30fps)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    def analyze_frame(self, frame_data):
        """
        Analyze a single video frame

        Args:
            frame_data: Base64 encoded image or numpy array

        Returns:
            dict with analysis results
        """
        try:
            # Decode frame if base64
            if isinstance(frame_data, str):
                frame = self._decode_base64_frame(frame_data)
            else:
                frame = frame_data

            if frame is None:
                return self._get_default_analysis()

            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

            if len(faces) == 0:
                return {
                    "face_detected": False,
                    "emotion": "unknown",
                    "confidence": 0,
                    "eye_contact": False,
                    "face_position": "not_detected",
                    "warnings": ["No face detected - please look at the camera"]
                }

            # Analyze first detected face
            (x, y, w, h) = faces[0]
            face_roi = frame[y:y + h, x:x + w]

            # Emotion detection using DeepFace (if available)
            emotion_result = self._detect_emotion_deepface(face_roi)

            # Eye contact detection
            eye_contact = self._detect_eye_contact(gray[y:y + h, x:x + w])

            # Face position analysis
            face_position = self._analyze_face_position(frame, x, y, w, h)

            # Update emotion history
            self.emotion_history.append(emotion_result['emotion'])

            # Calculate dominant emotion over time
            dominant_emotion = self._get_dominant_emotion()

            return {
                "face_detected": True,
                "emotion": emotion_result['emotion'],
                "emotion_confidence": emotion_result['confidence'],
                "dominant_emotion": dominant_emotion,
                "eye_contact": eye_contact,
                "face_position": face_position,
                "face_box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "timestamp": datetime.now().isoformat(),
                "warnings": self._generate_warnings(eye_contact, face_position)
            }

        except Exception as e:
            print(f"Error analyzing frame: {e}")
            return self._get_default_analysis()

    def _decode_base64_frame(self, base64_data):
        """Decode base64 image to numpy array"""
        try:
            # Remove data URL prefix if present
            if 'base64,' in base64_data:
                base64_data = base64_data.split('base64,')[1]

            img_bytes = base64.b64decode(base64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            print(f"Error decoding frame: {e}")
            return None

    def _detect_emotion_deepface(self, face_roi):
        """Detect emotion using DeepFace library"""
        if not DEEPFACE_AVAILABLE:
            return self._detect_emotion_simple(face_roi)

        try:
            # DeepFace emotion detection
            result = DeepFace.analyze(face_roi, actions=['emotion'], enforce_detection=False)

            if isinstance(result, list):
                result = result[0]

            emotion = result['dominant_emotion']
            confidence = result['emotion'][emotion]

            return {
                "emotion": emotion,
                "confidence": round(confidence, 2),
                "all_emotions": result['emotion']
            }
        except Exception as e:
            print(f"DeepFace error: {e}")
            return self._detect_emotion_simple(face_roi)

    def _detect_emotion_simple(self, face_roi):
        """Simple rule-based emotion detection (fallback)"""
        # Placeholder - basic brightness/contrast analysis
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray_face)

        # Very basic heuristic
        if brightness > 150:
            emotion = "happy"
            confidence = 0.6
        elif brightness < 80:
            emotion = "sad"
            confidence = 0.5
        else:
            emotion = "neutral"
            confidence = 0.7

        return {
            "emotion": emotion,
            "confidence": confidence,
            "all_emotions": {emotion: confidence}
        }

    def _detect_eye_contact(self, face_gray):
        """Detect if candidate is making eye contact"""
        try:
            eyes = self.eye_cascade.detectMultiScale(face_gray, 1.1, 3)
            # If 2 eyes detected in upper half of face, consider it eye contact
            return len(eyes) >= 2
        except BaseException:
            return False

    def _analyze_face_position(self, frame, x, y, w, h):
        """Analyze face position relative to frame"""
        frame_h, frame_w = frame.shape[:2]
        face_center_x = x + w // 2
        face_center_y = y + h // 2

        # Calculate position
        if face_center_x < frame_w * 0.4:
            h_pos = "left"
        elif face_center_x > frame_w * 0.6:
            h_pos = "right"
        else:
            h_pos = "center"

        if face_center_y < frame_h * 0.4:
            v_pos = "top"
        elif face_center_y > frame_h * 0.6:
            v_pos = "bottom"
        else:
            v_pos = "center"

        if h_pos == "center" and v_pos == "center":
            return "centered"
        else:
            return f"{v_pos}_{h_pos}"

    def _get_dominant_emotion(self):
        """Calculate dominant emotion from recent history"""
        if not self.emotion_history:
            return "neutral"

        # Count emotions
        emotion_counts = {}
        for emotion in self.emotion_history:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        # Get most frequent
        dominant = max(emotion_counts.items(), key=lambda x: x[1])
        return dominant[0]

    def _generate_warnings(self, eye_contact, face_position):
        """Generate real-time warnings for candidate"""
        warnings = []

        if not eye_contact:
            warnings.append("👁️ Maintain eye contact with the camera")

        if face_position != "centered":
            warnings.append("📍 Please center your face in the frame")

        return warnings

    def _get_default_analysis(self):
        """Return default analysis when detection fails"""
        return {
            "face_detected": False,
            "emotion": "unknown",
            "confidence": 0,
            "eye_contact": False,
            "face_position": "unknown",
            "warnings": ["Camera analysis unavailable"]
        }


class RealtimeSpeechRecognizer:
    """Real-time speech recognition and analysis"""

    def __init__(self):
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 4000
            self.recognizer.dynamic_energy_threshold = True
        else:
            self.recognizer = None

        self.transcript = ""
        self.filler_words = ['um', 'uh', 'like', 'you know', 'so', 'well', 'actually']
        self.filler_count = 0
        self.word_count = 0

    def process_audio_chunk(self, audio_data):
        """
        Process audio chunk and return text

        Args:
            audio_data: Audio data bytes or AudioData object

        Returns:
            dict with transcription and analysis
        """
        if not SPEECH_RECOGNITION_AVAILABLE or self.recognizer is None:
            return {
                "text": "",
                "success": False,
                "error": "Speech recognition not available"
            }

        try:
            # Recognize speech using Google Speech Recognition
            text = self.recognizer.recognize_google(audio_data)

            # Analyze text
            analysis = self._analyze_speech(text)

            # Update transcript
            self.transcript += " " + text

            return {
                "text": text,
                "success": True,
                "analysis": analysis,
                "total_words": self.word_count,
                "filler_words": self.filler_count
            }
        except sr.UnknownValueError:
            return {
                "text": "",
                "success": False,
                "error": "Could not understand audio"
            }
        except sr.RequestError as e:
            return {
                "text": "",
                "success": False,
                "error": f"Recognition service error: {e}"
            }

    def _analyze_speech(self, text):
        """Analyze speech for quality metrics"""
        words = text.lower().split()
        self.word_count += len(words)

        # Count filler words
        fillers_in_text = sum(1 for word in words if word in self.filler_words)
        self.filler_count += fillers_in_text

        # Calculate metrics
        filler_ratio = self.filler_count / max(self.word_count, 1)

        return {
            "word_count": len(words),
            "filler_count": fillers_in_text,
            "filler_ratio": round(filler_ratio, 3),
            "clarity_score": round((1 - filler_ratio) * 100, 1)
        }

    def get_full_transcript(self):
        """Get complete transcript"""
        return self.transcript.strip()

    def reset(self):
        """Reset transcript and counters"""
        self.transcript = ""
        self.filler_count = 0
        self.word_count = 0


class AIInterviewer:
    """AI Interviewer with text-to-speech and adaptive questioning"""

    def __init__(self):
        if TTS_AVAILABLE:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)  # Speed
            self.engine.setProperty('volume', 0.9)  # Volume
        else:
            self.engine = None

        self.current_question_index = 0
        self.questions = []
        self.conversation_history = []

    def load_questions(self, questions_list):
        """Load interview questions"""
        self.questions = questions_list
        self.current_question_index = 0

    def ask_question(self, question_text, use_voice=False):
        """
        Ask a question (with optional voice)

        Args:
            question_text: The question to ask
            use_voice: Whether to use text-to-speech

        Returns:
            dict with question info
        """
        if use_voice and self.engine:
            # Speak the question
            self.engine.say(question_text)
            self.engine.runAndWait()

        self.conversation_history.append({
            "type": "question",
            "text": question_text,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "question": question_text,
            "question_number": self.current_question_index + 1,
            "total_questions": len(self.questions),
            "timestamp": datetime.now().isoformat()
        }

    def get_next_question(self, previous_answer=None, emotion_state=None):
        """
        Get next question (adaptive based on previous answer and emotion)

        Args:
            previous_answer: The candidate's previous answer
            emotion_state: Current emotional state of candidate

        Returns:
            Next question or None if interview complete
        """
        if self.current_question_index >= len(self.questions):
            return None

        # Get base question
        question = self.questions[self.current_question_index]

        # Adapt based on emotion (make supportive if nervous)
        if emotion_state in ['sad', 'fear', 'angry']:
            adapted_question = self._make_question_supportive(question)
        else:
            adapted_question = question

        self.current_question_index += 1
        return adapted_question

    def _make_question_supportive(self, question):
        """Make question more supportive for nervous candidates"""
        supportive_prefix = "Take your time. "
        return supportive_prefix + question

    def provide_feedback(self, answer_quality, emotion, use_voice=False):
        """
        Provide real-time feedback

        Args:
            answer_quality: Score 0-100
            emotion: Detected emotion
            use_voice: Whether to speak feedback

        Returns:
            Feedback message
        """
        if answer_quality >= 80:
            feedback = "Excellent answer! Very well articulated."
        elif answer_quality >= 60:
            feedback = "Good response. You're doing well."
        elif answer_quality >= 40:
            feedback = "That's okay. Try to provide more specific examples."
        else:
            feedback = "Take your time and think through your answer."

        # Adjust based on emotion
        if emotion in ['fear', 'sad']:
            feedback = "You're doing fine. " + feedback

        if use_voice and self.engine:
            self.engine.say(feedback)
            self.engine.runAndWait()

        self.conversation_history.append({
            "type": "feedback",
            "text": feedback,
            "timestamp": datetime.now().isoformat()
        })

        return feedback


class RealtimeInterviewSession:
    """Manages complete real-time interview session"""

    def __init__(self, student_email, company_name, questions):
        self.student_email = student_email
        self.company_name = company_name
        self.session_id = f"{student_email}_{int(time.time())}"

        # Initialize components
        self.video_analyzer = RealtimeVideoAnalyzer()
        self.speech_recognizer = RealtimeSpeechRecognizer()
        self.ai_interviewer = AIInterviewer()

        # Load questions
        self.ai_interviewer.load_questions(questions)

        # Session data
        self.start_time = time.time()
        self.current_question = None
        self.current_answer = ""
        self.session_data = {
            "video_analysis": [],
            "speech_analysis": [],
            "emotions_timeline": [],
            "answers": []
        }

    def start_interview(self):
        """Start the interview session"""
        first_question = self.ai_interviewer.get_next_question()
        if first_question:
            self.current_question = self.ai_interviewer.ask_question(first_question, use_voice=False)
            return self.current_question
        return None

    def process_video_frame(self, frame_data):
        """Process incoming video frame"""
        analysis = self.video_analyzer.analyze_frame(frame_data)

        # Store analysis
        self.session_data['video_analysis'].append(analysis)
        self.session_data['emotions_timeline'].append({
            "timestamp": time.time() - self.start_time,
            "emotion": analysis.get('emotion', 'unknown'),
            "confidence": analysis.get('emotion_confidence', 0)
        })

        return analysis

    def process_audio_chunk(self, audio_data):
        """Process incoming audio chunk"""
        result = self.speech_recognizer.process_audio_chunk(audio_data)

        if result.get('success'):
            self.current_answer += " " + result['text']
            self.session_data['speech_analysis'].append(result)

        return result

    def submit_answer(self):
        """Submit current answer and move to next question"""
        # Analyze answer quality
        from ai_service import EnhancedNLPAnalysisService
        nlp = EnhancedNLPAnalysisService()
        answer_analysis = nlp.analyze_text(self.current_answer)

        # Get dominant emotion during answer
        dominant_emotion = self.video_analyzer._get_dominant_emotion()

        # Store answer data
        self.session_data['answers'].append({
            "question": self.current_question,
            "answer": self.current_answer,
            "nlp_analysis": answer_analysis,
            "dominant_emotion": dominant_emotion,
            "duration": time.time() - self.start_time
        })

        # Get AI feedback
        feedback = self.ai_interviewer.provide_feedback(
            answer_analysis.get('overall_score', 50),
            dominant_emotion,
            use_voice=False
        )

        # Get next question
        next_question = self.ai_interviewer.get_next_question(
            self.current_answer,
            dominant_emotion
        )

        # Reset for next question
        self.current_answer = ""
        self.speech_recognizer.reset()

        if next_question:
            self.current_question = self.ai_interviewer.ask_question(next_question, use_voice=False)
            return {
                "feedback": feedback,
                "next_question": self.current_question,
                "interview_complete": False
            }
        else:
            return {
                "feedback": feedback,
                "next_question": None,
                "interview_complete": True,
                "final_report": self.generate_final_report()
            }

    def generate_final_report(self):
        """Generate comprehensive interview report"""
        total_duration = time.time() - self.start_time

        # Calculate averages
        avg_emotion_confidence = np.mean([
            e['confidence'] for e in self.session_data['emotions_timeline']
        ]) if self.session_data['emotions_timeline'] else 0

        # Dominant emotions
        all_emotions = [e['emotion'] for e in self.session_data['emotions_timeline']]
        emotion_counts = {}
        for emotion in all_emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        return {
            "session_id": self.session_id,
            "student_email": self.student_email,
            "company_name": self.company_name,
            "total_duration": round(total_duration, 2),
            "questions_answered": len(self.session_data['answers']),
            "average_emotion_confidence": round(avg_emotion_confidence, 2),
            "emotion_distribution": emotion_counts,
            "answers": self.session_data['answers'],
            "overall_performance": self._calculate_overall_performance()
        }

    def _calculate_overall_performance(self):
        """Calculate overall interview performance score"""
        if not self.session_data['answers']:
            return 0

        scores = [ans['nlp_analysis'].get('overall_score', 0) for ans in self.session_data['answers']]
        return round(np.mean(scores), 2)


# Global sessions storage
active_sessions = {}


def create_realtime_session(student_email, company_name, questions):
    """Create a new real-time interview session"""
    session = RealtimeInterviewSession(student_email, company_name, questions)
    active_sessions[session.session_id] = session
    return session


def get_session(session_id):
    """Get an active session"""
    return active_sessions.get(session_id)


def end_session(session_id):
    """End and remove a session"""
    if session_id in active_sessions:
        del active_sessions[session_id]
