import { request } from "../api";
import { setToken } from "../auth";
import Form from "../components/Form";

const inputCls = "w-full rounded border border-gray-300 px-2 py-1 text-sm";
const labelCls = "block text-xs font-medium text-gray-700 mb-2";

function field(name: string, type = "text", placeholder?: string) {
  return (
    <label className={labelCls} key={name}>
      {name}
      <input name={name} type={type} placeholder={placeholder} className={inputCls} />
    </label>
  );
}

export default function Public() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Form
        title="Register"
        onSubmit={async (v) => request("POST", "/api/users/create", v)}
      >
        {field("first_name")}
        {field("last_name")}
        {field("email", "email")}
        {field("password", "password")}
      </Form>

      <Form
        title="Login"
        onSubmit={async (v) => {
          const res = await request<{ access_token?: string }>("POST", "/api/auth/login", v);
          if (res.status === 200 && res.body?.access_token) {
            setToken(res.body.access_token);
          }
          return res;
        }}
      >
        {field("email", "email")}
        {field("password", "password")}
      </Form>

      <Form
        title="Forgot password"
        onSubmit={async (v) => request("POST", "/api/auth/forgot-password", v)}
      >
        {field("email", "email")}
      </Form>

      <Form
        title="Validate reset code"
        onSubmit={async (v) => request("GET", `/api/auth/reset-password?code=${encodeURIComponent(v.code)}`)}
      >
        {field("code", "text", "paste from console")}
      </Form>

      <Form
        title="Reset password (paste code)"
        onSubmit={async (v) => request("POST", "/api/auth/reset-password", v)}
      >
        {field("code", "text", "paste from console")}
        {field("new_password", "password")}
      </Form>

      <Form
        title="Resend verification"
        onSubmit={async (v) => request("POST", "/api/auth/resend-verification", v)}
      >
        {field("email", "email")}
      </Form>

      <Form
        title="Verify email (paste code)"
        onSubmit={async (v) => request("GET", `/api/auth/verify-email?code=${encodeURIComponent(v.code)}`)}
      >
        {field("code", "text", "paste from console")}
      </Form>

      <Form
        title="Validate invite code"
        onSubmit={async (v) => request("GET", `/api/auth/accept-invite?code=${encodeURIComponent(v.code)}`)}
      >
        {field("code", "text", "paste from console")}
      </Form>

      <Form
        title="Accept invite (paste code)"
        onSubmit={async (v) => request("POST", "/api/auth/accept-invite", v)}
      >
        {field("code", "text", "paste from console")}
        {field("first_name")}
        {field("last_name")}
        {field("password", "password")}
      </Form>

      <Form
        title="Sign in with Google"
        submitLabel="Redirect"
        onSubmit={async () => {
          const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";
          window.location.href = `${base}/api/auth/google`;
          return { status: 0, body: null, error: "redirecting…" };
        }}
      >
        <p className="text-xs text-gray-500">Will 503 if Google credentials are not configured.</p>
      </Form>
    </div>
  );
}
