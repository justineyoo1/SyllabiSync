from __future__ import annotations

import io
import os
from typing import Any, Dict, List

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


st.set_page_config(page_title="SyllabusSync", layout="wide")
st.title("SyllabusSync")


def list_documents() -> List[Dict[str, Any]]:
    try:
        resp = requests.get(f"{API_BASE_URL}/documents", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def list_versions(doc_id: int) -> List[Dict[str, Any]]:
    try:
        resp = requests.get(f"{API_BASE_URL}/documents/{doc_id}/versions", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def upload_and_notify(file_name: str, content_type: str, data: bytes) -> Dict[str, Any] | None:
    try:
        pre = requests.post(
            f"{API_BASE_URL}/files/presign",
            json={"filename": file_name, "content_type": content_type},
            timeout=30,
        )
        pre.raise_for_status()
        prej = pre.json()

        # Upload to MinIO via presigned POST
        url = prej["url"]
        fields = prej["fields"]
        files = {"file": (file_name, io.BytesIO(data), content_type)}
        r = requests.post(url, data=fields, files=files, timeout=60)
        r.raise_for_status()

        # Notify API
        notify = requests.post(
            f"{API_BASE_URL}/files/notify",
            json={"title": file_name, "storage_uri": prej["storage_uri"]},
            timeout=30,
        )
        notify.raise_for_status()
        return notify.json()
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None


tab1, tab2, tab3 = st.tabs(["Upload", "Chat", "Calendar"])

with tab1:
    st.subheader("Upload Syllabi (batch supported)")
    files = st.file_uploader("Choose PDF files", type=["pdf"], accept_multiple_files=True)
    if st.button("Upload & Index", disabled=(not files)):
        statuses: list[str] = []
        for f in files or []:
            info = upload_and_notify(f.name, f.type or "application/pdf", f.read())
            if info:
                statuses.append(
                    f"✅ {f.name}: document_id={info['document_id']} version_id={info['document_version_id']}"
                )
                st.session_state["selected_version_id"] = info["document_version_id"]
            else:
                statuses.append(f"❌ {f.name}: failed")
        st.write("\n".join(statuses))

with tab2:
    st.subheader("Chat")
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []  # list of dicts {role, content}
    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    user_input = st.chat_input("Ask about your syllabi…")
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        try:
            resp = requests.post(
                f"{API_BASE_URL}/qa/chat",
                json={"messages": st.session_state.chat_messages[-6:], "scope": "all", "k": 5},
                timeout=45,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "")
            st.session_state.chat_messages.append({"role": "assistant", "content": answer})
            with st.chat_message("assistant"):
                st.markdown(answer)
                cits = data.get("citations", [])
                if cits:
                    with st.expander("Citations"):
                        for c in cits:
                            st.caption(f"doc {c['document_id']} p.{c['page']}")
                            st.write(c["snippet"]) 
        except Exception as e:
            st.error(f"Chat failed: {e}")

with tab3:
    st.subheader("Calendar Export (ICS)")
    docs = list_documents()
    doc_map = {f"{d['id']}: {d['title']}": d["id"] for d in docs}
    doc_label = st.selectbox("Document", list(doc_map.keys()), key="cal_doc") if doc_map else None
    versions = list_versions(doc_map[doc_label]) if doc_label else []
    ver_map = {f"v{v['id']} ({v['pages']} pages)": v["id"] for v in versions}
    ver_label = st.selectbox("Version", list(ver_map.keys()), key="cal_ver") if ver_map else None
    if ver_label:
        ver_id = ver_map[ver_label]
        try:
            ics_resp = requests.get(f"{API_BASE_URL}/calendar/ics", params={"document_version_id": ver_id}, timeout=30)
            ics_resp.raise_for_status()
            st.download_button(
                label="Download .ics",
                data=ics_resp.content,
                file_name="syllabus.ics",
                mime="text/calendar",
            )
        except Exception as e:
            st.error(f"ICS fetch failed: {e}")


