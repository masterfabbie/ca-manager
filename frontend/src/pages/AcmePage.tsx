import { useEffect, useState } from "react";
import { useCAs } from "../hooks/useCAs";
import { useSettings, useUpdateSettings } from "../hooks/useSettings";
import { useAcmeAccounts, useDeleteAcmeAccount } from "../hooks/useAcme";
import type { SettingsPayload } from "../types";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function AcmePage({ onSuccess, onError }: Props) {
  const { data: settings, isLoading: settingsLoading } = useSettings();
  const { data: cas } = useCAs();
  const { data: accounts, isLoading: accountsLoading } = useAcmeAccounts();
  const { mutate: save, isPending: saving } = useUpdateSettings();
  const { mutate: deleteAccount } = useDeleteAcmeAccount();

  const [form, setForm] = useState<Pick<SettingsPayload, "acme_enabled" | "acme_ca_id" | "acme_cert_days" | "acme_skip_challenges">>({
    acme_enabled: false,
    acme_ca_id: null,
    acme_cert_days: 90,
    acme_skip_challenges: false,
  });

  useEffect(() => {
    if (settings) {
      setForm({
        acme_enabled: settings.acme_enabled,
        acme_ca_id: settings.acme_ca_id,
        acme_cert_days: settings.acme_cert_days,
        acme_skip_challenges: settings.acme_skip_challenges,
      });
    }
  }, [settings]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    const payload: SettingsPayload = {
      smtp_host: settings.smtp_host,
      smtp_port: settings.smtp_port,
      smtp_username: settings.smtp_username,
      smtp_password: "",
      smtp_from: settings.smtp_from,
      alert_to: settings.alert_to,
      use_tls: settings.use_tls,
      alert_days: settings.alert_days,
      alerts_enabled: settings.alerts_enabled,
      ...form,
    };
    save(payload, {
      onSuccess: () => onSuccess("ACME settings saved"),
      onError: (err: unknown) => {
        const detail = (err as any)?.response?.data?.detail;
        onError(detail ?? "Failed to save settings");
      },
    });
  };

  const handleDelete = (id: string) => {
    deleteAccount(id, {
      onSuccess: () => onSuccess("Account deleted"),
      onError: () => onError("Failed to delete account"),
    });
  };

  const directoryUrl = `${window.location.origin}/acme/directory`;

  if (settingsLoading) return <p className="muted">Loading…</p>;

  const signingCAs = (cas ?? []).filter((ca) => ca.has_key);

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>ACME</h2>

      <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 660 }}>

        {/* Configuration */}
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Configuration</h3>
          <form onSubmit={handleSave}>
            <label>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                Enable ACME server
                <input
                  type="checkbox"
                  checked={form.acme_enabled}
                  onChange={(e) => setForm({ ...form, acme_enabled: e.target.checked })}
                  style={{ width: "auto" }}
                />
              </span>
            </label>

            <label>
              Signing CA
              <select
                value={form.acme_ca_id ?? ""}
                onChange={(e) => setForm({ ...form, acme_ca_id: e.target.value || null })}
                disabled={!form.acme_enabled}
              >
                <option value="">— select a CA —</option>
                {signingCAs.map((ca) => (
                  <option key={ca.id} value={ca.id}>
                    {ca.name} ({ca.is_intermediate ? "intermediate" : "root"})
                  </option>
                ))}
              </select>
            </label>

            <label>
              Certificate validity (days)
              <input
                type="number"
                min={1}
                max={3650}
                value={form.acme_cert_days}
                onChange={(e) => setForm({ ...form, acme_cert_days: Number(e.target.value) })}
                disabled={!form.acme_enabled}
              />
            </label>

            <label>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                Skip challenge verification
                <input
                  type="checkbox"
                  checked={form.acme_skip_challenges}
                  onChange={(e) => setForm({ ...form, acme_skip_challenges: e.target.checked })}
                  style={{ width: "auto" }}
                  disabled={!form.acme_enabled}
                />
              </span>
              <span className="muted" style={{ fontSize: "0.8em", marginTop: 2 }}>
                Auto-approve all challenges without HTTP verification. Useful for internal hostnames.
              </span>
            </label>

            <div className="row-actions" style={{ marginTop: 16 }}>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </div>

        {/* Directory URL */}
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Directory URL</h3>
          <p className="muted" style={{ marginBottom: 8 }}>
            Point your ACME client at this URL. Works with certbot, acme.sh, Caddy, Traefik, and others.
          </p>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <code
              style={{
                flex: 1,
                background: "var(--bg-secondary)",
                padding: "6px 10px",
                borderRadius: 4,
                wordBreak: "break-all",
                fontSize: "0.85em",
              }}
            >
              {directoryUrl}
            </code>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => {
                navigator.clipboard.writeText(directoryUrl);
                onSuccess("Copied to clipboard");
              }}
            >
              Copy
            </button>
          </div>
          <p className="muted" style={{ marginTop: 12, fontSize: "0.82em" }}>
            Example:{" "}
            <code>
              certbot certonly --standalone --server {directoryUrl} -d example.internal
            </code>
          </p>
        </div>

        {/* Accounts */}
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Registered Accounts</h3>
          {accountsLoading ? (
            <p className="muted">Loading…</p>
          ) : !accounts || accounts.length === 0 ? (
            <p className="muted">No accounts registered yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Thumbprint</th>
                  <th>Contact</th>
                  <th>Orders</th>
                  <th>Status</th>
                  <th>Registered</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((acct) => (
                  <tr key={acct.id}>
                    <td>
                      <code style={{ fontSize: "0.78em" }}>{acct.jwk_thumbprint.slice(0, 16)}…</code>
                    </td>
                    <td>
                      {acct.contact.length > 0
                        ? acct.contact.map((c) => c.replace("mailto:", "")).join(", ")
                        : <span className="muted">—</span>}
                    </td>
                    <td>{acct.order_count}</td>
                    <td>
                      <span
                        className="badge"
                        style={{ color: acct.status === "valid" ? "var(--success)" : "var(--danger)" }}
                      >
                        {acct.status}
                      </span>
                    </td>
                    <td>{new Date(acct.created_at).toLocaleDateString()}</td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDelete(acct.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
