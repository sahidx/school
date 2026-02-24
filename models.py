"""
Database Models for Modern Ideal Non Government Primary School
Management System - Flask/SQLAlchemy implementation
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from enum import Enum
from sqlalchemy import Numeric
import json

db = SQLAlchemy()

# Enums
class UserRole(Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    HEAD_TEACHER = "head_teacher"
    SUPER_USER = "super_user"

class ExamType(Enum):
    ONLINE = "online"
    OFFLINE = "offline"

class QuestionType(Enum):
    MCQ = "mcq"
    WRITTEN = "written"

class ExamStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class SubmissionStatus(Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EXPIRED = "expired"

class FeeStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"

class SmsStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class AttendanceStatus(Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LEAVE = "leave"

# Association Tables for Many-to-Many Relationships
user_batches = db.Table('user_batches',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('batch_id', db.Integer, db.ForeignKey('batches.id'), primary_key=True),
    db.Column('enrollment_date', db.DateTime, default=datetime.utcnow),
    db.Column('is_active', db.Boolean, default=True)
)

exam_batches = db.Table('exam_batches',
    db.Column('exam_id', db.Integer, db.ForeignKey('exams.id'), primary_key=True),
    db.Column('batch_id', db.Integer, db.ForeignKey('batches.id'), primary_key=True)
)

# Models
class User(db.Model):
    """User model for students, teachers, and super users"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    phoneNumber = db.Column(db.String(20), unique=False, nullable=False, index=True)  # Allow multiple students with same phone
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Only for teachers/admin
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    profile_image = db.Column(db.Text, nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    address = db.Column(db.Text, nullable=True)
    guardian_name = db.Column(db.String(200), nullable=True)
    guardian_phone = db.Column(db.String(20), nullable=True)
    mother_name = db.Column(db.String(200), nullable=True)
    emergency_contact = db.Column(db.String(20), nullable=True)
    admission_date = db.Column(db.Date, nullable=True)  # New field for student admission date
    exam_fee = db.Column(Numeric(10, 2), default=0.00)  # Student-level exam fee (not per month)
    others_fee = db.Column(Numeric(10, 2), default=0.00)  # Student-level other fees (not per month)
    sms_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    archive_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    batches = db.relationship('Batch', secondary=user_batches, back_populates='students')
    exam_submissions = db.relationship('ExamSubmission', back_populates='user')
    exam_answers = db.relationship('ExamAnswer', back_populates='user')
    fees = db.relationship('Fee', back_populates='user')
    sms_logs = db.relationship('SmsLog', back_populates='user', foreign_keys='SmsLog.user_id')
    attendance_records = db.relationship('Attendance', back_populates='user', foreign_keys='Attendance.user_id')
    monthly_results = db.relationship('MonthlyResult', back_populates='user')
    created_exams = db.relationship('Exam', back_populates='created_by_user')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def phone(self):
        """Alias for phoneNumber field"""
        return self.phoneNumber
    
    @phone.setter
    def phone(self, value):
        self.phoneNumber = value
    
    @property
    def student_id(self):
        """Generate student ID if not set"""
        if hasattr(self, '_student_id') and self._student_id:
            return self._student_id
        # Generate based on ID and year
        if self.id and self.role == UserRole.STUDENT:
            year = self.created_at.year if self.created_at else datetime.now().year
            return f"STU{year}{self.id:04d}"
        return None
    
    @student_id.setter
    def student_id(self, value):
        self._student_id = value
    
    def __repr__(self):
        return f'<User {self.phone}: {self.full_name}>'

class Batch(db.Model):
    """Batch/Class model"""
    __tablename__ = 'batches'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=True)
    description = db.Column(db.Text, nullable=True)
    subject = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    fee_amount = db.Column(Numeric(10, 2), default=0.00)
    class_time = db.Column(db.String(100), nullable=True)
    class_days = db.Column(db.String(100), nullable=True)
    max_students = db.Column(db.Integer, default=50)
    status = db.Column(db.String(20), default='active')
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    archive_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    students = db.relationship('User', secondary=user_batches, back_populates='batches')
    exams = db.relationship('Exam', secondary=exam_batches, back_populates='batches')
    fees = db.relationship('Fee', back_populates='batch')
    attendance_records = db.relationship('Attendance', back_populates='batch')
    monthly_results = db.relationship('MonthlyResult', back_populates='batch')
    
    @property
    def current_students(self):
        """Count of currently enrolled students"""
        return len([s for s in self.students if s.is_active])
    
    @property
    def monthly_fee(self):
        """Alias for fee_amount"""
        return float(self.fee_amount) if self.fee_amount else 0.0
    
    def __repr__(self):
        return f'<Batch {self.name}>'

class Exam(db.Model):
    """Exam model"""
    __tablename__ = 'exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    exam_type = db.Column(db.Enum(ExamType), nullable=False, default=ExamType.ONLINE)
    total_marks = db.Column(db.Integer, nullable=False, default=0)
    pass_marks = db.Column(db.Integer, nullable=False, default=0)
    duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(ExamStatus), default=ExamStatus.ACTIVE)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    allow_review = db.Column(db.Boolean, default=True)
    shuffle_questions = db.Column(db.Boolean, default=False)
    show_results_immediately = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    batches = db.relationship('Batch', secondary=exam_batches, back_populates='exams')
    questions = db.relationship('Question', back_populates='exam', cascade='all, delete-orphan')
    submissions = db.relationship('ExamSubmission', back_populates='exam', cascade='all, delete-orphan')
    created_by_user = db.relationship('User', back_populates='created_exams')
    
    def __repr__(self):
        return f'<Exam {self.title}>'

class Question(db.Model):
    """Question model"""
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.Enum(QuestionType), nullable=False, default=QuestionType.MCQ)
    marks = db.Column(db.Integer, nullable=False, default=1)
    options = db.Column(db.JSON, nullable=True)  # For MCQ: ["option1", "option2", "option3", "option4"]
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    order_index = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    exam = db.relationship('Exam', back_populates='questions')
    answers = db.relationship('ExamAnswer', back_populates='question', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:50]}>'

class ExamSubmission(db.Model):
    """Exam submission tracking"""
    __tablename__ = 'exam_submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    total_marks = db.Column(db.Integer, default=0)
    obtained_marks = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    status = db.Column(db.Enum(SubmissionStatus), default=SubmissionStatus.IN_PROGRESS)
    time_taken = db.Column(db.Integer, default=0)  # Time in minutes
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    
    # Relationships
    exam = db.relationship('Exam', back_populates='submissions')
    user = db.relationship('User', back_populates='exam_submissions')
    answers = db.relationship('ExamAnswer', back_populates='submission', cascade='all, delete-orphan')
    
    __table_args__ = (db.UniqueConstraint('exam_id', 'user_id', name='unique_exam_user'),)
    
    def __repr__(self):
        return f'<ExamSubmission {self.user_id} - {self.exam_id}>'

class ExamAnswer(db.Model):
    """Individual answers for exam questions"""
    __tablename__ = 'exam_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('exam_submissions.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, default=False)
    marks_obtained = db.Column(db.Integer, default=0)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    submission = db.relationship('ExamSubmission', back_populates='answers')
    question = db.relationship('Question', back_populates='answers')
    user = db.relationship('User', back_populates='exam_answers')
    
    __table_args__ = (db.UniqueConstraint('submission_id', 'question_id', name='unique_submission_question'),)
    
    def __repr__(self):
        return f'<ExamAnswer {self.question_id}: {self.answer_text}>'

class Fee(db.Model):
    """Fee management model"""
    __tablename__ = 'fees'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    amount = db.Column(Numeric(10, 2), nullable=False)  # Monthly fee amount
    exam_fee = db.Column(Numeric(10, 2), default=0.00)  # Exam fee
    others_fee = db.Column(Numeric(10, 2), default=0.00)  # Others fee
    due_date = db.Column(db.Date, nullable=False)
    paid_date = db.Column(db.Date, nullable=True)  # Auto-set when status changes to PAID
    status = db.Column(db.Enum(FeeStatus), default=FeeStatus.PENDING)
    payment_method = db.Column(db.String(50), nullable=True)
    transaction_id = db.Column(db.String(255), nullable=True)
    late_fee = db.Column(Numeric(10, 2), default=0.00)
    discount = db.Column(Numeric(10, 2), default=0.00)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='fees')
    batch = db.relationship('Batch', back_populates='fees')
    
    def __repr__(self):
        return f'<Fee {self.user_id} - {self.amount}>'

class SmsLog(db.Model):
    """SMS logging model"""
    __tablename__ = 'sms_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    phone_number = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(SmsStatus), default=SmsStatus.PENDING)
    api_response = db.Column(db.JSON, nullable=True)
    sent_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cost = db.Column(Numeric(5, 2), default=0.00)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='sms_logs', foreign_keys=[user_id])
    sent_by_user = db.relationship('User', foreign_keys=[sent_by])
    
    def __repr__(self):
        return f'<SmsLog {self.phone_number}: {self.status}>'

class Attendance(db.Model):
    """Attendance tracking model"""
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(AttendanceStatus), nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=True)
    check_out_time = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='attendance_records', foreign_keys=[user_id])
    batch = db.relationship('Batch', back_populates='attendance_records')
    marked_by_user = db.relationship('User', foreign_keys=[marked_by])
    
    __table_args__ = (db.UniqueConstraint('user_id', 'batch_id', 'date', name='unique_user_batch_date'),)
    
    def __repr__(self):
        return f'<Attendance {self.user_id} - {self.date}: {self.status}>'

class MonthlyResult(db.Model):
    """Monthly result calculation model"""
    __tablename__ = 'monthly_results'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    total_exams = db.Column(db.Integer, default=0)
    total_marks = db.Column(db.Integer, default=0)
    obtained_marks = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    grade = db.Column(db.String(5), nullable=True)
    rank = db.Column(db.Integer, nullable=True)
    attendance_percentage = db.Column(db.Float, default=0.0)
    fee_status = db.Column(db.String(20), default='pending')
    remarks = db.Column(db.Text, nullable=True)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='monthly_results')
    batch = db.relationship('Batch', back_populates='monthly_results')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'batch_id', 'month', 'year', name='unique_monthly_result'),)
    
    def __repr__(self):
        return f'<MonthlyResult {self.user_id} - {self.month}/{self.year}: {self.percentage}%>'

class Session(db.Model):
    """Session management model"""
    __tablename__ = 'sessions'
    
    id = db.Column(db.String(255), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    data = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<Session {self.id}: {self.user_id}>'

class SmsTemplate(db.Model):
    """SMS template model"""
    __tablename__ = 'sms_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    variables = db.Column(db.JSON, nullable=True)  # Available template variables
    category = db.Column(db.String(100), nullable=True)  # exam, attendance, fee, etc.
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = db.relationship('User')
    
    def __repr__(self):
        return f'<SmsTemplate {self.name}>'

class QuestionBank(db.Model):
    """Question bank for AI-generated questions"""
    __tablename__ = 'question_bank'
    
    id = db.Column(db.Integer, primary_key=True)
    class_level = db.Column(db.String(50), nullable=False)  # Class 1, 2, 3, etc.
    subject = db.Column(db.String(255), nullable=False)
    chapter = db.Column(db.String(255), nullable=True)
    topic = db.Column(db.String(255), nullable=True)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.Enum(QuestionType), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # easy, medium, hard
    category = db.Column(db.String(50), nullable=False)  # math, theory, mixed
    options = db.Column(db.JSON, nullable=True)  # For MCQ questions
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    solution = db.Column(db.Text, nullable=True)
    marks = db.Column(db.Integer, default=1)
    generated_by_ai = db.Column(db.Boolean, default=False)
    ai_model = db.Column(db.String(100), nullable=True)  # gemini-2.0-flash-exp
    tags = db.Column(db.JSON, nullable=True)  # Search tags
    usage_count = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Boolean, default=False)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    verified_by_user = db.relationship('User', foreign_keys=[verified_by])
    
    def __repr__(self):
        return f'<QuestionBank {self.class_level} - {self.subject}>'

class MonthlyExam(db.Model):
    """Monthly exam system with ranking"""
    __tablename__ = 'monthly_exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    total_marks = db.Column(db.Integer, nullable=False)
    pass_marks = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    show_results = db.Column(db.Boolean, default=False)
    show_on_homepage = db.Column(db.Boolean, default=False)  # Feature top 3 students on homepage
    result_published_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    batch = db.relationship('Batch')
    created_by_user = db.relationship('User')
    individual_exams = db.relationship('IndividualExam', back_populates='monthly_exam')
    monthly_marks = db.relationship('MonthlyMark', back_populates='monthly_exam')
    
    def __repr__(self):
        return f'<MonthlyExam {self.title} - {self.month}/{self.year}>'

class IndividualExam(db.Model):
    """Individual exam within monthly exam"""
    __tablename__ = 'individual_exams'
    
    id = db.Column(db.Integer, primary_key=True)
    monthly_exam_id = db.Column(db.Integer, db.ForeignKey('monthly_exams.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    marks = db.Column(db.Integer, nullable=False)
    exam_date = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # Minutes
    order_index = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    monthly_exam = db.relationship('MonthlyExam', back_populates='individual_exams')
    monthly_marks = db.relationship('MonthlyMark', back_populates='individual_exam')
    
    def __repr__(self):
        return f'<IndividualExam {self.title} - {self.subject}>'

class MonthlyMark(db.Model):
    """Student marks for monthly exams"""
    __tablename__ = 'monthly_marks'
    
    id = db.Column(db.Integer, primary_key=True)
    monthly_exam_id = db.Column(db.Integer, db.ForeignKey('monthly_exams.id'), nullable=False)
    individual_exam_id = db.Column(db.Integer, db.ForeignKey('individual_exams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    marks_obtained = db.Column(db.Integer, nullable=False)
    total_marks = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(5), nullable=True)
    gpa = db.Column(db.Float, nullable=True)
    is_absent = db.Column(db.Boolean, default=False)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    monthly_exam = db.relationship('MonthlyExam', back_populates='monthly_marks')
    individual_exam = db.relationship('IndividualExam', back_populates='monthly_marks')
    user = db.relationship('User')
    
    __table_args__ = (db.UniqueConstraint('monthly_exam_id', 'individual_exam_id', 'user_id', name='unique_monthly_mark'),)
    
    def __repr__(self):
        return f'<MonthlyMark {self.user_id} - {self.marks_obtained}/{self.total_marks}>'

class Settings(db.Model):
    """Application settings model"""
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.JSON, nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)  # sms, school, ai, etc.
    is_public = db.Column(db.Boolean, default=False)  # Can be seen by non-admin users
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    updated_by_user = db.relationship('User')
    
    def __repr__(self):
        return f'<Settings {self.key}>'

class MonthlyRanking(db.Model):
    """Final rankings for monthly exams with comprehensive scores"""
    __tablename__ = 'monthly_rankings'
    
    id = db.Column(db.Integer, primary_key=True)
    monthly_exam_id = db.Column(db.Integer, db.ForeignKey('monthly_exams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # Final ranking position (1, 2, 3...)
    roll_number = db.Column(db.Integer, nullable=True)  # Student roll number for this monthly exam
    total_exam_marks = db.Column(db.Float, nullable=False, default=0)  # Sum of individual exam marks
    total_possible_marks = db.Column(db.Float, nullable=False, default=0)  # Sum of total possible marks
    attendance_marks = db.Column(db.Integer, nullable=False, default=0)  # Present days count
    bonus_marks = db.Column(db.Float, nullable=False, default=0)  # Teacher-added bonus
    final_total = db.Column(db.Float, nullable=False, default=0)  # Grand total including attendance & bonus
    max_possible_total = db.Column(db.Float, nullable=False, default=0)  # Maximum possible score
    percentage = db.Column(db.Float, nullable=False, default=0)  # Final percentage
    grade = db.Column(db.String(5), nullable=True)  # Overall grade
    gpa = db.Column(db.Float, nullable=True)  # Overall GPA
    exam_gpa = db.Column(db.Float, nullable=True)  # GPA based on exam marks only
    previous_position = db.Column(db.Integer, nullable=True)  # Position in previous month for comparison
    is_final = db.Column(db.Boolean, default=False)  # Whether ranking is finalized
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    monthly_exam = db.relationship('MonthlyExam')
    user = db.relationship('User')
    
    __table_args__ = (db.UniqueConstraint('monthly_exam_id', 'user_id', name='unique_monthly_ranking'),)
    
    def __repr__(self):
        return f'<MonthlyRanking {self.position} - User {self.user_id}>'


class Document(db.Model):
    """PDF/Document storage for online exams and study materials"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(200), nullable=False)  # e.g., "HSC", "Class 10"
    book_name = db.Column(db.String(200), nullable=False)   # e.g., "Biology", "Chemistry"
    chapter_name = db.Column(db.String(200), nullable=False) # e.g., "Chapter 1: Cell Biology"
    file_name = db.Column(db.String(255), nullable=False)    # Original file name
    file_path = db.Column(db.String(500), nullable=False)    # Storage path
    file_size = db.Column(db.Integer, nullable=False)        # File size in bytes
    file_type = db.Column(db.String(50), nullable=False, default='application/pdf')  # MIME type
    description = db.Column(db.Text, nullable=True)          # Optional description
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def __repr__(self):
        return f'<Document {self.class_name} - {self.book_name} - {self.chapter_name}>'
    
    @property
    def file_size_mb(self):
        """Return file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)
    
    def to_dict(self):
        return {
            'id': self.id,
            'class_name': self.class_name,
            'book_name': self.book_name,
            'chapter_name': self.chapter_name,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'file_size_mb': self.file_size_mb,
            'file_type': self.file_type,
            'description': self.description,
            'uploaded_by': self.uploaded_by,
            'uploader_name': self.uploader.full_name if self.uploader else 'Unknown',
            'download_count': self.download_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class OnlineExam(db.Model):
    """Online exam model for class-wise MCQ exams"""
    __tablename__ = 'online_exams'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    class_name = db.Column(db.String(100), nullable=False)  # e.g., "Class 10", "HSC"
    book_name = db.Column(db.String(255), nullable=False)  # e.g., "Physics", "Chemistry"
    chapter_name = db.Column(db.String(255), nullable=False)  # e.g., "Chapter 1: Motion"
    duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    total_questions = db.Column(db.Integer, nullable=False)  # Max 40
    pass_percentage = db.Column(db.Float, default=40.0)  # Minimum percentage to pass
    allow_retake = db.Column(db.Boolean, default=True)  # Allow students to retake
    is_active = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)  # Only published exams visible to students
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    questions = db.relationship('OnlineQuestion', back_populates='exam', cascade='all, delete-orphan', lazy='dynamic')
    attempts = db.relationship('OnlineExamAttempt', back_populates='exam', cascade='all, delete-orphan', lazy='dynamic')
    
    def __repr__(self):
        return f'<OnlineExam {self.title} - {self.class_name}>'

class OnlineQuestion(db.Model):
    """Questions for online exams"""
    __tablename__ = 'online_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('online_exams.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, nullable=False)
    option_b = db.Column(db.Text, nullable=False)
    option_c = db.Column(db.Text, nullable=False)
    option_d = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', or 'D'
    explanation = db.Column(db.Text, nullable=True)  # Optional explanation for the answer
    question_order = db.Column(db.Integer, default=0)  # Order in which questions appear
    marks = db.Column(db.Integer, default=1)  # Marks for this question
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    exam = db.relationship('OnlineExam', back_populates='questions')
    student_answers = db.relationship('OnlineStudentAnswer', back_populates='question', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<OnlineQuestion {self.id} for Exam {self.exam_id}>'

class OnlineExamAttempt(db.Model):
    """Student attempts for online exams"""
    __tablename__ = 'online_exam_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('online_exams.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    attempt_number = db.Column(db.Integer, default=1)  # Track which attempt this is
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    time_taken = db.Column(db.Integer, nullable=True)  # Time taken in seconds
    is_submitted = db.Column(db.Boolean, default=False)
    auto_submitted = db.Column(db.Boolean, default=False)  # True if auto-submitted due to timeout
    score = db.Column(db.Integer, default=0)  # Total score
    total_marks = db.Column(db.Integer, default=0)  # Total possible marks
    percentage = db.Column(db.Float, default=0.0)
    is_passed = db.Column(db.Boolean, default=False)
    
    # Relationships
    exam = db.relationship('OnlineExam', back_populates='attempts')
    student = db.relationship('User', foreign_keys=[student_id])
    answers = db.relationship('OnlineStudentAnswer', back_populates='attempt', cascade='all, delete-orphan')
    
    __table_args__ = (db.Index('idx_exam_student', 'exam_id', 'student_id'),)
    
    def __repr__(self):
        return f'<OnlineExamAttempt {self.id} - Student {self.student_id} - Exam {self.exam_id}>'

class OnlineStudentAnswer(db.Model):
    """Student answers for each question"""
    __tablename__ = 'online_student_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('online_exam_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('online_questions.id'), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=True)  # 'A', 'B', 'C', 'D', or None if not answered
    is_correct = db.Column(db.Boolean, default=False)
    marks_obtained = db.Column(db.Integer, default=0)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    attempt = db.relationship('OnlineExamAttempt', back_populates='answers')
    question = db.relationship('OnlineQuestion', back_populates='student_answers')
    
    __table_args__ = (db.UniqueConstraint('attempt_id', 'question_id', name='unique_attempt_question'),)
    
    def __repr__(self):
        return f'<OnlineStudentAnswer {self.id} - Question {self.question_id}>'


# ============================================================
#  SCHOOL MANAGEMENT MODELS
# ============================================================

class SchoolClass(db.Model):
    """Represents Class 1–5 in the school"""
    __tablename__ = 'school_classes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)          # e.g. "Class 1", "Class 2"
    name_bn = db.Column(db.String(50), nullable=True)        # Bengali: "প্রথম শ্রেণি"
    class_number = db.Column(db.Integer, nullable=False)     # 1-5
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sections = db.relationship('SchoolSection', back_populates='school_class', cascade='all, delete-orphan')
    subjects = db.relationship('SchoolSubject', back_populates='school_class', cascade='all, delete-orphan')
    term_exams = db.relationship('TermExam', back_populates='school_class', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<SchoolClass {self.name}>'

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'name_bn': self.name_bn,
            'class_number': self.class_number, 'is_active': self.is_active,
            'sections': [s.to_dict() for s in self.sections],
        }


class SchoolSection(db.Model):
    """Sections within a class (A, B, C …)"""
    __tablename__ = 'school_sections'

    id = db.Column(db.Integer, primary_key=True)
    school_class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id'), nullable=False)
    name = db.Column(db.String(20), nullable=False)   # A / B / C
    name_bn = db.Column(db.String(20), nullable=True)
    class_teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    room_number = db.Column(db.String(20), nullable=True)
    capacity = db.Column(db.Integer, default=40)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    school_class = db.relationship('SchoolClass', back_populates='sections')
    class_teacher = db.relationship('User', foreign_keys=[class_teacher_id])

    def __repr__(self):
        return f'<Section {self.school_class.name if self.school_class else "?"}-{self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_bn': self.name_bn,
            'school_class_id': self.school_class_id,
            'class_teacher_id': self.class_teacher_id,
            'class_teacher_name': self.class_teacher.full_name if self.class_teacher else None,
            'room_number': self.room_number,
            'capacity': self.capacity,
        }


class SchoolSubject(db.Model):
    """Subjects for each class"""
    __tablename__ = 'school_subjects'

    id = db.Column(db.Integer, primary_key=True)
    school_class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)       # e.g. "Bangla"
    name_bn = db.Column(db.String(100), nullable=True)     # "বাংলা"
    code = db.Column(db.String(20), nullable=True)         # BAN, ENG, MATH …
    full_marks = db.Column(db.Integer, default=100)
    pass_marks = db.Column(db.Integer, default=33)
    order_index = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    school_class = db.relationship('SchoolClass', back_populates='subjects')

    def __repr__(self):
        return f'<Subject {self.name} (Class {self.school_class_id})>'

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'name_bn': self.name_bn,
            'code': self.code, 'full_marks': self.full_marks,
            'pass_marks': self.pass_marks, 'order_index': self.order_index,
        }


class TermExam(db.Model):
    """1st Term / 2nd Term exam definition"""
    __tablename__ = 'term_exams'

    TERM_FIRST  = '1st_term'
    TERM_SECOND = '2nd_term'
    TERM_CHOICES = [TERM_FIRST, TERM_SECOND]

    id = db.Column(db.Integer, primary_key=True)
    school_class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id'), nullable=False)
    term = db.Column(db.String(20), nullable=False)       # '1st_term' or '2nd_term'
    year = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)     # "1st Term Examination 2026"
    title_bn = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    result_published = db.Column(db.Boolean, default=False)
    result_published_at = db.Column(db.DateTime, nullable=True)
    show_on_homepage = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school_class = db.relationship('SchoolClass', back_populates='term_exams')
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    results = db.relationship('StudentTermResult', back_populates='term_exam', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('school_class_id', 'term', 'year', name='unique_term_class_year'),
    )

    @property
    def term_display(self):
        return '1st Term' if self.term == self.TERM_FIRST else '2nd Term'

    def __repr__(self):
        return f'<TermExam {self.title}>'

    def to_dict(self):
        return {
            'id': self.id, 'term': self.term, 'year': self.year,
            'title': self.title, 'title_bn': self.title_bn,
            'school_class_id': self.school_class_id,
            'class_name': self.school_class.name if self.school_class else None,
            'term_display': self.term_display,
            'result_published': self.result_published,
            'show_on_homepage': self.show_on_homepage,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
        }


class StudentTermResult(db.Model):
    """Marks of a student for each subject in a term exam"""
    __tablename__ = 'student_term_results'

    id = db.Column(db.Integer, primary_key=True)
    term_exam_id   = db.Column(db.Integer, db.ForeignKey('term_exams.id'), nullable=False)
    student_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id     = db.Column(db.Integer, db.ForeignKey('school_subjects.id'), nullable=False)
    section_id     = db.Column(db.Integer, db.ForeignKey('school_sections.id'), nullable=True)
    marks_obtained = db.Column(db.Float, default=0)
    full_marks     = db.Column(db.Integer, default=100)
    pass_marks     = db.Column(db.Integer, default=33)
    grade          = db.Column(db.String(5), nullable=True)   # A+, A, A-, B, C, D, F
    gpa            = db.Column(db.Float, nullable=True)
    is_absent      = db.Column(db.Boolean, default=False)
    remarks        = db.Column(db.String(200), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    term_exam = db.relationship('TermExam', back_populates='results')
    student   = db.relationship('User', foreign_keys=[student_id])
    subject   = db.relationship('SchoolSubject')
    section   = db.relationship('SchoolSection', foreign_keys=[section_id])

    __table_args__ = (
        db.UniqueConstraint('term_exam_id', 'student_id', 'subject_id', name='unique_term_student_subject'),
    )

    def __repr__(self):
        return f'<TermResult student={self.student_id} subject={self.subject_id} marks={self.marks_obtained}>'

    def to_dict(self):
        return {
            'id': self.id,
            'term_exam_id': self.term_exam_id,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else None,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else None,
            'marks_obtained': self.marks_obtained,
            'full_marks': self.full_marks,
            'pass_marks': self.pass_marks,
            'grade': self.grade,
            'gpa': self.gpa,
            'is_absent': self.is_absent,
        }


class StudentClassInfo(db.Model):
    """Extra school-specific info for each student"""
    __tablename__ = 'student_class_info'

    id              = db.Column(db.Integer, primary_key=True)
    student_id      = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    school_class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id'), nullable=True)
    section_id      = db.Column(db.Integer, db.ForeignKey('school_sections.id'), nullable=True)
    roll_number     = db.Column(db.Integer, nullable=True)
    reg_number      = db.Column(db.String(50), nullable=True)  # registration / board roll
    blood_group     = db.Column(db.String(5), nullable=True)   # A+, O-, …
    religion        = db.Column(db.String(50), nullable=True)
    nationality     = db.Column(db.String(50), default='Bangladeshi')
    academic_year   = db.Column(db.Integer, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student     = db.relationship('User', foreign_keys=[student_id])
    school_class = db.relationship('SchoolClass')
    section     = db.relationship('SchoolSection')

    def __repr__(self):
        return f'<StudentClassInfo student={self.student_id}>'


class Announcement(db.Model):
    """School announcements (notice board)"""
    __tablename__ = 'announcements'

    PRIORITY_LOW    = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH   = 'high'
    PRIORITY_URGENT = 'urgent'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(300), nullable=False)
    title_bn    = db.Column(db.String(300), nullable=True)
    content     = db.Column(db.Text, nullable=True)
    content_bn  = db.Column(db.Text, nullable=True)
    priority    = db.Column(db.String(20), default='normal')   # low/normal/high/urgent
    category    = db.Column(db.String(50), default='general')  # general/exam/holiday/event/result
    target      = db.Column(db.String(50), default='all')      # all/students/teachers/parents
    is_active   = db.Column(db.Boolean, default=True)
    is_pinned   = db.Column(db.Boolean, default=False)
    show_on_homepage = db.Column(db.Boolean, default=True)
    publish_date = db.Column(db.Date, default=date.today)
    expire_date = db.Column(db.Date, nullable=True)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by_user = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<Announcement {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'title_bn': self.title_bn,
            'content': self.content,
            'content_bn': self.content_bn,
            'priority': self.priority,
            'category': self.category,
            'target': self.target,
            'is_active': self.is_active,
            'is_pinned': self.is_pinned,
            'show_on_homepage': self.show_on_homepage,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'expire_date': self.expire_date.isoformat() if self.expire_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by_name': self.created_by_user.full_name if self.created_by_user else None,
        }


class SchoolInfo(db.Model):
    """Editable school information (CMS)"""
    __tablename__ = 'school_info'

    id           = db.Column(db.Integer, primary_key=True)
    key          = db.Column(db.String(100), unique=True, nullable=False)
    value        = db.Column(db.Text, nullable=True)
    value_bn     = db.Column(db.Text, nullable=True)
    description  = db.Column(db.String(255), nullable=True)
    category     = db.Column(db.String(50), default='general')
    updated_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updated_by_user = db.relationship('User', foreign_keys=[updated_by])

    def __repr__(self):
        return f'<SchoolInfo {self.key}>'
