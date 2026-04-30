import { useEffect, useState } from "react";
import Public from "./pages/Public";
import Account from "./pages/Account";
import Admin from "./pages/Admin";
import Inspect from "./pages/Inspect";
import { setToken, getToken, clearToken, subscribe } from "./auth";

type Tab = "public" | "account" | "admin" | "inspect";

export default function App() {
  const [tab, setTab] = useState<Tab>("public");
  const [token, setTokenState] = useState<string | null>(getToken());

  useEffect(() => {
    const unsub = subscribe(() => setTokenState(getToken()));
    return unsub;
  }, []);

  useEffect(() => {
    if (window.location.pathname === "/oauth-callback") {
      const params = new URLSearchParams(window.location.search);
      const t = params.get("token");
      if (t) {
        setToken(t);
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
          {token ? (
            <button type="button" className="underline" onClick={() => clearToken()}>
              clear token
            </button>
          ) : (
            "no token"
          )}
        </div>
      </div>
      <nav className="flex gap-2 border-b border-gray-200 mb-4">
        <button type="button" onClick={() => setTab("public")} className={tabClasses(tab === "public")}>Public</button>
        <button type="button" onClick={() => setTab("account")} className={tabClasses(tab === "account")}>Account</button>
        <button type="button" onClick={() => setTab("admin")} className={tabClasses(tab === "admin")}>Admin</button>
        <button type="button" onClick={() => setTab("inspect")} className={tabClasses(tab === "inspect")}>Inspect</button>
      </nav>
      {tab === "public" && <Public />}
      {tab === "account" && <Account />}
      {tab === "admin" && <Admin />}
      {tab === "inspect" && <Inspect />}
    </div>
  );
}
