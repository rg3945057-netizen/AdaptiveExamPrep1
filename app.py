from flask import Flask, render_template, request, session, redirect, url_for, Response
from datetime import datetime, timedelta
import csv
import io

app = Flask(__name__)
# For demo only. Replace with a stronger secret in production
app.secret_key = "dev-secret-replace-in-prod"

def calc_priority(confidence, score, difficulty, declared_strong, time_issue):
    """
    Explainable priority formula:
    - Lower confidence -> higher priority
    - Lower last_score -> higher priority
    - Higher difficulty -> higher priority
    - If user says 'strong' but last_score < 60 -> mismatch boost
    - If time management issue -> small boost
    """
    base = (100 - confidence) * 0.35 + (100 - score) * 0.4 + difficulty * 0.15
    if declared_strong and score < 60:
        base += 20  # mismatch boost
    if time_issue:
        base += 5
    return round(base, 2)

def generate_plan(topics, days=7, daily_minutes=60, time_issue=False):
    """
    Greedy scheduler:
    - Each day, fill daily_minutes with sessions (session_len based on time_issue).
    - Pick highest-priority topics first; allow up to 2 sessions per topic per day.
    - Skip extra sessions for topics already very strong (score >= 90).
    """
    plan = []
    today = datetime.now().date()
    session_len = 20 if time_issue else 45

    for d in range(days):
        date = today + timedelta(days=d)
        minutes_left = daily_minutes
        per_topic_count = {t['name']: 0 for t in topics}
        # Sort once per day by priority descending
        sorted_topics = sorted(topics, key=lambda t: -t['priority'])
        while minutes_left >= min(session_len, 10):
            # choose best topic that hasn't exceeded per-day cap
            selected = None
            for t in sorted_topics:
                if per_topic_count[t['name']] >= 2:
                    continue
                if t.get('score', 0) >= 90 and per_topic_count[t['name']] >= 1:
                    continue
                selected = t
                break
            if not selected:
                break
            use_len = min(session_len, minutes_left)
            plan.append({
                'date': str(date),
                'subject': selected.get('subject',''),
                'topic': selected['name'],
                'minutes': use_len,
                'priority': selected['priority']
            })
            minutes_left -= use_len
            per_topic_count[selected['name']] += 1
    return plan

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Profile inputs
        try:
            daily_minutes = int(request.form.get('daily_minutes', 60))
        except ValueError:
            daily_minutes = 60
        time_issue = request.form.get('time_issue') == 'on'
        try:
            days = int(request.form.get('days', 7))
        except ValueError:
            days = 7

        # topic arrays (names like name[] used on frontend)
        names = request.form.getlist('name[]')
        subjects = request.form.getlist('subject[]')
        confs = request.form.getlist('confidence[]')
        scores = request.form.getlist('score[]')
        diffs = request.form.getlist('difficulty[]')
        strongs = request.form.getlist('strong[]')

        topics = []
        for i, name in enumerate(names):
            name = name.strip()
            if not name:
                continue
            subject = subjects[i].strip() if i < len(subjects) else ''
            confidence = int(confs[i]) if i < len(confs) and confs[i] else 50
            score = int(scores[i]) if i < len(scores) and scores[i] else 50
            difficulty = int(diffs[i]) if i < len(diffs) and diffs[i] else 50
            declared_strong = (strongs[i] == 'yes') if i < len(strongs) else False
            priority = calc_priority(confidence, score, difficulty, declared_strong, time_issue)
            topics.append({
                'name': name,
                'subject': subject,
                'confidence': confidence,
                'score': score,
                'difficulty': difficulty,
                'declared_strong': declared_strong,
                'priority': priority
            })

        if not topics:
            return render_template('index.html', error="Please add at least one topic.")

        plan = generate_plan(topics, days=days, daily_minutes=daily_minutes, time_issue=time_issue)
        # store plan in session for CSV download
        session['plan'] = plan
        session['topics'] = topics
        session['profile'] = {'daily_minutes': daily_minutes, 'time_issue': time_issue, 'days': days}
        return render_template('plan.html', plan=plan, topics=topics, profile=session['profile'])

    return render_template('index.html')

@app.route('/download')
def download():
    plan = session.get('plan')
    if not plan:
        return redirect(url_for('index'))
    # write CSV to memory
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['date', 'subject', 'topic', 'minutes', 'priority'])
    for r in plan:
        writer.writerow([r['date'], r['subject'], r['topic'], r['minutes'], r.get('priority', '')])
    mem = io.BytesIO()
    mem.write(si.getvalue().encode('utf-8'))
    mem.seek(0)
    return Response(mem.read(),
                    mimetype='text/csv',
                    headers={"Content-disposition": "attachment; filename=adaptive_plan.csv"})

if __name__ == '__main__':
    # debug=True for development/demo only
    app.run(debug=True, host='127.0.0.1', port=5000)

