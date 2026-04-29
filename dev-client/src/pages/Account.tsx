import { request } from "../api";
import { clearToken, getToken, setToken } from "../auth";
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

export default function Account() {
  if (!getToken()) {
    return (
      <p className="text-sm text-gray-600">
        Not signed in. Use the Login form on the Public tab first.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Form
        title="Get profile"
        submitLabel="GET /me"
        onSubmit={async () => request("GET", "/api/users/me")}
      >
        <p className="text-xs text-gray-500">No fields — fetches the authenticated user.</p>
      </Form>

      <Form
        title="Update profile"
        submitLabel="PATCH /me"
        onSubmit={async (v) => {
          const body: Record<string, string> = {};
          if (v.first_name) body.first_name = v.first_name;
          if (v.last_name) body.last_name = v.last_name;
          return request("PATCH", "/api/users/me", body);
        }}
      >
        {field("first_name", "text", "leave blank to skip")}
        {field("last_name", "text", "leave blank to skip")}
      </Form>

      <Form
        title="Change password"
        onSubmit={async (v) => request("POST", "/api/auth/change-password", v)}
      >
        {field("current_password", "password")}
        {field("new_password", "password")}
      </Form>

      <Form
        title="Refresh access token"
        submitLabel="POST /refresh"
        onSubmit={async () => {
          const res = await request<{ access_token?: string }>("POST", "/api/auth/refresh");
          if (res.status === 200 && res.body?.access_token) {
            setToken(res.body.access_token);
          }
          return res;
        }}
      >
        <p className="text-xs text-gray-500">Uses the refresh-token cookie. Stores the new access token.</p>
      </Form>

      <Form
        title="Logout"
        submitLabel="POST /logout"
        onSubmit={async () => {
          const res = await request("POST", "/api/auth/logout");
          clearToken();
          return res;
        }}
      >
        <p className="text-xs text-gray-500">Revokes the current token and clears local storage.</p>
      </Form>

      <Form
        title="Delete account"
        submitLabel="DELETE /me"
        onSubmit={async (v) => {
          const res = await request("DELETE", "/api/users/me", v);
          if (res.status === 204) clearToken();
          return res;
        }}
      >
        {field("password", "password")}
      </Form>
    </div>
  );
}
