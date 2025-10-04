import streamlit as st
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import uuid

def uid():
    return str(uuid.uuid4())[:8]

if 'topics' not in st.session_state:
    st.session_state.topics = {}

if 'profile' not in st.session_state:
    st.session_state.profile = {'daily_minutes': 60, 'time_mgmt_issue': False, 'short_sessions': False}

if 'plan' not in st.session_state:
    st.session_state.plan = {}
def compute_priority(topic, profile):
    conf = topic.get('user_confidence', 50)
    last_score = topic.get('last_score') or 50
    difficulty = topic.get('difficulty', 50)
    mismatch_boost = 30 if (topic.get('declared_strength') and last_score < 60) else 0
    tm_boost = 10 if profile.get('time_mgmt_issue') else 0
    return ((100 - conf) * 0.35) + ((100 - last_score) * 0.4) + (difficulty * 0.15) + mismatch_boost*0.06 + tm_boost*0.04
def generate_plan(days=14, session_len=None):
    profile = st.session_state.profile
    if session_len is None:
        session_len = 15 if profile.get('time_mgmt_issue') or profile.get('short_sessions') else 45
    daily_minutes = profile.get('daily_minutes', 60)
    topics = list(st.session_state.topics.values())
    plan = {}
    for d in range(days):
        date = (datetime.now() + timedelta(days=d)).date()
        day_key = date.isoformat()
        plan[day_key] = []
        minutes_left = daily_minutes
        per_day_count = {t['id']:0 for t in topics}
        while minutes_left >= min(session_len, 10):
            priorities = [(compute_priority(t, profile), t) for t in topics]
            priorities.sort(key=lambda x: -x[0])
            selected = None
            for pr, t in priorities:
                if per_day_count[t['id']] >= 2:
                    continue
                if t.get('last_score') and t['last_score'] >= 85 and per_day_count[t['id']] >= 1:
                    continue
                selected = t
                break
            if not selected:
                break
            use_len = min(session_len, minutes_left, selected.get('est_time', session_len))
            session = {'topic_id': selected['id'], 'topic_name': selected['name'], 'subject': selected['subject'], 'minutes': use_len, 'reason_priority': round(compute_priority(selected, profile),2)}
            plan[day_key].append(session)
            minutes_left -= use_len
            per_day_count[selected['id']] += 1
    st.session_state.plan = plan
    return plan

