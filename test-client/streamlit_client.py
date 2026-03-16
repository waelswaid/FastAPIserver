import streamlit as st
import requests

API_BASE = "http://localhost:8000"

# --- Session state init ---
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None
if "http_session" not in st.session_state:
    st.session_state["http_session"] = requests.Session()

session: requests.Session = st.session_state["http_session"]


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state['access_token']}"}


def show_response(resp: requests.Response):
    with st.expander("Response details"):
        st.write(f"**Status:** {resp.status_code}")
        try:
            st.json(resp.json())
        except Exception:
            st.text(resp.text)


# --- Sidebar ---
st.sidebar.title("FastAPI Test Client")

if st.session_state["access_token"] and st.session_state["user_info"]:
    st.sidebar.success(f"Logged in as **{st.session_state['user_info']['name']}**")
else:
    st.sidebar.info("Not logged in")

pages = ["Register", "Login", "My Profile", "Forgot Password", "Resend Verification", "Refresh Token"]
page = st.sidebar.radio("Navigate", pages)

# --- Register ---
if page == "Register":
    st.header("Register")
    name = st.text_input("Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password", help="Min 8, max 128 characters")

    if st.button("Create Account"):
        if not name or not email or not password:
            st.error("All fields are required.")
        else:
            resp = session.post(f"{API_BASE}/api/users/create", json={"name": name, "email": email, "password": password})
            if resp.status_code == 200 or resp.status_code == 201:
                st.success("Account created! Check your email and click the verification link before logging in.")
            else:
                detail = resp.json().get("detail", "Unknown error")
                st.error(f"Error: {detail}")
            show_response(resp)

# --- Login ---
elif page == "Login":
    st.header("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if not email or not password:
            st.error("All fields are required.")
        else:
            resp = session.post(f"{API_BASE}/api/auth/login", json={"email": email, "password": password})
            if resp.status_code == 200:
                token_data = resp.json()
                st.session_state["access_token"] = token_data["access_token"]
                me_resp = session.get(f"{API_BASE}/api/users/me", headers=auth_headers())
                if me_resp.status_code == 200:
                    st.session_state["user_info"] = me_resp.json()
                st.success(f"Logged in as {st.session_state['user_info']['name'] if st.session_state['user_info'] else email}")
                st.rerun()
            else:
                detail = resp.json().get("detail", "Unknown error")
                st.error(f"Login failed: {detail}")
                show_response(resp)

# --- My Profile ---
elif page == "My Profile":
    st.header("My Profile")
    if not st.session_state["access_token"]:
        st.warning("You are not logged in.")
    else:
        info = st.session_state["user_info"]
        if info:
            st.write(f"**ID:** {info['id']}")
            st.write(f"**Name:** {info['name']}")
            st.write(f"**Email:** {info['email']}")
            st.write(f"**Created at:** {info['created_at']}")
        else:
            st.info("No profile data loaded.")

        if st.button("Refresh Profile"):
            resp = session.get(f"{API_BASE}/api/users/me", headers=auth_headers())
            if resp.status_code == 200:
                st.session_state["user_info"] = resp.json()
                st.rerun()
            else:
                detail = resp.json().get("detail", "Unknown error")
                st.error(f"Error: {detail}")
            show_response(resp)

        st.divider()
        if st.button("Logout", type="primary"):
            resp = session.post(f"{API_BASE}/api/auth/logout", headers=auth_headers())
            st.session_state["access_token"] = None
            st.session_state["user_info"] = None
            if resp.status_code == 204:
                st.success("Logged out successfully.")
            else:
                st.warning("Logout request returned an unexpected status, session cleared anyway.")
                show_response(resp)
            st.rerun()

# --- Forgot Password ---
elif page == "Forgot Password":
    st.header("Forgot Password")
    st.info("A password reset link will be sent to your email. Click it to open the reset form automatically.")
    email = st.text_input("Email")

    if st.button("Send Reset Email"):
        if not email:
            st.error("Email is required.")
        else:
            resp = session.post(f"{API_BASE}/api/auth/forgot-password", json={"email": email})
            if resp.status_code == 200:
                st.success("Check your email for a password reset link. It expires in 15 minutes.")
            else:
                detail = resp.json().get("detail", "Unknown error")
                st.error(f"Error: {detail}")
            show_response(resp)

# --- Resend Verification ---
elif page == "Resend Verification":
    st.header("Resend Verification Email")
    st.info("A new verification link will be sent to your email. Click it to verify automatically.")
    email = st.text_input("Email")

    if st.button("Resend Email"):
        if not email:
            st.error("Email is required.")
        else:
            resp = session.post(f"{API_BASE}/api/auth/resend-verification", json={"email": email})
            if resp.status_code == 200:
                st.success("Verification email sent! Check your inbox and click the link.")
            else:
                detail = resp.json().get("detail", "Unknown error")
                st.error(f"Error: {detail}")
            show_response(resp)

# --- Refresh Token ---
elif page == "Refresh Token":
    st.header("Refresh Access Token")
    st.write("Uses the refresh token cookie stored in the session to get a new access token.")

    if st.button("Refresh Access Token"):
        resp = session.post(f"{API_BASE}/api/auth/refresh")
        if resp.status_code == 200:
            st.session_state["access_token"] = resp.json()["access_token"]
            st.success("Access token refreshed.")
        else:
            detail = resp.json().get("detail", "Unknown error")
            st.error(f"Error: {detail}")
        show_response(resp)
