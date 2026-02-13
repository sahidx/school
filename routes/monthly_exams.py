"""
Monthly Exam System Routes
Ranking, GPA calculation, merit lists, and performance analytics
"""
from flask import Blueprint, request, jsonify, current_app
from models import (db, MonthlyExam, IndividualExam, MonthlyMark, Batch, User, 
                   UserRole, Settings, SmsLog, SmsStatus, Attendance, AttendanceStatus, MonthlyRanking)
from utils.auth import login_required, require_role, get_current_user
from utils.response import success_response, error_response
from services.sms_service import send_bulk_notification
from sqlalchemy import func, desc, case, and_, or_
from datetime import datetime, date, timedelta
from decimal import Decimal
import calendar
import logging
import requests
import os
import re

logger = logging.getLogger(__name__)

monthly_exams_bp = Blueprint('monthly_exams', __name__)

@monthly_exams_bp.route('/test-db', methods=['GET'])
@login_required
def test_database_connection():
    """Test database connection and basic queries"""
    try:
        current_user = get_current_user()
        
        # Test basic queries
        user_count = User.query.count()
        monthly_exam_count = MonthlyExam.query.count()
        individual_exam_count = IndividualExam.query.count()
        monthly_mark_count = MonthlyMark.query.count()
        
        return success_response('Database connection test successful', {
            'current_user': {
                'id': current_user.id,
                'name': current_user.full_name,
                'role': current_user.role.value
            },
            'counts': {
                'users': user_count,
                'monthly_exams': monthly_exam_count,
                'individual_exams': individual_exam_count,
                'monthly_marks': monthly_mark_count
            }
        })
        
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return error_response(f'Database test failed: {str(e)}', 500)

@monthly_exams_bp.route('', methods=['GET'])
@login_required
def get_monthly_exams():
    """Get monthly exams with filtering"""
    try:
        current_user = get_current_user()
        batch_id = request.args.get('batch_id', type=int)
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int) or datetime.now().year
        
        query = MonthlyExam.query
        
        # Students can now see ALL exams from all batches
        # No filtering by user role - removed batch restriction for students
        
        # Apply filters
        if batch_id:
            query = query.filter(MonthlyExam.batch_id == batch_id)
        
        if month:
            query = query.filter(MonthlyExam.month == month)
        
        query = query.filter(MonthlyExam.year == year)
        
        exams = query.order_by(desc(MonthlyExam.year), desc(MonthlyExam.month)).all()
        
        exam_list = []
        for exam in exams:
            exam_data = serialize_monthly_exam(exam)
            
            # Add student-specific data
            if current_user.role == UserRole.STUDENT:
                exam_data['student_marks'] = get_student_monthly_marks(exam.id, current_user.id)
                exam_data['student_rank'] = get_student_rank(exam.id, current_user.id)
            
            exam_list.append(exam_data)
        
        return success_response('Monthly exams retrieved successfully', exam_list)
        
    except Exception as e:
        logger.error(f"Error getting monthly exams: {e}")
        return error_response(f'Failed to retrieve monthly exams: {str(e)}', 500)

@monthly_exams_bp.route('', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def create_monthly_exam():
    """Create a new monthly exam"""
    try:
        data = request.get_json()
        logger.info(f"Creating monthly exam with data: {data}")
        
        if not data:
            logger.error("No request data provided")
            return error_response('Request data is required', 400)
        
        required_fields = ['title', 'month', 'year', 'batch_id']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return error_response(f'Missing required fields: {", ".join(missing_fields)}', 400)
        
        # Validate month and year
        month = int(data['month'])
        year = int(data['year'])
        
        if not (1 <= month <= 12):
            return error_response('Month must be between 1 and 12', 400)
        
        if year < 2020 or year > 2030:
            return error_response('Year must be between 2020 and 2030', 400)
        
        # Check if monthly exam already exists
        existing = MonthlyExam.query.filter_by(
            batch_id=data['batch_id'],
            month=month,
            year=year
        ).first()
        
        if existing:
            return error_response('Monthly exam already exists for this month', 400)
        
        # Set default values for optional fields
        # Total marks will be 0 initially and updated as individual exams are added
        total_marks = data.get('total_marks', 0)
        pass_marks = data.get('pass_marks', 0)  # Will be calculated later based on total
        
        # Set default dates (start of month to end of month)
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Create monthly exam
        monthly_exam = MonthlyExam(
            title=data['title'],
            description=data.get('description', ''),
            month=month,
            year=year,
            total_marks=total_marks,
            pass_marks=pass_marks,
            start_date=start_date,
            end_date=end_date,
            batch_id=data['batch_id'],
            created_by=get_current_user().id
        )
        
        db.session.add(monthly_exam)
        db.session.flush()
        
        # Create individual exams if provided
        individual_exams = data.get('individual_exams', [])
        calculated_total = 0
        
        for idx, exam_data in enumerate(individual_exams):
            individual_exam = IndividualExam(
                monthly_exam_id=monthly_exam.id,
                title=exam_data['title'],
                subject=exam_data['subject'],
                marks=exam_data['marks'],
                exam_date=datetime.fromisoformat(exam_data['exam_date'].replace('Z', '+00:00')),
                duration=exam_data.get('duration', 60),
                order_index=idx + 1
            )
            db.session.add(individual_exam)
            calculated_total += exam_data['marks']
        
        # Update monthly exam total marks if individual exams provided
        if individual_exams:
            monthly_exam.total_marks = calculated_total
            monthly_exam.pass_marks = int(calculated_total * 0.33)  # 33% of total
        
        db.session.commit()
        
        return success_response('Monthly exam created successfully', {
            'monthly_exam': serialize_monthly_exam(monthly_exam)
        }, 201)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating monthly exam: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return error_response(f'Failed to create monthly exam: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/marks', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def submit_marks():
    """Submit marks for students in monthly exam"""
    try:
        data = request.get_json()
        
        if not data or 'marks' not in data:
            return error_response('Marks data is required', 400)
        
        marks_data = data['marks']  # List of mark entries
        
        for mark_entry in marks_data:
            required_fields = ['monthly_exam_id', 'individual_exam_id', 'user_id', 'marks_obtained', 'total_marks']
            missing_fields = [field for field in required_fields if field not in mark_entry]
            
            if missing_fields:
                return error_response(f'Missing fields in mark entry: {", ".join(missing_fields)}', 400)
            
            # Check if mark already exists
            existing_mark = MonthlyMark.query.filter_by(
                monthly_exam_id=mark_entry['monthly_exam_id'],
                individual_exam_id=mark_entry['individual_exam_id'],
                user_id=mark_entry['user_id']
            ).first()
            
            percentage = (mark_entry['marks_obtained'] / mark_entry['total_marks']) * 100
            grade, gpa = calculate_grade_and_gpa(percentage)
            
            if existing_mark:
                # Update existing mark
                existing_mark.marks_obtained = mark_entry['marks_obtained']
                existing_mark.total_marks = mark_entry['total_marks']
                existing_mark.percentage = percentage
                existing_mark.grade = grade
                existing_mark.gpa = gpa
                existing_mark.is_absent = mark_entry.get('is_absent', False)
                existing_mark.remarks = mark_entry.get('remarks', '')
                existing_mark.updated_at = datetime.utcnow()
            else:
                # Create new mark
                monthly_mark = MonthlyMark(
                    monthly_exam_id=mark_entry['monthly_exam_id'],
                    individual_exam_id=mark_entry['individual_exam_id'],
                    user_id=mark_entry['user_id'],
                    marks_obtained=mark_entry['marks_obtained'],
                    total_marks=mark_entry['total_marks'],
                    percentage=percentage,
                    grade=grade,
                    gpa=gpa,
                    is_absent=mark_entry.get('is_absent', False),
                    remarks=mark_entry.get('remarks', '')
                )
                db.session.add(monthly_mark)
        
        db.session.commit()
        
        # Recalculate rankings
        monthly_exam_id = marks_data[0]['monthly_exam_id']
        calculate_monthly_rankings(monthly_exam_id)
        
        return success_response('Marks submitted successfully', {
            'marks_count': len(marks_data)
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error submitting marks: {e}")
        return error_response(f'Failed to submit marks: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/comprehensive-ranking', methods=['GET'])
@login_required
def get_comprehensive_monthly_ranking(exam_id):
    """Get comprehensive ranking with individual exams, attendance, roll numbers, and bonus marks"""
    try:
        current_user = get_current_user()
        
        # Get monthly exam
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        # Check access permission
        if current_user.role == UserRole.STUDENT:
            user_batch_ids = [b.id for b in current_user.batches if b.is_active]
            if monthly_exam.batch_id not in user_batch_ids:
                return error_response('Access denied', 403)
        
        # Get all individual exams for this monthly exam
        individual_exams = IndividualExam.query.filter_by(
            monthly_exam_id=exam_id
        ).order_by(IndividualExam.order_index).all()
        
        # Get all students in the batch (exclude archived students)
        batch_students = User.query.join(
            User.batches
        ).filter(
            User.role == UserRole.STUDENT,
            User.is_active == True,
            User.is_archived == False,
            Batch.id == monthly_exam.batch_id
        ).all()
        
        # Calculate comprehensive rankings
        rankings = []
        
        for student in batch_students:
            # Get existing ranking to get roll number and previous position
            existing_ranking = MonthlyRanking.query.filter_by(
                monthly_exam_id=exam_id,
                user_id=student.id
            ).first()
            
            # Get individual exam marks
            individual_marks = {}
            total_exam_marks = 0
            total_possible_marks = 0
            exam_count = len(individual_exams)
            passed_exams = 0
            
            for exam in individual_exams:
                mark = MonthlyMark.query.filter_by(
                    monthly_exam_id=exam_id,
                    individual_exam_id=exam.id,
                    user_id=student.id
                ).first()
                
                if mark:
                    individual_marks[exam.id] = {
                        'exam_title': exam.title,
                        'subject': exam.subject,
                        'marks_obtained': mark.marks_obtained,
                        'total_marks': mark.total_marks,
                        'percentage': round((mark.marks_obtained / mark.total_marks * 100), 2) if mark.total_marks > 0 else 0,
                        'is_absent': mark.is_absent,
                        'grade': calculate_grade_and_gpa((mark.marks_obtained / mark.total_marks * 100) if mark.total_marks > 0 else 0)[0]
                    }
                    if not mark.is_absent:
                        total_exam_marks += mark.marks_obtained
                        if mark.marks_obtained >= (mark.total_marks * 0.4):  # 40% pass mark
                            passed_exams += 1
                    total_possible_marks += mark.total_marks
                else:
                    individual_marks[exam.id] = {
                        'exam_title': exam.title,
                        'subject': exam.subject,
                        'marks_obtained': 0,
                        'total_marks': exam.marks,
                        'percentage': 0,
                        'is_absent': True,
                        'grade': 'F'
                    }
                    total_possible_marks += exam.marks
            
            # Calculate attendance marks (1 mark per present day in the month)
            # Only count attendance from the SAME MONTH as the exam
            attendance_marks = 0
            total_days = 0
            max_attendance_marks = 0
            
            if monthly_exam.start_date and monthly_exam.end_date:
                # Get the first and last day of the exam's month
                exam_month = monthly_exam.month
                exam_year = monthly_exam.year
                
                # First day of the month
                month_start = datetime(exam_year, exam_month, 1).date()
                
                # Last day of the month
                if exam_month == 12:
                    month_end = datetime(exam_year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    month_end = datetime(exam_year, exam_month + 1, 1).date() - timedelta(days=1)
                
                # Count total working days in this specific month (Monday to Friday)
                current_date = month_start
                
                while current_date <= month_end:
                    # Count only weekdays (Monday to Friday)
                    if current_date.weekday() < 5:  # 0-4 are Monday to Friday
                        total_days += 1
                    current_date += timedelta(days=1)
                
                max_attendance_marks = total_days  # Maximum possible attendance marks for the month
                
                # Count present days ONLY in this specific month
                present_count = Attendance.query.filter(
                    Attendance.user_id == student.id,
                    Attendance.batch_id == monthly_exam.batch_id,
                    Attendance.date >= month_start,
                    Attendance.date <= month_end,
                    Attendance.status == AttendanceStatus.PRESENT
                ).count()
                attendance_marks = present_count
            
            # Calculate attendance percentage
            attendance_percentage = (attendance_marks / total_days * 100) if total_days > 0 else 0
            
            # Calculate final totals (NO BONUS - just exam marks + attendance marks)
            final_total = total_exam_marks + attendance_marks
            total_possible = total_possible_marks + max_attendance_marks  # Total possible including max attendance
            
            # Calculate simple percentage based on obtained vs total possible
            percentage = (final_total / total_possible * 100) if total_possible > 0 else 0
            
            # Calculate grade and GPA based on final percentage
            grade, gpa = calculate_grade_and_gpa(percentage)
            exam_gpa = calculate_grade_and_gpa((total_exam_marks / total_possible_marks * 100) if total_possible_marks > 0 else 0)[1]
            
            # Get previous month ranking for comparison and roll number
            previous_position = None
            previous_roll_number = None
            
            if existing_ranking and existing_ranking.previous_position:
                previous_position = existing_ranking.previous_position
            
            # Always try to find previous month ranking for roll number inheritance
            prev_month = monthly_exam.month - 1 if monthly_exam.month > 1 else 12
            prev_year = monthly_exam.year if monthly_exam.month > 1 else monthly_exam.year - 1
            
            prev_exam = MonthlyExam.query.filter_by(
                batch_id=monthly_exam.batch_id,
                month=prev_month,
                year=prev_year
            ).first()
            
            if prev_exam:
                prev_ranking = MonthlyRanking.query.filter_by(
                    monthly_exam_id=prev_exam.id,
                    user_id=student.id,
                    is_final=True
                ).first()
                if prev_ranking:
                    previous_position = prev_ranking.position
                    previous_roll_number = prev_ranking.roll_number
            
            # Determine roll number: use existing, or inherit from previous month, or None
            current_roll_number = None
            if existing_ranking and existing_ranking.roll_number:
                current_roll_number = existing_ranking.roll_number
            elif previous_roll_number:
                current_roll_number = previous_roll_number  # Inherit from previous month
            
            ranking_data = {
                'user_id': student.id,
                'student_name': student.full_name,
                'student_phone': student.phoneNumber,
                'roll_number': current_roll_number,
                'individual_marks': individual_marks,
                'total_exam_marks': total_exam_marks,
                'total_possible_marks': total_possible_marks,
                'attendance_marks': attendance_marks,
                'max_attendance_marks': max_attendance_marks,
                'total_attendance_days': total_days,
                'attendance_percentage': round(attendance_percentage, 2),
                'final_total': final_total,
                'total_possible': total_possible,
                'percentage': round(percentage, 2),
                'grade': grade,
                'gpa': round(gpa, 2),
                'exam_gpa': round(exam_gpa, 2),
                'passed_exams': passed_exams,
                'total_exams': exam_count,
                'previous_position': previous_position
            }
            
            rankings.append(ranking_data)
        
        # Sort by final percentage (descending), then by total marks, then by name
        rankings.sort(key=lambda x: (-x['percentage'], -x['final_total'], x['student_name']))
        
        # Assign positions and calculate position changes
        for idx, rank in enumerate(rankings):
            current_position = idx + 1
            rank['current_position'] = current_position
            rank['position'] = current_position  # For compatibility
            
            # Calculate position change
            if rank['previous_position']:
                rank['position_change'] = rank['previous_position'] - current_position
                if rank['position_change'] > 0:
                    rank['position_trend'] = 'up'
                elif rank['position_change'] < 0:
                    rank['position_trend'] = 'down'
                else:
                    rank['position_trend'] = 'same'
            else:
                rank['position_change'] = None
                rank['position_trend'] = 'new'
        
        # Filter out archived students from rankings before returning
        # (in case any old data exists)
        active_student_ids = [s.id for s in batch_students]
        rankings = [r for r in rankings if r['user_id'] in active_student_ids]
        
        # Re-sort by roll number for display (students without roll go to end)
        # This maintains the rank calculation but displays in roll order like attendance
        rankings.sort(key=lambda x: (x['roll_number'] is None, x['roll_number'] if x['roll_number'] else 999999))
        
        # If student, only return their data and nearby rankings
        if current_user.role == UserRole.STUDENT:
            student_rank = next(
                (rank for rank in rankings if rank['user_id'] == current_user.id),
                None
            )
            
            if student_rank:
                current_pos = student_rank['position']
                nearby_rankings = [
                    rank for rank in rankings 
                    if abs(rank['position'] - current_pos) <= 2
                ]
                
                return success_response('Student comprehensive ranking retrieved', {
                    'monthly_exam': serialize_monthly_exam(monthly_exam),
                    'individual_exams': [{'id': e.id, 'title': e.title, 'exam_title': e.title, 'subject': e.subject, 'marks': e.marks} for e in individual_exams],
                    'student_position': current_pos,
                    'total_students': len(rankings),
                    'nearby_rankings': nearby_rankings
                })
            else:
                return error_response('No data found for student', 404)
        
        # For teachers/admin, return full comprehensive ranking
        return success_response('Comprehensive monthly ranking retrieved', {
            'monthly_exam': serialize_monthly_exam(monthly_exam),
            'individual_exams': [{'id': e.id, 'title': e.title, 'exam_title': e.title, 'subject': e.subject, 'marks': e.marks} for e in individual_exams],
            'rankings': rankings,
            'total_students': len(rankings)
        })
        
    except Exception as e:
        logger.error(f"Error getting comprehensive monthly ranking: {e}")
        return error_response(f'Failed to retrieve comprehensive ranking: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/update-bonus', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def update_bonus_marks(exam_id):
    """Update bonus marks for students"""
    try:
        data = request.get_json()
        
        if not data or 'bonus_data' not in data:
            return error_response('Bonus data is required', 400)
        
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        bonus_data = data['bonus_data']  # List of {user_id, bonus_marks}
        updated_count = 0
        
        # For now, we'll store bonus marks in the Settings table as JSON
        # Key format: "monthly_exam_bonus_{exam_id}"
        bonus_key = f"monthly_exam_bonus_{exam_id}"
        
        # Get existing bonus data or create new
        bonus_setting = Settings.query.filter_by(key=bonus_key).first()
        if not bonus_setting:
            bonus_setting = Settings(
                key=bonus_key,
                value={},
                description=f"Bonus marks for Monthly Exam {monthly_exam.title}",
                category="exam_bonus",
                updated_by=get_current_user().id
            )
            db.session.add(bonus_setting)
        
        # Update bonus marks
        current_bonus = bonus_setting.value or {}
        
        for entry in bonus_data:
            user_id = str(entry.get('user_id'))
            bonus_marks = float(entry.get('bonus_marks', 0))
            
            if user_id:
                current_bonus[user_id] = bonus_marks
                updated_count += 1
        
        bonus_setting.value = current_bonus
        bonus_setting.updated_at = datetime.utcnow()
        bonus_setting.updated_by = get_current_user().id
        
        db.session.commit()
        
        return success_response('Bonus marks updated successfully', {
            'updated_count': updated_count,
            'exam_title': monthly_exam.title
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating bonus marks: {e}")
        return error_response(f'Failed to update bonus marks: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/assign-roll-numbers', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def assign_roll_numbers(exam_id):
    """Assign roll numbers to students for monthly exam"""
    try:
        from models import MonthlyRanking
        
        data = request.get_json()
        if not data or 'roll_assignments' not in data:
            return error_response('Roll assignments data is required', 400)
        
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        roll_assignments = data['roll_assignments']  # List of {user_id, roll_number}
        updated_count = 0
        
        for assignment in roll_assignments:
            user_id = assignment.get('user_id')
            roll_number = assignment.get('roll_number')
            
            if not user_id or not roll_number:
                continue
            
            # Check if user is in the batch
            user = User.query.get(user_id)
            if not user or monthly_exam.batch_id not in [b.id for b in user.batches]:
                continue
            
            # Create or update MonthlyRanking record
            ranking = MonthlyRanking.query.filter_by(
                monthly_exam_id=exam_id,
                user_id=user_id
            ).first()
            
            if not ranking:
                ranking = MonthlyRanking(
                    monthly_exam_id=exam_id,
                    user_id=user_id,
                    position=0,  # Will be updated when rankings are calculated
                    roll_number=roll_number
                )
                db.session.add(ranking)
            else:
                ranking.roll_number = roll_number
                ranking.updated_at = datetime.utcnow()
            
            updated_count += 1
        
        db.session.commit()
        
        return success_response('Roll numbers assigned successfully', {
            'updated_count': updated_count,
            'exam_title': monthly_exam.title
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error assigning roll numbers: {e}")
        return error_response(f'Failed to assign roll numbers: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/auto-assign-roll-numbers', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def auto_assign_roll_numbers(exam_id):
    """Auto-assign roll numbers based on current ranking"""
    try:
        from models import MonthlyRanking
        
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        # Get current comprehensive ranking
        ranking_response = get_comprehensive_monthly_ranking(exam_id)
        if not ranking_response.json.get('success'):
            return error_response('Failed to get current rankings', 500)
        
        rankings = ranking_response.json['data']['rankings']
        updated_count = 0
        
        for rank_data in rankings:
            user_id = rank_data['user_id']
            position = rank_data['position']
            
            # Create or update MonthlyRanking record with roll number = position
            ranking = MonthlyRanking.query.filter_by(
                monthly_exam_id=exam_id,
                user_id=user_id
            ).first()
            
            if not ranking:
                ranking = MonthlyRanking(
                    monthly_exam_id=exam_id,
                    user_id=user_id,
                    position=position,
                    roll_number=position
                )
                db.session.add(ranking)
            else:
                ranking.roll_number = position
                ranking.position = position
                ranking.updated_at = datetime.utcnow()
            
            updated_count += 1
        
        db.session.commit()
        
        return success_response('Roll numbers auto-assigned based on ranking', {
            'updated_count': updated_count,
            'exam_title': monthly_exam.title
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error auto-assigning roll numbers: {e}")
        return error_response(f'Failed to auto-assign roll numbers: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/generate-ranking', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def generate_monthly_ranking(exam_id):
    """Generate and save final monthly rankings to database"""
    try:
        from models import MonthlyRanking
        
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        # Get comprehensive ranking data (same as the display function)
        ranking_response_tuple = get_comprehensive_monthly_ranking(exam_id)
        ranking_response, status_code = ranking_response_tuple
        
        if status_code != 200:
            return error_response('Failed to calculate rankings', 500)
            
        ranking_data = ranking_response.get_json()
        if not ranking_data.get('success'):
            return error_response('Failed to calculate rankings', 500)
            
        rankings = ranking_data['data']['rankings']
        updated_count = 0
        
        # Find previous month's exam to get roll numbers
        prev_month = monthly_exam.month - 1 if monthly_exam.month > 1 else 12
        prev_year = monthly_exam.year if monthly_exam.month > 1 else monthly_exam.year - 1
        
        prev_exam = MonthlyExam.query.filter_by(
            batch_id=monthly_exam.batch_id,
            month=prev_month,
            year=prev_year
        ).first()
        
        # Build a map of user_id to previous roll number
        prev_roll_map = {}
        if prev_exam:
            print(f"\n🔍 Found previous exam: {prev_exam.month}/{prev_exam.year} (ID: {prev_exam.id})")
            prev_rankings = MonthlyRanking.query.filter_by(
                monthly_exam_id=prev_exam.id,
                is_final=True
            ).all()
            print(f"📋 Previous rankings count: {len(prev_rankings)}")
            for pr in prev_rankings:
                if pr.roll_number:
                    prev_roll_map[pr.user_id] = pr.roll_number
                    print(f"  User {pr.user_id} had roll number: {pr.roll_number}")
        else:
            print(f"\n⚠️  No previous exam found for {prev_month}/{prev_year}")
        
        print(f"📊 Previous roll map: {prev_roll_map}")
        
        # Clear existing rankings for this exam
        MonthlyRanking.query.filter_by(monthly_exam_id=exam_id).delete()
        
        # Create new ranking records and assign roll numbers from previous month
        for idx, rank_data in enumerate(rankings):
            # ALWAYS use previous month's roll number map, ignore current roll_number
            user_id = rank_data['user_id']
            
            # Inherit from previous month or assign new roll number
            if user_id in prev_roll_map:
                roll_number = prev_roll_map[user_id]
                print(f"✅ User {user_id}: Inherited roll {roll_number} from previous month")
            else:
                # New student: assign roll number based on current rank
                roll_number = idx + 1
                print(f"🆕 User {user_id}: New student, assigned roll {roll_number}")
            
            ranking = MonthlyRanking(
                monthly_exam_id=exam_id,
                user_id=rank_data['user_id'],
                position=rank_data['position'],
                roll_number=roll_number,  # Use previous month's roll or auto-assigned
                total_exam_marks=rank_data['total_exam_marks'],
                total_possible_marks=rank_data['total_possible_marks'],
                attendance_marks=rank_data['attendance_marks'],
                bonus_marks=0,  # No bonus marks as requested
                final_total=rank_data['final_total'],
                max_possible_total=rank_data['total_possible'],
                percentage=rank_data['percentage'],
                grade=rank_data['grade'],
                gpa=rank_data['gpa'],
                exam_gpa=rank_data['exam_gpa'],
                previous_position=rank_data.get('previous_position'),
                is_final=True
            )
            db.session.add(ranking)
            updated_count += 1
        
        db.session.commit()
        
        return success_response('Monthly rankings generated and saved successfully', {
            'rankings_count': updated_count,
            'exam_title': monthly_exam.title,
            'total_students': len(rankings)
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating monthly ranking: {e}")
        return error_response(f'Failed to generate ranking: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/rankings-status', methods=['GET'])
@login_required
def check_rankings_status(exam_id):
    """Check if rankings have been generated and saved for this exam"""
    try:
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        # Check if any rankings exist for this exam
        rankings_count = MonthlyRanking.query.filter_by(
            monthly_exam_id=exam_id,
            is_final=True
        ).count()
        
        return success_response('Rankings status retrieved', {
            'has_rankings': rankings_count > 0,
            'rankings_count': rankings_count,
            'exam_id': exam_id,
            'exam_title': monthly_exam.title
        })
        
    except Exception as e:
        logger.error(f"Error checking rankings status: {e}")
        return error_response(f'Failed to check rankings status: {str(e)}', 500)


@monthly_exams_bp.route('/<int:exam_id>/toggle-homepage', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def toggle_homepage_feature(exam_id):
    """Toggle whether this exam's top 3 students appear on homepage"""
    try:
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        data = request.get_json()
        show_on_homepage = data.get('show_on_homepage', False)
        
        # Update the flag
        monthly_exam.show_on_homepage = show_on_homepage
        db.session.commit()
        
        message = 'Top 3 students will now appear on homepage' if show_on_homepage else 'Removed from homepage featured results'
        
        return success_response(message, {
            'exam_id': exam_id,
            'show_on_homepage': show_on_homepage,
            'exam_title': monthly_exam.title
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling homepage feature: {e}")
        return error_response(f'Failed to update homepage feature: {str(e)}', 500)


@monthly_exams_bp.route('/<int:exam_id>/ranking', methods=['GET'])
@login_required
def get_monthly_ranking(exam_id):
    """Get ranking for monthly exam (redirect to comprehensive ranking)"""
    return get_comprehensive_monthly_ranking(exam_id)

@monthly_exams_bp.route('/<int:exam_id>/merit-list', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_merit_list(exam_id):
    """Get merit list for monthly exam"""
    try:
        top_count = request.args.get('top', type=int, default=10)
        
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        rankings = calculate_monthly_rankings(exam_id, return_data=True)
        
        # Get top performers
        merit_list = rankings[:top_count]
        
        # Add detailed performance data
        for rank in merit_list:
            user = User.query.get(rank['user_id'])
            subject_wise_marks = get_subject_wise_marks(exam_id, rank['user_id'])
            
            rank.update({
                'student_name': user.full_name,
                'student_id': user.student_id,
                'phone_number': user.phoneNumber,
                'subject_wise_marks': subject_wise_marks
            })
        
        return success_response('Merit list retrieved successfully', {
            'monthly_exam': serialize_monthly_exam(monthly_exam),
            'merit_list': merit_list,
            'total_students': len(rankings)
        })
        
    except Exception as e:
        logger.error(f"Error getting merit list: {e}")
        return error_response(f'Failed to retrieve merit list: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/analytics', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_exam_analytics(exam_id):
    """Get performance analytics for monthly exam"""
    try:
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        # Get all marks for this exam
        marks = (db.session.query(MonthlyMark)
                .filter_by(monthly_exam_id=exam_id)
                .all())
        
        if not marks:
            return error_response('No marks data available', 404)
        
        # Calculate analytics
        total_students = len(set(mark.user_id for mark in marks))
        
        # Overall performance
        all_percentages = [mark.percentage for mark in marks if not mark.is_absent]
        
        if all_percentages:
            avg_percentage = sum(all_percentages) / len(all_percentages)
            highest_percentage = max(all_percentages)
            lowest_percentage = min(all_percentages)
        else:
            avg_percentage = highest_percentage = lowest_percentage = 0
        
        # Pass/Fail statistics
        pass_threshold = (monthly_exam.pass_marks / monthly_exam.total_marks) * 100
        passed_count = sum(1 for p in all_percentages if p >= pass_threshold)
        failed_count = len(all_percentages) - passed_count
        absent_count = sum(1 for mark in marks if mark.is_absent)
        
        # Grade distribution
        grade_distribution = {}
        for mark in marks:
            if not mark.is_absent:
                grade = mark.grade or 'F'
                grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
        
        # Subject-wise performance
        subjects = list(set(
            exam.subject for exam in monthly_exam.individual_exams
        ))
        
        subject_analytics = {}
        for subject in subjects:
            subject_marks = [
                mark for mark in marks 
                if mark.individual_exam.subject == subject and not mark.is_absent
            ]
            
            if subject_marks:
                subject_percentages = [mark.percentage for mark in subject_marks]
                subject_analytics[subject] = {
                    'average': sum(subject_percentages) / len(subject_percentages),
                    'highest': max(subject_percentages),
                    'lowest': min(subject_percentages),
                    'students_count': len(subject_marks)
                }
        
        analytics_data = {
            'monthly_exam': serialize_monthly_exam(monthly_exam),
            'overall_statistics': {
                'total_students': total_students,
                'average_percentage': round(avg_percentage, 2),
                'highest_percentage': round(highest_percentage, 2),
                'lowest_percentage': round(lowest_percentage, 2),
                'pass_percentage': round((passed_count / total_students * 100), 2) if total_students > 0 else 0
            },
            'performance_breakdown': {
                'passed': passed_count,
                'failed': failed_count,
                'absent': absent_count,
                'total': total_students
            },
            'grade_distribution': grade_distribution,
            'subject_wise_performance': subject_analytics
        }
        
        return success_response('Analytics retrieved successfully', analytics_data)
        
    except Exception as e:
        logger.error(f"Error getting exam analytics: {e}")
        return error_response(f'Failed to retrieve analytics: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/publish-results', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def publish_results(exam_id):
    """Publish monthly exam results"""
    try:
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        if monthly_exam.show_results:
            return error_response('Results already published', 400)
        
        # Mark results as published
        monthly_exam.show_results = True
        monthly_exam.result_published_at = datetime.utcnow()
        
        db.session.commit()
        
        # Send notifications to students (optional)
        send_notifications = request.get_json().get('send_notifications', False)
        
        if send_notifications:
            batch = monthly_exam.batch
            students = [s for s in batch.students if s.role == UserRole.STUDENT and s.is_active]
            
            message = f"প্রিয় শিক্ষার্থী, {monthly_exam.title} এর ফলাফল প্রকাশিত হয়েছে। আপনার ফলাফল দেখতে লগইন করুন।"
            
            try:
                send_bulk_notification(students, message, 'result')
            except Exception as e:
                logger.warning(f"Failed to send result notifications: {e}")
        
        return success_response('Results published successfully', {
            'monthly_exam': serialize_monthly_exam(monthly_exam),
            'notifications_sent': send_notifications
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error publishing results: {e}")
        return error_response(f'Failed to publish results: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/individual-exams', methods=['GET'])
@login_required
def get_individual_exams(exam_id):
    """Get individual exams for a monthly exam"""
    try:
        current_user = get_current_user()
        
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        # Check access permission
        if current_user.role == UserRole.STUDENT:
            user_batch_ids = [b.id for b in current_user.batches if b.is_active]
            if monthly_exam.batch_id not in user_batch_ids:
                return error_response('Access denied', 403)
        
        individual_exams = monthly_exam.individual_exams
        
        exams_data = []
        for exam in individual_exams:
            # Get marks count for this individual exam
            marks_count = MonthlyMark.query.filter_by(individual_exam_id=exam.id).count()
            
            exam_data = {
                'id': exam.id,
                'title': exam.title,
                'subject': exam.subject,
                'marks': exam.marks,
                'exam_date': exam.exam_date.isoformat(),
                'duration': exam.duration,
                'order_index': exam.order_index,
                'marks_count': marks_count
            }
            exams_data.append(exam_data)
        
        # Sort by order_index
        exams_data.sort(key=lambda x: x['order_index'])
        
        return success_response('Individual exams retrieved successfully', {
            'monthly_exam': serialize_monthly_exam(monthly_exam),
            'individual_exams': exams_data
        })
        
    except Exception as e:
        logger.error(f"Error getting individual exams: {e}")
        return error_response(f'Failed to retrieve individual exams: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/individual-exams', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def create_individual_exam(exam_id):
    """Create an individual exam within a monthly exam"""
    try:
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        required_fields = ['title', 'subject', 'marks']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return error_response(f'Missing required fields: {", ".join(missing_fields)}', 400)
        
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        # Set default exam date to current date if not provided
        exam_date_str = data.get('exam_date')
        if exam_date_str:
            exam_date = datetime.fromisoformat(exam_date_str.replace('Z', '+00:00'))
        else:
            exam_date = datetime.now()
        
        # Validate exam date is within monthly exam period
        if exam_date < monthly_exam.start_date or exam_date > monthly_exam.end_date:
            # If exam date is outside range, set it to start date of monthly exam
            exam_date = monthly_exam.start_date
        
        # Get the next order index
        max_order = db.session.query(func.max(IndividualExam.order_index)).filter_by(monthly_exam_id=exam_id).scalar() or 0
        
        individual_exam = IndividualExam(
            monthly_exam_id=exam_id,
            title=data['title'],
            subject=data['subject'],
            marks=data['marks'],
            exam_date=exam_date,
            duration=data.get('duration', 60),
            order_index=max_order + 1
        )
        
        db.session.add(individual_exam)
        db.session.flush()
        
        # Update monthly exam total marks automatically
        new_total_result = db.session.query(func.sum(IndividualExam.marks)).filter_by(monthly_exam_id=exam_id).scalar()
        new_total = int(new_total_result or 0)
        monthly_exam.total_marks = new_total
        monthly_exam.pass_marks = int(new_total * 0.33)  # Update pass marks to 33% of new total
        
        db.session.commit()
        
        return success_response('Individual exam created successfully', {
            'individual_exam': {
                'id': individual_exam.id,
                'title': individual_exam.title,
                'subject': individual_exam.subject,
                'marks': individual_exam.marks,
                'exam_date': individual_exam.exam_date.isoformat(),
                'duration': individual_exam.duration,
                'order_index': individual_exam.order_index,
                'marks_count': 0
            },
            'monthly_exam_total': new_total,
            'monthly_exam_pass_marks': monthly_exam.pass_marks
        }, 201)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating individual exam: {e}")
        return error_response(f'Failed to create individual exam: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/individual-exams/<int:individual_exam_id>/marks', methods=['POST'])
@login_required
def submit_individual_exam_marks(exam_id, individual_exam_id):
    """Submit marks for a specific individual exam"""
    try:
        # Check user permissions
        current_user = get_current_user()
        if not current_user:
            logger.error("No current user found in session")
            return error_response('Authentication required', 401)
        
        if current_user.role not in [UserRole.TEACHER, UserRole.SUPER_USER]:
            logger.error(f"User {current_user.id} with role {current_user.role} attempted to save marks")
            return error_response('Insufficient permissions - only teachers and administrators can save marks', 403)
        
        data = request.get_json()
        logger.info(f"Received marks submission request for exam {exam_id}, individual exam {individual_exam_id}")
        logger.info(f"Request data: {data}")
        logger.info(f"User: {current_user.id} ({current_user.role})")
        
        # Enhanced validation
        if not data:
            logger.error("No request data provided")
            return error_response('Request data is required', 400)
            
        if 'students' not in data:
            logger.error("No student marks data provided")
            return error_response('Student marks data is required', 400)
            
        if not isinstance(data['students'], list):
            logger.error("Student marks data must be a list")
            return error_response('Student marks data must be a list', 400)
        
        # Validate monthly exam exists
        try:
            monthly_exam = MonthlyExam.query.get(exam_id)
            if not monthly_exam:
                logger.error(f"Monthly exam not found: {exam_id}")
                return error_response('Monthly exam not found', 404)
        except Exception as db_error:
            logger.error(f"Database error while fetching monthly exam {exam_id}: {str(db_error)}")
            return error_response(f'Database error: {str(db_error)}', 500)
        
        # Validate individual exam exists and belongs to monthly exam
        try:
            individual_exam = IndividualExam.query.filter_by(
                id=individual_exam_id, 
                monthly_exam_id=exam_id
            ).first()
            
            if not individual_exam:
                logger.error(f"Individual exam not found: {individual_exam_id} for monthly exam {exam_id}")
                return error_response('Individual exam not found', 404)
        except Exception as db_error:
            logger.error(f"Database error while fetching individual exam {individual_exam_id}: {str(db_error)}")
            return error_response(f'Database error: {str(db_error)}', 500)
        
        students_data = data['students']  # List of student mark entries
        saved_count = 0
        errors = []  # Track any errors
        sms_notifications = []  # Track SMS notifications to send
        
        # Validate students data structure
        if not students_data:
            logger.error("Empty students data provided")
            return error_response('At least one student mark is required', 400)
        
        for idx, student_entry in enumerate(students_data):
            try:
                # Validate student entry structure
                if not isinstance(student_entry, dict):
                    errors.append(f"Student entry {idx + 1}: Must be an object")
                    continue
                
                user_id = student_entry.get('user_id')
                marks_obtained = student_entry.get('marks_obtained')
                
                # Validate user_id
                if not user_id:
                    errors.append(f"Student entry {idx + 1}: user_id is required")
                    continue
                
                # Validate marks_obtained
                if marks_obtained is None or marks_obtained == '':
                    errors.append(f"Student entry {idx + 1}: marks_obtained is required")
                    continue
                
                # Convert and validate marks
                try:
                    marks_obtained = float(marks_obtained)
                    if marks_obtained < 0:
                        errors.append(f"Student entry {idx + 1}: marks cannot be negative")
                        continue
                    if marks_obtained > individual_exam.marks:
                        errors.append(f"Student entry {idx + 1}: marks ({marks_obtained}) cannot exceed total marks ({individual_exam.marks})")
                        continue
                except (ValueError, TypeError) as e:
                    errors.append(f"Student entry {idx + 1}: invalid marks format ({marks_obtained})")
                    continue
                
                # Validate user exists
                try:
                    user = User.query.get(user_id)
                    if not user:
                        errors.append(f"Student entry {idx + 1}: student not found (ID: {user_id})")
                        continue
                except Exception as db_error:
                    error_msg = f"Student entry {idx + 1}: database error while fetching student {user_id}: {str(db_error)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
                # Check if mark already exists
                try:
                    existing_mark = MonthlyMark.query.filter_by(
                        monthly_exam_id=exam_id,
                        individual_exam_id=individual_exam_id,
                        user_id=user_id
                    ).first()
                except Exception as db_error:
                    error_msg = f"Student entry {idx + 1}: database error while checking existing marks: {str(db_error)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
                
                # Calculate percentage, grade, and GPA
                percentage = (marks_obtained / individual_exam.marks) * 100 if individual_exam.marks > 0 else 0
                grade, gpa = calculate_grade_and_gpa(percentage)
                
                # Prepare SMS notification data
                sms_notifications.append({
                    'student': user,
                    'marks_obtained': marks_obtained,
                    'total_marks': individual_exam.marks,
                    'percentage': percentage,
                    'grade': grade,
                    'subject': individual_exam.subject,
                    'exam_title': individual_exam.title
                })
                
                if existing_mark:
                    # Update existing mark
                    existing_mark.marks_obtained = marks_obtained
                    existing_mark.total_marks = individual_exam.marks
                    existing_mark.percentage = percentage
                    existing_mark.grade = grade
                    existing_mark.gpa = gpa
                    existing_mark.is_absent = False  # No absent option
                    existing_mark.remarks = ''      # No remarks option
                    existing_mark.updated_at = datetime.utcnow()
                    logger.info(f"Updated mark for user {user_id}: {marks_obtained}/{individual_exam.marks}")
                else:
                    # Create new mark
                    monthly_mark = MonthlyMark(
                        monthly_exam_id=exam_id,
                        individual_exam_id=individual_exam_id,
                        user_id=user_id,
                        marks_obtained=marks_obtained,
                        total_marks=individual_exam.marks,
                        percentage=percentage,
                        grade=grade,
                        gpa=gpa,
                        is_absent=False,  # No absent option
                        remarks=''        # No remarks option
                    )
                    db.session.add(monthly_mark)
                    logger.info(f"Created new mark for user {user_id}: {marks_obtained}/{individual_exam.marks}")
                
                saved_count += 1
                
            except Exception as entry_error:
                error_msg = f"Student entry {idx + 1}: {str(entry_error)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
        
        # If there were validation errors, return them
        if errors and saved_count == 0:
            return error_response(f'Validation errors: {"; ".join(errors[:5])}', 400)
        
        # Commit database changes
        try:
            db.session.commit()
            logger.info(f"Successfully saved {saved_count} marks to database")
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database commit failed: {str(db_error)}")
            return error_response(f'Failed to save marks to database: {str(db_error)}', 500)
        
        # Send SMS notifications after successful save
        current_user = get_current_user()
        sms_sent_count = 0
        sms_failed_count = 0
        sms_errors = []
        
        # Check if SMS is enabled and user has SMS balance
        send_sms = data.get('send_sms', False)
        if send_sms and current_user.sms_count > 0:
            # Get exam result template with better fallback system
            exam_template_message = get_sms_template('exam_result')
            
            for notification in sms_notifications:
                try:
                    student = notification['student']
                    
                    # Determine phone number to send to (prefer parent/guardian phone)
                    target_phone = get_target_phone(student)
                    
                    if not target_phone:
                        sms_errors.append(f"No valid phone number for {student.full_name}")
                        sms_failed_count += 1
                        continue
                    
                    # Generate message using template
                    message = generate_exam_result_message(exam_template_message, notification)
                    
                    # Send SMS
                    sms_result = send_sms_notification(target_phone, message, current_user)
                    if sms_result.get('success'):
                        sms_sent_count += 1
                        logger.info(f"SMS sent successfully to {target_phone} for {student.full_name}")
                    else:
                        error_msg = sms_result.get('error', 'Unknown SMS error')
                        sms_errors.append(f"SMS failed for {student.full_name}: {error_msg}")
                        sms_failed_count += 1
                            
                except Exception as sms_error:
                    error_msg = f"SMS error for {student.full_name}: {str(sms_error)}"
                    logger.warning(error_msg)
                    sms_errors.append(error_msg)
                    sms_failed_count += 1
        
        # Prepare response data
        response_data = {
            'saved_count': saved_count,
            'exam_title': individual_exam.title,
            'total_marks': individual_exam.marks
        }
        
        # Add validation errors if any
        if errors:
            response_data['validation_errors'] = errors[:10]  # Limit to first 10 errors
        
        # Add SMS info if SMS was attempted
        if send_sms:
            response_data.update({
                'sms_sent': sms_sent_count,
                'sms_failed': sms_failed_count,
                'remaining_sms_balance': current_user.sms_count
            })
            
            # Add SMS errors if any
            if sms_errors:
                response_data['sms_errors'] = sms_errors[:10]  # Limit to first 10 errors
        
        # Determine response message
        if saved_count > 0:
            message = f'Successfully saved {saved_count} marks'
            if errors:
                message += f' (with {len(errors)} validation errors)'
            return success_response(message, response_data)
        else:
            return error_response('No marks were saved due to validation errors', response_data, 400)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error saving individual exam marks: {str(e)}")
        return error_response(f'An unexpected error occurred while saving marks: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/individual-exams/<int:individual_exam_id>/marks', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_individual_exam_marks(exam_id, individual_exam_id):
    """Get existing marks for an individual exam"""
    try:
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        individual_exam = IndividualExam.query.filter_by(
            id=individual_exam_id, 
            monthly_exam_id=exam_id
        ).first()
        
        if not individual_exam:
            return error_response('Individual exam not found', 404)
        
        # Get existing marks
        marks = MonthlyMark.query.filter_by(
            monthly_exam_id=exam_id,
            individual_exam_id=individual_exam_id
        ).all()
        
        marks_dict = {}
        for mark in marks:
            marks_dict[mark.user_id] = {
                'marks_obtained': mark.marks_obtained,
                'is_absent': mark.is_absent,
                'remarks': mark.remarks or '',
                'percentage': mark.percentage,
                'grade': mark.grade
            }
        
        return success_response('Marks retrieved successfully', {
            'individual_exam': {
                'id': individual_exam.id,
                'title': individual_exam.title,
                'subject': individual_exam.subject,
                'marks': individual_exam.marks
            },
            'marks': marks_dict
        })
        
    except Exception as e:
        logger.error(f"Error getting individual exam marks: {e}")
        return error_response(f'Failed to retrieve marks: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>/individual-exams/<int:individual_exam_id>', methods=['DELETE'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def delete_individual_exam(exam_id, individual_exam_id):
    """Delete an individual exam and all associated marks, then update monthly exam total"""
    try:
        monthly_exam = MonthlyExam.query.get(exam_id)
        if not monthly_exam:
            return error_response('Monthly exam not found', 404)
        
        individual_exam = IndividualExam.query.filter_by(
            id=individual_exam_id, 
            monthly_exam_id=exam_id
        ).first()
        
        if not individual_exam:
            return error_response('Individual exam not found', 404)
        
        # Delete all marks associated with this individual exam (CASCADE delete)
        marks_deleted = MonthlyMark.query.filter_by(individual_exam_id=individual_exam_id).delete()
        
        # Delete all rankings that might be affected
        MonthlyRanking.query.filter_by(monthly_exam_id=exam_id).delete()
        
        # Delete the individual exam
        db.session.delete(individual_exam)
        db.session.flush()
        
        # Update monthly exam total marks automatically
        new_total_result = db.session.query(func.sum(IndividualExam.marks)).filter_by(monthly_exam_id=exam_id).scalar()
        new_total = int(new_total_result or 0)
        monthly_exam.total_marks = new_total
        monthly_exam.pass_marks = int(new_total * 0.33) if new_total > 0 else 0
        
        db.session.commit()
        
        return success_response(f'Individual exam deleted successfully. {marks_deleted} marks record(s) removed.', {
            'monthly_exam_total': new_total,
            'monthly_exam_pass_marks': monthly_exam.pass_marks,
            'marks_deleted': marks_deleted
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting individual exam: {e}")
        return error_response(f'Failed to delete individual exam: {str(e)}', 500)

@monthly_exams_bp.route('/<int:exam_id>', methods=['DELETE'])
@login_required
def delete_monthly_exam(exam_id):
    """Delete a monthly exam period and all associated data (marks, rankings, individual exams)"""
    try:
        current_user = get_current_user()
        monthly_exam = db.session.get(MonthlyExam, exam_id)
        
        if not monthly_exam:
            return error_response('Monthly exam not found. It may have been already deleted.', 404)
        
        # Check if user has permission
        if current_user.role not in [UserRole.SUPER_USER, UserRole.TEACHER]:
            return error_response('Permission denied', 403)
        
        # CASCADE DELETE: Delete all associated data
        
        # Delete all marks for this monthly exam
        marks_deleted = MonthlyMark.query.filter_by(monthly_exam_id=exam_id).delete()
        
        # Delete rankings
        rankings_deleted = MonthlyRanking.query.filter_by(monthly_exam_id=exam_id).delete()
        
        # Delete individual exams
        individual_exams_deleted = IndividualExam.query.filter_by(monthly_exam_id=exam_id).delete()
        
        # Delete the monthly exam
        db.session.delete(monthly_exam)
        db.session.commit()
        
        return success_response(f'Monthly exam period deleted successfully. Removed {marks_deleted} marks, {rankings_deleted} rankings, and {individual_exams_deleted} individual exams.', {
            'marks_deleted': marks_deleted,
            'rankings_deleted': rankings_deleted,
            'individual_exams_deleted': individual_exams_deleted
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting monthly exam: {str(e)}')
        return error_response(f'Failed to delete monthly exam: {str(e)}', 500)

# Helper functions

def serialize_monthly_exam(exam):
    """Serialize monthly exam to dict"""
    return {
        'id': exam.id,
        'title': exam.title,
        'description': exam.description,
        'month': exam.month,
        'year': exam.year,
        'month_name': calendar.month_name[exam.month],
        'total_marks': exam.total_marks,
        'pass_marks': exam.pass_marks,
        'start_date': exam.start_date.isoformat(),
        'end_date': exam.end_date.isoformat(),
        'batch_id': exam.batch_id,
        'batch_name': exam.batch.name,
        'status': exam.status,
        'show_results': exam.show_results,
        'show_on_homepage': exam.show_on_homepage if hasattr(exam, 'show_on_homepage') else False,
        'result_published_at': exam.result_published_at.isoformat() if exam.result_published_at else None,
        'individual_exams_count': len(exam.individual_exams),
        'created_at': exam.created_at.isoformat()
    }

def calculate_grade_and_gpa(percentage):
    """Calculate grade and GPA based on percentage"""
    if percentage >= 80:
        return 'A+', 5.00
    elif percentage >= 70:
        return 'A', 4.00
    elif percentage >= 60:
        return 'A-', 3.50
    elif percentage >= 50:
        return 'B', 3.00
    elif percentage >= 40:
        return 'C', 2.00
    elif percentage >= 33:
        return 'D', 1.00
    else:
        return 'F', 0.00

def get_bonus_marks_for_exam(exam_id, user_id):
    """Get bonus marks for a student in a monthly exam"""
    try:
        bonus_key = f"monthly_exam_bonus_{exam_id}"
        bonus_setting = Settings.query.filter_by(key=bonus_key).first()
        
        if bonus_setting and bonus_setting.value:
            return float(bonus_setting.value.get(str(user_id), 0))
        
        return 0
    except Exception as e:
        logger.error(f"Error getting bonus marks: {e}")
        return 0

def calculate_monthly_rankings(exam_id, return_data=False):
    """Calculate and update rankings for monthly exam"""
    try:
        # Get aggregated marks per student
        student_totals = (
            db.session.query(
                MonthlyMark.user_id,
                func.sum(MonthlyMark.marks_obtained).label('total_obtained'),
                func.sum(MonthlyMark.total_marks).label('total_marks'),
                func.avg(MonthlyMark.gpa).label('avg_gpa'),
                func.count(case((MonthlyMark.is_absent == True, 1))).label('absent_count')
            )
            .filter_by(monthly_exam_id=exam_id)
            .group_by(MonthlyMark.user_id)
            .all()
        )
        
        # Calculate overall percentage and rank
        rankings = []
        for student in student_totals:
            if student.total_marks > 0:
                overall_percentage = (student.total_obtained / student.total_marks) * 100
                overall_grade, overall_gpa = calculate_grade_and_gpa(overall_percentage)
                
                rankings.append({
                    'user_id': student.user_id,
                    'total_obtained': student.total_obtained,
                    'total_marks': student.total_marks,
                    'percentage': round(overall_percentage, 2),
                    'grade': overall_grade,
                    'gpa': round(overall_gpa, 2),
                    'absent_count': student.absent_count or 0
                })
        
        # Sort by percentage (descending) and assign ranks
        rankings.sort(key=lambda x: (-x['percentage'], x['user_id']))
        
        for idx, rank in enumerate(rankings):
            rank['position'] = idx + 1
        
        if return_data:
            return rankings
        
        return True
        
    except Exception as e:
        logger.error(f"Error calculating rankings: {e}")
        return False

def get_student_monthly_marks(exam_id, user_id):
    """Get marks for a specific student in monthly exam"""
    marks = (MonthlyMark.query
            .filter_by(monthly_exam_id=exam_id, user_id=user_id)
            .all())
    
    marks_data = []
    for mark in marks:
        marks_data.append({
            'subject': mark.individual_exam.subject,
            'marks_obtained': mark.marks_obtained,
            'total_marks': mark.total_marks,
            'percentage': mark.percentage,
            'grade': mark.grade,
            'gpa': mark.gpa,
            'is_absent': mark.is_absent
        })
    
    return marks_data

def get_student_rank(exam_id, user_id):
    """Get rank for a specific student"""
    rankings = calculate_monthly_rankings(exam_id, return_data=True)
    
    for rank in rankings:
        if rank['user_id'] == user_id:
            return rank['position']
    
    return None

def get_subject_wise_marks(exam_id, user_id):
    """Get subject-wise marks for a student"""
    marks = (MonthlyMark.query
            .filter_by(monthly_exam_id=exam_id, user_id=user_id)
            .join(IndividualExam)
            .all())
    
    subject_marks = {}
    for mark in marks:
        subject = mark.individual_exam.subject
        subject_marks[subject] = {
            'marks_obtained': mark.marks_obtained,
            'total_marks': mark.total_marks,
            'percentage': mark.percentage,
            'grade': mark.grade,
            'gpa': mark.gpa
        }
    
    return subject_marks

def validate_phone_number(phone):
    """Validate and format phone number"""
    # Remove any non-digit characters
    phone = re.sub(r'[^\d]', '', phone)
    
    # Handle country code
    if phone.startswith('880'):
        phone = phone[3:]
    elif phone.startswith('+880'):
        phone = phone[4:]
    
    # Validate Bangladesh mobile number format
    if len(phone) == 11 and phone.startswith('01'):
        return phone
    
    return None

def get_sms_template(template_type):
    """Get SMS template with fallback to default templates"""
    try:
        # PRIORITY 1: Get template from database (permanent storage for all teachers)
        template_key = f"sms_template_{template_type}"
        template_setting = Settings.query.filter_by(key=template_key).first()
        
        if template_setting and template_setting.value:
            message = template_setting.value.get('message')
            if message:
                return message
        
        # PRIORITY 2: Try session as fallback (for backward compatibility)
        from flask import session
        custom_templates = session.get('custom_templates', {})
        custom_template = custom_templates.get(template_type)
        
        if custom_template:
            return custom_template
        
        # PRIORITY 3: Return default template
        return get_default_template(template_type)
        
    except Exception as e:
        logger.warning(f"Error getting SMS template: {e}")
        return get_default_template(template_type)

def get_default_template(template_type):
    """Get default short SMS templates (Bangla, optimized for 1 SMS)"""
    templates = {
        'exam_result': "{student_name} পেয়েছে {marks}/{total} ({subject}) {date}",
        'attendance_present': "{student_name} উপস্থিত ({batch_name})",
        'attendance_absent': "{student_name} অনুপস্থিত {date} ({batch_name})",
        'fee_reminder': "{student_name} এর ফি {amount}৳ বকেয়া। শেষ তারিখ {due_date}",
        'general': "{student_name}: {message}"
    }
    return templates.get(template_type, templates['general'])

def get_target_phone(student):
    """Get the target phone number for SMS (prefer guardian phone)"""
    try:
        # Prefer guardian phone if available
        if hasattr(student, 'guardian_phone') and student.guardian_phone:
            formatted_phone = validate_phone_number(student.guardian_phone)
            if formatted_phone:
                return formatted_phone
        
        # Fall back to student phone
        if student.phoneNumber:
            formatted_phone = validate_phone_number(student.phoneNumber)
            if formatted_phone:
                return formatted_phone
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting target phone for student {student.id}: {e}")
        return None

def generate_exam_result_message(template, notification):
    """Generate SMS message using template and notification data"""
    try:
        # Prepare template variables (short format with DD/MM date)
        variables = {
            'student_name': notification['student'].first_name,
            'full_name': notification['student'].full_name,
            'subject': notification['subject'],
            'marks': int(notification['marks_obtained']),
            'total': int(notification['total_marks']),
            'percentage': notification['percentage'],
            'grade': notification['grade'],
            'exam_title': notification['exam_title'],
            'date': datetime.now().strftime('%d/%m')  # Short date format DD/MM
        }
        
        # Format the template (short Bangla: "{student_name} পেয়েছে {marks}/{total} ({subject}) {date}")
        message = template.format(**variables)
        
        # New short template fits in 1 SMS (100 chars for mixed Bangla/English)
        return message
        
    except Exception as e:
        logger.warning(f"Error generating SMS message: {e}")
        # Ultimate fallback
        return f"{notification['student'].first_name} scored {int(notification['marks_obtained'])}/{int(notification['total_marks'])} marks in {notification['subject']}"

def send_sms_notification(phone, message, current_user):
    """Send SMS notification and log the attempt"""
    try:
        # Use the BulkSMSBD API
        api_key = "gsOKLO6XtKsANCvgPHNt"
        sender_id = "8809617628909"
        api_url = "http://bulksmsbd.net/api/smsapi"
        
        # Format phone number
        formatted_phone = validate_phone_number(phone)
        if not formatted_phone:
            return {'success': False, 'error': 'Invalid phone number format'}
        
        # Prepare API payload
        payload = {
            'api_key': api_key,
            'type': 'text',
            'number': formatted_phone,
            'senderid': sender_id,
            'message': message
        }
        
        # Create SMS log entry
        sms_log = SmsLog(
            phone_number=formatted_phone,
            message=message,
            sent_by=current_user.id,
            status=SmsStatus.PENDING
        )
        
        # Find user by phone number for logging
        user = User.query.filter_by(phoneNumber=formatted_phone).first()
        if user:
            sms_log.user_id = user.id
        
        # Send SMS
        response = requests.post(api_url, data=payload, timeout=30)
        
        if response.status_code == 200:
            # Check if response contains success indicator
            response_text = response.text.lower()
            if 'success' in response_text or 'sent' in response_text:
                sms_log.status = SmsStatus.SENT
                sms_log.sent_at = datetime.utcnow()
                sms_log.cost = 1  # Default cost
                
                # Deduct SMS count from user
                current_user.sms_count = max(0, current_user.sms_count - 1)
                
                db.session.add(sms_log)
                db.session.commit()
                
                return {'success': True, 'message_id': None, 'cost': 1}
            else:
                sms_log.status = SmsStatus.FAILED
                sms_log.api_response = {'error': response.text}
                db.session.add(sms_log)
                db.session.commit()
                
                return {'success': False, 'error': response.text}
        else:
            sms_log.status = SmsStatus.FAILED
            sms_log.api_response = {'error': f'HTTP {response.status_code}: {response.text}'}
            db.session.add(sms_log)
            db.session.commit()
            
            return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
    
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'SMS API timeout'}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'SMS API connection error'}
    except Exception as e:
        return {'success': False, 'error': f'SMS API error: {str(e)}'}


@monthly_exams_bp.route('/homepage-top-performers', methods=['GET'])
def get_homepage_top_performers():
    """Get top 3 students from all monthly exams featured on homepage"""
    try:
        # Find all monthly exams that are marked to show on homepage
        featured_exams = MonthlyExam.query.filter_by(show_on_homepage=True).all()
        
        if not featured_exams:
            return success_response('No featured exams', {'featured_results': []})
        
        featured_results = []
        
        for exam in featured_exams:
            # Get top 3 rankings for this exam
            top_rankings = MonthlyRanking.query.filter_by(
                monthly_exam_id=exam.id,
                is_final=True
            ).order_by(MonthlyRanking.position.asc()).limit(3).all()
            
            if top_rankings:
                top_students = []
                for ranking in top_rankings:
                    student = User.query.get(ranking.user_id)
                    if student:
                        top_students.append({
                            'position': ranking.position,
                            'student_name': student.full_name,
                            'student_phone': student.phoneNumber,
                            'roll_number': ranking.roll_number,
                            'total_marks': ranking.final_total,
                            'total_possible': ranking.max_possible_total,
                            'percentage': round(ranking.percentage, 2) if ranking.percentage else 0,
                            'grade': ranking.grade
                        })
                
                featured_results.append({
                    'exam_id': exam.id,
                    'exam_title': exam.title,
                    'month': exam.month,
                    'year': exam.year,
                    'batch_name': exam.batch.name if exam.batch else 'N/A',
                    'top_students': top_students
                })
        
        return success_response('Featured top performers retrieved', {
            'featured_results': featured_results,
            'count': len(featured_results)
        })
        
    except Exception as e:
        logger.error(f"Error getting homepage top performers: {e}")
        return error_response(f'Failed to get top performers: {str(e)}', 500)