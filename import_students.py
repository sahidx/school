#!/usr/bin/env python3
"""
Student CSV Importer
====================
Run from project root on VPS:

    python3 import_students.py students.csv

Or edit the INLINE_CSV block at the bottom and run:

    python3 import_students.py

CSV format (first 3 header lines then data):
    school_name:Modern Ideal Non Govt. Pri.School Mohadevpur
    class: ৩য়,section name :moon
    ,student name,father name,mother name,Guardian phone number,
    100221,ফাতেমা-তুজ-জহুরা,আবু হাছান ,মোছা: নাজমিন সুলতানা,01727-743686,
    ...blank rows ignored...

Columns (0-indexed):  0=student_code  1=name  2=father  3=mother  4=phone
"""

import sys
import os
import csv
import io
import re
from datetime import datetime, date

# ── bootstrap Flask app ─────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from app import create_app
from models import db, User, UserRole, SchoolClass, SchoolSection, StudentClassInfo

app = create_app()

# ════════════════════════════════════════════════════════════════════════════
# INLINE CSV — paste your data here when you don't have a file
# ════════════════════════════════════════════════════════════════════════════
INLINE_CSV = """
school_name:Modern Ideal Non Govt. Pri.School Mohadevpur
class: ৩য়,section name :moon
,student name,father name,mother name,Guardian phone number,
100221,ফাতেমা-তুজ-জহুরা,আবু হাছান ,মোছা: নাজমিন সুলতানা,01727-743686,
100222,শিফা আক্তার ,মো:সামসুর রহমান,মোছা: সাবানা বানু,01796-686933,
100223,মেশকাত জান্নাত ,মো: রবিউল আওয়াল,মোছা:তামান্না ইয়াসমিন,01714-474850,
100224,সুমনা আক্তার ,মো: সামসুর রহমান,মোসা:সাবানা বানু,01796-686933,
100225,মোছা:ফাতেমা আক্তার মায়িশা,মো: ময়নুল হক,মোসা: রিনা আক্তার ,01737-740466,
100226,রিশান সিদ্ধ দাস,রতন দাস,স্মৃতিকনা,01304-760764,
100227,মো:আব্দুল্লাহ -আল-সাফওয়ান,মো: আব্দুল্লাহ আল মামুন,মোছা: শিল্পী খাতুন,01303-187759,
100228,মো:আসওয়াদ বায়াত,মো: হারুন অর রশিদ,রিক্তা পারভীন,01729-388811,
100229,আনিশা রহমান,এস এম সাজিবুর রহমান,রুমানা,01723-204580,
100230,নিয়ামুল হাসান,মো: আলমগীর ,নাসরিন আক্তার ,1761-527270,
100231,জেবা তাসনীম ,মো: জাহাঙ্গীর আলম ,শামীমা আক্তার ,01737-498482,
100232,মেফতাহুল জান্নাত ,জাহাঙ্গীর আলম ,হোসনে আরা,01739-488589,
100233,সোহানা সারা,সাকিল হোসেন ,নাসরিন পারভীন,01710-137061,
100234,রিয়া দেবনাথ শিমু,স্বপন কুমার দেবনাথ,শেফালী দেবনাথ,01761-702335,
,,,,,
100235,মোসা: উম্মে সাবিহা,মো:সাইয়েদুজ্জামন,মোছা: আছিয়া খাতুন ,01719-665295,
100236,মার্জিয়া আনসারী নাবা,এস এম তানজিল অনসারী,মিফতাহ জান্নাতী,01712-481377,
100237,মো: জামিনুর রহমান,মো:গোলাম রাব্বানী ,মোছা:আরিফা খাতুন ,01712-593342,
,,,,,
,,,,,
100238,তাইয়্যেবা সিরাত রিদ্ধি,শামছ-ই-তাবরিজ,শাহীন আরা রুমী,01781-411659,
100239,মোছা:উম্মে হানি মিম,মো:মশিউর রহমান,মোছা:মতিয়া জাহান সাথী ,01739-054695,
100240,জামিলা আক্তার রোজা,মো:মইন উদ্দিন ,মোছা:তৈয়বা,01787-893268,
""".strip()
# ════════════════════════════════════════════════════════════════════════════


def clean(v):
    return (v or '').strip()


def parse_header(lines):
    """Extract class_name, section_name from the first 2-3 header lines."""
    class_name = ''
    section_name = ''
    for line in lines[:3]:
        lc = line.lower()
        if 'class' in lc or 'শ্রেণ' in line:
            # try to pull value after colon or after 'class'
            m = re.search(r'class\s*[:\s]+([^,]+)', line, re.IGNORECASE)
            if m:
                class_name = clean(m.group(1))
        if 'section' in lc or 'বিভাগ' in line:
            m = re.search(r'section\s*(?:name\s*)?[:\s]+([^,\n]+)', line, re.IGNORECASE)
            if m:
                section_name = clean(m.group(1))
    return class_name, section_name


def parse_csv_text(text):
    """Return (class_name, section_name, rows).
    rows = list of dicts with keys: code, name, father, mother, phone
    """
    raw_lines = text.strip().splitlines()

    # first line may be school_name: ..., second class/section info
    header_lines = raw_lines[:3]
    class_name, section_name = parse_header(header_lines)

    # find the actual data header row (looks like ",student name,...")
    data_start = 0
    for i, line in enumerate(raw_lines):
        parts = [p.strip().lower() for p in line.split(',')]
        if 'student name' in parts or 'name' in parts:
            data_start = i + 1
            break
    else:
        # fallback: skip any line where first cell is non-numeric
        for i, line in enumerate(raw_lines):
            first = line.split(',')[0].strip()
            if re.match(r'^\d{5,}$', first):
                data_start = i
                break

    data_lines = raw_lines[data_start:]
    reader = csv.reader(data_lines)
    rows = []
    for row in reader:
        if len(row) < 2:
            continue
        code = clean(row[0])
        if not re.match(r'^\d{5,}$', code):
            continue  # blank / header row
        name   = clean(row[1]) if len(row) > 1 else ''
        father = clean(row[2]) if len(row) > 2 else ''
        mother = clean(row[3]) if len(row) > 3 else ''
        phone  = clean(row[4]) if len(row) > 4 else ''
        if not name:
            continue
        rows.append({'code': code, 'name': name, 'father': father,
                     'mother': mother, 'guardian_phone': phone})
    return class_name, section_name, rows


def get_or_create_class(class_name_bn):
    """Find or create a SchoolClass by Bengali name."""
    # try exact match on name_bn first, then name
    cls = SchoolClass.query.filter(
        (SchoolClass.name_bn == class_name_bn) |
        (SchoolClass.name == class_name_bn)
    ).first()
    if cls:
        return cls
    # create new
    # try to derive a class_number
    digit_map = {'১': 1, '২': 2, '৩': 3, '৪': 4, '৫': 5,
                 '৬': 6, '৭': 7, '৮': 8, '৯': 9, '১০': 10}
    num = 0
    for bn, n in digit_map.items():
        if bn in class_name_bn:
            num = n
            break
    # find max existing class_number to avoid clash
    existing = db.session.query(db.func.max(SchoolClass.class_number)).scalar() or 0
    if num == 0:
        num = existing + 1

    cls = SchoolClass(
        name=class_name_bn,
        name_bn=class_name_bn,
        class_number=num,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.session.add(cls)
    db.session.flush()
    print(f"  [+] Created class: {class_name_bn} (id={cls.id})")
    return cls


def get_or_create_section(cls, section_name):
    """Find or create a SchoolSection under the given class."""
    sec = SchoolSection.query.filter_by(
        school_class_id=cls.id, name=section_name
    ).first()
    if sec:
        return sec
    sec = SchoolSection(
        school_class_id=cls.id,
        name=section_name,
        name_bn=section_name,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.session.add(sec)
    db.session.flush()
    print(f"  [+] Created section: {section_name} under class {cls.name_bn} (id={sec.id})")
    return sec


def import_students(class_name, section_name, rows, academic_year=None):
    if academic_year is None:
        academic_year = datetime.now().year

    print(f"\nClass   : {class_name or '(not detected)'}")
    print(f"Section : {section_name or '(not detected)'}")
    print(f"Year    : {academic_year}")
    print(f"Rows    : {len(rows)}\n")

    # get/create class & section
    cls = get_or_create_class(class_name) if class_name else None
    sec = get_or_create_section(cls, section_name) if (cls and section_name) else None

    created = updated = skipped = 0

    for roll_num, r in enumerate(rows, start=1):
        code           = r['code']
        name           = r['name']
        father         = r['father']
        mother         = r['mother']
        guardian_phone = r['guardian_phone'] or ''

        # split name into first / last (last word = last_name)
        parts = name.split()
        first_name = ' '.join(parts[:-1]) if len(parts) > 1 else name
        last_name  = parts[-1] if len(parts) > 1 else ''

        # phoneNumber used for login — use guardian_phone if available,
        # otherwise a unique placeholder so NOT NULL constraint is satisfied
        login_phone = guardian_phone if guardian_phone else f'000{code}'

        # find existing student by student_code
        student = User.query.filter_by(student_code=code).first()
        if student:
            student.first_name     = first_name
            student.last_name      = last_name
            student.phoneNumber    = login_phone
            student.guardian_name  = father
            student.guardian_phone = guardian_phone
            student.mother_name    = mother
            student.updated_at     = datetime.utcnow()
            action = 'updated'
            updated += 1
        else:
            student = User(
                student_code   = code,
                first_name     = first_name,
                last_name      = last_name,
                phoneNumber    = login_phone,
                guardian_name  = father,
                guardian_phone = guardian_phone,
                mother_name    = mother,
                role           = UserRole.STUDENT,
                is_active      = True,
                is_archived    = False,
                admission_date = date.today(),
                created_at     = datetime.utcnow(),
                updated_at     = datetime.utcnow(),
            )
            db.session.add(student)
            db.session.flush()
            action = 'created'
            created += 1

        # assign to class+section + roll number via student_class_info
        if cls:
            sci = StudentClassInfo.query.filter_by(student_id=student.id).first()
            if sci:
                sci.school_class_id = cls.id
                sci.section_id      = sec.id if sec else sci.section_id
                sci.roll_number     = roll_num
                sci.academic_year   = academic_year
            else:
                sci = StudentClassInfo(
                    student_id      = student.id,
                    school_class_id = cls.id,
                    section_id      = sec.id if sec else None,
                    roll_number     = roll_num,
                    academic_year   = academic_year,
                    created_at      = datetime.utcnow(),
                    updated_at      = datetime.utcnow(),
                )
                db.session.add(sci)

        print(f"  [{action:7s}] roll={roll_num:3d}  {code}  {name}  ({guardian_phone})")

    db.session.commit()
    print(f"\n✓ Done — created: {created}  updated: {updated}  skipped: {skipped}")


def main():
    if len(sys.argv) >= 2:
        path = sys.argv[1]
        with open(path, encoding='utf-8-sig') as f:
            text = f.read()
        print(f"Reading file: {path}")
    else:
        text = INLINE_CSV
        print("Using inline CSV data")

    year = None
    if len(sys.argv) >= 3:
        try:
            year = int(sys.argv[2])
        except ValueError:
            pass

    class_name, section_name, rows = parse_csv_text(text)

    with app.app_context():
        import_students(class_name, section_name, rows, academic_year=year)


if __name__ == '__main__':
    main()
