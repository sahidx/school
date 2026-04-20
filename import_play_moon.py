import re
from datetime import datetime, date
from app import create_app
from models import db, User, UserRole, Batch, SchoolClass, SchoolSection, StudentClassInfo

app = create_app()

def clean_phone(raw):
    if not raw or str(raw).strip() == '':
        return None
    digits = re.sub(r'[^\d]', '', str(raw).strip())[:11]
    return digits if len(digits) == 11 and digits.startswith('01') else None

students_data = [
    (100037, 'মো:তাসাউফ আল রাহীম', 'এস. এম জাহাঙ্গীর আলম', 'মোছা:ফাহমিদা আক্তার', '01718-613939'),
    (100038, 'শিবম কুমার রোদ', 'টনি কুমার মন্ডল', 'শ্রাবণী রানী', '01740-864892'),
    (100039, 'উম্মে বেহেস্তী নীলা', 'মো:আল মামুন', 'মোছা:মরিয়ম বেগম', '01753-930035'),
    (100040, 'মো:গোলাম কিবরিয়া অলি', 'মো:গোলাম মাওলা', 'ফেরদৌসী আক্তার', '01733-258502'),
    (100041, 'আরিশা জান্নাত', 'মো:শাহীন', 'উম্মে খাইরুম', '01745-001191'),
    (100042, 'মোছা:সামিরা জাহান সারা', 'মো:সোলাইমান আলী', 'মোছা:জেমি আক্তার', '01768-619157'),
    (100043, 'মোছা:আজমি জান্নাত আলফি', 'মো: আল মাহমুদ পিন্টু', 'মোছা:বিউটি আক্তার', '01783-432653'),
    (100044, 'মো:আয়মান সাদিক', 'মো :মোতালেব হোসেন', 'মোছা: সোনিয়া খাতুন', '01777-831363'),
    (100045, 'মো:আরাফাত -বিন -সিফাত', 'মো:শফিকুল ইসলাম', 'আরিফা খাতুন', '01736-821415'),
    (100046, 'আদি মহন্ত', 'বিষ্নু মহন্ত', 'রমা রানী মহন্ত', '01719-863604'),
    (100047, 'নুসাইফা বিন্তে নূর', 'নূর মোহাম্মদ', 'মোছা: ইয়াসমিন', '01701-080602'),
    (100048, 'মো:মুনতাসির ইসলাম আয়ান', 'মো:আনরুল ইসলাম', 'মোছা: মৌসুমী আক্তার', '01798-719167'),
    (100049, 'মোসা: আয়েশা সিদ্দিকা', 'মো: কাইন আলম', 'মোছা: মৌসুমী আক্তার', '01767-649221'),
    (100050, 'নীল চৌধুরী', 'সুবল চৌধুরী', 'বিনা রানী', '01771-820286'),
    (100051, 'নদী চৌধুরী', 'শ্রী নয়ন চৌধুরী', 'শ্রীমতী বিজলী রানী চৌধুরী', '01774-891916'),
    (100052, 'মোসা: আরশি ইসলাম রেজিয়া', 'মো: শাহজান আলী পলাশ', 'মোছা: আসমা খানম', '01716-606527'),
    (100053, 'মোসা: তামান্না আক্তার', 'মো: নাইম হোসেন', 'মোসা: ফারজানা আক্তার', '01745-177151'),
    (100054, 'মোসা: ফারিয়া জান্নাত', 'মো: ফারুক হোসেন', 'মোসা:বর্ষা আক্তার', '01781-240337'),
    (100055, 'মো: সাকিবুল হাসান', 'মো: ইমরান', 'মোসা: সাথী', '01727-848657'),
    (100056, 'মোরসালিন হোসেন মেজবা', 'মো: শামসুল মন্ডল', 'মোছা: মেঘনা মন্ডল', '01740-099389'),
    (100057, 'মো:সোহরাব হোসেন সায়েম', 'মো: আলমগীর কবির', 'ফাল্গুনী আক্তার', '01725-018335'),
    (100058, 'মো: রোবায়েত মন্ডল', 'মো: রফিক মন্ডল', 'মোসা: মুন্নি আক্তার', '01343-171197'),
    (100059, 'মো: রোবায়েদ আব্রান খান আয়ান', 'মো: রাশেদ খান', 'শারমিন হক', '01736-009935'),
    (100060, 'সমরিন বিনতে নূর', 'মো:আহসান উল্লাহ খান', 'আরিকা সুলতানা', '01735-001264'),
    (100061, 'মো: আব্দুল্লাহ-আল-রিয়াদ', 'মো:আনারুল ইসলাম', 'মোসা: রিপা খাতুন', '01318-828427'),
]

with app.app_context():
    # Play class: id=6, Moon section: id=12, batch "Play 2026": id=6
    school_class = db.session.get(SchoolClass, 6)
    section = db.session.get(SchoolSection, 12)
    batch = db.session.get(Batch, 6)

    print(f"Class: {school_class.name}, Section: {section.name}, Batch: {batch.name}")

    created = skipped = 0
    no_phone = []

    for reg, name, father, mother, raw_phone in students_data:
        code = str(reg)
        if User.query.filter_by(student_code=code).first():
            print(f"  SKIP {reg} {name} (already exists)")
            skipped += 1
            continue

        phone = clean_phone(raw_phone)
        if phone is None:
            no_phone.append((reg, name))
        login_phone = phone if phone else f'000{code}'

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

        db.session.add(StudentClassInfo(
            student_id=student.id,
            school_class_id=school_class.id,
            section_id=section.id,
        ))
        student.batches.append(batch)
        created += 1
        print(f"  OK  {reg} {name} | phone={login_phone}")

    db.session.commit()
    print(f"\nDone. created={created} skipped={skipped}")
    if no_phone:
        print("No phone:")
        for r, n in no_phone:
            print(f"  {r} {n}")
