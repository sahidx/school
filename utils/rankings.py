from sqlalchemy import func

from models import db, MonthlyExam, MonthlyRanking, MonthlyMark


def get_batch_latest_rank_map(batch_id):
    """Return rank map for a batch using latest available monthly exam data.

    Priority:
    1) Latest exam with finalized MonthlyRanking rows having usable rank values.
    2) Latest exam with any MonthlyRanking rows having usable rank values.
    3) Latest exam with MonthlyMark rows (compute rank from total marks).

    Returns:
        tuple(dict, MonthlyExam|None): (rank_map, source_exam)
    """

    # 1/2: Try ranking table first (latest finalized preferred, then any ranking rows)
    ranked_exams = (
        MonthlyExam.query.join(MonthlyRanking, MonthlyRanking.monthly_exam_id == MonthlyExam.id)
        .filter(MonthlyExam.batch_id == batch_id)
        .order_by(MonthlyExam.year.desc(), MonthlyExam.month.desc(), MonthlyExam.id.desc())
        .all()
    )

    for exam in ranked_exams:
        finalized_rows = MonthlyRanking.query.filter_by(
            monthly_exam_id=exam.id,
            is_final=True
        ).all()

        candidate_rows = finalized_rows
        if not candidate_rows:
            candidate_rows = MonthlyRanking.query.filter_by(monthly_exam_id=exam.id).all()

        rank_map = {}
        for row in candidate_rows:
            current_rank = row.position or row.roll_number
            if current_rank:
                rank_map[row.user_id] = current_rank

        if rank_map:
            return rank_map, exam

    # 3: Fallback to exam marks and compute ranking on the fly (scan latest -> oldest)
    all_exams = (
        MonthlyExam.query.filter_by(batch_id=batch_id)
        .order_by(MonthlyExam.year.desc(), MonthlyExam.month.desc(), MonthlyExam.id.desc())
        .all()
    )

    if not all_exams:
        return {}, None

    for exam in all_exams:
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
        for row in mark_rows:
            obtained = float(row.total_obtained or 0)
            possible = float(row.total_possible or 0)
            percentage = (obtained / possible * 100) if possible > 0 else 0
            scored.append((row.user_id, percentage, obtained))

        if not scored:
            continue

        scored.sort(key=lambda item: (-item[1], -item[2], item[0]))

        rank_map = {}
        for index, item in enumerate(scored, start=1):
            rank_map[item[0]] = index

        return rank_map, exam

    return {}, all_exams[0]
