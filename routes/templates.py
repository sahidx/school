"""
Template Routes
HTML template rendering for frontend pages
"""
from flask import Blueprint, render_template, redirect, url_for, session, request
from models import db, User, UserRole, Batch, Settings, MonthlyExam, MonthlyRanking
from datetime import date

templates_bp = Blueprint('templates', __name__)

SCHOOL_DEFAULT_NAME = 'Modern Ideal Kindergarten'
SCHOOL_DEFAULT_NAME_BN = 'মডার্ণ আইডিয়াল বেসরকারি প্রাথমিক বিদ্যালয়'

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
        'address': info.get('school_address', 'Rabeya Polly, Mohadevpur, Naogaon'),
        'address_bn': info.get('school_address_bn', 'রাবেয়া পল্লী, মহাদেবপুর, নওগাঁ।'),
        'phone': info.get('school_phone', '01712-185138'),
        'email': info.get('school_email', ''),
        'eiin': info.get('school_eiin', ''),
        'estd': info.get('estd_year', ''),
        'logo': info.get('school_logo', ''),
        'website': info.get('school_website', 'https://modernidealschool.edu.bd/'),
        'facebook': info.get('school_facebook', 'https://www.facebook.com/mikgschool'),
        'ht_signature': info.get('head_teacher_signature', ''),
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

@templates_bp.route('/results/cards')
def result_cards_page():
    """Certificate-format result cards – one card per student, all 3 terms combined"""
    if 'user' not in session:
        return redirect(url_for('templates.login_page') + '?next=/results/cards')
    if session['user'].get('role') not in ('teacher', 'super_user', 'head_teacher'):
        return redirect(url_for('templates.index'))
    return render_template('result_card.html', user=session['user'])

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
    classes  = SchoolClass.query.filter_by(is_active=True).order_by(SchoolClass.name).all()
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
                student_id_display = s.student_code or f'STU{year}{s.id:05d}'
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
    classes  = SchoolClass.query.filter_by(is_active=True).order_by(SchoolClass.name).all()

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
                'student_id':      s.student_code or f'STU{year}{s.id:05d}',
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


# ──────────────────────────────────────────────────────────────────────────────
# LOGO SETUP PAGE
# ──────────────────────────────────────────────────────────────────────────────
@templates_bp.route('/setup/logo')
def setup_logo_page():
    return render_template('setup_logo.html')


# STUDENT ID CARDS (BULK, BOTH SIDES)
# ──────────────────────────────────────────────────────────────────────────────

@templates_bp.route('/students/id-cards')
def student_id_cards():
    """Professional double-sided student ID cards – bulk PDF printing.
    Filters: ?class_id=  or  ?batch_id=  or  ?student_ids=1,2,3
    """
    if not session.get('user_id'):
        return redirect(url_for('templates.login_page'))
    from models import SchoolClass, StudentClassInfo, Batch

    class_id     = request.args.get('class_id',  type=int)
    batch_id     = request.args.get('batch_id',  type=int)
    student_ids  = request.args.get('student_ids', '')   # comma-separated
    session_year = request.args.get('session_year', str(date.today().year))
    autoprint    = request.args.get('autoprint', '')      # '1' = auto-trigger print
    print_side   = request.args.get('side', 'both')       # front / back / both

    classes  = SchoolClass.query.filter_by(is_active=True).order_by(SchoolClass.name).all()
    batches  = Batch.query.filter_by(is_archived=False).order_by(Batch.name).all()

    selected_class = None
    selected_batch = None
    cards = []

    def _build_card(s, class_name='', section_name='', roll='', blood_group='', reg_number='', year_str=''):
        """Build card dict from User object."""
        yr = date.today().year
        return {
            'id':            s.id,
            'student_id':    s.student_code or f'STU{yr}{s.id:05d}',
            'full_name':     s.full_name,
            'first_name':    s.first_name,
            'last_name':     s.last_name,
            'phone':         s.phoneNumber or '',
            'guardian_name': s.guardian_name or '',
            'guardian_phone':s.guardian_phone or s.phoneNumber or '',
            'mother_name':   s.mother_name or '',
            'address':       s.address or '',
            'date_of_birth': s.date_of_birth.strftime('%d %b %Y') if s.date_of_birth else '',
            'admission_date':s.admission_date.strftime('%d %b %Y') if s.admission_date else '',
            'profile_image': s.profile_image or '',
            'class_name':    class_name,
            'section':       section_name,
            'roll':          str(roll) if roll else '',
            'blood_group':   blood_group,
            'reg_number':    reg_number,
            'session_year':  year_str or session_year,
        }

    if student_ids:
        ids = [int(x) for x in student_ids.split(',') if x.strip().isdigit()]
        users = User.query.filter(User.id.in_(ids), User.is_active == True).order_by(User.first_name).all()
        for s in users:
            info = StudentClassInfo.query.filter_by(student_id=s.id).first()
            cards.append(_build_card(
                s,
                class_name   = info.school_class.name if info and info.school_class else '',
                section_name = info.section.name if info and info.section else '',
                roll         = info.roll_number if info else '',
                blood_group  = info.blood_group if info else '',
                reg_number   = info.reg_number if info else '',
                year_str     = str(info.academic_year) if info and info.academic_year else '',
            ))

    elif class_id:
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
            for info in infos:
                s = info.student
                cards.append(_build_card(
                    s,
                    class_name   = selected_class.name,
                    section_name = info.section.name if info.section else '',
                    roll         = info.roll_number or '',
                    blood_group  = info.blood_group or '',
                    reg_number   = info.reg_number or '',
                    year_str     = str(info.academic_year) if info.academic_year else '',
                ))

    elif batch_id:
        selected_batch = Batch.query.get(batch_id)
        if selected_batch:
            for s in selected_batch.students:
                if not s.is_active:
                    continue
                info = StudentClassInfo.query.filter_by(student_id=s.id).first()
                cards.append(_build_card(
                    s,
                    class_name   = info.school_class.name if info and info.school_class else selected_batch.name,
                    section_name = info.section.name if info and info.section else '',
                    roll         = info.roll_number if info else '',
                    blood_group  = info.blood_group if info else '',
                    reg_number   = info.reg_number if info else '',
                    year_str     = str(info.academic_year) if info and info.academic_year else '',
                ))
            cards.sort(key=lambda c: (c['class_name'], c['roll'] or '9999', c['full_name']))

    else:
        # No filter — show all active students ordered by class order then roll number
        infos = (
            StudentClassInfo.query
            .join(User, User.id == StudentClassInfo.student_id)
            .filter(User.is_active == True)
            .join(SchoolClass, SchoolClass.id == StudentClassInfo.school_class_id)
            .order_by(SchoolClass.class_number, StudentClassInfo.roll_number, User.first_name)
            .all()
        )
        for info in infos:
            s = info.student
            cards.append(_build_card(
                s,
                class_name   = info.school_class.name if info.school_class else '',
                section_name = info.section.name if info.section else '',
                roll         = info.roll_number or '',
                blood_group  = info.blood_group or '',
                reg_number   = info.reg_number or '',
                year_str     = str(info.academic_year) if info.academic_year else '',
            ))

    school = _get_school_info()
    return render_template(
        'id_cards.html',
        school=school,
        classes=classes,
        batches=batches,
        cards=cards,
        class_id=class_id,
        batch_id=batch_id,
        selected_class=selected_class,
        selected_batch=selected_batch,
        session_year=session_year,
        print_date=date.today().strftime('%d %B %Y'),
        total=len(cards),
        autoprint=autoprint,
        print_side=print_side,
    )


@templates_bp.route('/students/id-cards/pdf')
def student_id_cards_pdf():
    if not session.get('user_id'):
        return redirect(url_for('templates.login_page'))
    """Generate and download a PDF of student ID cards at exact CR80 size.
    Same filters as /students/id-cards: ?class_id= or ?batch_id= or ?student_ids=
    Each card (front then back) gets its own page sized 54×85.6mm.
    """
    from models import SchoolClass, StudentClassInfo, Batch
    from flask import render_template as rt
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        return "WeasyPrint not installed. Run: pip install weasyprint", 500

    class_id     = request.args.get('class_id',  type=int)
    batch_id     = request.args.get('batch_id',  type=int)
    student_ids  = request.args.get('student_ids', '')
    session_year = request.args.get('session_year', str(date.today().year))
    side         = request.args.get('side', 'both')  # front / back / both

    selected_class = None
    selected_batch = None
    cards = []

    def _build_card(s, class_name='', section_name='', roll='', blood_group='', reg_number='', year_str=''):
        yr = date.today().year
        return {
            'id':            s.id,
            'student_id':    s.student_code or f'STU{yr}{s.id:05d}',
            'full_name':     s.full_name,
            'phone':         s.phoneNumber or '',
            'guardian_name': s.guardian_name or '',
            'guardian_phone':s.guardian_phone or s.phoneNumber or '',
            'mother_name':   s.mother_name or '',
            'address':       s.address or '',
            'date_of_birth': s.date_of_birth.strftime('%d %b %Y') if s.date_of_birth else '',
            'profile_image': s.profile_image or '',
            'class_name':    class_name,
            'section':       section_name,
            'roll':          str(roll) if roll else '',
            'blood_group':   blood_group,
            'reg_number':    reg_number,
            'session_year':  year_str or session_year,
        }

    if student_ids:
        ids = [int(x) for x in student_ids.split(',') if x.strip().isdigit()]
        users = User.query.filter(User.id.in_(ids), User.is_active == True).order_by(User.first_name).all()
        for s in users:
            info = StudentClassInfo.query.filter_by(student_id=s.id).first()
            cards.append(_build_card(s,
                class_name   = info.school_class.name if info and info.school_class else '',
                section_name = info.section.name if info and info.section else '',
                roll         = info.roll_number if info else '',
                blood_group  = info.blood_group if info else '',
                reg_number   = info.reg_number if info else '',
                year_str     = str(info.academic_year) if info and info.academic_year else '',
            ))
    elif class_id:
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
            for info in infos:
                s = info.student
                cards.append(_build_card(s,
                    class_name   = selected_class.name,
                    section_name = info.section.name if info.section else '',
                    roll         = info.roll_number or '',
                    blood_group  = info.blood_group or '',
                    reg_number   = info.reg_number or '',
                    year_str     = str(info.academic_year) if info.academic_year else '',
                ))
    elif batch_id:
        selected_batch = Batch.query.get(batch_id)
        if selected_batch:
            for s in selected_batch.students:
                if not s.is_active:
                    continue
                info = StudentClassInfo.query.filter_by(student_id=s.id).first()
                cards.append(_build_card(s,
                    class_name   = info.school_class.name if info and info.school_class else selected_batch.name,
                    section_name = info.section.name if info and info.section else '',
                    roll         = info.roll_number if info else '',
                    blood_group  = info.blood_group if info else '',
                    reg_number   = info.reg_number if info else '',
                    year_str     = str(info.academic_year) if info and info.academic_year else '',
                ))
            cards.sort(key=lambda c: (c['class_name'], c['roll'] or '9999', c['full_name']))

    if not cards:
        return "No students found for the selected filter.", 400

    school = _get_school_info()
    html_string = rt(
        'id_cards_pdf.html',
        school=school,
        cards=cards,
        session_year=session_year,
        side=side,
    )

    # Resolve base URL so WeasyPrint can load static assets
    base_url = request.host_url.rstrip('/')
    pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf()

    label = selected_class.name if selected_class else (selected_batch.name if selected_batch else 'students')
    # Use ASCII-safe filename (encode non-ASCII as hex for Content-Disposition)
    safe_label = ''.join(c if c.isascii() and c.isprintable() else f'_{ord(c):04x}_' for c in label)
    filename = f'id_cards_{safe_label}_{session_year}.pdf'

    from flask import Response
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f"attachment; filename=\"id_cards_{session_year}.pdf\"; filename*=UTF-8''{filename}"
        },
    )


@templates_bp.route('/students/id-cards/print')
def student_id_cards_print():
    if not session.get('user_id'):
        return redirect(url_for('templates.login_page'))
    """Standalone clean print page – no navbar, auto-triggers browser print.
    Same filters: ?class_id= or ?batch_id= or ?side=front|back|both
    """
    from models import SchoolClass, StudentClassInfo, Batch

    class_id     = request.args.get('class_id',  type=int)
    batch_id     = request.args.get('batch_id',  type=int)
    student_ids  = request.args.get('student_ids', '')
    session_year = request.args.get('session_year', str(date.today().year))
    side         = request.args.get('side', 'both')

    cards = []

    def _build_card(s, class_name='', section_name='', roll='', blood_group='', reg_number='', year_str=''):
        yr = date.today().year
        return {
            'id':            s.id,
            'student_id':    s.student_code or f'STU{yr}{s.id:05d}',
            'full_name':     s.full_name,
            'phone':         s.phoneNumber or '',
            'guardian_name': s.guardian_name or '',
            'guardian_phone':s.guardian_phone or s.phoneNumber or '',
            'mother_name':   s.mother_name or '',
            'address':       s.address or '',
            'date_of_birth': s.date_of_birth.strftime('%d %b %Y') if s.date_of_birth else '',
            'profile_image': s.profile_image or '',
            'class_name':    class_name,
            'section':       section_name,
            'roll':          str(roll) if roll else '',
            'blood_group':   blood_group,
            'reg_number':    reg_number,
            'session_year':  year_str or session_year,
        }

    if student_ids:
        ids = [int(x) for x in student_ids.split(',') if x.strip().isdigit()]
        users = User.query.filter(User.id.in_(ids), User.is_active == True).order_by(User.first_name).all()
        for s in users:
            info = StudentClassInfo.query.filter_by(student_id=s.id).first()
            cards.append(_build_card(s,
                class_name=info.school_class.name if info and info.school_class else '',
                section_name=info.section.name if info and info.section else '',
                roll=info.roll_number if info else '',
            ))
    elif class_id:
        selected_class = SchoolClass.query.get(class_id)
        if selected_class:
            infos = (StudentClassInfo.query.filter_by(school_class_id=class_id)
                .join(User, User.id == StudentClassInfo.student_id)
                .filter(User.is_active == True)
                .order_by(StudentClassInfo.roll_number, User.first_name).all())
            for info in infos:
                s = info.student
                cards.append(_build_card(s,
                    class_name=selected_class.name,
                    section_name=info.section.name if info.section else '',
                    roll=info.roll_number or '',
                    blood_group=info.blood_group or '',
                    reg_number=info.reg_number or '',
                    year_str=str(info.academic_year) if info.academic_year else '',
                ))
    elif batch_id:
        selected_batch = Batch.query.get(batch_id)
        if selected_batch:
            for s in selected_batch.students:
                if not s.is_active:
                    continue
                info = StudentClassInfo.query.filter_by(student_id=s.id).first()
                cards.append(_build_card(s,
                    class_name=info.school_class.name if info and info.school_class else selected_batch.name,
                    section_name=info.section.name if info and info.section else '',
                    roll=info.roll_number if info else '',
                ))
            cards.sort(key=lambda c: (c['class_name'], c['roll'] or '9999', c['full_name']))

    school = _get_school_info()
    return render_template(
        'id_cards_print.html',
        school=school,
        cards=cards,
        session_year=session_year,
        side=side,
        total=len(cards),
    )


@templates_bp.route('/students/id-cards/demo')
def student_id_cards_demo():
    """Static demo preview of the ID card design — no login required."""
    return render_template('id_cards_demo.html')
