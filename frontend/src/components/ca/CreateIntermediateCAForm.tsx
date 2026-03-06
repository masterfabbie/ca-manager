import { useState } from "react";
import { useCreateIntermediateCA } from "../../hooks/useCAs";
import type { CreateIntermediateCAPayload, RootCA } from "../../types";
import Modal from "../ui/Modal";

interface Props {
  rootCAs: RootCA[];
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function CreateIntermediateCAForm({ rootCAs, onSuccess, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CreateIntermediateCAPayload>({
    name: "",
    common_name: "",
    parent_ca_id: rootCAs[0]?.id ?? "",
    valid_days: 1825,
    key_size: 4096,
  });
  const { mutate, isPending } = useCreateIntermediateCA();

  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(form, {
      onSuccess: () => {
        onSuccess(`Intermediate CA "${form.name}" created`);
        setForm({ name: "", common_name: "", parent_ca_id: rootCAs[0]?.id ?? "", valid_days: 1825, key_size: 4096 });
        setOpen(false);
      },
      onError: (err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to create intermediate CA";
        onError(msg);
      },
    });
  };

  return (
    <>
      <button
        className="btn btn-secondary"
        onClick={() => setOpen(true)}
        disabled={rootCAs.length === 0}
        title={rootCAs.length === 0 ? "Create a Root CA first" : undefined}
      >
        + New Intermediate CA
      </button>
      {open && (
        <Modal title="Create Intermediate CA" onClose={() => setOpen(false)} size="md">
          <form onSubmit={handle}>
            <label>
              Parent CA
              <select
                value={form.parent_ca_id}
                onChange={(e) => setForm({ ...form, parent_ca_id: e.target.value })}
                required
              >
                {rootCAs.map((ca) => (
                  <option key={ca.id} value={ca.id}>
                    {ca.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Display Name
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My Intermediate CA"
              />
            </label>
            <label>
              Common Name (CN)
              <input
                required
                value={form.common_name}
                onChange={(e) => setForm({ ...form, common_name: e.target.value })}
                placeholder="Homelab Intermediate CA"
              />
            </label>
            <div className="row-2">
              <label>
                Valid Days
                <input
                  type="number"
                  min={1}
                  max={3650}
                  required
                  value={form.valid_days}
                  onChange={(e) => setForm({ ...form, valid_days: Number(e.target.value) })}
                />
              </label>
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
            </div>
            <div className="row-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={isPending}>
                {isPending ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
