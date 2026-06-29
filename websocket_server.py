"""
WebSocket Server for Real-Time Video Interview
Handles live video frames, audio chunks, and bidirectional communication
"""

from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import time
from datetime import datetime
import logging

from realtime_video_interview import (
    create_realtime_session,
    get_session,
    end_session
)
from realtime_gd_interview import (
    create_gd_session,
    get_gd_session,
    end_gd_session
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app for WebSocket
socketio_app = Flask(__name__)
socketio_app.config['SECRET_KEY'] = 'realtime_interview_secret'
CORS(socketio_app)

# Initialize SocketIO
socketio = SocketIO(socketio_app, cors_allowed_origins="*", async_mode='threading')


# ==================== WebSocket Event Handlers ====================

@socketio.on('connect')
def handle_connect():
    """Client connected"""
    logger.info(f"Client connected: {request.sid}")
    emit('connection_response', {
        'status': 'connected',
        'message': 'WebSocket connection established',
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('start_interview')
def handle_start_interview(data):
    """
    Start a new real-time interview session

    Expected data:
    {
        "student_email": "student@example.com",
        "company_name": "Google",
        "questions": ["Question 1", "Question 2", ...]
    }
    """
    try:
        student_email = data.get('student_email')
        company_name = data.get('company_name')
        questions = data.get('questions', [])

        if not student_email or not company_name or not questions:
            emit('error', {
                'message': 'Missing required fields: student_email, company_name, questions'
            })
            return

        # Create session
        session = create_realtime_session(student_email, company_name, questions)

        # Start interview
        first_question = session.start_interview()

        # Join room for this session
        join_room(session.session_id)

        logger.info(f"Started interview session: {session.session_id}")

        emit('interview_started', {
            'session_id': session.session_id,
            'company_name': company_name,
            'first_question': first_question,
            'total_questions': len(questions),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        emit('error', {'message': f'Failed to start interview: {str(e)}'})


@socketio.on('video_frame')
def handle_video_frame(data):
    """
    Process video frame for facial analysis

    Expected data:
    {
        "session_id": "session_123",
        "frame": "base64_encoded_image"
    }
    """
    try:
        session_id = data.get('session_id')
        frame_data = data.get('frame')

        if not session_id or not frame_data:
            emit('error', {'message': 'Missing session_id or frame data'})
            return

        # Get session
        session = get_session(session_id)
        if not session:
            emit('error', {'message': 'Invalid session ID'})
            return

        # Process frame
        analysis = session.process_video_frame(frame_data)

        # Send real-time feedback to client
        emit('video_analysis', {
            'face_detected': analysis.get('face_detected'),
            'emotion': analysis.get('emotion'),
            'emotion_confidence': analysis.get('emotion_confidence'),
            'dominant_emotion': analysis.get('dominant_emotion'),
            'eye_contact': analysis.get('eye_contact'),
            'face_position': analysis.get('face_position'),
            'warnings': analysis.get('warnings', []),
            'timestamp': datetime.now().isoformat()
        }, room=session_id)

    except Exception as e:
        logger.error(f"Error processing video frame: {e}")
        emit('error', {'message': f'Video processing error: {str(e)}'})


@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """
    Process audio chunk for speech-to-text

    Expected data:
    {
        "session_id": "session_123",
        "audio": "base64_encoded_audio"
    }
    """
    try:
        session_id = data.get('session_id')
        audio_data = data.get('audio')

        if not session_id or not audio_data:
            emit('error', {'message': 'Missing session_id or audio data'})
            return

        # Get session
        session = get_session(session_id)
        if not session:
            emit('error', {'message': 'Invalid session ID'})
            return

        # Process audio
        result = session.process_audio_chunk(audio_data)

        # Send transcription to client
        if result.get('success'):
            emit('speech_recognized', {
                'text': result.get('text'),
                'word_count': result.get('total_words'),
                'filler_count': result.get('filler_words'),
                'analysis': result.get('analysis'),
                'timestamp': datetime.now().isoformat()
            }, room=session_id)

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        emit('error', {'message': f'Audio processing error: {str(e)}'})


@socketio.on('submit_answer')
def handle_submit_answer(data):
    """
    Submit current answer and get next question

    Expected data:
    {
        "session_id": "session_123"
    }
    """
    try:
        session_id = data.get('session_id')

        if not session_id:
            emit('error', {'message': 'Missing session_id'})
            return

        # Get session
        session = get_session(session_id)
        if not session:
            emit('error', {'message': 'Invalid session ID'})
            return

        # Submit answer and get next question
        result = session.submit_answer()

        # Send response
        emit('answer_submitted', {
            'feedback': result.get('feedback'),
            'next_question': result.get('next_question'),
            'interview_complete': result.get('interview_complete'),
            'final_report': result.get('final_report') if result.get('interview_complete') else None,
            'timestamp': datetime.now().isoformat()
        }, room=session_id)

        # End session if complete
        if result.get('interview_complete'):
            leave_room(session_id)
            end_session(session_id)
            logger.info(f"Interview completed: {session_id}")

    except Exception as e:
        logger.error(f"Error submitting answer: {e}")
        emit('error', {'message': f'Submit error: {str(e)}'})


@socketio.on('end_interview')
def handle_end_interview(data):
    """
    End interview session prematurely

    Expected data:
    {
        "session_id": "session_123"
    }
    """
    try:
        session_id = data.get('session_id')

        if not session_id:
            emit('error', {'message': 'Missing session_id'})
            return

        # Get session for final report
        session = get_session(session_id)
        if session:
            final_report = session.generate_final_report()

            emit('interview_ended', {
                'message': 'Interview ended',
                'final_report': final_report,
                'timestamp': datetime.now().isoformat()
            }, room=session_id)

            # Clean up
            leave_room(session_id)
            end_session(session_id)
            logger.info(f"Interview ended by user: {session_id}")
        else:
            emit('error', {'message': 'Session not found'})

    except Exception as e:
        logger.error(f"Error ending interview: {e}")
        emit('error', {'message': f'End interview error: {str(e)}'})


@socketio.on('get_real_time_stats')
def handle_get_stats(data):
    """Get real-time statistics during interview"""
    try:
        session_id = data.get('session_id')

        if not session_id:
            emit('error', {'message': 'Missing session_id'})
            return

        session = get_session(session_id)
        if not session:
            emit('error', {'message': 'Invalid session ID'})
            return

        # Calculate current stats
        stats = {
            'current_question_number': session.ai_interviewer.current_question_index,
            'total_questions': len(session.ai_interviewer.questions),
            'elapsed_time': int(time.time() - session.start_time),
            'words_spoken': session.speech_recognizer.word_count,
            'filler_words': session.speech_recognizer.filler_count,
            'dominant_emotion': session.video_analyzer._get_dominant_emotion()
        }

        emit('real_time_stats', stats, room=session_id)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        emit('error', {'message': f'Stats error: {str(e)}'})


# ==================== Group Discussion Events ====================

@socketio.on('start_gd')
def handle_start_gd(data):
    """
    Start a new real-time GD session

    Expected data:
    {
        "topic": "Discussion topic",
        "participants": ["Alice", "Bob", "Charlie"],
        "duration": 10  # minutes
    }
    """
    try:
        topic = data.get('topic')
        participants = data.get('participants', [])
        duration = data.get('duration', 10)

        if not topic or not participants:
            emit('error', {'message': 'Missing topic or participants'})
            return

        if len(participants) < 2:
            emit('error', {'message': 'At least 2 participants required for GD'})
            return

        # Create session ID
        session_id = f"gd_{int(time.time())}"

        # Create GD session
        gd_session = create_gd_session(session_id, topic, participants, duration)

        # Join room
        join_room(session_id)

        logger.info(f"Started GD session: {session_id} with {len(participants)} participants")

        emit('gd_started', {
            'session_id': session_id,
            'topic': topic,
            'participants': participants,
            'duration_minutes': duration,
            'start_time': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error starting GD: {e}")
        emit('error', {'message': f'Failed to start GD: {str(e)}'})


@socketio.on('gd_video_frame')
def handle_gd_video_frame(data):
    """
    Process video frame for GD participant

    Expected data:
    {
        "session_id": "gd_123",
        "participant_name": "Alice",
        "frame": "base64_encoded_image"
    }
    """
    try:
        session_id = data.get('session_id')
        participant_name = data.get('participant_name')
        frame_data = data.get('frame')

        if not all([session_id, participant_name, frame_data]):
            emit('error', {'message': 'Missing required data'})
            return

        # Get session
        gd_session = get_gd_session(session_id)
        if not gd_session:
            emit('error', {'message': 'Invalid GD session ID'})
            return

        # Process frame
        analysis = gd_session.process_video_frame(participant_name, frame_data)

        # Broadcast to all in room
        emit('gd_video_analysis', {
            'participant': participant_name,
            'analysis': analysis,
            'timestamp': datetime.now().isoformat()
        }, room=session_id)

    except Exception as e:
        logger.error(f"Error processing GD video frame: {e}")
        emit('error', {'message': f'Video processing error: {str(e)}'})


@socketio.on('gd_audio_activity')
def handle_gd_audio_activity(data):
    """
    Update audio activity for GD participant (who's speaking)

    Expected data:
    {
        "session_id": "gd_123",
        "participant_name": "Alice",
        "is_speaking": true
    }
    """
    try:
        session_id = data.get('session_id')
        participant_name = data.get('participant_name')
        is_speaking = data.get('is_speaking', False)

        if not session_id or not participant_name:
            emit('error', {'message': 'Missing required data'})
            return

        # Get session
        gd_session = get_gd_session(session_id)
        if not gd_session:
            emit('error', {'message': 'Invalid GD session ID'})
            return

        # Update audio activity
        current_speaker = gd_session.process_audio_activity(participant_name, is_speaking)

        # Broadcast current speaker to all
        emit('gd_current_speaker', {
            'current_speaker': current_speaker,
            'participant': participant_name,
            'is_speaking': is_speaking,
            'timestamp': datetime.now().isoformat()
        }, room=session_id)

    except Exception as e:
        logger.error(f"Error processing audio activity: {e}")
        emit('error', {'message': f'Audio activity error: {str(e)}'})


@socketio.on('gd_statement')
def handle_gd_statement(data):
    """
    Add a transcribed statement to GD

    Expected data:
    {
        "session_id": "gd_123",
        "participant_name": "Alice",
        "text": "I think we should consider..."
    }
    """
    try:
        session_id = data.get('session_id')
        participant_name = data.get('participant_name')
        text = data.get('text')

        if not all([session_id, participant_name, text]):
            emit('error', {'message': 'Missing required data'})
            return

        # Get session
        gd_session = get_gd_session(session_id)
        if not gd_session:
            emit('error', {'message': 'Invalid GD session ID'})
            return

        # Add statement
        statement = gd_session.add_statement(participant_name, text)

        # Broadcast to all participants
        emit('gd_new_statement', {
            'participant': participant_name,
            'text': text,
            'timestamp': statement['timestamp'],
            'behaviors': statement.get('behaviors', []),
            'statement_number': len(gd_session.statements)
        }, room=session_id)

    except Exception as e:
        logger.error(f"Error processing GD statement: {e}")
        emit('error', {'message': f'Statement error: {str(e)}'})


@socketio.on('get_gd_stats')
def handle_get_gd_stats(data):
    """Get real-time GD statistics"""
    try:
        session_id = data.get('session_id')

        if not session_id:
            emit('error', {'message': 'Missing session_id'})
            return

        gd_session = get_gd_session(session_id)
        if not gd_session:
            emit('error', {'message': 'Invalid GD session ID'})
            return

        # Get comprehensive stats
        stats = gd_session.get_real_time_stats()

        emit('gd_stats_update', stats, room=session_id)

    except Exception as e:
        logger.error(f"Error getting GD stats: {e}")
        emit('error', {'message': f'GD stats error: {str(e)}'})


@socketio.on('end_gd')
def handle_end_gd(data):
    """End GD session and generate final report"""
    try:
        session_id = data.get('session_id')

        if not session_id:
            emit('error', {'message': 'Missing session_id'})
            return

        # Get session
        gd_session = get_gd_session(session_id)
        if not gd_session:
            emit('error', {'message': 'Invalid GD session ID'})
            return

        # Generate final report
        final_report = gd_session.generate_final_report()

        # Broadcast to all participants
        emit('gd_ended', {
            'message': 'Group discussion completed',
            'final_report': final_report,
            'timestamp': datetime.now().isoformat()
        }, room=session_id)

        # Clean up
        leave_room(session_id)
        end_gd_session(session_id)
        logger.info(f"GD session ended: {session_id}")

    except Exception as e:
        logger.error(f"Error ending GD: {e}")
        emit('error', {'message': f'End GD error: {str(e)}'})


# ==================== Run WebSocket Server ====================

def run_websocket_server(host='0.0.0.0', port=5001):
    """Run the WebSocket server"""
    logger.info(f"Starting WebSocket server on {host}:{port}")
    logger.info("Real-time video interview ready!")
    socketio.run(socketio_app, host=host, port=port, debug=True, use_reloader=False)


if __name__ == '__main__':
    from flask import request
    run_websocket_server()
