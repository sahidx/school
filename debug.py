"""
Debug routes to check data
"""
from flask import Blueprint, request
from models import db, User, UserRole, Batch
from utils.response import success_response

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/rankings/<int:batch_id>', methods=['GET'])
def debug_rankings(batch_id):
    """Debug ranking logic for a specific batch"""
    from utils.rankings import get_batch_latest_rank_map
    from models import Batch, MonthlyExam, MonthlyRanking, MonthlyMark
    
    try:
        batch = Batch.query.get(batch_id)
        if not batch:
            return {'error': 'Batch not found'}, 404
            
        # 1. Run the utility
        rank_map, source_exam = get_batch_latest_rank_map(batch_id)
        
        # 2. Get details about what happened
        exams = MonthlyExam.query.filter_by(batch_id=batch_id).order_by(MonthlyExam.year.desc(), MonthlyExam.month.desc(), MonthlyExam.id.desc()).all()
        
        exam_details = []
        for ex in exams:
            rank_count = MonthlyRanking.query.filter_by(monthly_exam_id=ex.id).count()
            mark_count = MonthlyMark.query.filter_by(monthly_exam_id=ex.id).count()
            exam_details.append({
                'id': ex.id,
                'title': ex.title,
                'date': f"{ex.month}/{ex.year}",
                'rankings_count': rank_count,
                'marks_count': mark_count
            })
            
        return {
            'batch': {'id': batch.id, 'name': batch.name},
            'source_exam': {'id': source_exam.id, 'title': source_exam.title} if source_exam else None,
            'rank_map_size': len(rank_map),
            'rank_map_sample': {k: v for i, (k, v) in enumerate(rank_map.items()) if i < 10},
            'all_exams_history': exam_details
        }
    except Exception as e:
        import traceback
        return {'error': str(e), 'trace': traceback.format_exc()}, 500

@debug_bp.route('/check-data', methods=['GET'])
def check_data():
    """Check if test data exists"""
    try:
        # Check batches
        batches = Batch.query.all()
        batch_data = []
        for batch in batches:
            students = [s for s in batch.students if s.is_active]
            batch_info = {
                'id': batch.id,
                'name': batch.name,
                'student_count': len(students),
                'students': [{'id': s.id, 'name': s.full_name, 'phone': s.phoneNumber} for s in students[:5]]  # First 5 students
            }
            batch_data.append(batch_info)
        
        # Check users
        students = User.query.filter_by(role=UserRole.STUDENT, is_active=True).all()
        teachers = User.query.filter_by(role=UserRole.TEACHER, is_active=True).all()
        
        return success_response('Data check completed', {
            'batches': batch_data,
            'total_students': len(students),
            'total_teachers': len(teachers),
            'student_sample': [{'id': s.id, 'name': s.full_name, 'phone': s.phoneNumber} for s in students[:3]]
        })
        
    except Exception as e:
        return {'error': str(e)}, 500

@debug_bp.route('/test-marks', methods=['POST'])
def test_marks():
    """Test marks submission without authentication"""
    try:
        data = request.get_json()
        return success_response('Test marks endpoint working', {
            'received_data': data,
            'data_type': type(data).__name__,
            'keys': list(data.keys()) if isinstance(data, dict) else 'Not a dict'
        })
    except Exception as e:
        return {'error': str(e)}, 500