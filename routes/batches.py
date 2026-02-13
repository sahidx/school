"""
Batch Management Routes
CRUD operations for batches and student enrollment
"""
from flask import Blueprint, request
from models import db, Batch, User, UserRole, user_batches
from utils.auth import login_required, require_role, get_current_user
from utils.response import success_response, error_response, paginated_response, serialize_batch
from sqlalchemy import or_
from datetime import datetime, date
from decimal import Decimal

batches_bp = Blueprint('batches', __name__)

@batches_bp.route('', methods=['GET'])
@login_required
def get_batches():
    """Get all batches with pagination (excludes archived by default)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        
        query = Batch.query
        
        # Exclude archived batches by default
        query = query.filter_by(is_archived=False)
        
        # Search filter
        if search:
            search_filter = or_(
                Batch.name.ilike(f'%{search}%'),
                Batch.description.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Order by creation date
        query = query.order_by(Batch.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        batches_data = []
        for batch in pagination.items:
            batch_info = serialize_batch(batch)
            
            # Extract class from description if available
            if ' - ' in batch.description:
                class_name = batch.description.split(' - ')[0]
                batch_info['class'] = class_name
            
            # Add current student count
            batch_info['currentStudents'] = len([s for s in batch.students if s.is_active])
            batch_info['maxStudents'] = batch.max_students or 50
            
            batches_data.append(batch_info)
        
        # Return simplified response for frontend compatibility
        return success_response("Batches retrieved successfully", batches_data)
        
    except Exception as e:
        return error_response(f'Failed to retrieve batches: {str(e)}', 500)

@batches_bp.route('/<int:batch_id>', methods=['GET'])
@login_required
def get_batch(batch_id):
    """Get specific batch details"""
    try:
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        batch_data = serialize_batch(batch)
        
        # Add detailed student information if user is teacher or admin
        current_user = get_current_user()
        if current_user.role in [UserRole.TEACHER, UserRole.SUPER_USER]:
            students = []
            for student in batch.students:
                if student.is_active:
                    student_data = {
                        'id': student.id,
                        'phoneNumber': student.phoneNumber,
                        'first_name': student.first_name,
                        'last_name': student.last_name,
                        'full_name': student.full_name,
                        'email': student.email,
                        'guardian_phone': student.guardian_phone,
                        'created_at': student.created_at.isoformat()
                    }
                    students.append(student_data)
            
            batch_data['students'] = students
        
        return success_response('Batch details retrieved', {'batch': batch_data})
        
    except Exception as e:
        return error_response(f'Failed to get batch: {str(e)}', 500)

@batches_bp.route('', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def create_batch():
    """Create a new batch - requires name, class, and subject"""
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        # Required fields - name, class, and subject
        required_fields = ['name', 'class', 'subject']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return error_response(f'Missing required fields: {", ".join(missing_fields)}', 400)
        
        # Validate class is one of the allowed values
        allowed_classes = [
            'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5',
            'Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10',
            'HSC 1st Year', 'HSC 2nd Year'
        ]
        class_name = data['class'].strip()
        if class_name not in allowed_classes:
            return error_response(f'Class must be one of: {", ".join(allowed_classes)}', 400)
        
        # Validate subject is one of the allowed values
        allowed_subjects = [
            'Mathematics', 'Higher Mathematics', 'Physics', 'Chemistry', 
            'Biology', 'English', 'Bangla', 'ICT', 'General Science'
        ]
        subject = data['subject'].strip()
        if subject not in allowed_subjects:
            return error_response(f'Subject must be one of: {", ".join(allowed_subjects)}', 400)
        
        # Check if batch name already exists
        existing_batch = Batch.query.filter_by(name=data['name'].strip()).first()
        if existing_batch:
            return error_response('Batch with this name already exists', 409)
        
        # Use today as default start date
        start_date = date.today()
        
        # Create new batch with required fields
        batch = Batch(
            name=data['name'].strip(),
            subject=subject,
            start_date=start_date,
            description=f"{class_name} - {subject}",
            status='active',
            is_active=True,
            fee_amount=Decimal('0.00'),
            max_students=50
        )
        
        # Store class information in the description or add a class field to the model
        # For now, we'll include it in the description
        batch.description = f"{class_name} - {subject}"
        
        db.session.add(batch)
        db.session.commit()
        
        batch_data = serialize_batch(batch)
        # Add class info to the response
        batch_data['class'] = class_name
        
        return success_response('Batch created successfully', {'batch': batch_data}, 201)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to create batch: {str(e)}', 500)

@batches_bp.route('/<int:batch_id>', methods=['PUT'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def update_batch(batch_id):
    """Update batch information"""
    try:
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        # Check if new name conflicts with existing batch
        if 'name' in data and data['name'].strip() != batch.name:
            existing_batch = Batch.query.filter(
                Batch.name == data['name'].strip(),
                Batch.id != batch_id
            ).first()
            if existing_batch:
                return error_response('Batch with this name already exists', 409)
        
        # Handle class and subject updates
        if 'class' in data or 'subject' in data:
            current_class = None
            current_subject = batch.subject
            
            # Extract current class from description if it exists
            if ' - ' in batch.description:
                current_class = batch.description.split(' - ')[0]
            
            new_class = data.get('class', current_class)
            new_subject = data.get('subject', current_subject)
            
            # Validate class if provided
            if new_class:
                allowed_classes = [
                    'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5',
                    'Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10',
                    'HSC 1st Year', 'HSC 2nd Year'
                ]
                if new_class not in allowed_classes:
                    return error_response(f'Class must be one of: {", ".join(allowed_classes)}', 400)
            
            # Validate subject if provided
            if new_subject:
                allowed_subjects = [
                    'Mathematics', 'Higher Mathematics', 'Physics', 'Chemistry', 
                    'Biology', 'English', 'Bangla', 'ICT', 'General Science'
                ]
                if new_subject not in allowed_subjects:
                    return error_response(f'Subject must be one of: {", ".join(allowed_subjects)}', 400)
                
                batch.subject = new_subject
            
            # Update description with class and subject
            if new_class and new_subject:
                batch.description = f"{new_class} - {new_subject}"
        
        # Update other allowed fields
        updatable_fields = ['name']
        
        for field in updatable_fields:
            if field in data:
                if field in ['start_date', 'end_date'] and data[field]:
                    try:
                        setattr(batch, field, datetime.strptime(data[field], '%Y-%m-%d').date())
                    except ValueError:
                        return error_response(f'Invalid {field} format. Use YYYY-MM-DD', 400)
                elif field == 'fee_amount' and data[field] is not None:
                    try:
                        fee_amount = Decimal(str(data[field]))
                        if fee_amount < 0:
                            return error_response('Fee amount cannot be negative', 400)
                        setattr(batch, field, fee_amount)
                    except (ValueError, TypeError):
                        return error_response('Invalid fee amount', 400)
                else:
                    setattr(batch, field, data[field])
        
        # Validate date range
        if batch.end_date and batch.end_date <= batch.start_date:
            return error_response('End date must be after start date', 400)
        
        batch.updated_at = datetime.utcnow()
        db.session.commit()
        
        batch_data = serialize_batch(batch)
        
        return success_response('Batch updated successfully', {'batch': batch_data})
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to update batch: {str(e)}', 500)

@batches_bp.route('/<int:batch_id>', methods=['DELETE'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def delete_batch(batch_id):
    """Delete a batch permanently (hard delete)"""
    try:
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        # Check if batch has students enrolled
        active_students = [s for s in batch.students if s.is_active]
        if active_students:
            return error_response(f'Cannot delete batch with {len(active_students)} active students. Please remove students first.', 400)
        
        # Hard delete - permanently remove from database
        batch_name = batch.name
        
        # Remove all student associations first
        batch.students.clear()
        
        # Delete the batch permanently
        db.session.delete(batch)
        db.session.commit()
        
        return success_response(f'Batch "{batch_name}" deleted permanently')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to delete batch: {str(e)}', 500)

@batches_bp.route('/<int:batch_id>/students', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_batch_students(batch_id):
    """Get all students in a batch, sorted by roll number from most recent monthly exam"""
    try:
        from models import MonthlyExam, MonthlyRanking
        
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        # Find most recent monthly exam for this batch with finalized rankings
        most_recent_exam = MonthlyExam.query.filter_by(
            batch_id=batch_id
        ).order_by(
            MonthlyExam.year.desc(),
            MonthlyExam.month.desc()
        ).first()
        
        # Build a map of user_id to current rank from most recent exam
        rank_map = {}
        if most_recent_exam:
            rankings = MonthlyRanking.query.filter_by(
                monthly_exam_id=most_recent_exam.id,
                is_final=True
            ).all()
            
            for ranking in rankings:
                if ranking.roll_number:
                    rank_map[ranking.user_id] = ranking.roll_number  # Use roll number
        
        students = []
        for student in batch.students:
            if student.is_active and not student.is_archived:
                student_data = {
                    'id': student.id,
                    'phoneNumber': student.phoneNumber,  # Correct field name
                    'phone': student.phoneNumber,  # Add alias for compatibility
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'full_name': student.full_name,
                    'email': student.email,
                    'student_id': student.student_id,  # Generated student ID property
                    'guardian_phone': student.guardian_phone,
                    'emergency_contact': student.emergency_contact,
                    'created_at': student.created_at.isoformat(),
                    'roll_number': rank_map.get(student.id),  # Current rank as roll number
                    'current_rank': rank_map.get(student.id)  # Current rank
                }
                students.append(student_data)
        
        # Sort students by current rank (students without rank go to the end)
        students.sort(key=lambda s: (s['current_rank'] is None, s['current_rank'] if s['current_rank'] else 999999))
        
        return success_response('Batch students retrieved', {'students': students})
        
    except Exception as e:
        return error_response(f'Failed to get batch students: {str(e)}', 500)

@batches_bp.route('/<int:batch_id>/students', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def add_student_to_batch(batch_id):
    """Add a student to a batch"""
    try:
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        data = request.get_json()
        student_id = data.get('student_id')
        
        if not student_id:
            return error_response('Student ID is required', 400)
        
        student = User.query.filter_by(id=student_id, role=UserRole.STUDENT, is_active=True, is_archived=False).first()
        
        if not student:
            return error_response('Student not found', 404)
        
        # Check if student is already in batch
        if batch in student.batches:
            return error_response('Student is already enrolled in this batch', 409)
        
        # Add student to batch
        student.batches.append(batch)
        db.session.commit()
        
        return success_response('Student added to batch successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to add student to batch: {str(e)}', 500)

@batches_bp.route('/<int:batch_id>/students/<int:student_id>', methods=['DELETE'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def remove_student_from_batch(batch_id, student_id):
    """Remove a student from a batch"""
    try:
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        student = User.query.filter_by(id=student_id, role=UserRole.STUDENT).first()
        
        if not student:
            return error_response('Student not found', 404)
        
        # Check if student is in batch
        if batch not in student.batches:
            return error_response('Student is not enrolled in this batch', 404)
        
        # Remove student from batch
        student.batches.remove(batch)
        db.session.commit()
        
        return success_response('Student removed from batch successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to remove student from batch: {str(e)}', 500)

@batches_bp.route('/my-batches', methods=['GET'])
@login_required
@require_role(UserRole.STUDENT)
def get_my_batches():
    """Get current student's batches"""
    try:
        current_user = get_current_user()
        
        batches = []
        for batch in current_user.batches:
            if batch.is_active:
                batch_data = serialize_batch(batch)
                
                # Add student-specific information
                batch_data['enrollment_date'] = None  # This would need to be added to the association table
                
                batches.append(batch_data)
        
        return success_response('Student batches retrieved', {'batches': batches})
        
    except Exception as e:
        return error_response(f'Failed to get student batches: {str(e)}', 500)

@batches_bp.route('/active', methods=['GET'])
@login_required
def get_active_batches():
    """Get all active batches (simplified list) - excludes archived"""
    try:
        batches = Batch.query.filter_by(is_active=True, is_archived=False).order_by(Batch.name).all()
        
        batches_data = []
        for batch in batches:
            batch_data = {
                'id': batch.id,
                'name': batch.name,
                'description': batch.description,
                'fee_amount': float(batch.fee_amount),
                'start_date': batch.start_date.isoformat(),
                'end_date': batch.end_date.isoformat() if batch.end_date else None,
                'student_count': len([s for s in batch.students if s.is_active and not s.is_archived])
            }
            batches_data.append(batch_data)
        
        return success_response('Active batches retrieved', {'batches': batches_data})
        
    except Exception as e:
        return error_response(f'Failed to get active batches: {str(e)}', 500)

# ============================================================================
# ARCHIVE MANAGEMENT ROUTES
# ============================================================================

@batches_bp.route('/<int:batch_id>/archive', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def archive_batch(batch_id):
    """Archive a batch and all its students"""
    try:
        current_user = get_current_user()
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        if batch.is_archived:
            return error_response('Batch is already archived', 400)
        
        # Get reason from request
        data = request.get_json() or {}
        reason = data.get('reason', 'Archived by teacher')
        
        # Archive the batch
        batch.is_archived = True
        batch.archived_at = datetime.utcnow()
        batch.archived_by = current_user.id
        batch.archive_reason = reason
        
        # Archive all students in this batch
        archived_students_count = 0
        for student in batch.students:
            if not student.is_archived and student.role == UserRole.STUDENT:
                student.is_archived = True
                student.archived_at = datetime.utcnow()
                student.archived_by = current_user.id
                student.archive_reason = f"Archived with batch: {batch.name}"
                archived_students_count += 1
        
        db.session.commit()
        
        return success_response('Batch and students archived successfully', {
            'batch_id': batch.id,
            'batch_name': batch.name,
            'archived_students': archived_students_count,
            'archived_at': batch.archived_at.isoformat(),
            'reason': reason
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to archive batch: {str(e)}', 500)

@batches_bp.route('/<int:batch_id>/restore', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def restore_batch(batch_id):
    """Restore an archived batch and optionally its students"""
    try:
        current_user = get_current_user()
        batch = Batch.query.get(batch_id)
        
        if not batch:
            return error_response('Batch not found', 404)
        
        if not batch.is_archived:
            return error_response('Batch is not archived', 400)
        
        # Get restore options from request
        data = request.get_json() or {}
        restore_students = data.get('restore_students', True)
        
        # Restore the batch
        batch.is_archived = False
        batch.archived_at = None
        batch.archived_by = None
        batch.archive_reason = None
        
        # Restore students if requested
        restored_students_count = 0
        if restore_students:
            for student in batch.students:
                if student.is_archived and student.role == UserRole.STUDENT:
                    # Only restore if archived with this batch
                    if student.archive_reason and f"Archived with batch: {batch.name}" in student.archive_reason:
                        student.is_archived = False
                        student.archived_at = None
                        student.archived_by = None
                        student.archive_reason = None
                        restored_students_count += 1
        
        db.session.commit()
        
        return success_response('Batch restored successfully', {
            'batch_id': batch.id,
            'batch_name': batch.name,
            'restored_students': restored_students_count
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to restore batch: {str(e)}', 500)

@batches_bp.route('/archived', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_archived_batches():
    """Get all archived batches"""
    try:
        batches = Batch.query.filter_by(is_archived=True).order_by(Batch.archived_at.desc()).all()
        
        batches_data = []
        for batch in batches:
            batch_data = serialize_batch(batch)
            batch_data['archived_at'] = batch.archived_at.isoformat() if batch.archived_at else None
            batch_data['archive_reason'] = batch.archive_reason
            
            # Get archived by user info
            if batch.archived_by:
                archived_by_user = User.query.get(batch.archived_by)
                batch_data['archived_by_name'] = archived_by_user.full_name if archived_by_user else 'Unknown'
            else:
                batch_data['archived_by_name'] = 'Unknown'
            
            # Count archived students in this batch
            archived_student_count = len([s for s in batch.students if s.is_archived and s.role == UserRole.STUDENT])
            batch_data['archived_students_count'] = archived_student_count
            batch_data['total_students_count'] = len([s for s in batch.students if s.role == UserRole.STUDENT])
            
            batches_data.append(batch_data)
        
        return success_response('Archived batches retrieved', {'batches': batches_data})
        
    except Exception as e:
        return error_response(f'Failed to get archived batches: {str(e)}', 500)

