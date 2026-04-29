import { request } from "../api";
import { getToken } from "../auth";
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

export default function Admin() {
  if (!getToken()) {
    return (
      <p className="text-sm text-gray-600">
        Not signed in. Sign in as an admin user first (use the Public tab Login form).
        The backend will return 403 if the user does not have the admin role.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Form
        title="List users"
        submitLabel="GET /users"
        onSubmit={async (v) => {
          const params = new URLSearchParams();
          if (v.role) params.set("role", v.role);
          if (v.skip) params.set("skip", v.skip);
          if (v.limit) params.set("limit", v.limit);
          const qs = params.toString();
          return request("GET", `/api/admin/users/${qs ? `?${qs}` : ""}`);
        }}
      >
        {field("role", "text", "user | admin (optional)")}
        {field("skip", "number", "default 0")}
        {field("limit", "number", "default 50, max 100")}
      </Form>

      <Form
        title="Change user role"
        submitLabel="PATCH /role"
        onSubmit={async (v) => request("PATCH", `/api/admin/users/${v.user_id}/role`, { role: v.role })}
      >
        {field("user_id", "text", "uuid")}
        {field("role", "text", "user | admin")}
      </Form>

      <Form
        title="Disable / enable user"
        submitLabel="PATCH /status"
        onSubmit={async (v) => request("PATCH", `/api/admin/users/${v.user_id}/status`, { is_disabled: v.is_disabled === "true" })}
      >
        {field("user_id", "text", "uuid")}
        {field("is_disabled", "text", "true | false")}
      </Form>

      <Form
        title="Invite user"
        submitLabel="POST /invite"
        onSubmit={async (v) => request("POST", "/api/admin/users/invite", v)}
      >
        {field("email", "email")}
      </Form>

      <Form
        title="Force password reset"
        submitLabel="POST /force-password-reset"
        onSubmit={async (v) => request("POST", `/api/admin/users/${v.user_id}/force-password-reset`)}
      >
        {field("user_id", "text", "uuid")}
      </Form>
    </div>
  );
}
