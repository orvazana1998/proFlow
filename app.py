import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math
from supabase import create_client, Client

st.set_page_config(page_title="ProFlow Enterprise", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
[data-testid="stSidebarNav"] {display: none !important;}
[data-testid="collapsedControl"] {display: none !important;}

.stApp {
    background-color: #F8FAFC;
    color: #0F172A;
    direction: rtl;
    font-family: 'Segoe UI', sans-serif;
}

section[data-testid="stSidebar"] {
    background: #0F172A !important;
    min-width: 280px !important;
    max-width: 280px !important;
}

section[data-testid="stSidebar"] * {
    color: white;
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
    border-radius: 10px !important;
    border: none !important;
    font-weight: 700 !important;
    width: 100% !important;
    height: 46px !important;
    margin-bottom: 8px !important;
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

.sidebar-title {
    color: white;
    font-size: 25px;
    font-weight: 800;
    text-align: center;
    margin-top: 10px;
}

.sidebar-subtitle {
    color: #CBD5E1;
    font-size: 13px;
    text-align: center;
    margin-bottom: 25px;
}

.sidebar-sep {
    border-top: 1px solid #334155;
    margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)

SUPABASE_URL = "https://mtfhapzuvckucyuqtuju.supabase.co"
SUPABASE_KEY = "sb_publishable_XjpjwBN1gqk1s6LC1he2HQ_S3l_F9vU"

def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_connection()

if "page" not in st.session_state:
    st.session_state.page = "landing"
if "user" not in st.session_state:
    st.session_state.user = None
if "app_view" not in st.session_state:
    st.session_state.app_view = "תכנון CCPM חדש"
if "last_results" not in st.session_state:
    st.session_state.last_results = None

def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def navigate_to(page_name):
    st.session_state.page = page_name
    safe_rerun()

def calculate_pert_ccpm(tasks):
    task_dict = {t["id"]: t.copy() for t in tasks if t["id"]}

    for task in task_dict.values():
        o, m, p = task["opt"], task["lik"], task["pes"]
        te = (o + 4 * m + p) / 6
        var = ((p - o) / 6) ** 2
        task.update({
            "TE": te, "Var": var, "ES": 0, "EF": 0,
            "LS": 0, "LF": 0, "Slack": 0, "סטטוס": "NORMAL"
        })

    changed = True
    while changed:
        changed = False
        for task in task_dict.values():
            es = 0
            if task["predecessors"]:
                vals = [task_dict[p]["EF"] for p in task["predecessors"] if p in task_dict]
                if vals:
                    es = max(vals)

            ef = es + task["TE"]

            if abs(task["ES"] - es) > 0.001 or abs(task["EF"] - ef) > 0.001:
                task["ES"], task["EF"] = es, ef
                changed = True

    project_duration = max([t["EF"] for t in task_dict.values()]) if task_dict else 0

    for task in task_dict.values():
        task["LF"] = project_duration
        task["LS"] = project_duration - task["TE"]

    changed = True
    while changed:
        changed = False
        for t_id, task in task_dict.items():
            successors = [t for t in task_dict.values() if t_id in t["predecessors"]]

            if successors:
                lf = min([s["LS"] for s in successors])
                ls = lf - task["TE"]

                if abs(task["LF"] - lf) > 0.001 or abs(task["LS"] - ls) > 0.001:
                    task["LF"], task["LS"] = lf, ls
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

def identify_drum(results):
    loads = {}

    for r in results:
        if r["machine"] != "ללא מכונה":
            loads[r["machine"]] = loads.get(r["machine"], 0) + r["TE"]

    if not loads:
        return None, 0

    drum = max(loads, key=loads.get)
    return drum, loads[drum]

if st.session_state.page == "landing":
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
        <div class="card" style="text-align:center; border-top:4px solid #0284C7;">
            <h1 style="font-size:42px;">מערכת תכנון אופטימלית - Enterprise</h1>
            <h3 style="color:#475569 !important; font-weight:400;">
                יישום CCPM, תורת האילוצים וניהול עומסי מסד הנתונים בחברה.
            </h3>
        </div>
        """, unsafe_allow_html=True)

        if st.button("כניסה למערכת ➔"):
            navigate_to("auth")

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
                except Exception as e:
                    st.error("שגיאה בהתחברות.")
                    st.code(str(e))

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
                        try:
                            supabase.table("profiles").update({
                                "full_name": reg_name
                            }).eq("id", res.user.id).execute()
                        except Exception:
                            pass

                    st.success("נרשמת! עבור להתחברות.")

                except Exception as e:
                    st.error("שגיאה בהרשמה.")
                    st.code(str(e))

        if st.button("← חזרה"):
            navigate_to("landing")

        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == "app" and st.session_state.user is not None:

    with st.sidebar:
        st.markdown("""
        <div class="sidebar-title">⚙️ ProFlow</div>
        <div class="sidebar-subtitle">Enterprise Dashboard</div>
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

        st.markdown('<div class="sidebar-sep"></div>', unsafe_allow_html=True)

        if st.button("🚪 התנתק"):
            st.session_state.user = None
            st.session_state.last_results = None
            supabase.auth.sign_out()
            navigate_to("landing")

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
            st.markdown("**הערכת זמנים PERT:** הזן זמן אופטימי, סביר ופסימי לכל משימה.")

            tasks_input = []
            machine_options = [
                "ללא מכונה",
                "מכונת CNC 3 צירים",
                "אקסטרוזיה",
                "חיתוך למידה",
                "בדיקת איכות",
                "מכונת CNC 5 צירים",
                "צביעה",
                "בקרה סופית"
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
                    pred_text = st.text_input("קודמות (פסיק)", key=f"pred_{i}")
                    preds = [p.strip() for p in pred_text.split(",") if p.strip()]

                with c6:
                    mach = st.selectbox("משאב", machine_options, key=f"mach_{i}")

                tasks_input.append({
                    "id": t_id,
                    "opt": opt,
                    "lik": lik,
                    "pes": pes,
                    "predecessors": preds,
                    "machine": mach
                })

            submitted = st.form_submit_button("🚀 חשב רשת והקצה חוצצים")

        if submitted:
            if not any(t["id"] for t in tasks_input):
                st.error("יש להזין לפחות מזהה משימה אחד, למשל A.")
            else:
                results, proj_dur, proj_buffer, safe_dur = calculate_pert_ccpm(tasks_input)
                drum_machine, drum_load = identify_drum(results)

                st.session_state.last_results = {
                    "results": results,
                    "proj_dur": proj_dur,
                    "proj_buffer": proj_buffer,
                    "safe_dur": safe_dur,
                    "drum_machine": drum_machine,
                    "drum_load": drum_load,
                    "due_date": due_date,
                    "proj_name": proj_name
                }

                try:
                    new_proj = supabase.table("projects").insert({
                        "user_id": st.session_state.user.id,
                        "project_name": proj_name,
                        "target_due_date": int(due_date)
                    }).execute()

                    project_id = new_proj.data[0]["id"]

                    supabase.table("project_snapshots").insert({
                        "project_id": project_id,
                        "total_days": int(round(safe_dur)),
                        "critical_tasks_count": int(sum(1 for r in results if r["סטטוס"] == "CRITICAL")),
                        "bottleneck_machine": drum_machine
                    }).execute()

                    st.success("הפרויקט נשמר בהצלחה.")

                except Exception as e:
                    st.warning("החישוב הצליח, אבל הייתה בעיה בשמירה למסד הנתונים.")
                    st.code(str(e))

        if st.session_state.last_results:
            data = st.session_state.last_results
            results = data["results"]
            proj_dur = data["proj_dur"]
            proj_buffer = data["proj_buffer"]
            safe_dur = data["safe_dur"]
            drum_machine = data["drum_machine"]
            drum_load = data["drum_load"]
            due_date = data["due_date"]

            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">זמן בסיס</div>
                    <div class="kpi-value">{proj_dur:.1f}</div>
                    <div class="kpi-note">ללא מקדמי ביטחון</div>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">חוצץ פרויקט</div>
                    <div class="kpi-value">+{proj_buffer:.1f}</div>
                    <div class="kpi-note">הגנת שרשרת קריטית</div>
                </div>
                """, unsafe_allow_html=True)

            with c3:
                color = "#10B981" if safe_dur <= due_date else "#EF4444"
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">זמן סיום בטוח</div>
                    <div class="kpi-value" style="color:{color};">{safe_dur:.1f}</div>
                    <div class="kpi-note">מול יעד: {due_date}</div>
                </div>
                """, unsafe_allow_html=True)

            with c4:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">אילוץ Drum</div>
                    <div class="kpi-value" style="font-size:24px;">{drum_machine if drum_machine else "אין"}</div>
                    <div class="kpi-note">עומס: {drum_load:.1f} ימים</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📊 תרשים גאנט - שרשרת קריטית וחוצץ פרויקט")

            fig = go.Figure()

            for r in results:
                bar_color = "#EF4444" if r["סטטוס"] == "CRITICAL" else "#3B82F6"

                fig.add_trace(go.Bar(
                    x=[r["TE"]],
                    y=[f"{r['machine']} ➔ {r['id']}"],
                    base=[r["ES"]],
                    orientation="h",
                    marker=dict(color=bar_color, line=dict(color="#0F172A", width=1)),
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

            fig.add_vline(x=due_date, line_width=2, line_dash="dash", line_color="black")

            fig.update_layout(
                template="plotly_white",
                barmode="stack",
                showlegend=False,
                xaxis_title="ציר זמן מתוקנן",
                height=430
            )

            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📋 טבלת תוצאות")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    elif app_view == "סטטיסטיקה ובקרה (SPC)":
        st.header("📈 בקרת תהליכים סטטיסטית - עומסי משאבים")
        st.write("מודול תומך החלטה המנתח עומסים היסטוריים לזיהוי אנומליות תפעוליות.")

        days = list(range(1, 31))
        loads = [math.sin(d / 3) * 2 + 10 + (d % 3) for d in days]

        mean_load = sum(loads) / len(loads)
        ucl = mean_load + 3 * 1.5
        lcl = mean_load - 3 * 1.5

        fig_spc = go.Figure()
        fig_spc.add_trace(go.Scatter(x=days, y=loads, mode="lines+markers", name="עומס יומי"))
        fig_spc.add_hline(y=mean_load, line_dash="solid", line_color="green", annotation_text="ממוצע")
        fig_spc.add_hline(y=ucl, line_dash="dash", line_color="red", annotation_text="UCL")
        fig_spc.add_hline(y=lcl, line_dash="dash", line_color="red", annotation_text="LCL")

        fig_spc.update_layout(
            title="תרשים בקרת עומס מכונות לחודש האחרון",
            xaxis_title="יום",
            yaxis_title="שעות עומס",
            template="plotly_white"
        )

        st.plotly_chart(fig_spc, use_container_width=True)

    elif app_view == "היסטוריית פרויקטים":
        st.header("🗂️ מאגר נתוני פרויקטים")

        try:
            response = (
                supabase.table("project_snapshots")
                .select("id, project_id, total_days, critical_tasks_count, bottleneck_machine, created_at, projects(id, project_name, target_due_date, user_id)")
                .order("created_at", desc=True)
                .execute()
            )

            rows = []

            for snap in response.data or []:
                project_data = snap.get("projects")
                
                # טיפול במבנה הנתונים החוזר מ-Supabase (רשימה או מילון)
                if isinstance(project_data, list) and len(project_data) > 0:
                    project = project_data[0]
                elif isinstance(project_data, dict):
                    project = project_data
                else:
                    project = {}

                # בדיקה האם הפרויקט שייך למשתמש הנוכחי
                if project.get("user_id") == st.session_state.user.id:
                    
                    # ניקוי פורמט התאריך לתצוגה חלקה
                    created_at = snap.get("created_at", "")
                    if created_at:
                        created_at = created_at.split("T")[0]

                    rows.append({
                        "שם פרויקט": project.get("project_name", "ללא שם"),
                        "יעד אספקה": project.get("target_due_date", ""),
                        "זמן בטוח": snap.get("total_days", ""),
                        "משימות קריטיות": snap.get("critical_tasks_count", ""),
                        "אילוץ": snap.get("bottleneck_machine", "") or "אין",
                        "תאריך יצירה": created_at,
                        "מזהה פרויקט": snap.get("project_id", "")
                    })

            if not rows:
                st.info("אין נתונים היסטוריים למשתמש הזה.")
            else:
                df = pd.DataFrame(rows)
                st.success(f"נמצאו {len(df)} רשומות")
                st.dataframe(df, use_container_width=True)

                for i, row in enumerate(rows, start=1):
                    with st.expander(f"📁 {row['שם פרויקט']}"):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("זמן בטוח", row["זמן בטוח"])
                        c2.metric("משימות קריטיות", row["משימות קריטיות"])
                        c3.metric("אילוץ", row["אילוץ"])
                        st.caption(f"יעד אספקה: {row['יעד אספקה']}")
                        st.caption(f"תאריך יצירה: {row['תאריך יצירה']}")

        except Exception as e:
            st.error("שגיאה בקריאת היסטוריית הפרויקטים")
            st.code(str(e))

else:
    navigate_to("landing")
