import { useEffect, useState } from "react";
import Public from "./pages/Public";
import Account from "./pages/Account";
import Admin from "./pages/Admin";
import { setToken, getToken, clearToken } from "./auth";

type Tab = "public" | "account" | "admin";

export default function App() {
  const [tab, setTab] = useState<Tab>("public");
  const [, force] = useState(0);

  useEffect(() => {
    if (window.location.pathname === "/oauth-callback") {
      const params = new URLSearchParams(window.location.search);
      const token = params.get("token");
      if (token) {
        setToken(token);
        force((n) => n + 1);
      }
      window.history.replaceState({}, "", "/");
    }
  }, []);

  const tabClasses = (active: boolean) =>
    `px-3 py-1.5 text-sm border-b-2 ${active ? "border-gray-900 font-semibold" : "border-transparent text-gray-600"}`;

  return (
    <div className="p-6 font-sans max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">auth-system dev client</h1>
        <div className="text-xs text-gray-600">
          {getToken() ? (
            <button
              className="underline"
              onClick={() => {
                clearToken();
                force((n) => n + 1);
              }}
            >
              clear token
            </button>
          ) : (
            "no token"
          )}
        </div>
      </div>
      <nav className="flex gap-2 border-b border-gray-200 mb-4">
        <button onClick={() => setTab("public")} className={tabClasses(tab === "public")}>Public</button>
        <button onClick={() => setTab("account")} className={tabClasses(tab === "account")}>Account</button>
        <button onClick={() => setTab("admin")} className={tabClasses(tab === "admin")}>Admin</button>
      </nav>
      {tab === "public" && <Public />}
      {tab === "account" && <Account />}
      {tab === "admin" && <Admin />}
    </div>
  );
}
