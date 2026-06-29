"""
Real-Time Group Discussion (GD) System
- Multi-participant video analysis
- Turn-taking detection
- Speaking time tracking
- Interruption detection
- Leadership & teamwork analysis
- Real-time comparative metrics
"""

import time
from collections import deque, defaultdict

# Import video analyzer from HR module
from realtime_video_interview import RealtimeVideoAnalyzer

try:
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

try:
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False


class MultiParticipantAnalyzer:
    """Analyzes multiple participant video streams simultaneously"""

    def __init__(self, participant_names):
        self.participants = {name: RealtimeVideoAnalyzer() for name in participant_names}
        self.participant_data = {name: {
            'emotions': deque(maxlen=100),
            'face_detected_count': 0,
            'total_frames': 0,
            'eye_contact_count': 0,
            'warnings': []
        } for name in participant_names}

    def analyze_participant_frame(self, participant_name, frame_data):
        """
        Analyze frame for specific participant

        Args:
            participant_name: Name of participant
            frame_data: Base64 encoded frame

        Returns:
            Analysis results
        """
        if participant_name not in self.participants:
            return {"error": "Participant not found"}

        # Analyze frame
        analyzer = self.participants[participant_name]
        analysis = analyzer.analyze_frame(frame_data)

        # Update participant data
        data = self.participant_data[participant_name]
        data['total_frames'] += 1

        if analysis.get('face_detected'):
            data['face_detected_count'] += 1
            data['emotions'].append(analysis.get('emotion', 'neutral'))

            if analysis.get('eye_contact'):
                data['eye_contact_count'] += 1

        # Add participant context
        analysis['participant_name'] = participant_name
        analysis['engagement_score'] = self._calculate_engagement(participant_name)

        return analysis

    def _calculate_engagement(self, participant_name):
        """Calculate engagement score for participant"""
        data = self.participant_data[participant_name]

        if data['total_frames'] == 0:
            return 0

        # Face detection rate
        face_rate = data['face_detected_count'] / data['total_frames']

        # Eye contact rate
        eye_contact_rate = data['eye_contact_count'] / max(data['face_detected_count'], 1)

        # Emotion variety (engaged people show varied emotions)
        unique_emotions = len(set(data['emotions']))
        emotion_variety = min(unique_emotions / 4, 1.0)  # Max 4 different emotions

        # Combined score
        engagement = (face_rate * 0.4 + eye_contact_rate * 0.4 + emotion_variety * 0.2) * 100

        return round(engagement, 2)

    def get_all_participants_summary(self):
        """Get summary for all participants"""
        summary = {}

        for name in self.participants.keys():
            data = self.participant_data[name]
            analyzer = self.participants[name]

            summary[name] = {
                'engagement_score': self._calculate_engagement(name),
                'dominant_emotion': analyzer._get_dominant_emotion(),
                'face_detected_rate': round(
                    data['face_detected_count'] / max(data['total_frames'], 1) * 100, 1
                ),
                'eye_contact_rate': round(
                    data['eye_contact_count'] / max(data['face_detected_count'], 1) * 100, 1
                ),
                'total_frames_analyzed': data['total_frames']
            }

        return summary


class TurnTakingDetector:
    """Detects who is speaking and manages turn-taking"""

    def __init__(self, participant_names):
        self.participants = participant_names
        self.current_speaker = None
        self.speaking_history = []
        self.turn_start_time = None

        # Per-participant metrics
        self.speaking_time = defaultdict(float)
        self.turn_count = defaultdict(int)
        self.interruptions = defaultdict(int)
        self.last_speaker = None

    def detect_speaker(self, audio_activity):
        """
        Detect who is currently speaking

        Args:
            audio_activity: Dict {participant_name: bool} indicating who's speaking

        Returns:
            Current speaker or None
        """
        # Find who's speaking now
        active_speakers = [name for name, is_active in audio_activity.items() if is_active]

        now = time.time()

        # Handle turn changes
        if len(active_speakers) == 0:
            # Silence - end current turn
            if self.current_speaker and self.turn_start_time:
                duration = now - self.turn_start_time
                self.speaking_time[self.current_speaker] += duration

                self.speaking_history.append({
                    'speaker': self.current_speaker,
                    'duration': duration,
                    'start_time': self.turn_start_time,
                    'end_time': now
                })

            self.current_speaker = None
            self.turn_start_time = None

        elif len(active_speakers) == 1:
            # Single speaker
            new_speaker = active_speakers[0]

            if new_speaker != self.current_speaker:
                # New turn started
                if self.current_speaker and self.turn_start_time:
                    # End previous turn
                    duration = now - self.turn_start_time
                    self.speaking_time[self.current_speaker] += duration

                    self.speaking_history.append({
                        'speaker': self.current_speaker,
                        'duration': duration,
                        'start_time': self.turn_start_time,
                        'end_time': now
                    })

                # Start new turn
                self.current_speaker = new_speaker
                self.turn_start_time = now
                self.turn_count[new_speaker] += 1
                self.last_speaker = new_speaker

        else:
            # Multiple people speaking - interruption!
            for speaker in active_speakers:
                if speaker != self.current_speaker:
                    self.interruptions[speaker] += 1

        return self.current_speaker

    def get_speaking_stats(self):
        """Get speaking time statistics"""
        total_time = sum(self.speaking_time.values())

        stats = {}
        for participant in self.participants:
            speaking_time = self.speaking_time[participant]

            stats[participant] = {
                'speaking_time': round(speaking_time, 2),
                'speaking_percentage': round(speaking_time / max(total_time, 1) * 100, 1),
                'turn_count': self.turn_count[participant],
                'interruptions': self.interruptions[participant],
                'avg_turn_duration': round(
                    speaking_time / max(self.turn_count[participant], 1), 2
                )
            }

        return stats

    def get_turn_distribution(self):
        """Get turn distribution fairness score"""
        stats = self.get_speaking_stats()
        percentages = [s['speaking_percentage'] for s in stats.values()]

        # Ideal is equal distribution
        ideal_percentage = 100 / len(self.participants)

        # Calculate variance from ideal
        variance = sum(abs(p - ideal_percentage) for p in percentages) / len(self.participants)

        # Fairness score (100 = perfect equality, 0 = one person dominated)
        fairness_score = max(0, 100 - variance)

        return round(fairness_score, 2)


class LeadershipAnalyzer:
    """Analyzes leadership behaviors in group discussion"""

    def __init__(self, participant_names):
        self.participants = participant_names
        self.leadership_scores = defaultdict(float)
        self.teamwork_scores = defaultdict(float)

        # Track leadership behaviors
        self.initiated_topics = defaultdict(int)
        self.summarized_points = defaultdict(int)
        self.asked_others = defaultdict(int)
        self.built_on_ideas = defaultdict(int)
        self.resolved_conflicts = defaultdict(int)

    def analyze_statement(self, participant, statement_text):
        """
        Analyze a statement for leadership/teamwork indicators

        Args:
            participant: Name of participant
            statement_text: What they said

        Returns:
            Leadership/teamwork behaviors detected
        """
        text_lower = statement_text.lower()
        behaviors = []

        # Leadership indicators
        leadership_phrases = {
            'initiated': ['i suggest', 'i propose', 'let\'s discuss', 'what if we', 'i think we should'],
            'summarized': ['to summarize', 'in summary', 'what we\'ve discussed', 'key points are'],
            'invited': ['what do you think', 'do you agree', 'what\'s your opinion', 'anyone else'],
            'decided': ['let\'s conclude', 'we should decide', 'final decision', 'let\'s agree on']
        }

        for behavior, phrases in leadership_phrases.items():
            if any(phrase in text_lower for phrase in phrases):
                if behavior == 'initiated':
                    self.initiated_topics[participant] += 1
                    self.leadership_scores[participant] += 2.0
                    behaviors.append('topic_initiation')
                elif behavior == 'summarized':
                    self.summarized_points[participant] += 1
                    self.leadership_scores[participant] += 3.0
                    behaviors.append('summarization')
                elif behavior == 'invited':
                    self.asked_others[participant] += 1
                    self.teamwork_scores[participant] += 2.0
                    behaviors.append('inclusive')
                elif behavior == 'decided':
                    self.leadership_scores[participant] += 2.5
                    behaviors.append('decision_making')

        # Teamwork indicators
        teamwork_phrases = {
            'agreement': ['i agree with', 'good point', 'exactly', 'you\'re right'],
            'building': ['building on that', 'adding to', 'also', 'furthermore'],
            'disagreement_polite': ['i see your point but', 'respectfully', 'another perspective']
        }

        for behavior, phrases in teamwork_phrases.items():
            if any(phrase in text_lower for phrase in phrases):
                if behavior == 'agreement':
                    self.teamwork_scores[participant] += 1.5
                    behaviors.append('supportive')
                elif behavior == 'building':
                    self.built_on_ideas[participant] += 1
                    self.teamwork_scores[participant] += 2.0
                    behaviors.append('collaborative')
                elif behavior == 'disagreement_polite':
                    self.teamwork_scores[participant] += 1.0
                    behaviors.append('respectful')

        return behaviors

    def get_leadership_ranking(self):
        """Get leadership ranking for all participants"""
        rankings = []

        for participant in self.participants:
            leadership = self.leadership_scores[participant]
            teamwork = self.teamwork_scores[participant]

            # Combined score with weights
            overall_score = leadership * 0.6 + teamwork * 0.4

            rankings.append({
                'participant': participant,
                'leadership_score': round(leadership, 2),
                'teamwork_score': round(teamwork, 2),
                'overall_score': round(overall_score, 2),
                'initiated_topics': self.initiated_topics[participant],
                'summarized': self.summarized_points[participant],
                'invited_others': self.asked_others[participant],
                'built_on_ideas': self.built_on_ideas[participant]
            })

        # Sort by overall score
        rankings.sort(key=lambda x: x['overall_score'], reverse=True)

        return rankings


class RealtimeGDSession:
    """Manages complete real-time group discussion session"""

    def __init__(self, session_id, topic, participants, duration_minutes=10):
        self.session_id = session_id
        self.topic = topic
        self.participants = participants
        self.duration_minutes = duration_minutes
        self.start_time = time.time()

        # Initialize analyzers
        self.video_analyzer = MultiParticipantAnalyzer(participants)
        self.turn_detector = TurnTakingDetector(participants)
        self.leadership_analyzer = LeadershipAnalyzer(participants)

        # Session data
        self.transcripts = defaultdict(list)  # Per-participant transcripts
        self.statements = []  # All statements in order
        self.current_audio_activity = {name: False for name in participants}

    def process_video_frame(self, participant_name, frame_data):
        """Process video frame for a participant"""
        return self.video_analyzer.analyze_participant_frame(participant_name, frame_data)

    def process_audio_activity(self, participant_name, is_speaking):
        """Update audio activity for participant"""
        self.current_audio_activity[participant_name] = is_speaking
        current_speaker = self.turn_detector.detect_speaker(self.current_audio_activity)
        return current_speaker

    def add_statement(self, participant_name, text):
        """Add a spoken statement"""
        timestamp = time.time() - self.start_time

        # Store statement
        statement = {
            'participant': participant_name,
            'text': text,
            'timestamp': timestamp
        }
        self.statements.append(statement)
        self.transcripts[participant_name].append(text)

        # Analyze for leadership/teamwork
        behaviors = self.leadership_analyzer.analyze_statement(participant_name, text)
        statement['behaviors'] = behaviors

        return statement

    def get_real_time_stats(self):
        """Get real-time statistics for dashboard"""
        elapsed = time.time() - self.start_time

        return {
            'elapsed_time': round(elapsed, 2),
            'remaining_time': max(0, self.duration_minutes * 60 - elapsed),
            'total_statements': len(self.statements),
            'current_speaker': self.turn_detector.current_speaker,
            'speaking_stats': self.turn_detector.get_speaking_stats(),
            'turn_fairness': self.turn_detector.get_turn_distribution(),
            'participant_engagement': self.video_analyzer.get_all_participants_summary(),
            'leadership_ranking': self.leadership_analyzer.get_leadership_ranking()
        }

    def generate_final_report(self):
        """Generate comprehensive GD report"""
        total_duration = time.time() - self.start_time

        # Get all stats
        speaking_stats = self.turn_detector.get_speaking_stats()
        engagement = self.video_analyzer.get_all_participants_summary()
        leadership = self.leadership_analyzer.get_leadership_ranking()

        # Generate per-participant reports
        participant_reports = []

        for participant in self.participants:
            report = {
                'participant': participant,
                'speaking_stats': speaking_stats[participant],
                'engagement': engagement[participant],
                'leadership_data': next((item for item in leadership if item['participant'] == participant), {}),
                'transcript': ' '.join(self.transcripts[participant]),
                'total_statements': len(self.transcripts[participant])
            }

            # Calculate overall GD score (0-100)
            speaking_pct = speaking_stats[participant]['speaking_percentage']
            engagement_score = engagement[participant]['engagement_score']
            leadership_score = report['leadership_data'].get('overall_score', 0)

            # Balanced participation is key
            balance_penalty = abs(speaking_pct - (100 / len(self.participants)))
            balance_score = max(0, 100 - balance_penalty * 2)

            overall_score = (
                balance_score * 0.25 +
                engagement_score * 0.25 +
                leadership_score * 0.3 +
                min(speaking_pct, 40) * 0.2  # Cap at 40% (don't dominate)
            )

            report['overall_gd_score'] = round(overall_score, 2)
            report['recommendation'] = self._get_recommendation(overall_score)

            participant_reports.append(report)

        # Sort by score
        participant_reports.sort(key=lambda x: x['overall_gd_score'], reverse=True)

        return {
            'session_id': self.session_id,
            'topic': self.topic,
            'duration': round(total_duration, 2),
            'participant_count': len(self.participants),
            'total_statements': len(self.statements),
            'turn_fairness_score': self.turn_detector.get_turn_distribution(),
            'participant_reports': participant_reports,
            'timeline': self.statements,
            'top_performer': participant_reports[0]['participant'] if participant_reports else None
        }

    def _get_recommendation(self, score):
        """Get hiring recommendation based on GD score"""
        if score >= 75:
            return "strong_pass"
        elif score >= 60:
            return "pass"
        elif score >= 45:
            return "borderline"
        else:
            return "needs_improvement"


# Global sessions storage
active_gd_sessions = {}


def create_gd_session(session_id, topic, participants, duration=10):
    """Create a new real-time GD session"""
    session = RealtimeGDSession(session_id, topic, participants, duration)
    active_gd_sessions[session_id] = session
    return session


def get_gd_session(session_id):
    """Get an active GD session"""
    return active_gd_sessions.get(session_id)


def end_gd_session(session_id):
    """End and remove a GD session"""
    if session_id in active_gd_sessions:
        del active_gd_sessions[session_id]
