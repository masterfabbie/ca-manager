import { useState } from "react";
import { useGenerateCSR } from "../../hooks/useCSRs";
import SANEditor from "../certificates/SANEditor";
import type { CSRGeneratePayload, SANEntry } from "../../types";
import Modal from "../ui/Modal";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function CSRGenerate({ onSuccess, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CSRGeneratePayload>({
    common_name: "",
    sans: [],
    key_size: 2048,
  });
  const { mutate, isPending } = useGenerateCSR();

  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(form, {
      onSuccess: (rec) => {
        onSuccess(`CSR for "${rec.common_name}" generated — download it from the table below`);
        setForm({ common_name: "", sans: [], key_size: 2048 });
        setOpen(false);
      },
      onError: () => onError("Failed to generate CSR"),
    });
  };

  return (
    <>
      <button className="btn btn-secondary" onClick={() => setOpen(true)}>
        + Generate CSR
      </button>
      {open && (
        <Modal title="Generate CSR" onClose={() => setOpen(false)} size="md">
          <form onSubmit={handle}>
            <p className="muted" style={{ margin: "0 0 12px", fontSize: "12px" }}>
              Generates a key pair and CSR in-app. The private key is stored server-side so you can import the
              signed cert later. Download the CSR to submit to an external CA.
            </p>
            <label>
              Common Name (CN)
              <input
                required
                value={form.common_name}
                onChange={(e) => setForm({ ...form, common_name: e.target.value })}
                placeholder="my.domain.com"
              />
            </label>
            <label style={{ color: "var(--muted)", fontSize: "13px" }}>
              Subject Alternative Names
            </label>
            <SANEditor
              value={form.sans}
              onChange={(sans: SANEntry[]) => setForm({ ...form, sans })}
            />
            <label>
              Key Size
              <select
                value={form.key_size}
                onChange={(e) => setForm({ ...form, key_size: Number(e.target.value) as 2048 | 4096 })}
              >
                <option value={2048}>2048 bit</option>
                <option value={4096}>4096 bit</option>
              </select>
            </label>
            <div className="row-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={isPending}>
                {isPending ? "Generating…" : "Generate"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
