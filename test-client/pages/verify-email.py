import streamlit as st
import requests

API_BASE = "http://localhost:8000"

# Inherit shared http_session if available, otherwise create a local one
if "http_session" not in st.session_state:
    st.session_state["http_session"] = requests.Session()

session: requests.Session = st.session_state["http_session"]


def show_response(resp: requests.Response):
    with st.expander("Response details"):
        st.write(f"**Status:** {resp.status_code}")
        try:
            st.json(resp.json())
        except Exception:
            st.text(resp.text)


st.title("Verify Email")

code_from_url = st.query_params.get("code", "")
token_from_url = st.query_params.get("token", "")

if code_from_url:
    # Opaque code from email link — auto-verify via GET endpoint
    st.info("Verification code loaded from email link. Verifying...")

    if "email_verified" not in st.session_state:
        resp = session.get(
            f"{API_BASE}/api/auth/verify-email",
            params={"code": code_from_url},
        )
        st.session_state["email_verified"] = resp.status_code == 200
        st.session_state["verify_resp_status"] = resp.status_code
        try:
            st.session_state["verify_resp_json"] = resp.json()
        except Exception:
            st.session_state["verify_resp_json"] = {"text": resp.text}

    if st.session_state.get("email_verified"):
        st.success("Email verified! You can now log in.")
        st.query_params.clear()
    else:
        detail = st.session_state.get("verify_resp_json", {}).get("detail", "Unknown error")
        st.error(f"Verification failed: {detail}")

    with st.expander("Response details"):
        st.write(f"**Status:** {st.session_state.get('verify_resp_status')}")
        st.json(st.session_state.get("verify_resp_json", {}))

elif token_from_url:
    # Legacy JWT token from email link — auto-verify via POST endpoint
    st.info("Verification token loaded from email link. Verifying...")

    if "email_verified" not in st.session_state:
        resp = session.post(
            f"{API_BASE}/api/auth/verify-email",
            json={"token": token_from_url},
        )
        st.session_state["email_verified"] = resp.status_code == 200
        st.session_state["verify_resp_status"] = resp.status_code
        try:
            st.session_state["verify_resp_json"] = resp.json()
        except Exception:
            st.session_state["verify_resp_json"] = {"text": resp.text}

    if st.session_state.get("email_verified"):
        st.success("Email verified! You can now log in.")
        st.query_params.clear()
    else:
        detail = st.session_state.get("verify_resp_json", {}).get("detail", "Unknown error")
        st.error(f"Verification failed: {detail}")

    with st.expander("Response details"):
        st.write(f"**Status:** {st.session_state.get('verify_resp_status')}")
        st.json(st.session_state.get("verify_resp_json", {}))

else:
    # No code/token in URL — manual fallback
    st.write("Paste a verification code or token from your email below.")
    method = st.radio("Verification method", ["Code (from email link)", "Token (legacy JWT)"], horizontal=True)

    if method == "Code (from email link)":
        code = st.text_input("Verification Code", help="The code parameter from your email link URL")
        if st.button("Verify Email", type="primary"):
            if not code:
                st.error("Code is required.")
            else:
                resp = session.get(
                    f"{API_BASE}/api/auth/verify-email",
                    params={"code": code},
                )
                if resp.status_code == 200:
                    st.success("Email verified! You can now log in.")
                else:
                    detail = resp.json().get("detail", "Unknown error")
                    st.error(f"Verification failed: {detail}")
                show_response(resp)
    else:
        token = st.text_input("Verification Token", help="A JWT token")
        if st.button("Verify Email", type="primary"):
            if not token:
                st.error("Token is required.")
            else:
                resp = session.post(
                    f"{API_BASE}/api/auth/verify-email",
                    json={"token": token},
                )
                if resp.status_code == 200:
                    st.success("Email verified! You can now log in.")
                else:
                    detail = resp.json().get("detail", "Unknown error")
                    st.error(f"Verification failed: {detail}")
                show_response(resp)
