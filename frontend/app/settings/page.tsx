"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, Wifi, WifiOff, Loader2 } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import type { EmailConfigResponse } from "@/lib/types";

export default function SettingsPage() {
  const [emailConfig, setEmailConfig] = useState<EmailConfigResponse | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.email.config().then(setEmailConfig).catch((e) => {
      setError(e instanceof Error ? e.message : "Failed to load email config");
    });
  }, []);

  async function testSmtp() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.email.test();
      setTestResult(res);
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <PageHeader title="Settings" subtitle="Email configuration and system status" />

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-rose-800/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-400">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Email section */}
      <section className="mb-6">
        <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">Email / SMTP</h2>
        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 divide-y divide-zinc-800/60">
          {emailConfig ? (
            <>
              <Row label="Mode" value={emailConfig.dry_run ? "Dry run (no emails sent)" : "Live"} />
              <Row
                label="SMTP"
                value={
                  <span className={`flex items-center gap-1.5 text-sm ${emailConfig.smtp_configured ? "text-emerald-400" : "text-zinc-500"}`}>
                    {emailConfig.smtp_configured ? (
                      <><Wifi className="w-3.5 h-3.5" /> Configured</>
                    ) : (
                      <><WifiOff className="w-3.5 h-3.5" /> Not configured</>
                    )}
                  </span>
                }
              />
              {emailConfig.from_address && (
                <Row label="From" value={emailConfig.from_name ? `${emailConfig.from_name} <${emailConfig.from_address}>` : emailConfig.from_address} />
              )}
            </>
          ) : (
            <div className="px-4 py-4">
              <div className="h-4 bg-zinc-800 rounded animate-pulse w-48" />
            </div>
          )}
        </div>

        {emailConfig?.smtp_configured && (
          <div className="mt-3">
            <button
              onClick={testSmtp}
              disabled={testing}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-zinc-700 hover:bg-zinc-800 text-zinc-300 text-sm transition-colors disabled:opacity-50"
            >
              {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" />}
              Test SMTP connection
            </button>
            {testResult && (
              <div className={`mt-2 flex items-center gap-2 text-sm px-4 py-3 rounded-lg border ${
                testResult.ok
                  ? "border-emerald-800/50 bg-emerald-500/10 text-emerald-400"
                  : "border-rose-800/50 bg-rose-500/10 text-rose-400"
              }`}>
                {testResult.ok ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                {testResult.message}
              </div>
            )}
          </div>
        )}
      </section>

      {/* ENV reminder */}
      <section>
        <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">Configuration</h2>
        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-4 text-xs text-zinc-500 space-y-2">
          <p>Set these variables in your backend <code className="text-zinc-400 bg-zinc-800 px-1 rounded">.env</code> file:</p>
          <table className="w-full mt-2 text-xs">
            <tbody className="divide-y divide-zinc-800/40">
              {[
                ["SMTP_HOST", "SMTP server hostname"],
                ["SMTP_PORT", "587 (TLS) or 465 (SSL)"],
                ["SMTP_USERNAME", "Your email address"],
                ["SMTP_PASSWORD", "App password or SMTP key"],
                ["EMAIL_FROM_ADDRESS", "Sender address"],
                ["EMAIL_FROM_NAME", "Your display name"],
                ["EMAIL_DRY_RUN", "false to enable live sending"],
              ].map(([key, desc]) => (
                <tr key={key}>
                  <td className="py-1.5 pr-4 font-mono text-zinc-400">{key}</td>
                  <td className="py-1.5 text-zinc-600">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className="text-sm text-zinc-300">{value}</span>
    </div>
  );
}
