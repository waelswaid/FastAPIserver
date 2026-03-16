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


st.title("Reset Password")

# Read code/token from URL query params (set when user clicks the email link)
code_from_url = st.query_params.get("code", "")
token_from_url = st.query_params.get("token", "")

if code_from_url:
    st.info("Reset code loaded from email link.")
elif token_from_url:
    st.info("Reset token loaded from email link.")

method = st.radio("Reset method", ["Code (from email link)", "Token (legacy JWT)"], horizontal=True)

if method == "Code (from email link)":
    code = st.text_input("Reset Code", value=code_from_url, help="The code parameter from your email link URL, or paste manually.")
    new_password = st.text_input("New Password", type="password", help="Min 8, max 128 characters", key="pw_code")

    if st.button("Reset Password", type="primary", key="btn_code"):
        if not code or not new_password:
            st.error("Both fields are required.")
        elif len(new_password) < 8:
            st.error("Password must be at least 8 characters.")
        elif len(new_password) > 128:
            st.error("Password must be at most 128 characters.")
        else:
            resp = session.post(
                f"{API_BASE}/api/auth/reset-password",
                json={"code": code, "new_password": new_password},
            )
            if resp.status_code == 200:
                st.success("Password reset successfully. You can now log in with your new password.")
                st.query_params.clear()
            else:
                detail = resp.json().get("detail", "Unknown error")
                st.error(f"Error: {detail}")
            show_response(resp)
else:
    token = st.text_input("Reset Token", value=token_from_url, help="A JWT token, or paste manually.")
    new_password = st.text_input("New Password", type="password", help="Min 8, max 128 characters", key="pw_token")

    if st.button("Reset Password", type="primary", key="btn_token"):
        if not token or not new_password:
            st.error("Both fields are required.")
        elif len(new_password) < 8:
            st.error("Password must be at least 8 characters.")
        elif len(new_password) > 128:
            st.error("Password must be at most 128 characters.")
        else:
            resp = session.post(
                f"{API_BASE}/api/auth/reset-password",
                json={"token": token, "new_password": new_password},
            )
            if resp.status_code == 200:
                st.success("Password reset successfully. You can now log in with your new password.")
                st.query_params.clear()
            else:
                detail = resp.json().get("detail", "Unknown error")
                st.error(f"Error: {detail}")
            show_response(resp)
