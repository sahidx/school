"""
Template Routes
HTML template rendering for frontend pages
"""
from flask import Blueprint, render_template, redirect, url_for, session, request
from models import db, User, UserRole, Batch, Settings, MonthlyExam, MonthlyRanking
from datetime import date

templates_bp = Blueprint('templates', __name__)

SCHOOL_DEFAULT_NAME = 'Modern Ideal Non Government Primary School'
SCHOOL_DEFAULT_NAME_BN = 'মডার্ন আইডিয়াল নন-গভর্নমেন্ট প্রাইমারি স্কুল'

def _get_school_info():
    """Return school settings dict — reads from SchoolInfo model first, falls back to Settings."""
    info = {}
    try:
        from models import SchoolInfo
        rows = SchoolInfo.query.all()
        info = {r.key: r.value for r in rows}
    except Exception:
        pass
    if not info:
        try:
            rows = Settings.query.all()
            info = {r.key: r.value for r in rows}
        except Exception:
            info = {}
    return {
        'name': info.get('school_name', SCHOOL_DEFAULT_NAME),
        'name_bn': info.get('school_name_bn', SCHOOL_DEFAULT_NAME_BN),
        'address': info.get('school_address', ''),
        'phone': info.get('school_phone', ''),
        'email': info.get('school_email', ''),
        'eiin': info.get('school_eiin', ''),
        'estd': info.get('estd_year', ''),
    }

@templates_bp.route('/')
def index():
    """Landing page - redirects based on login status and role"""
    try:
        # Check if user is logged in
        if 'user' in session and session['user']:
            user_role = session['user'].get('role')
            
            if user_role == 'student':
                return render_template('dashboard_student_new.html', user=session['user'])
            elif user_role == 'teacher':
                return render_template('dashboard_teacher.html', user=session['user'])
            elif user_role == 'super_user':
                # Super users get their own dashboard
                return render_template('dashboard_super_admin.html', user=session['user'])
    except (KeyError, AttributeError, TypeError) as e:
        # Clear invalid session data
        session.clear()
    
    # Not logged in, show landing page
    return render_template('index.html')

@templates_bp.route('/results')
def results_page():
    """Class-wise / section-wise results page – teacher/admin only"""
    if 'user' not in session:
        return redirect(url_for('templates.login_page') + '?next=/results')
    if session['user'].get('role') not in ('teacher', 'super_user', 'head_teacher'):
        return redirect(url_for('templates.index'))
    return render_template('results.html', user=session['user'])

@templates_bp.route('/results/transcript')
def transcript_page():
    """Individual student transcript page – teacher/admin only"""
    if 'user' not in session:
        return redirect(url_for('templates.login_page') + '?next=/results/transcript')
    if session['user'].get('role') not in ('teacher', 'super_user', 'head_teacher'):
        return redirect(url_for('templates.index'))
    return render_template('transcript.html', user=session['user'])

@templates_bp.route('/results/marks-entry')
def marks_entry_page():
    """Marks entry page for admin/teacher"""
    if 'user' not in session:
        return redirect(url_for('templates.login_page') + '?next=/results/marks-entry')
    if session['user'].get('role') not in ('teacher', 'super_user', 'head_teacher'):
        return redirect(url_for('templates.index'))
    return render_template('marks_entry.html', user=session['user'])

@templates_bp.route('/debug-fees')
def debug_fees():
    """Debug page for fees feature"""
    try:
        with open('debug_fees.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Debug fees page not found</h1><p>The debug_fees.html file was not found.</p>", 404

@templates_bp.route('/test-fee-save')
def test_fee_save():
    """Test page for fee save endpoint"""
    return render_template('test_fee_save.html')

@templates_bp.route('/login')
def login_page():
    """Login page"""
    
    return render_template('login.html')

@templates_bp.route('/dashboard')
def dashboard():
    """Main dashboard - same as index, redirects based on role"""
    return redirect(url_for('templates.index'))

@templates_bp.route('/student')
def student_dashboard():
    """Student dashboard direct route"""
    if 'user' not in session:
        return redirect(url_for('templates.login_page'))
    
    user_role = session['user'].get('role')
    if user_role != 'student':
        return redirect(url_for('templates.index'))
    
    return render_template('dashboard_student_new.html', user=session['user'])

@templates_bp.route('/student-selection')
def student_selection():
    """Student selection page for shared parent accounts"""
    if 'pending_students' not in session:
        return redirect(url_for('templates.login_page'))
    
    students = session.get('pending_students', [])
    phone = session.get('pending_phone', '')
    
    return render_template('student_selection.html', students=students, phone=phone)

@templates_bp.route('/teacher')  
def teacher_dashboard():
    """Teacher dashboard direct route"""
    if 'user' not in session:
        return redirect(url_for('templates.login_page'))
    
    user_role = session['user'].get('role')
    if user_role != 'teacher':
        return redirect(url_for('templates.index'))
    
    return render_template('dashboard_teacher.html', user=session['user'])

@templates_bp.route('/super')
def super_dashboard():
    """Super user dashboard direct route"""
    if 'user' not in session:
        return redirect(url_for('templates.login_page'))
    
    user_role = session['user'].get('role')
    if user_role != 'super_user':
        return redirect(url_for('templates.index'))
    
    return render_template('dashboard_super_admin_simple.html', user=session['user'])


@templates_bp.route('/results')
def public_results():
    """Public result search page – no login required"""
    return render_template('result_search.html')

# ──────────────────────────────────────────────────────────────────────────────
# STUDENT LIST PRINT
# ──────────────────────────────────────────────────────────────────────────────

@templates_bp.route('/students/list-print')
def student_list_print():
    """Professional student list with photos – teacher/staff only."""
    if 'user' not in session:
        return redirect(url_for('templates.login_page'))
    if session['user'].get('role') not in ('teacher', 'super_user'):
        return redirect(url_for('templates.index'))

    from models import SchoolClass, StudentClassInfo
    class_id = request.args.get('class_id', type=int)
    classes  = SchoolClass.query.order_by(SchoolClass.name).all()

    students       = []
    selected_class = None
    if class_id:
        selected_class = SchoolClass.query.get(class_id)
        if selected_class:
            infos = (
                StudentClassInfo.query
                .filter_by(school_class_id=class_id)
                .join(User, User.id == StudentClassInfo.student_id)
                .filter(User.is_active == True)
                .order_by(StudentClassInfo.roll_number, User.first_name)
                .all()
            )
            year = date.today().year
            for i, info in enumerate(infos, 1):
                s = info.student
                student_id_display = f"STU{year}{s.id:05d}"
                students.append({
                    'serial':        i,
                    'id':            s.id,
                    'student_id':    student_id_display,
                    'full_name':     s.full_name,
                    'phone':         s.phoneNumber or '',
                    'guardian_name': s.guardian_name or '',
                    'guardian_phone':s.guardian_phone or '',
                    'date_of_birth': s.date_of_birth.strftime('%d %b %Y') if s.date_of_birth else '',
                    'admission_date':s.admission_date.strftime('%d %b %Y') if s.admission_date else '',
                    'profile_image': s.profile_image or '',
                    'roll':          info.roll_number or '',
                    'address':       s.address or '',
                    'section':       info.section.name if info.section else '',
                })

    school = _get_school_info()
    return render_template(
        'student_list_print.html',
        school=school,
        classes=classes,
        selected_class=selected_class,
        students=students,
        class_id=class_id,
        print_date=date.today().strftime('%d %B %Y'),
    )


# ──────────────────────────────────────────────────────────────────────────────
# ADMIT CARD PRINT
# ──────────────────────────────────────────────────────────────────────────────

@templates_bp.route('/students/admit-cards')
def admit_cards_print():
    """Admit card sheet – teacher/staff only. Pass ?class_id= and optionally ?exam_id=."""
    if 'user' not in session:
        return redirect(url_for('templates.login_page'))
    if session['user'].get('role') not in ('teacher', 'super_user'):
        return redirect(url_for('templates.index'))

    from models import SchoolClass, StudentClassInfo, TermExam

    class_id = request.args.get('class_id', type=int)
    exam_id  = request.args.get('exam_id',  type=int)
    classes  = SchoolClass.query.order_by(SchoolClass.name).all()

    selected_class = None
    selected_exam  = None
    exams          = []
    student_cards  = []

    if class_id:
        selected_class = SchoolClass.query.get(class_id)
        exams = (
            TermExam.query
            .filter_by(school_class_id=class_id)
            .order_by(TermExam.year.desc(), TermExam.term)
            .all()
        )

    if class_id and exam_id:
        selected_exam = TermExam.query.get(exam_id)
        infos = (
            StudentClassInfo.query
            .filter_by(school_class_id=class_id)
            .join(User, User.id == StudentClassInfo.student_id)
            .filter(User.is_active == True)
            .order_by(StudentClassInfo.roll_number, User.first_name)
            .all()
        )
        year = date.today().year
        for i, info in enumerate(infos, 1):
            s = info.student
            student_cards.append({
                'serial':          i,
                'id':              s.id,
                'student_id':      f"STU{year}{s.id:05d}",
                'full_name':       s.full_name,
                'date_of_birth':   s.date_of_birth.strftime('%d %b %Y') if s.date_of_birth else '',
                'profile_image':   s.profile_image or '',
                'roll':            info.roll_number or '',
                'guardian_name':   s.guardian_name or '',
                'guardian_phone':  s.guardian_phone or s.phoneNumber or '',
                'mother_name':     s.mother_name or '',
                'section':         info.section.name if info.section else '',
            })

    school = _get_school_info()
    return render_template(
        'admit_card.html',
        school=school,
        classes=classes,
        selected_class=selected_class,
        selected_exam=selected_exam,
        exams=exams,
        students=student_cards,
        class_id=class_id,
        exam_id=exam_id,
        print_date=date.today().strftime('%d %B %Y'),
    )
