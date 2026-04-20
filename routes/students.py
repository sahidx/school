"""
Student Management Routes
CRUD operations specifically for student management from teacher dashboard
"""
from flask import Blueprint, request, session, make_response
from flask_bcrypt import generate_password_hash
from models import db, User, UserRole, Batch, user_batches, StudentClassInfo
from utils.auth import login_required, require_role, get_current_user
from utils.response import success_response, error_response, serialize_user
from utils.rankings import get_batch_latest_rank_map
from sqlalchemy import or_, func
import re
import secrets
import string
import base64
from datetime import datetime

students_bp = Blueprint('students', __name__)

def generate_password(length=8):
    """Generate a random password"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_student_code() -> str:
    """Generate the next unique 6-digit student code (100001, 100002, ...)"""
    max_code = db.session.query(func.max(User.student_code)).scalar()
    if max_code:
        try:
            return str(int(max_code) + 1)
        except (ValueError, TypeError):
            pass
    # Find highest numeric code in case of gaps
    students = User.query.filter(
        User.student_code.isnot(None),
        User.role == UserRole.STUDENT
    ).with_entities(User.student_code).all()
    codes = []
    for (c,) in students:
        try: codes.append(int(c))
        except: pass
    return str(max(codes) + 1) if codes else '100001'

def validate_phone(phone):
    """Validate and format phone number"""
    phone = re.sub(r'[^\d]', '', phone)
    
    if phone.startswith('880'):
        phone = phone[3:]
    elif phone.startswith('+880'):
        phone = phone[4:]
    
    if len(phone) == 11 and phone.startswith('01'):
        return phone
    
    return None

@students_bp.route('', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_students():
    """Get all students with their batch information (excludes archived, sorted by roll number)"""
    try:
        batch_id = request.args.get('batch_id', type=int)
        search = request.args.get('search', '').strip()
        
        query = User.query.filter(User.role == UserRole.STUDENT, User.is_active == True, User.is_archived == False)
        
        # Filter by batch
        if batch_id:
            query = query.join(user_batches).filter(user_batches.c.batch_id == batch_id)
        
        # Search filter
        if search:
            search_filter = or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.phoneNumber.ilike(f'%{search}%'),
                User.guardian_name.ilike(f'%{search}%'),
                User.guardian_phone.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        students = query.all()
        
        # Build roll number map from latest usable monthly exam
        roll_map = {}
        if batch_id:
            roll_map, _ = get_batch_latest_rank_map(batch_id)
        
        # Sort by roll number (students without roll go to end)
        students.sort(key=lambda s: (s.id not in roll_map, roll_map.get(s.id, 999999), s.first_name))

        # Attach school class info (class/section/roll) for filtering in student management UI
        student_ids = [s.id for s in students]
        class_info_map = {}
        if student_ids:
            class_infos = StudentClassInfo.query.filter(StudentClassInfo.student_id.in_(student_ids)).all()
            class_info_map = {info.student_id: info for info in class_infos}
        
        students_data = []
        for student in students:
            student_data = serialize_user(student)
            student_data['roll_number'] = roll_map.get(student.id)  # Add roll number
            class_info = class_info_map.get(student.id)
            student_data['schoolClassId'] = class_info.school_class_id if class_info else None
            student_data['sectionId'] = class_info.section_id if class_info else None
            student_data['classRollNumber'] = class_info.roll_number if class_info else None
            
            # Add batch information - include ALL batches
            if student.batches:
                # Primary batch (first one for backward compatibility)
                student_data['batch'] = {
                    'id': student.batches[0].id,
                    'name': student.batches[0].name,
                    'description': student.batches[0].description
                }
                student_data['batchId'] = student.batches[0].id
                
                # All batches this student is enrolled in
                student_data['batches'] = [{
                    'id': batch.id,
                    'name': batch.name,
                    'description': batch.description
                } for batch in student.batches]
                student_data['batchIds'] = [batch.id for batch in student.batches]
            else:
                student_data['batch'] = None
                student_data['batchId'] = None
                student_data['batches'] = []
                student_data['batchIds'] = []
            
            # Format for frontend
            student_data['firstName'] = student_data.get('first_name', '')
            student_data['lastName'] = student_data.get('last_name', '')
            student_data['phoneNumber'] = student_data.get('phoneNumber', '')  # Fixed: use phoneNumber not phone
            student_data['studentId'] = student_data.get('student_id', '')
            student_data['isActive'] = student_data.get('is_active', True)
            student_data['guardianPhone'] = student_data.get('guardian_phone', '')
            student_data['guardianName'] = student_data.get('guardian_name', '')
            student_data['motherName'] = student_data.get('mother_name', '')
            student_data['address'] = student_data.get('address', '')
            student_data['school'] = student_data.get('address', '')
            
            students_data.append(student_data)
        
        return success_response('Students retrieved successfully', students_data)
        
    except Exception as e:
        return error_response(f'Failed to retrieve students: {str(e)}', 500)

@students_bp.route('', methods=['POST'])
# @login_required  # Temporarily disabled for testing
# @require_role(UserRole.TEACHER, UserRole.SUPER_USER)  # Temporarily disabled for testing
def create_student():
    """Create a new student"""
    try:
        data = request.get_json()
        
        if not data:
            print("ERROR: No data received")
            return error_response('Request data is required', 400)
        
        print(f"DEBUG: Received data: {data}")
        
        # Required fields
        required_fields = ['firstName', 'lastName']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            error_msg = f'Missing required fields: {", ".join(missing_fields)}'
            print(f"ERROR: {error_msg}")
            return error_response(error_msg, 400)
        
        # Use guardian phone as primary phone if student phone not provided
        guardian_phone = data.get('guardianPhone', '')
        student_phone = data.get('phoneNumber', '')
        
        # Prioritize guardian phone for login
        if guardian_phone:
            # Validate guardian phone number
            phone = validate_phone(guardian_phone)
            if not phone:
                error_msg = f'Invalid guardian phone number format: {guardian_phone}'
                print(f"ERROR: {error_msg}")
                return error_response(error_msg, 400)
            
            # Check if guardian phone already exists - ALLOW multiple students with same phone (siblings)
            existing_users = User.query.filter_by(phoneNumber=phone, role=UserRole.STUDENT).all()
            if existing_users:
                # Check if this is the SAME student (by name match) or a SIBLING (different name)
                for existing_user in existing_users:
                    same_name = (existing_user.first_name.lower() == data['firstName'].strip().lower() and 
                               existing_user.last_name.lower() == data['lastName'].strip().lower())
                    
                    if same_name:
                        # SAME student exists - add them to the new batch if provided
                        print(f"INFO: Student {existing_user.first_name} {existing_user.last_name} already exists with phone {phone}.")
                        batch_id = data.get('batchId')
                        if batch_id:
                            batch = Batch.query.get(batch_id)
                            if batch:
                                # Check if already in this batch
                                if batch not in existing_user.batches:
                                    existing_user.batches.append(batch)
                                    db.session.commit()
                                    print(f"✅ Enrolled existing student in new batch: {batch.name}")
                                    
                                    # Prepare response
                                    student_data = serialize_user(existing_user)
                                    student_data['firstName'] = student_data.get('first_name', '')
                                    student_data['lastName'] = student_data.get('last_name', '')
                                    student_data['phoneNumber'] = student_data.get('phoneNumber', '')
                                    student_data['message'] = 'Student already exists - enrolled in new batch'
                                    
                                    return success_response('Student enrolled in batch successfully', student_data, 200)
                                else:
                                    return error_response('Student is already enrolled in this batch', 409)
                            else:
                                return error_response('Batch not found', 404)
                        else:
                            return error_response('Student with this name and guardian phone already exists. Please provide a batch to enroll them in.', 409)
                
                # No exact name match found - it's a SIBLING or different child
                # ALLOW creation to continue - this is the fix!
                print(f"✅ CREATING SIBLING: Guardian phone {phone} has {len(existing_users)} existing student(s), creating NEW student '{data['firstName']} {data['lastName']}'")
                # Continue to create the new student below - DO NOT RETURN ERROR
            
            # Check if phone belongs to teacher/admin (not student)
            existing_non_student = User.query.filter_by(phoneNumber=phone).filter(User.role != UserRole.STUDENT).first()
            if existing_non_student:
                # Phone belongs to a teacher or admin
                error_msg = 'This phone number is already registered as a teacher/admin account'
                print(f"ERROR: {error_msg} - Phone: {phone}")
                return error_response(error_msg, 409)
        elif student_phone:
            # Fallback to student phone if no guardian phone
            phone = validate_phone(student_phone)
            if not phone:
                return error_response('Invalid phone number format', 400)
            
            existing_user = User.query.filter_by(phoneNumber=phone).first()
            if existing_user and existing_user.role == UserRole.STUDENT:
                # Student already exists - add them to the new batch if provided
                print(f"INFO: Student with phone {phone} already exists. Enrolling in batch if provided.")
                batch_id = data.get('batchId')
                if batch_id:
                    batch = Batch.query.get(batch_id)
                    if batch:
                        # Check if already in this batch
                        if batch not in existing_user.batches:
                            existing_user.batches.append(batch)
                            db.session.commit()
                            
                            # Prepare response
                            student_data = serialize_user(existing_user)
                            student_data['firstName'] = student_data.get('first_name', '')
                            student_data['lastName'] = student_data.get('last_name', '')
                            student_data['phoneNumber'] = student_data.get('phoneNumber', '')
                            student_data['message'] = 'Student already exists - enrolled in new batch'
                            
                            return success_response('Student enrolled in batch successfully', student_data, 200)
                        else:
                            return error_response('Student is already enrolled in this batch', 409)
                    else:
                        return error_response('Batch not found', 404)
                else:
                    # Allow creating new student with same phone but different name (sibling)
                    print(f"INFO: Phone {phone} exists but allowing new student (different child, same parent phone)")
            elif existing_user and existing_user.role != UserRole.STUDENT:
                return error_response('This phone number is already registered as a teacher/admin account', 409)
        else:
            # Generate a unique placeholder phone number if no phone provided
            import random
            phone = f"0199{random.randint(1000000, 9999999)}"
        
        # Validate email if provided
        email = data.get('email')
        if email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                return error_response('Student with this email already exists', 409)
        
        # Generate student ID if not provided
        student_id = data.get('studentId')
        if not student_id:
            # Generate student ID based on current year and sequence
            current_year = datetime.now().year
            count = User.query.filter(User.role == UserRole.STUDENT).count()
            student_id = f"{current_year}{count + 1:04d}"
        
        # Create new student
        print(f"🆕 CREATING NEW STUDENT: Name='{data['firstName']} {data['lastName']}', Phone={phone}, Guardian={data.get('guardianName', 'N/A')}")
        student = User(
            phoneNumber=phone,  # This will be guardian phone for login
            phone=phone,  # Set phone field to same as phoneNumber for SMS
            first_name=data['firstName'].strip(),
            last_name=data['lastName'].strip(),
            email=data.get('email', '').strip() if data.get('email') else None,
            role=UserRole.STUDENT,
            date_of_birth=datetime.strptime(data['dateOfBirth'], '%Y-%m-%d').date() if data.get('dateOfBirth') else None,
            address=data.get('address', '').strip() if data.get('address') else data.get('school', '').strip() if data.get('school') else None,
            guardian_phone=phone,  # Set guardian phone to same as phoneNumber for SMS
            guardian_name=data.get('guardianName', '').strip() if data.get('guardianName') else None,
            mother_name=data.get('motherName', '').strip() if data.get('motherName') else None,
            emergency_contact=data.get('emergencyContact', '').strip() if data.get('emergencyContact') else None,
            admission_date=datetime.strptime(str(data['admissionDate']).strip(), '%Y-%m-%d').date() if data.get('admissionDate') and str(data['admissionDate']).strip() else None,
            is_active=data.get('isActive', True)
        )
        
        # Generate password as last 4 digits of parent phone
        # Students login with parent phone number + last 4 digits as password
        unique_password = phone[-4:]  # Last 4 digits of parent phone
        student.password_hash = generate_password_hash(unique_password)
        
        db.session.add(student)
        db.session.flush()  # Get the student ID

        # Assign 6-digit unique student code
        student.student_code = generate_student_code()

        # Assign to batch if provided
        batch_id = data.get('batchId')
        if batch_id:
            batch = Batch.query.get(batch_id)
            if batch:
                student.batches.append(batch)
        
        db.session.commit()
        
        # Prepare response data
        student_data = serialize_user(student)
        student_data['firstName'] = student_data.get('first_name', '')
        student_data['lastName'] = student_data.get('last_name', '')
        student_data['phoneNumber'] = student_data.get('phoneNumber', '')  # Fixed: use phoneNumber not phone
        student_data['studentId'] = student_data.get('student_id', '')
        student_data['isActive'] = student_data.get('is_active', True)
        student_data['guardianPhone'] = student_data.get('guardian_phone', '')
        student_data['guardianName'] = student_data.get('guardian_name', '')
        student_data['motherName'] = student_data.get('mother_name', '')
        student_data['address'] = student_data.get('address', '')
        student_data['school'] = student_data.get('address', '')
        
        if student.batches:
            student_data['batch'] = {
                'id': student.batches[0].id,
                'name': student.batches[0].name,
                'description': student.batches[0].description
            }
            student_data['batchId'] = student.batches[0].id
        
        # Add login credentials to response
        student_data['loginCredentials'] = {
            'username': phone,  # Parent phone number
            'password': unique_password,  # Last 4 digits of parent phone
            'note': 'Student logs in with Parent Phone Number (username) + Last 4 Digits of Parent Phone (password)'
        }
        
        return success_response('Student created successfully', student_data, 201)
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR creating student: {str(e)}")
        print(f"Full traceback: {error_details}")
        return error_response(f'Failed to create student: {str(e)}', 500)

@students_bp.route('/<int:student_id>', methods=['PUT'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def update_student(student_id):
    """Update student information"""
    try:
        student = User.query.filter(
            User.id == student_id,
            User.role == UserRole.STUDENT
        ).first()
        
        if not student:
            return error_response('Student not found', 404)
        
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        # Update basic information
        if 'firstName' in data:
            student.first_name = data['firstName'].strip()
        if 'lastName' in data:
            student.last_name = data['lastName'].strip()
        if 'email' in data:
            if data['email']:
                # Check if email is already taken
                existing_email = User.query.filter(
                    User.email == data['email'],
                    User.id != student_id
                ).first()
                if existing_email:
                    return error_response('Email is already taken', 409)
            student.email = data['email'].strip() if data['email'] else None
        
        if 'studentId' in data:
            student.student_id = data['studentId'].strip() if data['studentId'] else None
        
        if 'phoneNumber' in data and 'guardianPhone' not in data:
            phone = validate_phone(data['phoneNumber'])
            if not phone:
                return error_response('Invalid phone number format', 400)
            
            # Only block if phone belongs to a teacher/admin (students can share phones as siblings)
            existing_phone = User.query.filter(
                User.phoneNumber == phone,
                User.id != student_id,
                User.role != UserRole.STUDENT
            ).first()
            if existing_phone:
                return error_response('Phone number is already registered as a teacher/admin account', 409)
            
            student.phoneNumber = phone
            student.phone = phone  # Sync phone field for SMS
            student.guardian_phone = phone  # Sync guardian phone for SMS
        
        if 'dateOfBirth' in data and data['dateOfBirth']:
            try:
                student.date_of_birth = datetime.strptime(data['dateOfBirth'], '%Y-%m-%d').date()
            except ValueError:
                return error_response('Invalid date format. Use YYYY-MM-DD', 400)
        
        if 'address' in data:
            student.address = data['address'].strip() if data['address'] else None
        
        if 'school' in data:
            student.address = data['school'].strip() if data['school'] else None
        
        if 'guardianPhone' in data:
            guardian_phone = data['guardianPhone'].strip() if data['guardianPhone'] else None
            if guardian_phone:
                phone = validate_phone(guardian_phone)
                if phone:
                    student.guardian_phone = phone
                    student.phone = phone
                    student.phoneNumber = phone  # Always sync phoneNumber from guardianPhone
                else:
                    return error_response('Invalid phone number format', 400)
            else:
                student.guardian_phone = None
        
        if 'guardianName' in data:
            student.guardian_name = data['guardianName'].strip() if data['guardianName'] else None
        
        if 'motherName' in data:
            student.mother_name = data['motherName'].strip() if data['motherName'] else None
        
        if 'emergencyContact' in data:
            student.emergency_contact = data['emergencyContact'].strip() if data['emergencyContact'] else None
        
        if 'admissionDate' in data:
            if data['admissionDate'] and data['admissionDate'].strip():
                try:
                    student.admission_date = datetime.strptime(data['admissionDate'], '%Y-%m-%d').date()
                except ValueError:
                    return error_response('Invalid admission date format. Use YYYY-MM-DD', 400)
            else:
                student.admission_date = None
        
        if 'isActive' in data:
            student.is_active = data['isActive']
        
        # Update batch assignment
        if 'batchId' in data:
            student.batches.clear()
            if data['batchId']:
                batch = Batch.query.get(data['batchId'])
                if batch:
                    student.batches.append(batch)
        
        student.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Prepare response data
        student_data = serialize_user(student)
        student_data['firstName'] = student_data.get('first_name', '')
        student_data['lastName'] = student_data.get('last_name', '')
        student_data['phoneNumber'] = student_data.get('phoneNumber', '')  # Fixed: use phoneNumber not phone
        student_data['studentId'] = student_data.get('student_id', '')
        student_data['isActive'] = student_data.get('is_active', True)
        student_data['guardianPhone'] = student_data.get('guardian_phone', '')
        student_data['guardianName'] = student_data.get('guardian_name', '')
        student_data['motherName'] = student_data.get('mother_name', '')
        student_data['address'] = student_data.get('address', '')
        student_data['school'] = student_data.get('address', '')
        
        if student.batches:
            student_data['batch'] = {
                'id': student.batches[0].id,
                'name': student.batches[0].name,
                'description': student.batches[0].description
            }
            student_data['batchId'] = student.batches[0].id
        
        return success_response('Student updated successfully', student_data)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to update student: {str(e)}', 500)

@students_bp.route('/<int:student_id>', methods=['DELETE'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def delete_student(student_id):
    """Delete a student (soft delete by deactivating)"""
    try:
        student = User.query.filter(
            User.id == student_id,
            User.role == UserRole.STUDENT
        ).first()
        
        if not student:
            return error_response('Student not found', 404)
        
        # Soft delete by deactivating
        student.is_active = False
        student.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response('Student deleted successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to delete student: {str(e)}', 500)

@students_bp.route('/<int:student_id>/reset-password', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def reset_student_password(student_id):
    """Reset student password to last 4 digits of parent phone"""
    try:
        student = User.query.filter(
            User.id == student_id,
            User.role == UserRole.STUDENT
        ).first()
        
        if not student:
            return error_response('Student not found', 404)
        
        # Get parent phone number
        parent_phone = student.guardian_phone or student.phoneNumber
        
        if not parent_phone or len(parent_phone) < 4:
            return error_response('Parent phone number not found or invalid', 400)
        
        # Generate password as last 4 digits of parent phone
        new_password = parent_phone[-4:]
        student.password_hash = generate_password_hash(new_password)
        student.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response('Password reset successfully', {
            'newPassword': new_password,
            'note': 'Password is the last 4 digits of parent phone number'
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to reset password: {str(e)}', 500)

@students_bp.route('/bulk-import', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def bulk_import_students():
    """Bulk import students from CSV data"""
    try:
        data = request.get_json()
        
        if not data or 'students' not in data:
            return error_response('Students data is required', 400)
        
        students_data = data['students']
        successful_imports = []
        failed_imports = []
        
        for idx, student_data in enumerate(students_data):
            try:
                # Validate required fields
                if not all(field in student_data for field in ['firstName', 'lastName', 'phoneNumber']):
                    failed_imports.append({
                        'row': idx + 1,
                        'error': 'Missing required fields (firstName, lastName, phoneNumber)',
                        'data': student_data
                    })
                    continue
                
                # Validate phone number
                phone = validate_phone(student_data['phoneNumber'])
                if not phone:
                    failed_imports.append({
                        'row': idx + 1,
                        'error': 'Invalid phone number format',
                        'data': student_data
                    })
                    continue
                
                # Check if student already exists
                existing_user = User.query.filter_by(phoneNumber=phone).first()
                if existing_user:
                    failed_imports.append({
                        'row': idx + 1,
                        'error': 'Student with this phone number already exists',
                        'data': student_data
                    })
                    continue
                
                # Generate student ID if not provided
                student_id = student_data.get('studentId')
                if not student_id:
                    current_year = datetime.now().year
                    count = User.query.filter(User.role == UserRole.STUDENT).count()
                    student_id = f"{current_year}{count + len(successful_imports) + 1:04d}"
                
                # Create new student
                student = User(
                    phoneNumber=phone,  # This will be guardian phone for login
                    first_name=student_data['firstName'].strip(),
                    last_name=student_data['lastName'].strip(),
                    email=student_data.get('email', '').strip() if student_data.get('email') else None,
                    role=UserRole.STUDENT,
                    is_active=True
                )
                
                # Generate unique password for student
                from utils.password_generator import generate_simple_unique_password
                unique_password = generate_simple_unique_password(student_data['firstName'].strip(), phone)
                student.password_hash = generate_password_hash(unique_password)
                
                db.session.add(student)
                db.session.flush()
                
                # Assign to batch if provided
                batch_id = student_data.get('batchId')
                if batch_id:
                    batch = Batch.query.get(batch_id)
                    if batch:
                        student.batches.append(batch)
                
                successful_imports.append({
                    'row': idx + 1,
                    'studentId': student_id,
                    'name': f"{student.first_name} {student.last_name}",
                    'phone': phone
                })
                
            except Exception as e:
                failed_imports.append({
                    'row': idx + 1,
                    'error': str(e),
                    'data': student_data
                })
        
        if successful_imports:
            db.session.commit()
        else:
            db.session.rollback()
        
        return success_response('Bulk import completed', {
            'successful': len(successful_imports),
            'failed': len(failed_imports),
            'successfulImports': successful_imports,
            'failedImports': failed_imports
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to import students: {str(e)}', 500)

# ============================================================================
# ARCHIVE MANAGEMENT ROUTES
# ============================================================================

@students_bp.route('/bulk-archive', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def bulk_archive_students():
    """Archive multiple students at once"""
    try:
        current_user = get_current_user()
        data = request.get_json() or {}
        student_ids = data.get('student_ids', [])
        reason = data.get('reason', 'Bulk archived by teacher')
        
        if not student_ids or not isinstance(student_ids, list):
            return error_response('student_ids array is required', 400)
        
        if len(student_ids) == 0:
            return error_response('No students selected', 400)
        
        archived_students = []
        already_archived = []
        not_found = []
        
        for student_id in student_ids:
            student = User.query.get(student_id)
            
            if not student or student.role != UserRole.STUDENT:
                not_found.append(student_id)
                continue
            
            if student.is_archived:
                already_archived.append({
                    'id': student.id,
                    'name': student.full_name
                })
                continue
            
            # Archive the student
            student.is_archived = True
            student.archived_at = datetime.utcnow()
            student.archived_by = current_user.id
            student.archive_reason = reason
            
            archived_students.append({
                'id': student.id,
                'name': student.full_name
            })
        
        db.session.commit()
        
        return success_response(f'Successfully archived {len(archived_students)} student(s)', {
            'archived_count': len(archived_students),
            'archived_students': archived_students,
            'already_archived_count': len(already_archived),
            'already_archived': already_archived,
            'not_found_count': len(not_found),
            'not_found': not_found
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to archive students: {str(e)}', 500)

@students_bp.route('/<int:student_id>/archive', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def archive_student(student_id):
    """Archive a student"""
    try:
        current_user = get_current_user()
        student = User.query.get(student_id)
        
        if not student or student.role != UserRole.STUDENT:
            return error_response('Student not found', 404)
        
        if student.is_archived:
            return error_response('Student is already archived', 400)
        
        # Get reason from request
        data = request.get_json() or {}
        reason = data.get('reason', 'Archived by teacher')
        
        # Archive the student
        student.is_archived = True
        student.archived_at = datetime.utcnow()
        student.archived_by = current_user.id
        student.archive_reason = reason
        
        db.session.commit()
        
        return success_response('Student archived successfully', {
            'student_id': student.id,
            'student_name': student.full_name,
            'archived_at': student.archived_at.isoformat(),
            'reason': reason
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to archive student: {str(e)}', 500)

@students_bp.route('/<int:student_id>/restore', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def restore_student(student_id):
    """Restore an archived student"""
    try:
        student = User.query.get(student_id)
        
        if not student or student.role != UserRole.STUDENT:
            return error_response('Student not found', 404)
        
        if not student.is_archived:
            return error_response('Student is not archived', 400)
        
        # Restore the student
        student.is_archived = False
        student.archived_at = None
        student.archived_by = None
        student.archive_reason = None
        
        db.session.commit()
        
        return success_response('Student restored successfully', {
            'student_id': student.id,
            'student_name': student.full_name
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to restore student: {str(e)}', 500)

@students_bp.route('/archived', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_archived_students():
    """Get all archived students"""
    try:
        batch_id = request.args.get('batch_id', type=int)
        
        query = User.query.filter(User.role == UserRole.STUDENT, User.is_archived == True)
        
        # Filter by batch if specified
        if batch_id:
            query = query.join(user_batches).filter(user_batches.c.batch_id == batch_id)
        
        students = query.order_by(User.archived_at.desc()).all()
        
        students_data = []
        for student in students:
            student_data = serialize_user(student)
            student_data['archived_at'] = student.archived_at.isoformat() if student.archived_at else None
            student_data['archive_reason'] = student.archive_reason
            
            # Get archived by user info
            if student.archived_by:
                archived_by_user = User.query.get(student.archived_by)
                student_data['archived_by_name'] = archived_by_user.full_name if archived_by_user else 'Unknown'
            else:
                student_data['archived_by_name'] = 'Unknown'
            
            # Add batch information
            if student.batches:
                student_data['batch'] = {
                    'id': student.batches[0].id,
                    'name': student.batches[0].name,
                    'description': student.batches[0].description
                }
            else:
                student_data['batch'] = None
            
            # Format for frontend
            student_data['firstName'] = student_data.get('first_name', '')
            student_data['lastName'] = student_data.get('last_name', '')
            student_data['phoneNumber'] = student_data.get('phoneNumber', '')
            student_data['guardianPhone'] = student_data.get('guardian_phone', '')
            student_data['guardianName'] = student_data.get('guardian_name', '')
            student_data['motherName'] = student_data.get('mother_name', '')
            student_data['address'] = student_data.get('address', '')
            student_data['school'] = student_data.get('address', '')
            
            students_data.append(student_data)
        
        return success_response('Archived students retrieved', {'students': students_data})
        
    except Exception as e:
        return error_response(f'Failed to get archived students: {str(e)}', 500)
@students_bp.route('/me/batches', methods=['GET'])
def get_my_batches():
    """Get current student's batches"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return error_response('Not authenticated', 401)
        
        student = User.query.get(user_id)
        if not student or student.role != UserRole.STUDENT:
            return error_response('Student not found', 404)
        
        batches_data = []
        if student.batches:
            for batch in student.batches:
                if batch.is_active:
                    batches_data.append({
                        'id': batch.id,
                        'name': batch.name,
                        'description': batch.description,
                        'fee_amount': float(batch.fee_amount),
                        'is_active': batch.is_active
                    })
        
        return success_response('Batches retrieved', {'batches': batches_data})
        
    except Exception as e:
        return error_response(f'Failed to get batches: {str(e)}', 500)


# ──────────────────────────────────────────────────────────────────────────────
# PHOTO VIEW / DOWNLOAD / UPLOAD / DELETE
# ──────────────────────────────────────────────────────────────────────────────

@students_bp.route('/<int:student_id>/photo', methods=['GET'])
@login_required
def get_student_photo(student_id):
    """Serve a student's profile photo as an actual image.
    Add ?download=1 to force browser download.
    """
    student = User.query.get(student_id)
    if not student or student.role != UserRole.STUDENT:
        return error_response('Student not found', 404)
    if not student.profile_image:
        return error_response('No photo', 404)

    try:
        # profile_image is stored as a data URI: "data:image/jpeg;base64,/9j/..."
        header, b64data = student.profile_image.split(',', 1)
        mime = header.split(':')[1].split(';')[0]   # e.g. "image/jpeg"
        raw  = base64.b64decode(b64data)

        ext_map = {'image/jpeg':'jpg','image/png':'png','image/gif':'gif','image/webp':'webp'}
        ext = ext_map.get(mime, 'jpg')
        filename = f"student_{student_id}_photo.{ext}"

        resp = make_response(raw)
        resp.headers['Content-Type'] = mime
        resp.headers['Content-Length'] = len(raw)
        if request.args.get('download'):
            resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        else:
            resp.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp
    except Exception as e:
        return error_response(f'Failed to serve photo: {str(e)}', 500)


@students_bp.route('/<int:student_id>/photo', methods=['PUT', 'POST'])
@login_required
def upload_student_photo(student_id):
    """Upload or update a student profile photo.
    Accepts multipart/form-data with 'photo' file OR JSON { "photo": "<base64 data URI>" }
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return error_response('Not authenticated', 401)

        student = User.query.get(student_id)
        if not student or student.role != UserRole.STUDENT:
            return error_response('Student not found', 404)

        # Only teacher/super_user OR the student themselves
        is_self = (current_user.id == student_id)
        is_staff = current_user.role in (UserRole.TEACHER, UserRole.SUPER_USER)
        if not is_self and not is_staff:
            return error_response('Permission denied', 403)

        # ── Case 1: file upload ──────────────────────────────────────────────
        if 'photo' in request.files:
            file = request.files['photo']
            if file.filename == '':
                return error_response('No file selected', 400)
            allowed = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in allowed:
                return error_response('File type not allowed', 400)
            mime = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
            raw = file.read()
            if len(raw) > 5 * 1024 * 1024:
                return error_response('File too large (max 5 MB)', 400)
            data_uri = f'data:{mime};base64,{base64.b64encode(raw).decode()}'
            student.profile_image = data_uri

        # ── Case 2: base64 JSON body ─────────────────────────────────────────
        elif request.is_json:
            body = request.get_json(silent=True) or {}
            photo = body.get('photo', '')
            if not photo:
                return error_response('No photo data provided', 400)
            if not photo.startswith('data:image/'):
                return error_response('Invalid photo format', 400)
            # Rough size guard: base64 is ~1.37x raw
            if len(photo) > 7 * 1024 * 1024:
                return error_response('File too large (max 5 MB)', 400)
            student.profile_image = photo

        else:
            return error_response('No photo provided', 400)

        db.session.commit()
        return success_response('Photo updated', {'profile_image': student.profile_image[:80] + '...'})

    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to upload photo: {str(e)}', 500)


@students_bp.route('/<int:student_id>/photo', methods=['DELETE'])
@login_required
def delete_student_photo(student_id):
    """Remove a student's profile photo."""
    try:
        current_user = get_current_user()
        if not current_user:
            return error_response('Not authenticated', 401)

        student = User.query.get(student_id)
        if not student or student.role != UserRole.STUDENT:
            return error_response('Student not found', 404)

        is_staff = current_user.role in (UserRole.TEACHER, UserRole.SUPER_USER)
        if not is_staff:
            return error_response('Permission denied', 403)

        student.profile_image = None
        db.session.commit()
        return success_response('Photo removed')

    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to remove photo: {str(e)}', 500)
