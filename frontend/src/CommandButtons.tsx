import { useState } from "react";
import type { Telemetry } from "./useTelemetry";

const COMMAND_URL = "http://localhost:8000/api/command/";

type CommandName = "RTL" | "LAND";
type CommandResult = { ok: boolean; reason: string };

// POSTs to /api/command/rtl or /api/command/land and returns the backend's
// {ok, reason}. Network problems become a failed result, never an exception.
async function sendCommand(name: CommandName): Promise<CommandResult> {
    try {
        const response = await fetch(COMMAND_URL + name.toLowerCase(), { method: "POST" });
        if (!response.ok) {
            return { ok: false, reason: `HTTP ${response.status}` };
        }
        return await response.json();
    } catch {
        return { ok: false, reason: "Backend not reachable" };
    }
}

// RTL and LAND buttons, fixed at the top of the screen and always visible.
// One click sends the command straight away (no confirmation dialog: in an
// emergency, speed matters). The backend decides whether it's allowed.
export default function CommandButtons({
    telemetry,
    connected,
}: {
    telemetry: Telemetry | null;
    connected: boolean;
}) {
    const [sending, setSending] = useState<CommandName | null>(null);
    const [result, setResult] = useState<(CommandResult & { name: CommandName }) | null>(null);

    // Why the buttons are disabled, or null if they can be used.
    function blockedReason(): string | null {
        if (!connected || telemetry === null) return "Backend disconnected";
        if (telemetry.link !== "ok") return "No link to the drone";
        if (!telemetry.commands_enabled) return "Commands disabled (COMMANDS_ENABLED in backend/.env)";
        return null;
    }
    const reason = blockedReason();

    async function handleClick(name: CommandName) {
        setSending(name);
        setResult(null);
        const answer = await sendCommand(name);
        setResult({ name, ...answer });
        setSending(null);
    }

    return (
        <div className="command-buttons">
            <div>
                <button onClick={() => handleClick("RTL")} disabled={reason !== null || sending !== null}>
                    {sending === "RTL" ? "Sending…" : "RTL"}
                </button>
                <button onClick={() => handleClick("LAND")} disabled={reason !== null || sending !== null}>
                    {sending === "LAND" ? "Sending…" : "LAND"}
                </button>
            </div>
            {reason && <div className="wp-note">{reason}</div>}
            {result && (
                <div className={result.ok ? "status-ok" : "status-failed"}>
                    {result.name}: {result.reason}
                </div>
            )}
        </div>
    );
}
