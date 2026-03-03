"""
School Management Routes
Handles Classes, Sections, Subjects, Term Results, Announcements, School CMS
"""
from flask import Blueprint, request, jsonify, session
from datetime import datetime, date
from sqlalchemy import desc, asc
from models import (
    db, User, UserRole,
    SchoolClass, SchoolSection, SchoolSubject,
    TermExam, StudentTermResult, StudentClassInfo,
    Announcement, SchoolInfo
)

school_bp = Blueprint('school', __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin():
    user_id = session.get('user_id')
    if not user_id:
        return None, jsonify({'error': 'Not authenticated'}), 401
    user = User.query.get(user_id)
    if not user or user.role not in (UserRole.SUPER_USER, UserRole.HEAD_TEACHER):
        return None, jsonify({'error': 'Admin / Head Teacher required'}), 403
    return user, None, None

def _require_teacher():
    user_id = session.get('user_id')
    if not user_id:
        return None, jsonify({'error': 'Not authenticated'}), 401
    user = User.query.get(user_id)
    if not user or user.role not in (UserRole.SUPER_USER, UserRole.HEAD_TEACHER, UserRole.TEACHER):
        return None, jsonify({'error': 'Teacher access required'}), 403
    return user, None, None


def _calc_grade_gpa(marks, full=100):
    """Bangladesh primary school grade calculation"""
    if full == 0:
        return ('F', 0.00)
    pct = (marks / full) * 100
    if pct >= 80:   return ('A+', 5.00)
    if pct >= 70:   return ('A',  4.00)
    if pct >= 60:   return ('A-', 3.50)
    if pct >= 50:   return ('B',  3.00)
    if pct >= 40:   return ('C',  2.00)
    if pct >= 33:   return ('D',  1.00)
    return ('F', 0.00)


def _assign_tied_ranks(rows, key='total_marks', attr='rank'):
    """Assign '1', '2a', '2b' style tied ranks to a list sorted desc by key."""
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and rows[j][key] == rows[i][key]:
            j += 1
        group_size = j - i
        base = i + 1
        if group_size == 1:
            rows[i][attr] = str(base)
            rows[i][attr + '_num'] = base
        else:
            for k in range(group_size):
                rows[i + k][attr] = f"{base}{chr(97 + k)}"   # 1a, 1b, 1c …
                rows[i + k][attr + '_num'] = base
        i = j
    return rows


# ---------------------------------------------------------------------------
# School Info (CMS)
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/info', methods=['GET'])
def get_school_info():
    """Public endpoint – returns all public school info"""
    items = SchoolInfo.query.all()
    return jsonify({row.key: row.value for row in items})


@school_bp.route('/api/school/info', methods=['POST'])
def upsert_school_info():
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    for key, value in data.items():
        row = SchoolInfo.query.filter_by(key=key).first()
        if row:
            row.value = str(value)
            row.updated_by = user.id
            row.updated_at = datetime.utcnow()
        else:
            row = SchoolInfo(key=key, value=str(value), updated_by=user.id)
            db.session.add(row)
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/announcements', methods=['GET'])
def get_announcements():
    show_all = request.args.get('all', 'false').lower() == 'true'
    today = date.today()
    q = Announcement.query
    if not show_all:
        q = q.filter(
            Announcement.is_active == True,
            Announcement.show_on_homepage == True,
            (Announcement.publish_date <= today) | (Announcement.publish_date == None),
            (Announcement.expire_date >= today) | (Announcement.expire_date == None)
        )
    q = q.order_by(desc(Announcement.is_pinned), desc(Announcement.created_at))
    announcements = q.all()
    return jsonify([a.to_dict() for a in announcements])


@school_bp.route('/api/school/announcements', methods=['POST'])
def create_announcement():
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    ann = Announcement(
        title    = data.get('title', '').strip(),
        title_bn = data.get('title_bn', '').strip() or None,
        content  = data.get('content', ''),
        content_bn = data.get('content_bn', '') or None,
        priority = data.get('priority', 'normal'),
        category = data.get('category', 'general'),
        target   = data.get('target', 'all'),
        is_pinned = data.get('is_pinned', False),
        show_on_homepage = data.get('show_on_homepage', True),
        publish_date = datetime.strptime(data['publish_date'], '%Y-%m-%d').date() if data.get('publish_date') else date.today(),
        expire_date  = datetime.strptime(data['expire_date'],  '%Y-%m-%d').date() if data.get('expire_date')  else None,
        attachment      = data.get('attachment') or None,
        attachment_name = data.get('attachment_name') or None,
        created_by = user.id,
    )
    db.session.add(ann)
    db.session.commit()
    return jsonify({'success': True, 'id': ann.id})


@school_bp.route('/api/school/announcements/<int:ann_id>', methods=['PUT'])
def update_announcement(ann_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    ann = Announcement.query.get_or_404(ann_id)
    data = request.get_json() or {}
    for field in ('title','title_bn','content','content_bn','priority','category','target','is_active','is_pinned','show_on_homepage'):
        if field in data:
            setattr(ann, field, data[field])
    if 'publish_date' in data and data['publish_date']:
        ann.publish_date = datetime.strptime(data['publish_date'], '%Y-%m-%d').date()
    if 'expire_date' in data:
        ann.expire_date = datetime.strptime(data['expire_date'], '%Y-%m-%d').date() if data['expire_date'] else None
    if 'attachment' in data:
        ann.attachment      = data['attachment'] or None
        ann.attachment_name = data.get('attachment_name') or None
    ann.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@school_bp.route('/api/school/announcements/<int:ann_id>/attachment', methods=['GET'])
def download_announcement_attachment(ann_id):
    """Serve the PDF attachment for an announcement."""
    ann = Announcement.query.get_or_404(ann_id)
    if not ann.attachment:
        return jsonify({'error': 'No attachment'}), 404
    import base64, mimetypes
    try:
        # data URI format: data:<mime>;base64,<data>
        if ann.attachment.startswith('data:'):
            header, b64data = ann.attachment.split(',', 1)
            mime = header.split(':')[1].split(';')[0]
        else:
            b64data = ann.attachment
            mime = 'application/pdf'
        file_bytes = base64.b64decode(b64data)
        ext = mimetypes.guess_extension(mime) or '.pdf'
        filename = ann.attachment_name or f'notice_{ann_id}{ext}'
        from flask import make_response
        resp = make_response(file_bytes)
        resp.headers['Content-Type'] = mime
        resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@school_bp.route('/api/school/announcements/<int:ann_id>', methods=['DELETE'])
def delete_announcement(ann_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    ann = Announcement.query.get_or_404(ann_id)
    db.session.delete(ann)
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# School Classes
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/classes', methods=['GET'])
def get_classes():
    classes = SchoolClass.query.filter_by(is_active=True).order_by(asc(SchoolClass.class_number)).all()
    return jsonify([c.to_dict() for c in classes])


@school_bp.route('/api/school/classes', methods=['POST'])
def create_class():
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    cls = SchoolClass(
        name=data.get('name', '').strip(),
        name_bn=data.get('name_bn', '') or None,
        class_number=int(data.get('class_number', 1)),
        description=data.get('description') or None,
    )
    db.session.add(cls)
    db.session.commit()
    return jsonify({'success': True, 'id': cls.id})


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/classes/<int:class_id>/sections', methods=['GET'])
def get_sections(class_id):
    sections = SchoolSection.query.filter_by(school_class_id=class_id, is_active=True).order_by(asc(SchoolSection.name)).all()
    return jsonify([s.to_dict() for s in sections])


@school_bp.route('/api/school/sections', methods=['POST'])
def create_section():
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    sec = SchoolSection(
        school_class_id=int(data['school_class_id']),
        name=data.get('name', '').strip(),
        name_bn=data.get('name_bn', '') or None,
        class_teacher_id=data.get('class_teacher_id') or None,
        room_number=data.get('room_number') or None,
        capacity=int(data.get('capacity', 40)),
    )
    db.session.add(sec)
    db.session.commit()
    return jsonify({'success': True, 'id': sec.id})


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/classes/<int:class_id>/subjects', methods=['GET'])
def get_subjects(class_id):
    subjects = (SchoolSubject.query
                .filter_by(school_class_id=class_id, is_active=True)
                .order_by(asc(SchoolSubject.order_index), asc(SchoolSubject.name))
                .all())
    return jsonify([s.to_dict() for s in subjects])


@school_bp.route('/api/school/subjects', methods=['POST'])
def create_subject():
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    sub = SchoolSubject(
        school_class_id=int(data['school_class_id']),
        name=data.get('name', '').strip(),
        name_bn=data.get('name_bn', '') or None,
        code=data.get('code', '') or None,
        full_marks=int(data.get('full_marks', 100)),
        pass_marks=int(data.get('pass_marks', 33)),
        order_index=int(data.get('order_index', 0)),
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({'success': True, 'id': sub.id})


@school_bp.route('/api/school/subjects/<int:sub_id>', methods=['DELETE'])
def delete_subject(sub_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    sub = SchoolSubject.query.get_or_404(sub_id)
    sub.is_active = False
    db.session.commit()
    return jsonify({'success': True})


@school_bp.route('/api/school/classes/<int:class_id>', methods=['DELETE'])
def delete_class(class_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    cls = SchoolClass.query.get_or_404(class_id)
    cls.is_active = False
    db.session.commit()
    return jsonify({'success': True})


@school_bp.route('/api/school/sections/<int:section_id>', methods=['DELETE'])
def delete_section(section_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    sec = SchoolSection.query.get_or_404(section_id)
    sec.is_active = False
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Term Exams
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/term-exams', methods=['GET'])
def get_term_exams():
    year = request.args.get('year', date.today().year, type=int)
    class_id = request.args.get('class_id', type=int)
    q = TermExam.query.filter_by(year=year)
    if class_id:
        q = q.filter_by(school_class_id=class_id)
    exams = q.order_by(asc(TermExam.term)).all()
    return jsonify([e.to_dict() for e in exams])


@school_bp.route('/api/school/term-exams', methods=['POST'])
def create_term_exam():
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    cls_id = int(data['school_class_id'])
    term   = data.get('term', TermExam.TERM_FIRST)
    year   = int(data.get('year', date.today().year))
    sc = SchoolClass.query.get(cls_id)
    title = data.get('title') or f"{sc.name} – {term.replace('_',' ').title()} Examination {year}"
    exam = TermExam(
        school_class_id=cls_id,
        term=term,
        year=year,
        title=title,
        title_bn=data.get('title_bn') or None,
        start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data.get('start_date') else None,
        end_date  =datetime.strptime(data['end_date'],   '%Y-%m-%d').date() if data.get('end_date')   else None,
        created_by=user.id,
    )
    db.session.add(exam)
    db.session.commit()
    return jsonify({'success': True, 'id': exam.id})


@school_bp.route('/api/school/term-exams/<int:exam_id>', methods=['PUT'])
def update_term_exam(exam_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    exam = TermExam.query.get_or_404(exam_id)
    data = request.get_json() or {}
    for field in ('title', 'title_bn', 'show_on_homepage'):
        if field in data:
            setattr(exam, field, data[field])
    if 'result_published' in data:
        exam.result_published = bool(data['result_published'])
        if data['result_published']:
            exam.result_published_at = datetime.utcnow()
        else:
            exam.result_published_at = None
    db.session.commit()
    return jsonify({'success': True})


@school_bp.route('/api/school/term-exams/<int:exam_id>', methods=['DELETE'])
def delete_term_exam(exam_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    exam = TermExam.query.get_or_404(exam_id)
    db.session.delete(exam)
    db.session.commit()
    return jsonify({'success': True})


@school_bp.route('/api/school/term-exams/bulk-generate', methods=['POST'])
def bulk_generate_term_exams():
    """Auto-generate 1st Term, 2nd Term, and Annual exams for ALL active classes for a given year."""
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    year = int(data.get('year', date.today().year))

    classes = SchoolClass.query.filter_by(is_active=True).all()
    terms = [
        (TermExam.TERM_FIRST,  '1st Term Examination'),
        (TermExam.TERM_SECOND, '2nd Term Examination'),
        (TermExam.TERM_ANNUAL, 'Annual Examination'),
    ]

    created, skipped = 0, 0
    for cls in classes:
        for term_key, term_label in terms:
            exists = TermExam.query.filter_by(
                school_class_id=cls.id, term=term_key, year=year
            ).first()
            if exists:
                skipped += 1
                continue
            exam = TermExam(
                school_class_id=cls.id,
                term=term_key,
                year=year,
                title=f"{cls.name} – {term_label} {year}",
                created_by=user.id,
            )
            db.session.add(exam)
            created += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'created': created,
        'skipped': skipped,
        'message': f"Created {created} exams, skipped {skipped} (already exist)."
    })


# ---------------------------------------------------------------------------
# Term Result Entry (marks)
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/term-exams/<int:exam_id>/marks', methods=['GET'])
def get_term_marks(exam_id):
    """Get all marks for a term exam, grouped by section or student"""
    section_id = request.args.get('section_id', type=int)
    student_id = request.args.get('student_id', type=int)
    q = StudentTermResult.query.filter_by(term_exam_id=exam_id)
    if section_id:
        q = q.filter_by(section_id=section_id)
    if student_id:
        q = q.filter_by(student_id=student_id)
    results = q.all()
    return jsonify([r.to_dict() for r in results])


@school_bp.route('/api/school/term-exams/<int:exam_id>/marks', methods=['POST'])
def save_term_marks(exam_id):
    """Bulk save marks: [{student_id, subject_id, section_id, marks_obtained, is_absent}]"""
    user, err, code = _require_teacher()
    if err:
        return err, code
    exam = TermExam.query.get_or_404(exam_id)
    data = request.get_json() or {}
    marks_list = data.get('marks', [])

    saved = 0
    for item in marks_list:
        stu_id  = int(item['student_id'])
        sub_id  = int(item['subject_id'])
        sec_id  = item.get('section_id')
        is_abs  = bool(item.get('is_absent', False))
        marks   = 0 if is_abs else float(item.get('marks_obtained', 0))

        sub = SchoolSubject.query.get(sub_id)
        grade, gpa = _calc_grade_gpa(marks, sub.full_marks if sub else 100)

        existing = StudentTermResult.query.filter_by(
            term_exam_id=exam_id, student_id=stu_id, subject_id=sub_id
        ).first()
        if existing:
            existing.marks_obtained = marks
            existing.is_absent = is_abs
            existing.grade     = 'F' if is_abs else grade
            existing.gpa       = 0   if is_abs else gpa
            existing.section_id = sec_id
            existing.full_marks = sub.full_marks if sub else 100
            existing.pass_marks = sub.pass_marks if sub else 33
            existing.updated_at = datetime.utcnow()
        else:
            r = StudentTermResult(
                term_exam_id=exam_id,
                student_id=stu_id,
                subject_id=sub_id,
                section_id=sec_id,
                marks_obtained=marks,
                full_marks=sub.full_marks if sub else 100,
                pass_marks=sub.pass_marks if sub else 33,
                grade='F' if is_abs else grade,
                gpa=0 if is_abs else gpa,
                is_absent=is_abs,
            )
            db.session.add(r)
        saved += 1

    db.session.commit()
    return jsonify({'success': True, 'saved': saved})


# ---------------------------------------------------------------------------
# Result Reports
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/results/class-wise', methods=['GET'])
def class_wise_results():
    """Summary results for all students in a class for a term exam"""
    exam_id = request.args.get('exam_id', type=int)
    if not exam_id:
        return jsonify({'error': 'exam_id required'}), 400

    exam = TermExam.query.get_or_404(exam_id)
    subjects = (SchoolSubject.query
                .filter_by(school_class_id=exam.school_class_id, is_active=True)
                .order_by(asc(SchoolSubject.order_index)).all())

    all_marks = StudentTermResult.query.filter_by(term_exam_id=exam_id).all()

    student_map = {}
    for m in all_marks:
        if m.student_id not in student_map:
            info = StudentClassInfo.query.filter_by(student_id=m.student_id).first()
            student_map[m.student_id] = {
                'student_id':   m.student_id,
                'display_id':   info.reg_number if info and info.reg_number else str(m.student_id),
                'student_name': m.student.full_name if m.student else 'Unknown',
                'section':      m.section.name if m.section else '-',
                'section_id':   m.section_id,
                'roll_number':  info.roll_number if info else None,
                'subjects':     {},
                'total_marks':  0,
                'total_full':   0,
                'failed':       False,
                'failed_subjects_count': 0,
            }
        subj = student_map[m.student_id]
        subj['subjects'][m.subject_id] = {
            'marks':     m.marks_obtained,
            'grade':     m.grade,
            'gpa':       m.gpa,
            'is_absent': m.is_absent,
        }
        subj['total_marks'] += m.marks_obtained
        subj['total_full']  += m.full_marks
        if m.grade == 'F' or m.is_absent:
            subj['failed'] = True
            subj['failed_subjects_count'] += 1

    rows = []
    for sid, s in student_map.items():
        pct = round((s['total_marks'] / s['total_full']) * 100, 2) if s['total_full'] else 0
        og, ogpa = _calc_grade_gpa(s['total_marks'], s['total_full'])
        s['percentage']    = pct
        s['overall_grade'] = 'F'    if s['failed'] else og
        s['overall_gpa']   = 0.00   if s['failed'] else ogpa
        rows.append(s)

    rows.sort(key=lambda x: (-x['total_marks'], x['roll_number'] or 9999))
    _assign_tied_ranks(rows, key='total_marks', attr='rank')

    return jsonify({
        'exam':     exam.to_dict(),
        'subjects': [s.to_dict() for s in subjects],
        'results':  rows,
    })


@school_bp.route('/api/school/results/section-wise', methods=['GET'])
def section_wise_results():
    """Filter class-wise results by section; returns both class rank and section rank"""
    exam_id    = request.args.get('exam_id', type=int)
    section_id = request.args.get('section_id', type=int)
    if not exam_id:
        return jsonify({'error': 'exam_id required'}), 400

    exam = TermExam.query.get_or_404(exam_id)
    subjects = (SchoolSubject.query
                .filter_by(school_class_id=exam.school_class_id, is_active=True)
                .order_by(asc(SchoolSubject.order_index)).all())

    # Fetch ALL marks for class-wide ranking
    all_marks = StudentTermResult.query.filter_by(term_exam_id=exam_id).all()

    student_map = {}
    for m in all_marks:
        if m.student_id not in student_map:
            info = StudentClassInfo.query.filter_by(student_id=m.student_id).first()
            student_map[m.student_id] = {
                'student_id':   m.student_id,
                'display_id':   info.reg_number if info and info.reg_number else str(m.student_id),
                'student_name': m.student.full_name if m.student else 'Unknown',
                'section':      m.section.name if m.section else '-',
                'section_id':   m.section_id,
                'roll_number':  info.roll_number if info else None,
                'subjects':     {},
                'total_marks':  0,
                'total_full':   0,
                'failed':       False,
                'failed_subjects_count': 0,
            }
        subj = student_map[m.student_id]
        subj['subjects'][m.subject_id] = {
            'marks':     m.marks_obtained,
            'grade':     m.grade,
            'gpa':       m.gpa,
            'is_absent': m.is_absent,
        }
        subj['total_marks'] += m.marks_obtained
        subj['total_full']  += m.full_marks
        if m.grade == 'F' or m.is_absent:
            subj['failed'] = True
            subj['failed_subjects_count'] += 1

    all_rows = []
    for sid, s in student_map.items():
        pct = round((s['total_marks'] / s['total_full']) * 100, 2) if s['total_full'] else 0
        og, ogpa = _calc_grade_gpa(s['total_marks'], s['total_full'])
        s['percentage']    = pct
        s['overall_grade'] = 'F'    if s['failed'] else og
        s['overall_gpa']   = 0.00   if s['failed'] else ogpa
        all_rows.append(s)

    # Class-wide rank
    all_rows.sort(key=lambda x: (-x['total_marks'], x['roll_number'] or 9999))
    _assign_tied_ranks(all_rows, key='total_marks', attr='class_rank')

    # Filter by section if requested
    if section_id:
        rows = [r for r in all_rows if r['section_id'] == section_id]
    else:
        rows = all_rows

    # Section rank within the filtered set
    rows_sorted = sorted(rows, key=lambda x: (-x['total_marks'], x['roll_number'] or 9999))
    _assign_tied_ranks(rows_sorted, key='total_marks', attr='rank')

    # Also set rank = class_rank when no section filter
    if not section_id:
        for r in rows_sorted:
            r['rank'] = r['class_rank']
            r['rank_num'] = r['class_rank_num']

    return jsonify({
        'exam':     exam.to_dict(),
        'subjects': [s.to_dict() for s in subjects],
        'results':  rows_sorted,
    })


@school_bp.route('/api/school/results/transcript/<int:student_id>', methods=['GET'])
def student_transcript(student_id):
    """Individual student transcript for a term exam"""
    exam_id = request.args.get('exam_id', type=int)
    if not exam_id:
        return jsonify({'error': 'exam_id required'}), 400

    exam    = TermExam.query.get_or_404(exam_id)
    student = User.query.get_or_404(student_id)
    info    = StudentClassInfo.query.filter_by(student_id=student_id).first()

    marks = (StudentTermResult.query
             .filter_by(term_exam_id=exam_id, student_id=student_id)
             .all())

    subjects_marks = []
    total_obtained = 0
    total_full     = 0
    failed         = False
    for m in marks:
        sub = m.subject
        subjects_marks.append({
            'subject_name': sub.name if sub else 'Unknown',
            'subject_name_bn': sub.name_bn if sub else '',
            'full_marks':     m.full_marks,
            'marks_obtained': m.marks_obtained,
            'grade': m.grade,
            'gpa':   m.gpa,
            'is_absent': m.is_absent,
        })
        total_obtained += m.marks_obtained
        total_full     += m.full_marks
        if m.grade == 'F' or m.is_absent:
            failed = True

    pct = round((total_obtained / total_full) * 100, 2) if total_full else 0
    og, ogpa = _calc_grade_gpa(total_obtained, total_full)

    # Compute class rank for this exam (tied format)
    all_results = StudentTermResult.query.filter_by(term_exam_id=exam_id).all()
    student_totals = {}
    for m in all_results:
        student_totals.setdefault(m.student_id, 0)
        student_totals[m.student_id] += m.marks_obtained
    sorted_ids = sorted(student_totals, key=lambda s: -student_totals[s])

    # Build temporary rows to get tied rank
    tmp = [{'student_id': sid, 'total_marks': tot} for sid, tot in
           sorted((student_totals.items()), key=lambda x: -x[1])]
    _assign_tied_ranks(tmp, key='total_marks', attr='rank')
    rank_map = {r['student_id']: r['rank'] for r in tmp}
    class_rank = rank_map.get(student_id, '—')

    return jsonify({
        'student': {
            'id': student.id,
            'display_id': info.reg_number if info and info.reg_number else str(student.id),
            'name': student.full_name,
            'roll_number': info.roll_number if info else None,
            'reg_number':  info.reg_number  if info else None,
            'blood_group': info.blood_group if info else None,
            'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
            'guardian_name': student.guardian_name,
            'class_name': exam.school_class.name if exam.school_class else '',
            'section': info.section.name if info and info.section else '',
        },
        'exam': exam.to_dict(),
        'subjects': subjects_marks,
        'summary': {
            'total_obtained': total_obtained,
            'total_full':     total_full,
            'percentage':     pct,
            'overall_grade':  'F' if failed else og,
            'overall_gpa':    0.00 if failed else ogpa,
            'class_rank':     class_rank,
            'result':         'FAILED' if failed else 'PASSED',
            'failed_subjects_count': sum(1 for m in subjects_marks if m['grade']=='F' or m['is_absent']),
        },
    })


# ---------------------------------------------------------------------------
# Combined Result Cards  (all 3 terms on one landscape marksheet per student)
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/results/cards', methods=['GET'])
def result_cards():
    """Return combined 3-term result card data for a class+year (or one student).

    Query params:
      class_id  int  required
      year      int  required
      student_id int optional  — if given, returns only that student's card
    """
    class_id   = request.args.get('class_id',   type=int)
    year       = request.args.get('year',        type=int)
    student_id = request.args.get('student_id',  type=int)

    if not class_id or not year:
        return jsonify({'error': 'class_id and year are required'}), 400

    school_class = SchoolClass.query.get_or_404(class_id)

    # All active subjects for this class, ordered
    subjects = (SchoolSubject.query
                .filter_by(school_class_id=class_id, is_active=True)
                .order_by(asc(SchoolSubject.order_index)).all())

    # All 3 term exams for this class+year
    exams = (TermExam.query
             .filter_by(school_class_id=class_id, year=year)
             .all())
    exam_by_term = {e.term: e for e in exams}   # '1st_term','2nd_term','annual'

    TERMS = ['1st_term', '2nd_term', 'annual']
    TERM_LABELS = {'1st_term': '1st Term', '2nd_term': '2nd Term', 'annual': 'Annual'}

    # Collect all StudentTermResults for these exams
    exam_ids = [e.id for e in exams]
    all_marks = StudentTermResult.query.filter(
        StudentTermResult.term_exam_id.in_(exam_ids)
    ).all() if exam_ids else []

    # Build a lookup: student_id → term → subject_id → result row
    exam_id_to_term = {e.id: e.term for e in exams}
    data = {}   # {student_id: {term: {subject_id: row}}}
    for m in all_marks:
        term_key = exam_id_to_term.get(m.term_exam_id)
        if not term_key:
            continue
        data.setdefault(m.student_id, {}).setdefault(term_key, {})[m.subject_id] = m

    # If single student requested, filter
    student_ids = (StudentClassInfo.query
                   .filter_by(school_class_id=class_id)
                   .with_entities(StudentClassInfo.student_id)
                   .all())
    student_ids = [s[0] for s in student_ids]
    if student_id:
        student_ids = [s for s in student_ids if s == student_id]

    # Class-wide grand totals for ranking (using all students)
    grand_totals_all = {}
    for sid in data:
        gt = 0
        for term in TERMS:
            for sub_id, m in data.get(sid, {}).get(term, {}).items():
                gt += m.marks_obtained
        grand_totals_all[sid] = gt

    tmp_rank = [{'student_id': sid, 'total_marks': tot}
                for sid, tot in grand_totals_all.items()]
    tmp_rank.sort(key=lambda x: -x['total_marks'])
    _assign_tied_ranks(tmp_rank, 'total_marks', 'rank')
    rank_map = {r['student_id']: r['rank'] for r in tmp_rank}

    cards = []
    for sid in student_ids:
        student = User.query.get(sid)
        if not student or not student.is_active or student.is_archived:
            continue
        info = StudentClassInfo.query.filter_by(student_id=sid).first()

        # Build subject rows: {subject_id: {term: {obtained, full, grade, gpa, is_absent}}}
        subject_rows = []
        overall_failed = False
        for sub in subjects:
            row = {
                'subject_id': sub.id,
                'subject_name':    sub.name,
                'subject_name_bn': sub.name_bn or '',
                'grand_obtained': 0,
                'grand_full':     0,
                'failed':         False,
            }
            for term in TERMS:
                m = data.get(sid, {}).get(term, {}).get(sub.id)
                if m:
                    row[term] = {
                        'obtained':   m.marks_obtained,
                        'full':       m.full_marks,
                        'grade':      m.grade,
                        'gpa':        m.gpa,
                        'is_absent':  m.is_absent,
                        'pass_marks': m.pass_marks,
                    }
                    row['grand_obtained'] += m.marks_obtained
                    row['grand_full']     += m.full_marks
                    if m.grade == 'F' or m.is_absent:
                        row['failed'] = True
                        overall_failed = True
                else:
                    # Find expected full marks from exam if exists
                    full = sub.full_marks or 100
                    row[term] = {'obtained': None, 'full': full, 'grade': None, 'gpa': None, 'is_absent': False, 'pass_marks': None}
            # Grand GPA for subject
            g_grade, g_gpa = _calc_grade_gpa(row['grand_obtained'], row['grand_full']) if row['grand_full'] else ('—', 0.0)
            row['grand_grade'] = g_grade
            row['grand_gpa']   = g_gpa
            subject_rows.append(row)

        # Per-term totals
        term_totals = {}
        for term in TERMS:
            tot_obt = sum(data.get(sid, {}).get(term, {}).get(sub.id).marks_obtained
                         for sub in subjects
                         if data.get(sid, {}).get(term, {}).get(sub.id) is not None)
            tot_full = sum(data.get(sid, {}).get(term, {}).get(sub.id).full_marks
                          for sub in subjects
                          if data.get(sid, {}).get(term, {}).get(sub.id) is not None)
            pct = round((tot_obt / tot_full) * 100, 2) if tot_full else 0
            tg, tgpa = _calc_grade_gpa(tot_obt, tot_full) if tot_full else ('—', 0.0)
            term_totals[term] = {
                'obtained': tot_obt, 'full': tot_full,
                'percentage': pct, 'grade': tg, 'gpa': tgpa,
                'label': TERM_LABELS.get(term, term),
                'has_data': bool(data.get(sid, {}).get(term)),
            }

        # Grand total
        grand_obt  = sum(r['grand_obtained'] for r in subject_rows)
        grand_full = sum(r['grand_full'] for r in subject_rows)
        grand_pct  = round((grand_obt / grand_full) * 100, 2) if grand_full else 0
        g_grade, g_gpa = _calc_grade_gpa(grand_obt, grand_full) if grand_full else ('—', 0.0)
        if overall_failed:
            g_grade = 'F'; g_gpa = 0.0

        failed_count = sum(1 for r in subject_rows if r['failed'])

        cards.append({
            'student': {
                'id':           sid,
                'display_id':   info.reg_number if info and info.reg_number else str(sid),
                'name':         student.full_name,
                'roll_number':  info.roll_number if info else None,
                'guardian_name': student.guardian_name or '',
                'mother_name':  student.mother_name or '',
                'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
                'blood_group':  info.blood_group if info else '',
                'section':      info.section.name if info and info.section else '',
                'class_name':   school_class.name,
            },
            'year':         year,
            'subjects':     subject_rows,
            'term_totals':  term_totals,
            'grand': {
                'obtained':    grand_obt,
                'full':        grand_full,
                'percentage':  grand_pct,
                'grade':       g_grade,
                'gpa':         round(g_gpa, 2),
                'class_rank':  rank_map.get(sid, '—'),
                'result':      'FAILED' if overall_failed else 'PASSED',
                'failed_subjects': failed_count,
            },
        })

    # Sort by roll number
    cards.sort(key=lambda c: c['student']['roll_number'] or 9999)

    return jsonify({
        'class_name': school_class.name,
        'year':       year,
        'subjects':   [{'id': s.id, 'name': s.name, 'name_bn': s.name_bn or '', 'full_marks': s.full_marks} for s in subjects],
        'terms':      TERMS,
        'term_labels': TERM_LABELS,
        'cards':      cards,
    })


# ---------------------------------------------------------------------------
# Student Class Info  (assign class/section/roll to a student)
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/student-info', methods=['GET'])
def get_students_by_class():
    class_id = request.args.get('class_id', type=int)
    if not class_id:
        return jsonify({'error': 'class_id is required'}), 400
    
    infos = StudentClassInfo.query.filter_by(school_class_id=class_id).all()
    students = []
    for info in infos:
        user = info.student
        if user and user.is_active and not user.is_archived:
            students.append({
                'id': user.id,
                'name': f"{user.first_name} {user.last_name}".strip(),
                'username': user.phoneNumber,
                'school_class_id': info.school_class_id,
                'section_id': info.section_id,
                'roll_number': info.roll_number,
                'reg_number': info.reg_number,
            })
    return jsonify({'students': students})

@school_bp.route('/api/school/student-info/<int:student_id>', methods=['GET'])
def get_student_class_info(student_id):
    info = StudentClassInfo.query.filter_by(student_id=student_id).first()
    if not info:
        return jsonify({})
    return jsonify({
        'student_id':      info.student_id,
        'school_class_id': info.school_class_id,
        'section_id':      info.section_id,
        'roll_number':     info.roll_number,
        'reg_number':      info.reg_number,
        'blood_group':     info.blood_group,
        'religion':        info.religion,
        'academic_year':   info.academic_year,
        'class_name':      info.school_class.name if info.school_class else None,
        'section_name':    info.section.name if info.section else None,
    })


@school_bp.route('/api/school/student-info/<int:student_id>', methods=['POST'])
def save_student_class_info(student_id):
    user, err, code = _require_admin()
    if err:
        return err, code
    data = request.get_json() or {}
    info = StudentClassInfo.query.filter_by(student_id=student_id).first()
    if not info:
        info = StudentClassInfo(student_id=student_id)
        db.session.add(info)
    for field in ('school_class_id', 'section_id', 'roll_number', 'reg_number',
                  'blood_group', 'religion', 'nationality', 'academic_year'):
        if field in data:
            setattr(info, field, data[field] or None)
    info.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Dashboard summary for school
# ---------------------------------------------------------------------------

@school_bp.route('/api/school/dashboard', methods=['GET'])
def school_dashboard():
    total_students  = User.query.filter_by(role=UserRole.STUDENT, is_active=True, is_archived=False).count()
    total_teachers  = User.query.filter(
        User.role.in_([UserRole.TEACHER, UserRole.HEAD_TEACHER]),
        User.is_active == True
    ).count()
    total_classes   = SchoolClass.query.filter_by(is_active=True).count()
    total_sections  = SchoolSection.query.filter_by(is_active=True).count()
    recent_ann      = (Announcement.query.filter_by(is_active=True)
                       .order_by(desc(Announcement.created_at)).limit(5).all())
    published_exams = TermExam.query.filter_by(result_published=True).count()

    return jsonify({
        'total_students':  total_students,
        'total_teachers':  total_teachers,
        'total_classes':   total_classes,
        'total_sections':  total_sections,
        'published_results': published_exams,
        'recent_announcements': [a.to_dict() for a in recent_ann],
    })
