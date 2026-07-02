import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import math
from supabase import create_client, Client

# ==========================================
# הגדרות עמוד בסיסיות
# ==========================================
st.set_page_config(
    page_title="ProFlow Enterprise",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# CSS
# ==========================================
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebar"] {display: none !important;}
[data-testid="collapsedControl"] {display: none !important;}

.stApp {
    background-color: #F8FAFC;
    color: #0F172A;
    direction: rtl;
    font-family: 'Segoe UI', sans-serif;
}

h1, h2, h3 {
    color: #0369A1 !important;
    font-weight: 700;
}

.card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}

.kpi-card {
    background-color: #FFFFFF;
    border-top: 4px solid #0284C7;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    height: 100%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.kpi-title {
    color: #64748B;
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 8px;
}

.kpi-value {
    color: #0F172A;
    font-size: 32px;
    font-weight: 800;
}

.kpi-note {
    color: #94A3B8;
    font-size: 13px;
    margin-top: 8px;
}

.stButton > button {
    background-color: #0284C7 !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 600 !important;
    width: 100%;
    transition: 0.2s;
}

.stButton > button:hover {
    background-color: #0369A1 !important;
}

.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    text-align: right !important;
}

[data-testid="stPlotlyChart"] {
    direction: ltr;
}

.nav-box {
    background: #0F172A;
    min-height: 88vh;
    border-radius: 18px;
    padding: 22px 16px;
    box-shadow: 0 10px 25px rgba(15,23,42,0.18);
}

.nav-title {
    color: white;
    font-size: 22px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 6px;
}

.nav-subtitle {
    color: #CBD5E1;
    font-size: 13px;
    text-align: center;
    margin-bottom: 24px;
}

.nav-label {
    color: #94A3B8;
    font-size: 13px;
    font-weight: 700;
    margin: 18px 0 8px 0;
}

.nav-sep {
    border-top: 1px solid #334155;
    margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# Supabase
# ==========================================
SUPABASE_URL = "https://mtfhapzuvckucyuqtuju.supabase.co"
SUPABASE_KEY = "sb_publishable_XjpjwBN1gqk1s6LC1he2HQ_S3l_F9vU"

def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

# ==========================================
# Session State
# ==========================================
if "page" not in st.session_state:
    st.session_state.page = "landing"

if "user" not in st.session_state:
    st.session_state.user = None

if "profile_name" not in st.session_state:
    st.session_state.profile_name = ""

if "app_view" not in st.session_state:
    st.session_state.app_view = "תכנון CCPM חדש"

def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def navigate_to(page_name):
    st.session_state.page = page_name
    safe_rerun()

# ==========================================
# חישובים
# ==========================================
def calculate_pert_ccpm(tasks):
    task_dict = {t["id"]: t.copy() for t in tasks if t["id"]}

    for t_id, task in task_dict.items():
        o = task["opt"]
        m = task["lik"]
        p = task["pes"]
        te = (o + 4*m + p) / 6.0
        var = ((p - o) / 6.0) ** 2

        task_dict[t_id].update({
            "TE": te,
            "Var": var,
            "ES": 0,
            "EF": 0,
            "LS": 0,
            "LF": 0,
            "Slack": 0,
            "סטטוס": "NORMAL"
        })

    changed = True
    while changed:
        changed = False
        for t_id, task in task_dict.items():
            es = 0
            if task["predecessors"]:
                preds_ef = [
                    task_dict[pred]["EF"]
                    for pred in task["predecessors"]
                    if pred in task_dict
                ]
                if preds_ef:
                    es = max(preds_ef)

            ef = es + task["TE"]

            if abs(es - task["ES"]) > 0.001 or abs(ef - task["EF"]) > 0.001:
                task["ES"] = es
                task["EF"] = ef
                changed = True

    project_duration = max([t["EF"] for t in task_dict.values()]) if task_dict else 0

    for t_id in task_dict:
        task_dict[t_id]["LF"] = project_duration
        task_dict[t_id]["LS"] = project_duration - task_dict[t_id]["TE"]

    changed = True
    while changed:
        changed = False
        for t_id, task in task_dict.items():
            successors = [
                t for t in task_dict.values()
                if t_id in t["predecessors"]
            ]

            if successors:
                lf = min([succ["LS"] for succ in successors])
                ls = lf - task["TE"]

                if abs(lf - task["LF"]) > 0.001 or abs(ls - task["LS"]) > 0.001:
                    task["LF"] = lf
                    task["LS"] = ls
                    changed = True

    critical_variance_sum = 0

    for task in task_dict.values():
        task["Slack"] = task["LF"] - task["EF"]

        if task["Slack"] <= 0.001:
            task["סטטוס"] = "CRITICAL"
            critical_variance_sum += task["Var"]

    project_buffer = math.sqrt(critical_variance_sum) if critical_variance_sum > 0 else 0
    safe_project_duration = project_duration + project_buffer

    return list(task_dict.values()), project_duration, project_buffer, safe_project_duration

def identify_drum(tasks_results):
    machine_loads = {}

    for r in tasks_results:
        if r["machine"] != "ללא מכונה":
            machine_loads[r["machine"]] = machine_loads.get(r["machine"], 0) + r["TE"]

    if not machine_loads:
        return None, 0

    drum_machine = max(machine_loads, key=machine_loads.get)
    return drum_machine, machine_loads[drum_machine]

# ==========================================
# עמוד פתיחה
# ==========================================
if st.session_state.page == "landing":
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
        <div class="card" style="text-align: center; border-top: 4px solid #0284C7;">
            <h1 style="font-size: 42px;">מערכת תכנון אופטימלית - Enterprise</h1>
            <h3 style="color: #475569 !important; font-weight: 400;">
                יישום CCPM, תורת האילוצים וניהול עומסי מסד הנתונים בחברה.
            </h3>
            <hr>
        </div>
        """, unsafe_allow_html=True)

        if st.button("כניסה למערכת ➔"):
            navigate_to("auth")

# ==========================================
# התחברות / הרשמה
# ==========================================
elif st.session_state.page == "auth":
    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.title("🔒 כניסה / הרשמה")

        tab1, tab2 = st.tabs(["התחברות", "הרשמה"])

        with tab1:
            log_email = st.text_input("אימייל", key="log_email")
            log_pass = st.text_input("סיסמה", type="password", key="log_pass")

            if st.button("התחבר"):
                try:
                    res = supabase.auth.sign_in_with_password({
                        "email": log_email,
                        "password": log_pass
                    })
                    st.session_state.user = res.user
                    navigate_to("app")
                except Exception:
                    st.error("שגיאה בהתחברות.")

        with tab2:
            reg_name = st.text_input("שם מלא", key="reg_name")
            reg_email = st.text_input("אימייל", key="reg_email")
            reg_pass = st.text_input("סיסמה", type="password", key="reg_pass")

            if st.button("הרשם"):
                try:
                    res = supabase.auth.sign_up({
                        "email": reg_email,
                        "password": reg_pass
                    })

                    if res.user:
                        supabase.table("profiles").update({
                            "full_name": reg_name
                        }).eq("id", res.user.id).execute()

                    st.success("נרשמת! עבור להתחברות.")
                except Exception:
                    st.error("שגיאה בהרשמה.")

        if st.button("← חזרה"):
            navigate_to("landing")

        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# אזור מערכת
# ==========================================
elif st.session_state.page == "app" and st.session_state.user is not None:

    nav_col, main_col = st.columns([1.1, 4.9], gap="large")

    with nav_col:
        st.markdown("""
        <div class="nav-box">
            <div class="nav-title">⚙️ ProFlow</div>
            <div class="nav-subtitle">Enterprise Dashboard</div>
            <div class="nav-label">ניווט מערכת</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🏠 תכנון CCPM חדש"):
            st.session_state.app_view = "תכנון CCPM חדש"
            safe_rerun()

        if st.button("📊 סטטיסטיקה ובקרה"):
            st.session_state.app_view = "סטטיסטיקה ובקרה (SPC)"
            safe_rerun()

        if st.button("🗂️ היסטוריית פרויקטים"):
            st.session_state.app_view = "היסטוריית פרויקטים"
            safe_rerun()

        st.markdown("<div class='nav-sep'></div>", unsafe_allow_html=True)

        if st.button("🚪 התנתק"):
            st.session_state.user = None
            supabase.auth.sign_out()
            navigate_to("landing")

    with main_col:
        app_view = st.session_state.app_view

        if app_view == "תכנון CCPM חדש":
            st.header("⚙️ תכנון פרויקט מבוסס שרשרת קריטית (CCPM)")

            with st.form("project_form"):
                c_name, c_tasks, c_due = st.columns(3)

                with c_name:
                    proj_name = st.text_input("שם הפרויקט", value="מודל תכנון 1")

                with c_tasks:
                    num_tasks = st.number_input("מספר משימות", min_value=1, value=5)

                with c_due:
                    due_date = st.number_input("יעד אספקה (ימים)", min_value=1, value=25)

                st.markdown("---")
                st.markdown("**הערכת זמנים (PERT 3-Point):** הזן זמן אופטימי, סביר ופסימי לכל משימה.")

                tasks_input = []

                machine_options = [
                    "ללא מכונה",
                    "מכונת CNC 3 צירים",
                    "אקסטרוזיה",
                    "חיתוך למידה",
                    "בדיקת איכות",
                    "מכונת CNC 5 מכונת",
                    "צביעה",
                    "בקרה סופית CNC"
                ]

                for i in range(int(num_tasks)):
                    c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1, 1, 1, 2, 2])

                    with c1:
                        t_id = st.text_input("מזהה", key=f"id_{i}", placeholder="A").strip()

                    with c2:
                        opt = st.number_input("אופטימי", min_value=0.1, value=1.0, key=f"opt_{i}")

                    with c3:
                        lik = st.number_input("סביר", min_value=0.1, value=2.0, key=f"lik_{i}")

                    with c4:
                        pes = st.number_input("פסימי", min_value=0.1, value=4.0, key=f"pes_{i}")

                    with c5:
                        t_pred_str = st.text_input("קודמות (פסיק)", key=f"pred_{i}")
                        preds = [p.strip() for p in t_pred_str.split(",") if p.strip()]

                    with c6:
                        t_mach = st.selectbox("משאב", machine_options, key=f"mach_{i}")

                    tasks_input.append({
                        "id": t_id,
                        "opt": opt,
                        "lik": lik,
                        "pes": pes,
                        "predecessors": preds,
                        "machine": t_mach
                    })

                submitted = st.form_submit_button("🚀 חשב רשת והקצה חוצצים")

            if submitted:
                results, proj_dur, proj_buffer, safe_dur = calculate_pert_ccpm(tasks_input)
                drum_machine, drum_load = identify_drum(results)

                st.markdown("---")

                c1, c2, c3, c4 = st.columns(4)

                with c1:
                    st.markdown(
                        f"""
                        <div class="kpi-card">
                            <div class="kpi-title">זמן בסיס (תוחלת)</div>
                            <div class="kpi-value">{proj_dur:.1f}</div>
                            <div class="kpi-note">ללא מקדמי ביטחון</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c2:
                    st.markdown(
                        f"""
                        <div class="kpi-card">
                            <div class="kpi-title">חוצץ פרויקט דינמי</div>
                            <div class="kpi-value">+{proj_buffer:.1f}</div>
                            <div class="kpi-note">הגנת שרשרת קריטית</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c3:
                    color = "#10B981" if safe_dur <= due_date else "#EF4444"
                    st.markdown(
                        f"""
                        <div class="kpi-card">
                            <div class="kpi-title">זמן סיום בטוח</div>
                            <div class="kpi-value" style="color:{color}">{safe_dur:.1f}</div>
                            <div class="kpi-note">מול יעד: {due_date}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c4:
                    st.markdown(
                        f"""
                        <div class="kpi-card">
                            <div class="kpi-title">אילוץ (Drum)</div>
                            <div class="kpi-value" style="font-size:24px;">
                                {drum_machine if drum_machine else "אין"}
                            </div>
                            <div class="kpi-note">עומס: {drum_load:.1f} ימים</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("📊 תרשים גאנט - שרשרת קריטית וחוצץ פרויקט")

                fig = go.Figure()

                for r in results:
                    color = "#EF4444" if r["סטטוס"] == "CRITICAL" else "#3B82F6"

                    fig.add_trace(go.Bar(
                        x=[r["TE"]],
                        y=[f"{r['machine']} ➔ {r['id']}"],
                        base=[r["ES"]],
                        orientation="h",
                        marker=dict(color=color, line=dict(color="#0F172A", width=1)),
                        name=f"משימה {r['id']}",
                        hovertemplate=f"תוחלת משך: {r['TE']:.2f}<br>שונות: {r['Var']:.2f}<extra></extra>"
                    ))

                fig.add_trace(go.Bar(
                    x=[proj_buffer],
                    y=["הגנת מועד אספקה ➔ חוצץ פרויקט"],
                    base=[proj_dur],
                    orientation="h",
                    marker=dict(color="#F59E0B", pattern_shape="/"),
                    name="Project Buffer"
                ))

                fig.add_vline(
                    x=due_date,
                    line_width=2,
                    line_dash="dash",
                    line_color="black"
                )

                fig.update_layout(
                    template="plotly_white",
                    barmode="stack",
                    showlegend=False,
                    xaxis_title="ציר זמן מתוקנן",
                    height=400
                )

                st.plotly_chart(fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                try:
                    new_proj = supabase.table("projects").insert({
                        "user_id": st.session_state.user.id,
                        "project_name": proj_name,
                        "target_due_date": due_date
                    }).execute()

                    supabase.table("project_snapshots").insert({
                        "project_id": new_proj.data[0]["id"],
                        "total_days": safe_dur,
                        "critical_tasks_count": sum(1 for r in results if r["סטטוס"] == "CRITICAL"),
                        "bottleneck_machine": drum_machine
                    }).execute()

                except Exception:
                    pass

        elif app_view == "סטטיסטיקה ובקרה (SPC)":
            st.header("📈 בקרת תהליכים סטטיסטית - עומסי משאבים")
            st.write("מודול תומך החלטה המנתח עומסים היסטוריים לזיהוי אנומליות תפעוליות.")

            st.markdown('<div class="card">', unsafe_allow_html=True)

            days = list(range(1, 31))
            loads = [math.sin(d / 3) * 2 + 10 + (d % 3) for d in days]

            mean_load = sum(loads) / len(loads)
            ucl = mean_load + 3 * 1.5
            lcl = mean_load - 3 * 1.5

            fig_spc = go.Figure()

            fig_spc.add_trace(go.Scatter(
                x=days,
                y=loads,
                mode="lines+markers",
                name="עומס יומי",
                marker=dict(color="#0284C7")
            ))

            fig_spc.add_hline(y=mean_load, line_dash="solid", line_color="green", annotation_text="ממוצע (CL)")
            fig_spc.add_hline(y=ucl, line_dash="dash", line_color="red", annotation_text="גבול עליון (UCL)")
            fig_spc.add_hline(y=lcl, line_dash="dash", line_color="red", annotation_text="גבול תחתון (LCL)")

            fig_spc.update_layout(
                title="תרשים בקרת עומס מכונות לחודש האחרון (X-Bar Chart)",
                xaxis_title="יום",
                yaxis_title="שעות עומס",
                template="plotly_white"
            )

            st.plotly_chart(fig_spc, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        elif app_view == "היסטוריית פרויקטים":
            st.header("🗂️ מאגר נתוני פרויקטים (Enterprise DB)")

            try:
                response = supabase.table("projects") \
                    .select("*, project_snapshots(*)") \
                    .eq("user_id", st.session_state.user.id) \
                    .order("created_at", desc=True) \
                    .execute()

                if not response.data:
                    st.info("אין נתונים היסטוריים.")

                for proj in response.data:
                    with st.expander(f"📁 {proj['project_name']} | יעד מקורי: {proj['target_due_date']}"):
                        if proj.get("project_snapshots"):
                            s = proj["project_snapshots"][0]

                            c1, c2 = st.columns(2)

                            c1.metric("זמן בטוח מחושב", f"{s['total_days']:.1f}")
                            c2.metric("אילוץ אסטרטגי (Drum)", s["bottleneck_machine"])

            except Exception:
                st.error("שגיאה בתקשורת מול מסד הנתונים.")

else:
    navigate_to("landing")
