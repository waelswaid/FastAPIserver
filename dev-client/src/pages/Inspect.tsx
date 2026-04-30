import { useState } from "react";
import Token from "./inspect/Token";
import Activity from "./inspect/Activity";
import Codes from "./inspect/Codes";
import Health from "./inspect/Health";

type Sub = "token" | "activity" | "codes" | "health";

export default function Inspect() {
  const [sub, setSub] = useState<Sub>("activity");

  const cls = (active: boolean) =>
    `px-3 py-1.5 text-xs border-b-2 ${
      active ? "border-gray-900 font-semibold" : "border-transparent text-gray-600"
    }`;

  return (
    <div>
      <nav className="flex gap-2 border-b border-gray-200 mb-4">
        <button type="button" onClick={() => setSub("token")} className={cls(sub === "token")}>
          Token
        </button>
        <button type="button" onClick={() => setSub("activity")} className={cls(sub === "activity")}>
          Activity
        </button>
        <button type="button" onClick={() => setSub("codes")} className={cls(sub === "codes")}>
          Codes
        </button>
        <button type="button" onClick={() => setSub("health")} className={cls(sub === "health")}>
          Health
        </button>
      </nav>
      {sub === "token" && <Token />}
      {sub === "activity" && <Activity />}
      {sub === "codes" && <Codes />}
      {sub === "health" && <Health />}
    </div>
  );
}
