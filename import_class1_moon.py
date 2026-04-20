import re
import sys
from datetime import datetime, date
from app import create_app
from models import db, User, UserRole, Batch, SchoolClass, SchoolSection, StudentClassInfo

app = create_app()

def clean_phone(raw):
    if not raw or str(raw).strip() == '':
        return None
    raw = str(raw).strip()
    digits = re.sub(r'[^\d]', '', raw)
    digits = digits[:11]
    if len(digits) == 11 and digits.startswith('01'):
        return digits
    return None

students_data = [
    (100138, 'মোসা: সাওদা মেহেজাবিন', 'মো: সুজন রানা', 'মোছা: উম্মে হাবিবা খানম', '01799-124232'),
    (100139, 'মো:গোলাম সাদিন আনসারী', 'মো: গোলাম সাব্বির আনসারী', 'রেহেনা নুসরাত হক', '01761-636536'),
    (100140, 'মারছাদ রাকীন', 'মনিরুজ্জামান', 'মনিরা খাতুন', '01736-420086'),
    (100141, 'মিন্নাতুন রহমান মাহির', 'মো: মারুফ হোসেন', 'মোসা: জাকিয়া খাতুন', '01754-122051'),
    (100142, 'মৌমিতা জান্নাত', 'মো: মোরশেদুল আলম', 'মোসা :মোকলেদা খাতুন', '01753-018892'),
    (100143, 'অঙ্কিতা রায় প্রাপ্তি', 'শয়ন কুমার', 'সবিতা রানী', '01741-282764'),
    (100144, 'জিহাদ শাহরিয়ার', 'মো: শান্ত আলী', 'খাদিজা আফরোজা', '01885-631213'),
    (100145, 'সিনহা আক্তার', 'মো: তুহিন হোসেন', 'মোছা: রুপালী খাতুন', '01626-688686'),
    (100146, 'মো: হাবিবুল্লাহ', 'মো: বাবলু', 'মোছা: আক্তারা', '01781-102033'),
    (100147, 'মো: জোনাইদ আল হাবিব', 'মো: বচ্চু', 'জেরিন আক্তার', '01742-306787'),
    (100148, 'অভিজিৎ কুমার রায়', 'পলাশ কুমার রায়', 'বাসনা রানী রায়', '01753-025510'),
    (100149, 'মো:বায়জিদ ইসলাম', 'মো: আরিফুল ইসলাম', 'মোছা: বুলি খাতুন', '01770-536142'),
    (100150, 'মেহবুবা জান্নাত শোহানা', 'মো:শাজাহান আলী', 'মোরশেদা', '01757-452575'),
    (100151, 'মোছা:মরিয়ম জান্নাত', 'মো: মুমিউদ্দিন সরদার', 'মোছা: মোরশেদা আক্তার', '01762-116507'),
    (100152, 'ঋত্বিক মন্ডল', 'রিপন মন্ডল', 'অতসি রানী', '01748-862034'),
    (100153, 'মো: আশিকুর রহমান রাতুল', 'মো: সাদিক হাসান সুমন', 'মোসা: আরছিনা পারভীন', '01740-877448'),
    (100154, 'অর্পণ কুমার মন্ডল', 'সঞ্জয় কুমার মন্ডল', 'নিপা রানী মন্ডল', None),
    (100155, 'খাতিজা আক্তার রুপা', 'মো:আতাউল', 'মোছা: রশিদা বানু', '01745-313510'),
    (100156, 'বাপ্পি কুমার মন্ডল', 'বিদ্যুৎ কুমার মন্ডল', 'সুমনা রানী', '01792-522295'),
    (100157, 'কুমারী নন্দিনী রানী', 'নয়ন কুমার চৌধুরী', 'বিজলী রানী', '01751-654261'),
    (100158, 'জিনাত আরা', 'জোবায়ের আহমেদ', 'মোছা: ফাহমিদা আক্তার', '01719-543888'),
    (100159, 'মোছা:আরশিয়া', 'মো: রবিউল ইসলাম', 'মোছা: আয়েশা সিদ্দকা', '01712-628607'),
    (100160, 'তাসফিয়া তুবা', 'শামসুজ্জোহা জামিল', 'তাজনুর', '01346-676121'),
    (100161, 'মেহেরিমা সুলতানা', 'মো: জাহাঙ্গীর আলম', 'মোসা রাজিয়া সুলতানা', '01712-775244'),
    (100162, 'ফারহা', 'মো: সোহেল', 'রাবেয়া', '01733-261865'),
    (100163, 'নিরব কুমার রায়', 'নিখিল কুমার রায়', 'পপি রানী', '01781-929328'),
]

with app.app_context():
    # প্রথম class: id=3, Moon section: id=6, batch: id=3
    school_class = db.session.get(SchoolClass, 3)
    section = db.session.get(SchoolSection, 6)
    batch = db.session.get(Batch, 3)

    print(f"Class: {school_class.name}, Section: {section.name}, Batch: {batch.name}")

    created = 0
    skipped = 0
    no_phone = []

    for reg, name, father, mother, raw_phone in students_data:
        code = str(reg)
        existing = User.query.filter_by(student_code=code).first()
        if existing:
            print(f"  SKIP {reg} {name} (already exists)")
            skipped += 1
            continue

        phone = clean_phone(raw_phone)
        if phone is None:
            no_phone.append((reg, name))
            login_phone = f'000{code}'
        else:
            login_phone = phone

        parts = name.split()
        first_name = ' '.join(parts[:-1]) if len(parts) > 1 else name
        last_name  = parts[-1] if len(parts) > 1 else ''

        student = User(
            student_code=code,
            first_name=first_name,
            last_name=last_name,
            phoneNumber=login_phone,
            guardian_name=father,
            guardian_phone=login_phone,
            mother_name=mother,
            role=UserRole.STUDENT,
            is_active=True,
            is_archived=False,
            admission_date=date.today(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(student)
        db.session.flush()

        sci = StudentClassInfo(
            student_id=student.id,
            school_class_id=school_class.id,
            section_id=section.id,
        )
        db.session.add(sci)
        student.batches.append(batch)
        created += 1
        print(f"  OK  {reg} {name} | phone={login_phone}")

    db.session.commit()
    print(f"\nDone. created={created} skipped={skipped}")
    if no_phone:
        print("No phone:")
        for r, n in no_phone:
            print(f"  {r} {n}")
