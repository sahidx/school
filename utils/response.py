"""
Response Utilities
Standardized response formats for API endpoints
"""
from flask import jsonify
from datetime import datetime, date
from decimal import Decimal
from functools import wraps

def success_response(message="Success", data=None, status_code=200):
    """Create a standardized success response"""
    response = {
        'success': True,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if data is not None:
        response['data'] = serialize_data(data)
    
    return jsonify(response), status_code

def error_response(message="Error", status_code=400, error_code=None):
    """Create a standardized error response"""
    response = {
        'success': False,
        'error': message,
        'message': message,  # Add message field for consistency
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if error_code:
        response['error_code'] = error_code
    
    return jsonify(response), status_code

def paginated_response(data, page, per_page, total, message="Data retrieved successfully"):
    """Create a paginated response"""
    response = {
        'success': True,
        'message': message,
        'data': serialize_data(data),
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_next': page * per_page < total,
            'has_prev': page > 1
        },
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return jsonify(response), 200

def serialize_data(data):
    """Serialize data for JSON response"""
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    elif isinstance(data, Decimal):
        return float(data)
    elif hasattr(data, '__dict__') and hasattr(data, '__table__'):
        return serialize_model(data)
    elif isinstance(data, list):
        return [serialize_data(item) for item in data]
    elif isinstance(data, dict):
        return {key: serialize_data(value) for key, value in data.items()}
    else:
        return data

def serialize_model(model, exclude_fields=None):
    """Serialize SQLAlchemy model to dictionary"""
    if exclude_fields is None:
        exclude_fields = ['password_hash']
    
    result = {}
    
    for column in model.__table__.columns:
        field_name = column.name
        
        if field_name in exclude_fields:
            continue
        
        value = getattr(model, field_name)
        
        if isinstance(value, (datetime, date)):
            result[field_name] = value.isoformat() if value else None
        elif isinstance(value, Decimal):
            result[field_name] = float(value) if value else None
        elif hasattr(value, 'value'):  # Enum
            result[field_name] = value.value if value else None
        else:
            result[field_name] = value
    
    return result

def serialize_user(user, include_sensitive=False):
    """Serialize user model with role-specific data"""
    user_data = serialize_model(user, exclude_fields=['password_hash'] if not include_sensitive else [])
    user_data['full_name'] = user.full_name
    user_data['student_code'] = getattr(user, 'student_code', None)
    # Add admission_date if it exists
    if hasattr(user, 'admission_date') and user.admission_date:
        user_data['admissionDate'] = user.admission_date.isoformat()
    if getattr(user, 'role', None) and getattr(user.role, 'value', '') == 'student':
        user_data['batches'] = [serialize_batch(batch) for batch in getattr(user, 'batches', []) if getattr(batch, 'is_active', False)]
        # Include guardian phone
        user_data['guardianPhone'] = getattr(user, 'guardian_phone', None) or getattr(user, 'phoneNumber', None) or ''
        # Include class/section/roll from student_class_info
        try:
            from models import StudentClassInfo
            sci = StudentClassInfo.query.filter_by(student_id=user.id).first()
            if sci:
                user_data['roll'] = sci.roll_number
                sc = getattr(sci, 'school_class', None)
                user_data['schoolClass'] = (getattr(sc, 'name_bn', None) or getattr(sc, 'name', None)) if sc else None
                sec = getattr(sci, 'section', None)
                user_data['section'] = (getattr(sec, 'name_bn', None) or getattr(sec, 'name', None)) if sec else None
            else:
                user_data['roll'] = None
                user_data['schoolClass'] = None
                user_data['section'] = None
        except Exception:
            user_data['roll'] = None
            user_data['schoolClass'] = None
            user_data['section'] = None
    return user_data

def serialize_batch(batch):
    """Serialize batch model"""
    batch_data = serialize_model(batch)
    class_name = None
    description = getattr(batch, 'description', None)
    if description and ' - ' in description:
        class_name = description.split(' - ')[0]
    batch_data['class'] = class_name
    students = getattr(batch, 'students', [])
    batch_data['student_count'] = len([s for s in students if getattr(s, 'is_active', False)])
    batch_data['currentStudents'] = batch_data['student_count']
    batch_data['maxStudents'] = getattr(batch, 'max_students', 50) or 50
    batch_data['isActive'] = getattr(batch, 'is_active', True)
    return batch_data

def serialize_exam(exam, include_questions=False, include_submissions=False):
    exam_data = serialize_model(exam)
    exam_data['question_count'] = len(getattr(exam, 'questions', []))
    exam_data['submission_count'] = len(getattr(exam, 'submissions', []))
    if include_questions:
        exam_data['questions'] = [serialize_question(q) for q in getattr(exam, 'questions', []) if getattr(q, 'is_active', False)]
    if include_submissions:
        exam_data['submissions'] = [serialize_submission(s) for s in getattr(exam, 'submissions', [])]
    exam_data['batches'] = [{'id': b.id, 'name': b.name} for b in getattr(exam, 'batches', [])]
    return exam_data

def serialize_question(question, include_correct_answer=False):
    question_data = serialize_model(question)
    if not include_correct_answer:
        question_data.pop('correct_answer', None)
    return question_data

def serialize_submission(submission, include_answers=False):
    submission_data = serialize_model(submission)
    if include_answers:
        submission_data['answers'] = [serialize_data(answer) for answer in getattr(submission, 'answers', [])]
    return submission_data

def serialize_fee(fee):
    fee_data = serialize_model(fee)
    amount = getattr(fee, 'amount', 0) or 0
    late_fee = getattr(fee, 'late_fee', 0) or 0
    discount = getattr(fee, 'discount', 0) or 0
    exam_fee = getattr(fee, 'exam_fee', 0) or 0
    # Map database column 'others_fee' to API field 'other_fee'
    other_fee = getattr(fee, 'others_fee', 0) or 0
    fee_data['other_fee'] = float(other_fee)  # Export as 'other_fee' in API response
    total_amount = amount + late_fee + exam_fee + other_fee - discount
    fee_data['total_amount'] = float(total_amount)
    due_date = getattr(fee, 'due_date', None)
    status = getattr(fee, 'status', None)
    if due_date and status and getattr(status, 'value', '') == 'pending':
        fee_data['is_overdue'] = due_date < date.today()
    else:
        fee_data['is_overdue'] = False
    return fee_data

def validate_json_request(required_fields=None):
    """Decorator to validate JSON request data"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            if not request.is_json:
                return error_response('Request must be JSON', 400)
            data = request.get_json()
            if not data:
                return error_response('Request data is required', 400)
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return error_response(f'Missing required fields: {", ".join(missing_fields)}', 400)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
