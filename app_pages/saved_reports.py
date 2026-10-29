"""
saved_reports.py
----------------
Lists every report stored in the project's reports/ folder (generated
automatically by the Dashboard, or added manually here), with download
and delete options.
"""

import pandas as pd
import streamlit as st

from utils.report_store import list_reports, save_uploaded_file, delete_report


def render_saved_reports():
    try:
        st.title("Saved Reports")
        st.caption("Reports are saved automatically in the project's `reports/` folder "
                   "whenever a PDF is generated on the Dashboard or a batch summary is shown.")

        # ---- Add older reports ----
        with st.expander("Add previously downloaded reports (PDF / CSV)"):
            files = st.file_uploader("Choose report files", type=["pdf", "csv"],
                                     accept_multiple_files=True, key="saved_reports_uploader")
            if files and st.button("Save to reports folder", type="primary"):
                ok = sum(save_uploaded_file(f.name, f.getvalue()) for f in files)
                st.success(f"Saved {ok} of {len(files)} file(s).")
                if ok < len(files):
                    st.warning("Some files could not be saved (only PDF/CSV are accepted).")
                st.rerun() if ok else None

        reports = list_reports()
        if not reports:
            st.info("No saved reports yet. Generate a Digital Twin and open the Dashboard "
                    "to create the first one, or add older reports above.")
            return

        st.markdown(f"**{len(reports)} saved report(s)**")
        st.dataframe(pd.DataFrame([{"File": r["name"], "Type": r["type"], "Size (KB)": r["size_kb"],
                                    "Saved": r["modified"].strftime("%Y-%m-%d %H:%M")} for r in reports]),
                     use_container_width=True, hide_index=True)

        st.markdown("---")
        selected = st.selectbox("Select a report", [r["name"] for r in reports])
        item = next(r for r in reports if r["name"] == selected)
        with open(item["path"], "rb") as f:
            data = f.read()
        c1, c2, _ = st.columns([1, 1, 3])
        with c1:
            st.download_button("Download", data=data, file_name=item["name"],
                               mime="application/pdf" if item["type"] == "PDF" else "text/csv",
                               key=f"dl_saved_{item['name']}")
        with c2:
            if st.button("Delete", key=f"del_saved_{item['name']}"):
                if delete_report(item["name"]):
                    st.rerun()
                st.error("Could not delete this file.")
        if item["type"] == "CSV":
            try:
                st.dataframe(pd.read_csv(item["path"]).head(50), use_container_width=True)
            except Exception:
                pass
    except Exception as e:
        st.error(f"Error displaying saved reports: {e}")
