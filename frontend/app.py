import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
from pathlib import Path

API_BASE = os.getenv("ANALISDAT_API_URL", "http://localhost:8000/api/v1")

st.set_page_config(page_title="analisDAT", layout="wide", page_icon="📊")
st.title("📊 analisDAT")
st.caption("Your AI-Powered Data Analyst Assistant — Backend Tester")

# ─── Session State ───
for k in ["dataset_id", "datasets", "chat_messages"]:
    if k not in st.session_state:
        st.session_state[k] = None if k != "chat_messages" else []


def api(method, path, **kwargs):
    url = f"{API_BASE}{path}"
    try:
        r = requests.request(method, url, timeout=120, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot connect to {API_BASE}")
        return None
    except requests.HTTPError as e:
        try:
            detail = r.json()
            msg = detail.get("error") or detail.get("detail") or str(e)
            st.error(f"⚠️ {msg}")
        except Exception:
            st.error(f"⚠️ {e}")
        return None
    except Exception as e:
        st.error(f"⚠️ {e}")
        return None


def build_plotly(v: dict) -> go.Figure:
    fig = go.Figure()
    chart_type = v.get("chart_type", "scatter")
    layout_config = v.get("layout", {})

    for trace_data in v.get("data", []):
        trace_type = trace_data.pop("type", chart_type)

        if trace_type == "scatter":
            mode = trace_data.pop("mode", "markers")
            fig.add_trace(go.Scatter(mode=mode, **trace_data))
        elif trace_type == "bar":
            fig.add_trace(go.Bar(**trace_data))
        elif trace_type == "histogram":
            fig.add_trace(go.Histogram(**trace_data))
        elif trace_type == "box":
            fig.add_trace(go.Box(**trace_data))
        elif trace_type == "heatmap":
            fig.add_trace(go.Heatmap(**trace_data))
        elif trace_type == "line":
            mode = trace_data.pop("mode", "lines")
            fig.add_trace(go.Scatter(mode=mode, **trace_data))
        else:
            fig.add_trace(go.Scatter(**trace_data))

    title = v.get("title", "")
    x_title = v.get("x_axis", "")
    y_title = v.get("y_axis", "")

    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        height=400,
        margin=dict(l=40, r=20, t=40, b=40),
        **layout_config,
    )
    return fig


# ─── Sidebar ───
with st.sidebar:
    st.subheader("API Configuration")
    api_url = st.text_input("API Base URL", value=API_BASE)
    os.environ["ANALISDAT_API_URL"] = api_url

    st.divider()
    st.subheader("Datasets")

    if st.button("🔄 Refresh List", use_container_width=True):
        st.session_state.datasets = api("GET", "/datasets") or []

    datasets = st.session_state.datasets
    if datasets:
        opts = {d["id"]: f"#{d['id']} — {d['original_filename']} ({d['rows']} rows)" for d in datasets}
        selected = st.selectbox("Active Dataset", opts, index=0, format_func=lambda x: opts.get(x, ""))
        if selected != st.session_state.dataset_id:
            st.session_state.dataset_id = selected
            st.session_state.chat_messages = []
            st.rerun()

        with st.expander("Dataset Info", expanded=True):
            d = next((d for d in datasets if d["id"] == selected), None)
            if d:
                cols = st.columns(2)
                cols[0].metric("Rows", d["rows"])
                cols[1].metric("Columns", d["columns"])
                qs = d.get("quality_score")
                qc = d.get("quality_category")
                if qs is not None and qc:
                    st.metric("Quality", f"{qs}/100 — {qc}")
                else:
                    st.caption("Processing... refresh to see results")
    else:
        st.info("No datasets yet. Upload one below.")

api_paths = {
    "📋 Data Profiling": "profile",
    "✅ Data Quality": "quality",
    "🧹 Cleaning Recs": "cleaning-recommendations",
    "📈 Statistics": "statistics",
    "🎨 Visualizations": "visualizations",
    "💡 Insights": "insights",
}

tab_names = ["📤 Upload", "🔍 Analysis", "💬 Chat"]
tab1, tab2, tab3 = st.tabs(tab_names)

# ═══════════════════════════════════════════
# TAB 1 — UPLOAD
# ═══════════════════════════════════════════
with tab1:
    st.subheader("Upload Dataset")
    uploaded_file = st.file_uploader("Choose a CSV or XLSX file", type=["csv", "xlsx"])

    if uploaded_file and st.button("🚀 Upload", type="primary", use_container_width=True):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/octet-stream")}
        with st.spinner("Uploading and processing..."):
            res = api("POST", "/datasets/upload", files=files)
        if res:
            st.success(f"✅ Uploaded **{res['original_filename']}** — ID: `{res['id']}`")
            st.session_state.dataset_id = res["id"]
            st.session_state.datasets = api("GET", "/datasets") or []
            st.rerun()

    st.divider()
    st.subheader("Upload History")
    if st.session_state.datasets:
        df = pd.DataFrame(st.session_state.datasets)
        cols = ["id", "original_filename", "rows", "columns", "file_type", "created_at"]
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("No datasets uploaded yet")

# ═══════════════════════════════════════════
# TAB 2 — ANALYSIS
# ═══════════════════════════════════════════
with tab2:
    did = st.session_state.dataset_id
    if not did:
        st.info("👈 Select a dataset from the sidebar first")
    else:
        st.subheader(f"Analysis for Dataset #{did}")

        cols = st.columns(len(api_paths))
        for i, (label, path) in enumerate(api_paths.items()):
            with cols[i]:
                if st.button(label, use_container_width=True):
                    with st.spinner(f"Loading {label}..."):
                        res = api("GET", f"/analysis/{did}/{path}")
                    st.session_state[f"result_{path}"] = res

        st.divider()

        for label, path in api_paths.items():
            key = f"result_{path}"
            if key not in st.session_state or st.session_state[key] is None:
                continue
            data = st.session_state[key]

            with st.expander(f"{label}", expanded=True):
                if path == "profile":
                    mcols = st.columns(4)
                    mcols[0].metric("Rows", data.get("row_count", 0))
                    mcols[1].metric("Columns", data.get("column_count", 0))
                    mcols[2].metric("Numeric", data.get("numeric_columns", 0))
                    mcols[3].metric("Categorical", data.get("categorical_columns", 0))
                    mcols2 = st.columns(3)
                    mcols2[0].metric("Datetime", data.get("datetime_columns", 0))
                    mcols2[1].metric("Boolean", data.get("boolean_columns", 0))
                    mcols2[2].metric("Duplicates", data.get("duplicate_rows", 0))
                    cols_info = data.get("column_profiles", [])
                    if cols_info:
                        df = pd.DataFrame(cols_info)
                        if "sample_values" in df.columns:
                            df["sample_values"] = df["sample_values"].apply(lambda x: ", ".join(str(v) for v in (x or [])))
                        st.dataframe(df, use_container_width=True, hide_index=True)

                elif path == "quality":
                    sc = data.get("overall_score", 0)
                    cat = data.get("quality_category", "")
                    color = "#22c55e" if sc >= 80 else "#f59e0b" if sc >= 70 else "#ef4444"
                    st.markdown(f"<h1 style='color:{color}; text-align:center'>{sc}/100 — {cat}</h1>", unsafe_allow_html=True)
                    df_checks = pd.DataFrame(data.get("checks", []))
                    if not df_checks.empty:
                        df_checks["passed"] = df_checks["passed"].map({True: "✅", False: "❌"})
                        st.dataframe(df_checks[["check_name", "score", "max_score", "passed"]], use_container_width=True, hide_index=True)

                elif path == "cleaning-recommendations":
                    issues = data.get("detected_issues", [])
                    recs = data.get("recommendations", [])
                    if issues:
                        st.warning(f"{len(issues)} issue(s) detected")
                        st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)
                    else:
                        st.success("No issues found!")
                    if recs:
                        st.subheader("Recommendations")
                        st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

                elif path == "statistics":
                    if "_errors" in data:
                        for err in data["_errors"]:
                            st.error(f"⚠️ {err}")
                    corr = data.get("correlations", [])
                    if corr:
                        st.subheader("Correlations")
                        st.dataframe(pd.DataFrame(corr[:15])[["column_x", "column_y", "correlation", "p_value", "strength"]], use_container_width=True, hide_index=True)
                    sm = data.get("summary_stats", {})
                    if sm:
                        st.subheader("Summary Statistics")
                        st.dataframe(pd.DataFrame(sm).T, use_container_width=True)

                elif path == "visualizations":
                    viz_list = data.get("visualizations", [])
                    st.info(data.get("summary", ""))
                    for vi, v in enumerate(viz_list):
                        st.markdown(f"**{v['title']}** `({v['chart_type']})`")
                        try:
                            fig = build_plotly(v)
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Render failed: {e}")
                            st.json(v, expanded=False)

                elif path == "insights":
                    ranked = data.get("insights", [])
                    if not ranked:
                        st.info("No insights discovered")
                    else:
                        for ins in ranked[:10]:
                            score = ins.get("score", 0)
                            icon = "🔴" if score < 50 else "🟡" if score < 70 else "🟢"
                            st.markdown(f"{icon} **{ins['title']}** — Score: `{score:.0f}`")
                            st.caption(ins["description"])
                            st.json(ins["supporting_data"], expanded=False)

            st.divider()

# ═══════════════════════════════════════════
# TAB 3 — CHAT
# ═══════════════════════════════════════════
with tab3:
    did = st.session_state.dataset_id
    if not did:
        st.info("👈 Select a dataset from the sidebar first")
    else:
        st.subheader(f"Chat With Dataset #{did}")

        sessions = api("GET", f"/chat/{did}/sessions")
        session_opts = {}
        if sessions:
            session_opts = {s["id"]: s.get("session_name", f"Session {s['id']}") for s in sessions}

        col1, col2 = st.columns([3, 1])
        with col2:
            sel_session = st.selectbox(
                "Session",
                ["New"] + list(session_opts.keys()),
                format_func=lambda x: "🆕 New Session" if x == "New" else session_opts.get(x, f"Session {x}"),
                key="chat_session_sel",
            )

        for m in st.session_state.chat_messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])

        with col1:
            msg = st.chat_input("Ask something about your data...")
            if msg:
                body = {"message": msg, "session_id": None if sel_session == "New" else sel_session}
                st.session_state.chat_messages.append({"role": "user", "content": msg})
                with st.chat_message("user"):
                    st.write(msg)
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        res = api("POST", f"/chat/{did}/chat", json=body)
                    if res:
                        reply = res.get("content", "No response")
                        st.write(reply)
                        if res.get("supporting_stats"):
                            with st.expander("📊 Statistics"):
                                st.json(res["supporting_stats"])
                        if res.get("visualization_data"):
                            with st.expander("📈 Visualization"):
                                st.json(res["visualization_data"])
                        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                    else:
                        st.error("Failed to get response")

        if session_opts:
            st.divider()
            with st.expander("📜 Session History"):
                view_id = st.selectbox("Load Session", list(session_opts.keys()), format_func=lambda x: session_opts[x], key="load_session")
                if st.button("Load Messages"):
                    sess = api("GET", f"/chat/sessions/{view_id}")
                    if sess:
                        st.session_state.chat_messages = [
                            {"role": m["role"], "content": m["content"]}
                            for m in sess.get("messages", [])
                        ]
                        st.rerun()
