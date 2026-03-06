import { useEffect, useState } from "react";
import { useSettings, useUpdateSettings, useTestEmail } from "../hooks/useSettings";
import type { SettingsPayload } from "../types";

const defaultForm = (): SettingsPayload => ({
  smtp_host: "",
  smtp_port: 587,
  smtp_username: "",
  smtp_password: "",
  smtp_from: "",
  alert_to: "",
  use_tls: true,
  alert_days: 30,
  alerts_enabled: false,
});

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function SettingsPage({ onSuccess, onError }: Props) {
  const { data, isLoading } = useSettings();
  const { mutate: save, isPending: saving } = useUpdateSettings();
  const { mutate: testEmail, isPending: testing } = useTestEmail();
  const [form, setForm] = useState<SettingsPayload>(defaultForm());

  useEffect(() => {
    if (data) {
      setForm({
        smtp_host: data.smtp_host,
        smtp_port: data.smtp_port,
        smtp_username: data.smtp_username,
        smtp_password: "",  // never pre-fill password
        smtp_from: data.smtp_from,
        alert_to: data.alert_to,
        use_tls: data.use_tls,
        alert_days: data.alert_days,
        alerts_enabled: data.alerts_enabled,
      });
    }
  }, [data]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    save(form, {
      onSuccess: () => onSuccess("Settings saved"),
      onError: (err: unknown) => {
        const detail = (err as any)?.response?.data?.detail;
        onError(detail ?? "Failed to save settings");
      },
    });
  };

  const handleTestEmail = () => {
    testEmail(undefined, {
      onSuccess: () => onSuccess("Test email sent successfully"),
      onError: (err: unknown) => {
        const detail = (err as any)?.response?.data?.detail;
        onError(detail ?? "Failed to send test email");
      },
    });
  };

  if (isLoading) return <p className="muted">Loading…</p>;

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>Settings</h2>

      <div className="card" style={{ maxWidth: 560 }}>
        <h3 style={{ marginTop: 0 }}>SMTP / Expiry Alerts</h3>
        <form onSubmit={handleSubmit}>
          <label>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              Enable expiry alerts
              <input
                type="checkbox"
                checked={form.alerts_enabled}
                onChange={(e) => setForm({ ...form, alerts_enabled: e.target.checked })}
                style={{ width: "auto" }}
              />
            </span>
          </label>

          <label>
            Alert days before expiry
            <input
              type="number"
              min={1}
              max={365}
              value={form.alert_days}
              onChange={(e) => setForm({ ...form, alert_days: Number(e.target.value) })}
            />
          </label>

          <label>
            SMTP Host
            <input
              value={form.smtp_host}
              onChange={(e) => setForm({ ...form, smtp_host: e.target.value })}
              placeholder="smtp.example.com"
            />
          </label>

          <label>
            SMTP Port
            <input
              type="number"
              min={1}
              max={65535}
              value={form.smtp_port}
              onChange={(e) => setForm({ ...form, smtp_port: Number(e.target.value) })}
            />
          </label>

          <label>
            Username
            <input
              value={form.smtp_username}
              onChange={(e) => setForm({ ...form, smtp_username: e.target.value })}
              placeholder="user@example.com"
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={form.smtp_password}
              onChange={(e) => setForm({ ...form, smtp_password: e.target.value })}
              placeholder="leave blank to keep existing"
              autoComplete="new-password"
            />
          </label>

          <label>
            From address
            <input
              value={form.smtp_from}
              onChange={(e) => setForm({ ...form, smtp_from: e.target.value })}
              placeholder="ca-manager@example.com"
            />
          </label>

          <label>
            Alert recipient
            <input
              value={form.alert_to}
              onChange={(e) => setForm({ ...form, alert_to: e.target.value })}
              placeholder="admin@example.com"
            />
          </label>

          <label style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={form.use_tls}
              onChange={(e) => setForm({ ...form, use_tls: e.target.checked })}
              style={{ width: "auto" }}
            />
            Use STARTTLS
          </label>

          <div className="row-actions" style={{ marginTop: 16 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleTestEmail}
              disabled={testing}
            >
              {testing ? "Sending…" : "Send test email"}
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
