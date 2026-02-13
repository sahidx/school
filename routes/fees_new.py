"""
Fee Management Routes - Simplified (No JF/TF columns)
"""
from flask import Blueprint, request, jsonify
from models import db, User, Batch, Fee, UserRole, FeeStatus
from sqlalchemy import extract
from datetime import datetime, date
from decimal import Decimal
import calendar

fees_bp = Blueprint('fees', __name__)

def success_response(message, data=None, status=200):
    """Standard success response format"""
    response = {
        'success': True,
        'message': message
    }
    if data:
        response['data'] = data
    return jsonify(response), status

def error_response(message, status=400):
    """Standard error response format"""
    return jsonify({
        'success': False,
        'error': message
    }), status


@fees_bp.route('/load-monthly', methods=['GET'])
def load_monthly_fees():
    """
    Load monthly fees for a batch and year
    GET /api/fees/load-monthly?batch_id=1&year=2025
    """
    try:
        batch_id = request.args.get('batch_id', type=int)
        year = request.args.get('year', type=int)
        
        if not batch_id:
            return error_response('batch_id is required', 400)
        
        if not year:
            year = datetime.now().year
        
        if year < 2020 or year > 2030:
            return error_response('Year must be between 2020 and 2030', 400)
        
        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)
        
        # Get students sorted by roll number from most recent monthly exam
        from models import MonthlyExam, MonthlyRanking
        
        # Find most recent monthly exam for this batch that has finalized rankings
        most_recent_exam = (
            MonthlyExam.query.join(MonthlyRanking, MonthlyRanking.monthly_exam_id == MonthlyExam.id)
            .filter(
                MonthlyExam.batch_id == batch_id,
                MonthlyRanking.is_final == True
            )
            .order_by(MonthlyExam.year.desc(), MonthlyExam.month.desc(), MonthlyExam.id.desc())
            .first()
        )
        
        # Build roll number map
        roll_map = {}
        if most_recent_exam:
            rankings = MonthlyRanking.query.filter_by(
                monthly_exam_id=most_recent_exam.id,
                is_final=True
            ).all()
            
            for ranking in rankings:
                if ranking.roll_number:
                    roll_map[ranking.user_id] = ranking.roll_number
        
        students = User.query.filter(
            User.role == UserRole.STUDENT,
            User.is_active == True,
            User.is_archived == False
        ).join(User.batches).filter(Batch.id == batch_id).all()
        
        # Sort by roll number (students without roll go to end)
        students.sort(key=lambda s: (s.id not in roll_map, roll_map.get(s.id, 999999)))
        
        if not students:
            return error_response('No students found in this batch', 404)
        
        fees = Fee.query.filter(
            Fee.batch_id == batch_id,
            extract('year', Fee.due_date) == year
        ).all()
        
        # Create lookup: student_id -> month -> fee_data
        fees_lookup = {}
        for fee in fees:
            student_id = fee.user_id
            month = fee.due_date.month
            
            if student_id not in fees_lookup:
                fees_lookup[student_id] = {}
            
            fees_lookup[student_id][month] = {
                'amount': float(fee.amount),
                'fee_id': fee.id,
                'status': fee.status.value,
                'paid_date': fee.paid_date.isoformat() if fee.paid_date else None,
                'updated_at': fee.updated_at.isoformat() if fee.updated_at else None
            }
        
        # Build response
        result = []
        for student in students:
            student_data = {
                'student_id': student.id,
                'student_name': student.full_name,
                'roll_number': roll_map.get(student.id),  # Add roll number
                'months': {}
            }
            
            for month in range(1, 13):
                if student.id in fees_lookup and month in fees_lookup[student.id]:
                    student_data['months'][str(month)] = fees_lookup[student.id][month]
                else:
                    student_data['months'][str(month)] = {
                        'amount': 0,
                        'fee_id': None,
                        'status': None,
                        'paid_date': None,
                        'updated_at': None
                    }
            
            result.append(student_data)
        
        return success_response('Fees loaded successfully', {
            'fees': result,
            'batch_id': batch_id,
            'year': year,
            'student_count': len(students)
        })
        
    except Exception as e:
        print(f"Error loading fees: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(f'Failed to load fees: {str(e)}', 500)


@fees_bp.route('/save-monthly', methods=['POST'])
def save_monthly_fee():
    """
    Save or update a monthly fee
    POST /api/fees/save-monthly
    
    Request: {"student_id": 1, "batch_id": 1, "month": 11, "year": 2025, "amount": 1000.00}
    """
    try:
        data = request.get_json()
        
        student_id = data.get('student_id')
        batch_id = data.get('batch_id')
        month = data.get('month')
        year = data.get('year')
        amount = data.get('amount', 0)
        
        if not all([student_id, batch_id, month, year is not None]):
            return error_response('student_id, batch_id, month, and year are required', 400)
        
        try:
            student_id = int(student_id)
            batch_id = int(batch_id)
            month = int(month)
            year = int(year)
            amount = float(amount)
        except (ValueError, TypeError):
            return error_response('Invalid data types', 400)
        
        if not (1 <= month <= 12):
            return error_response('Month must be between 1 and 12', 400)
        
        if not (2020 <= year <= 2030):
            return error_response('Year must be between 2020 and 2030', 400)
        
        if amount < 0:
            return error_response('Amount cannot be negative', 400)
        
        student = User.query.filter_by(
            id=student_id,
            role=UserRole.STUDENT,
            is_active=True,
            is_archived=False
        ).first()
        
        if not student:
            return error_response('Student not found or inactive', 404)
        
        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)
        
        if batch not in student.batches:
            return error_response('Student is not enrolled in this batch', 400)
        
        # Calculate due date
        last_day = calendar.monthrange(year, month)[1]
        due_date = date(year, month, last_day)
        
        # Check if fee exists
        existing_fee = Fee.query.filter(
            Fee.user_id == student_id,
            Fee.batch_id == batch_id,
            extract('month', Fee.due_date) == month,
            extract('year', Fee.due_date) == year
        ).first()
        
        if existing_fee:
            if amount == 0:
                # Delete fee
                db.session.delete(existing_fee)
                db.session.commit()
                return success_response('Fee deleted successfully', {
                    'deleted': True,
                    'student_id': student_id,
                    'month': month,
                    'year': year
                })
            else:
                # Update fee
                existing_fee.amount = Decimal(str(amount))
                existing_fee.updated_at = datetime.utcnow()
                db.session.commit()
                
                return success_response('Fee updated successfully', {
                    'fee_id': existing_fee.id,
                    'student_id': existing_fee.user_id,
                    'batch_id': existing_fee.batch_id,
                    'month': month,
                    'year': year,
                    'amount': float(existing_fee.amount),
                    'status': existing_fee.status.value,
                    'paid_date': existing_fee.paid_date.isoformat() if existing_fee.paid_date else None,
                    'updated_at': existing_fee.updated_at.isoformat() if existing_fee.updated_at else None
                })
        else:
            if amount == 0:
                return success_response('No fee created (amount is zero)', {
                    'created': False,
                    'student_id': student_id,
                    'month': month,
                    'year': year
                })
            else:
                # Create new fee
                new_fee = Fee(
                    user_id=student_id,
                    batch_id=batch_id,
                    amount=Decimal(str(amount)),
                    due_date=due_date,
                    status=FeeStatus.PENDING,
                    notes=f'Monthly fee for {calendar.month_name[month]} {year}'
                )
                
                db.session.add(new_fee)
                db.session.commit()
                
                return success_response('Fee created successfully', {
                    'fee_id': new_fee.id,
                    'student_id': new_fee.user_id,
                    'batch_id': new_fee.batch_id,
                    'month': month,
                    'year': year,
                    'amount': float(new_fee.amount),
                    'status': new_fee.status.value,
                    'paid_date': None,
                    'updated_at': new_fee.updated_at.isoformat() if new_fee.updated_at else datetime.utcnow().isoformat()
                }, 201)
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving fee: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(f'Failed to save fee: {str(e)}', 500)


@fees_bp.route('/mark-paid', methods=['POST'])
def mark_fee_paid():
    """Mark a fee as paid and automatically set paid_date"""
    try:
        data = request.get_json()
        fee_id = data.get('fee_id')
        
        if not fee_id:
            return error_response('fee_id is required', 400)
        
        fee = Fee.query.get(fee_id)
        if not fee:
            return error_response('Fee not found', 404)
        
        # Update status and paid_date
        fee.status = FeeStatus.PAID
        fee.paid_date = date.today()
        fee.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response('Fee marked as paid', {
            'fee_id': fee.id,
            'status': fee.status.value,
            'paid_date': fee.paid_date.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to mark fee as paid: {str(e)}', 500)


@fees_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Test endpoint"""
    return success_response('Fee routes are working!', {
        'timestamp': datetime.utcnow().isoformat(),
        'available_endpoints': [
            'GET /api/fees/load-monthly?batch_id=X&year=Y',
            'POST /api/fees/save-monthly',
            'POST /api/fees/mark-paid',
            'GET /api/fees/test'
        ]
    })
