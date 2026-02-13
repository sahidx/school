from sqlalchemy import func
from datetime import datetime

from models import db, MonthlyExam, MonthlyRanking, MonthlyMark


def get_global_latest_rank_map(candidate_user_ids):
    """
    Find the best exam rank map for a set of users across ALL batches.
    Prioritizes Previous Month (Historic) exams over Current Month exams.
    """
    if not candidate_user_ids:
        return {}, None

    # Get all potential exams for these students (Marks OR Rankings)
    # We query exams that have either marks or rankings for these users
    candidates_query = (
        MonthlyExam.query
        .join(MonthlyMark, MonthlyMark.monthly_exam_id == MonthlyExam.id, isouter=True)
        .join(MonthlyRanking, MonthlyRanking.monthly_exam_id == MonthlyExam.id, isouter=True)
        .filter(
            (MonthlyMark.user_id.in_(candidate_user_ids)) | 
            (MonthlyRanking.user_id.in_(candidate_user_ids))
        )
        .order_by(MonthlyExam.year.desc(), MonthlyExam.month.desc(), MonthlyExam.id.desc())
        .limit(20) # Optimize: Check last 20 relevant exams
    )
    
    all_candidates = candidates_query.all()
    if not all_candidates:
        return {}, None

    # Sort into Historic vs Current
    now = datetime.now()
    historic_exams = []
    current_exams = []
    
    for ex in all_candidates:
        if ex.year < now.year or (ex.year == now.year and ex.month < now.month):
            historic_exams.append(ex)
        else:
            current_exams.append(ex)
            
    prioritized_exams = historic_exams + current_exams

    # Iterate through prioritized exams to find the first valid map
    for exam in prioritized_exams:
        # A. Check Rankings
        rankings = MonthlyRanking.query.filter_by(monthly_exam_id=exam.id).all()
        rank_map = {}
        for row in rankings:
            current_rank = row.position
            if current_rank:
                rank_map[row.user_id] = current_rank
        
        if rank_map:
            return rank_map, exam

        # B. Check Marks
        mark_rows = (
            db.session.query(
                MonthlyMark.user_id,
                func.sum(MonthlyMark.marks_obtained).label('total_obtained'),
                func.sum(MonthlyMark.total_marks).label('total_possible')
            )
            .filter(MonthlyMark.monthly_exam_id == exam.id)
            .group_by(MonthlyMark.user_id)
            .all()
        )
        
        scored = []
        max_obtained = 0
        for row in mark_rows:
            obtained = float(row.total_obtained or 0)
            if obtained > max_obtained:
                max_obtained = obtained
            possible = float(row.total_possible or 0)
            percentage = (obtained / possible * 100) if possible > 0 else 0
            scored.append((row.user_id, percentage, obtained))

        if scored and max_obtained > 0:
            scored.sort(key=lambda item: (-item[1], -item[2], item[0]))
            rank_map = {}
            for index, item in enumerate(scored, start=1):
                rank_map[item[0]] = index
            return rank_map, exam

    return {}, None


def get_batch_latest_rank_map(batch_id):
    """Return rank map for a batch using latest available monthly exam data.

    Priority:
    1) Latest exam with finalized MonthlyRanking rows having usable rank values.
    2) Latest exam with any MonthlyRanking rows having usable rank values.
    3) Latest exam with MonthlyMark rows (compute rank from total marks).

    Returns:
        tuple(dict, MonthlyExam|None): (rank_map, source_exam)
    """

    # PRE-FILTER: Prefer Previous Month's Exams (Stability Rule)
    # "If this is February, show January roll in whole February"
    now = datetime.now()
    all_exams_raw = (
        MonthlyExam.query.filter_by(batch_id=batch_id)
        .order_by(MonthlyExam.year.desc(), MonthlyExam.month.desc(), MonthlyExam.id.desc())
        .all()
    )
    
    if not all_exams_raw:
        # Step 4: Fallback to Global Search (Cross-Batch Ranking)
        # If no exams exist for this specific batch, look for exams taken by these students in ANY batch
        from models import User, Batch, UserRole
        students = User.query.join(User.batches).filter(
            Batch.id == batch_id, 
            User.is_active == True,
            User.is_archived == False
        ).all()
        
        if students:
            student_ids = [s.id for s in students]
            global_rank_map, source_exam = get_global_latest_rank_map(student_ids)
            if global_rank_map:
                return global_rank_map, source_exam
        
        return {}, None

    # Sort exams into "Historic" (Previous Months) and "Current/Future"
    historic_exams = []
    current_exams = []
    
    for ex in all_exams_raw:
        # Check if exam is strictly before current month
        if ex.year < now.year or (ex.year == now.year and ex.month < now.month):
            historic_exams.append(ex)
        else:
            current_exams.append(ex)
            
    # Priority: Historic Exams -> Current Exams
    # This ensures Jan results are used throughout Feb, even if Feb results exist.
    prioritized_exams = historic_exams + current_exams

    # 1/2: Try ranking table first
    for exam in prioritized_exams:
        finalized_rows = MonthlyRanking.query.filter_by(
            monthly_exam_id=exam.id,
            is_final=True
        ).all()

        candidate_rows = finalized_rows
        # Only check non-finalized rankings if we don't have finalized ones?
        # Actually, let's stick to the prioritized order.
        if not candidate_rows:
             candidate_rows = MonthlyRanking.query.filter_by(monthly_exam_id=exam.id).all()

        rank_map = {}
        for row in candidate_rows:
            # STRICT: Only accept 'position' (Merit Rank). 
            # Do NOT fallback to 'roll_number' because new exams have rolls but no merit rank.
            current_rank = row.position
            if current_rank:
                rank_map[row.user_id] = current_rank

        if rank_map:
            return rank_map, exam

    # 3: Fallback to exam marks
    for exam in prioritized_exams:
        mark_rows = (
            db.session.query(
                MonthlyMark.user_id,
                func.sum(MonthlyMark.marks_obtained).label('total_obtained'),
                func.sum(MonthlyMark.total_marks).label('total_possible')
            )
            .filter(MonthlyMark.monthly_exam_id == exam.id)
            .group_by(MonthlyMark.user_id)
            .all()
        )

        if not mark_rows:
            continue

        scored = []
        max_obtained = 0
        for row in mark_rows:
            obtained = float(row.total_obtained or 0)
            if obtained > max_obtained:
                max_obtained = obtained
            possible = float(row.total_possible or 0)
            percentage = (obtained / possible * 100) if possible > 0 else 0
            scored.append((row.user_id, percentage, obtained))

        if not scored:
            continue

        # Skip exam if all students have 0 marks (likely just initialized but not taken)
        if max_obtained == 0:
            continue

        scored.sort(key=lambda item: (-item[1], -item[2], item[0]))

        rank_map = {}
        for index, item in enumerate(scored, start=1):
            rank_map[item[0]] = index

        return rank_map, exam

    # Step 4 (Late Fallback): If we had exams but none yielded a valid map (e.g. all empty marks), 
    # try the Global Fallback one last time.
    # ALSO: Per user request, check if we accidentally skipped the "Latest" exam because it wasn't the target month.
    # However, the current logic scans Newest -> Oldest. 
    # If Feb exam has 0 marks, it skips, and finds Jan exam. This IS the desired behavior.
    # The issue might be that "Latest" exam isn't the one we want if it's incomplete.
    # My "max_obtained > 0" check handles this already.
    
    from models import User, Batch
    students = User.query.join(User.batches).filter(
        Batch.id == batch_id, 
        User.is_active == True,
        User.is_archived == False
    ).all()
    
    if students:
        student_ids = [s.id for s in students]
        global_rank_map, source_exam = get_global_latest_rank_map(student_ids)
        if global_rank_map:
            return global_rank_map, source_exam

    if all_exams:
         return {}, all_exams[0]
    return {}, None
