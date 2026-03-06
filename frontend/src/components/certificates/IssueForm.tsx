import { useState } from "react";
import { useIssueCert } from "../../hooks/useCertificates";
import { useAppStore } from "../../store/appStore";
import { useCAs } from "../../hooks/useCAs";
import type { CreateCertPayload, SANEntry } from "../../types";
import SANEditor from "./SANEditor";
import Modal from "../ui/Modal";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

const defaultForm = (): Omit<CreateCertPayload, "root_ca_id"> => ({
  common_name: "",
  sans: [],
  valid_days: 365,
  key_size: 2048,
});

export default function IssueForm({ onSuccess, onError }: Props) {
  const { selectedCAId } = useAppStore();
  const { data: cas } = useCAs();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(defaultForm());
  const { mutate, isPending } = useIssueCert();

  const caId = selectedCAId ?? cas?.[0]?.id ?? "";

  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    if (!caId) {
      onError("Please create a Root CA first");
      return;
    }
    mutate(
      { ...form, root_ca_id: caId },
      {
        onSuccess: () => {
          onSuccess(`Certificate for "${form.common_name}" issued`);
          setForm(defaultForm());
          setOpen(false);
        },
        onError: (err: unknown) => {
          const msg =
            err instanceof Error ? err.message : "Failed to issue certificate";
          onError(msg);
        },
      }
    );
  };

  return (
    <>
      <button
        className="btn btn-primary"
        onClick={() => setOpen(true)}
        disabled={!cas?.length}
        title={!cas?.length ? "Create a Root CA first" : undefined}
      >
        + Issue Certificate
      </button>
      {open && (
        <Modal title="Issue Certificate" onClose={() => setOpen(false)} size="md">
          <form onSubmit={handle}>
            <label>
              Common Name (hostname)
              <input
                required
                value={form.common_name}
                onChange={(e) => setForm({ ...form, common_name: e.target.value })}
                placeholder="myserver.home.lab"
              />
            </label>
            <label>Subject Alternative Names (SANs)</label>
            <SANEditor
              value={form.sans}
              onChange={(sans: SANEntry[]) => setForm({ ...form, sans })}
            />
            <div className="row-2">
              <label>
                Valid Days
                <input
                  type="number"
                  min={1}
                  max={3650}
                  required
                  value={form.valid_days}
                  onChange={(e) =>
                    setForm({ ...form, valid_days: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                Key Size
                <select
                  value={form.key_size}
                  onChange={(e) =>
                    setForm({ ...form, key_size: Number(e.target.value) as 2048 | 4096 })
                  }
                >
                  <option value={2048}>2048 bit</option>
                  <option value={4096}>4096 bit</option>
                </select>
              </label>
            </div>
            <div className="row-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={isPending || !caId}>
                {isPending ? "Issuing…" : "Issue"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
