"""
Enhanced API Routes for New Features
Integrates candidate profiles, recommendations, simulations, and AI feedback
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps

from candidate_profile import profile_manager
from recommendation_engine import recommendation_engine
from simulation_tracker import simulation_tracker
from ai_feedback_engine import ai_feedback_engine

enhanced_api_bp = Blueprint('enhanced_api', __name__, url_prefix='/api/v2')


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


@enhanced_api_bp.route('/profile/create', methods=['POST'])
@require_auth
def create_profile():
    """Create or update candidate profile"""
    try:
        email = session.get('email')
        profile_data = request.json

        success = profile_manager.create_or_update_profile(email, profile_data)

        if success:
            profile = profile_manager.get_complete_profile(email)
            analytics = profile_manager.get_profile_analytics(email)

            return jsonify({
                'success': True,
                'profile': profile,
                'analytics': analytics
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to create profile'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/profile/get', methods=['GET'])
@require_auth
def get_profile():
    """Get complete candidate profile"""
    try:
        email = session.get('email')
        profile = profile_manager.get_complete_profile(email)

        if profile:
            analytics = profile_manager.get_profile_analytics(email)
            return jsonify({
                'success': True,
                'profile': profile,
                'analytics': analytics
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Profile not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/profile/add-skill', methods=['POST'])
@require_auth
def add_skill():
    """Add skill to candidate profile"""
    try:
        email = session.get('email')
        skill_data = request.json

        success = profile_manager.add_skill(email, skill_data)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/profile/update-preferences', methods=['POST'])
@require_auth
def update_preferences():
    """Update candidate preferences"""
    try:
        email = session.get('email')
        preferences = request.json

        success = profile_manager.update_preferences(email, preferences)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/recommendations/generate', methods=['POST'])
@require_auth
def generate_recommendations():
    """Generate AI-driven company recommendations with 80%+ match"""
    try:
        email = session.get('email')
        top_k = request.json.get('top_k', 10)
        min_threshold = request.json.get('min_match_threshold', 80.0)

        recommendations = recommendation_engine.generate_recommendations(
            email, top_k=top_k, min_match_threshold=min_threshold
        )

        stats = recommendation_engine.get_recommendation_stats(email)

        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'total_count': len(recommendations),
            'stats': stats
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/recommendations/feedback', methods=['POST'])
@require_auth
def submit_recommendation_feedback():
    """Submit feedback for a company recommendation"""
    try:
        email = session.get('email')
        data = request.json

        company_id = data.get('company_id')
        satisfaction_rating = data.get('satisfaction_rating', 3)
        feedback_data = {
            'match_quality': data.get('match_quality', satisfaction_rating),
            'relevance': data.get('relevance', satisfaction_rating),
            'would_recommend': data.get('would_recommend', True),
            'feedback_text': data.get('feedback_text', ''),
            'comment': data.get('comment', ''),
            'action': data.get('action', 'feedback')
        }

        success = recommendation_engine.record_user_feedback(
            email, company_id, satisfaction_rating, feedback_data
        )

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/recommendations/mark-viewed/<int:company_id>', methods=['POST'])
@require_auth
def mark_recommendation_viewed(company_id):
    """Mark a recommendation as viewed"""
    try:
        email = session.get('email')
        success = recommendation_engine.mark_recommendation_viewed(email, company_id)
        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/recommendations/mark-accepted/<int:company_id>', methods=['POST'])
@require_auth
def mark_recommendation_accepted(company_id):
    """Mark a recommendation as accepted"""
    try:
        email = session.get('email')
        success = recommendation_engine.mark_recommendation_accepted(email, company_id)
        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/recommendations/stats', methods=['GET'])
@require_auth
def get_recommendation_stats():
    """Get recommendation statistics"""
    try:
        email = session.get('email')
        stats = recommendation_engine.get_recommendation_stats(email)
        return jsonify({'success': True, 'stats': stats}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/start', methods=['POST'])
@require_auth
def start_simulation():
    """Start a new simulation session"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        simulation_type = data.get('simulation_type')
        company_name = data.get('company_name')

        success = simulation_tracker.start_simulation(
            email, session_id, simulation_type, company_name
        )

        return jsonify({'success': success, 'session_id': session_id}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/complete', methods=['POST'])
@require_auth
def complete_simulation():
    """Complete a simulation and record performance"""
    try:
        data = request.json
        session_id = data.get('session_id')
        performance_data = data.get('performance_data', {})

        success = simulation_tracker.complete_simulation(session_id, performance_data)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/track/aptitude', methods=['POST'])
@require_auth
def track_aptitude_test():
    """Track aptitude test performance"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        test_data = data.get('test_data', {})

        success = simulation_tracker.track_aptitude_test(session_id, email, test_data)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/track/gd', methods=['POST'])
@require_auth
def track_gd():
    """Track group discussion performance"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        gd_data = data.get('gd_data', {})

        success = simulation_tracker.track_gd_session(session_id, email, gd_data)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/track/hr', methods=['POST'])
@require_auth
def track_hr():
    """Track HR interview performance"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        hr_data = data.get('hr_data', {})

        success = simulation_tracker.track_hr_interview(session_id, email, hr_data)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/track/technical', methods=['POST'])
@require_auth
def track_technical():
    """Track technical test performance"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        tech_data = data.get('tech_data', {})

        success = simulation_tracker.track_technical_test(session_id, email, tech_data)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/feedback/submit', methods=['POST'])
@require_auth
def submit_simulation_feedback():
    """Submit feedback about simulation realism and engagement"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        simulation_type = data.get('simulation_type')
        feedback_data = {
            'realism_rating': data.get('realism_rating'),
            'engagement_rating': data.get('engagement_rating'),
            'difficulty_rating': data.get('difficulty_rating'),
            'usefulness_rating': data.get('usefulness_rating'),
            'overall_rating': data.get('overall_rating'),
            'feedback_text': data.get('feedback_text', ''),
            'improvements_suggested': data.get('improvements_suggested', ''),
            'would_recommend': data.get('would_recommend', True)
        }

        success = simulation_tracker.save_simulation_feedback(
            session_id, email, simulation_type, feedback_data
        )

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/stats', methods=['GET'])
@require_auth
def get_simulation_stats():
    """Get user simulation statistics"""
    try:
        email = session.get('email')
        stats = simulation_tracker.get_user_stats(email)

        return jsonify({'success': True, 'stats': stats}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/simulation/global-metrics', methods=['GET'])
def get_global_metrics():
    """Get platform-wide completion metrics"""
    try:
        metrics = simulation_tracker.get_global_completion_metrics()
        return jsonify({'success': True, 'metrics': metrics}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/feedback/generate/aptitude', methods=['POST'])
@require_auth
def generate_aptitude_feedback():
    """Generate AI feedback for aptitude test (< 5 minutes)"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        test_results = data.get('test_results', {})

        feedback = ai_feedback_engine.generate_aptitude_test_feedback(
            session_id, email, test_results
        )

        return jsonify({'success': True, 'feedback': feedback}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/feedback/generate/gd', methods=['POST'])
@require_auth
def generate_gd_feedback():
    """Generate AI feedback for group discussion (< 5 minutes)"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        gd_data = data.get('gd_data', {})

        feedback = ai_feedback_engine.generate_gd_feedback(
            session_id, email, gd_data
        )

        return jsonify({'success': True, 'feedback': feedback}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/feedback/generate/hr', methods=['POST'])
@require_auth
def generate_hr_feedback():
    """Generate AI feedback for HR interview (< 5 minutes)"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        interview_data = data.get('interview_data', {})

        feedback = ai_feedback_engine.generate_hr_interview_feedback(
            session_id, email, interview_data
        )

        return jsonify({'success': True, 'feedback': feedback}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/feedback/generate/technical', methods=['POST'])
@require_auth
def generate_technical_feedback():
    """Generate AI feedback for technical test (< 5 minutes)"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        tech_data = data.get('tech_data', {})

        feedback = ai_feedback_engine.generate_technical_test_feedback(
            session_id, email, tech_data
        )

        return jsonify({'success': True, 'feedback': feedback}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/feedback/rate', methods=['POST'])
@require_auth
def rate_feedback():
    """Rate the quality of AI-generated feedback"""
    try:
        email = session.get('email')
        data = request.json

        session_id = data.get('session_id')
        ratings = {
            'overall_rating': data.get('overall_rating'),
            'usefulness_rating': data.get('usefulness_rating'),
            'clarity_rating': data.get('clarity_rating'),
            'feedback_text': data.get('feedback_text', '')
        }

        success = ai_feedback_engine.record_feedback_rating(session_id, email, ratings)

        return jsonify({'success': success}), 200 if success else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/feedback/quality-stats', methods=['GET'])
@require_auth
def get_feedback_quality_stats():
    """Get feedback quality statistics"""
    try:
        email = session.get('email')
        stats = ai_feedback_engine.get_feedback_quality_stats(email)

        return jsonify({'success': True, 'stats': stats}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/feedback/platform-stats', methods=['GET'])
def get_platform_feedback_stats():
    """Get platform-wide feedback quality statistics"""
    try:
        stats = ai_feedback_engine.get_feedback_quality_stats()
        return jsonify({'success': True, 'stats': stats}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@enhanced_api_bp.route('/analytics/dashboard', methods=['GET'])
@require_auth
def get_analytics_dashboard():
    """Get comprehensive analytics dashboard data"""
    try:
        email = session.get('email')

        profile = profile_manager.get_complete_profile(email)
        profile_analytics = profile_manager.get_profile_analytics(email)
        recommendation_stats = recommendation_engine.get_recommendation_stats(email)
        simulation_stats = simulation_tracker.get_user_stats(email)
        feedback_stats = ai_feedback_engine.get_feedback_quality_stats(email)

        dashboard_data = {
            'profile': {
                'completeness': profile.get('profile_completeness', 0) if profile else 0,
                'strength': profile_analytics.get('profile_strength', 'N/A')
            },
            'recommendations': {
                'total': recommendation_stats.get('total_recommendations', 0),
                'accepted': recommendation_stats.get('total_accepted', 0),
                'avg_match_score': recommendation_stats.get('average_match_score', 0),
                'satisfaction_score': recommendation_stats.get('average_satisfaction_score', 0)
            },
            'simulations': {
                'total_completed': simulation_stats.get('total_simulations_completed', 0),
                'completion_rate': simulation_stats.get('completion_rate', 0),
                'avg_performance': simulation_stats.get('avg_performance_score', 0),
                'breakdown': {
                    'aptitude': simulation_stats.get('aptitude_count', 0),
                    'technical': simulation_stats.get('technical_count', 0),
                    'gd': simulation_stats.get('gd_count', 0),
                    'hr': simulation_stats.get('hr_count', 0)
                }
            },
            'feedback_quality': {
                'avg_rating': feedback_stats.get('avg_user_rating', 0),
                'positive_percentage': feedback_stats.get('positive_feedback_percentage', 0),
                'total_received': feedback_stats.get('total_feedbacks_received', 0)
            }
        }

        return jsonify({'success': True, 'dashboard': dashboard_data}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
