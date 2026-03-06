import { useState } from "react";
import { useCreateCA } from "../../hooks/useCAs";
import type { CreateCAPayload } from "../../types";
import Modal from "../ui/Modal";

interface Props {
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function CreateCAForm({ onSuccess, onError }: Props) {
  const [form, setForm] = useState<CreateCAPayload>({
    name: "",
    common_name: "",
    valid_days: 3650,
    key_size: 4096,
  });
  const [open, setOpen] = useState(false);
  const { mutate, isPending } = useCreateCA();

  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(form, {
      onSuccess: () => {
        onSuccess(`Root CA "${form.name}" created`);
        setForm({ name: "", common_name: "", valid_days: 3650, key_size: 4096 });
        setOpen(false);
      },
      onError: (err: unknown) => {
        const msg =
          err instanceof Error ? err.message : "Failed to create CA";
        onError(msg);
      },
    });
  };

  return (
    <>
      <button className="btn btn-primary" onClick={() => setOpen(true)}>
        + New Root CA
      </button>
      {open && (
        <Modal title="Create New Root CA" onClose={() => setOpen(false)} size="md">
          <form onSubmit={handle}>
            <label>
              Display Name
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My Homelab CA"
              />
            </label>
            <label>
              Common Name (CN)
              <input
                required
                value={form.common_name}
                onChange={(e) => setForm({ ...form, common_name: e.target.value })}
                placeholder="Homelab Root CA"
              />
            </label>
            <div className="row-2">
              <label>
                Valid Days
                <input
                  type="number"
                  min={1}
                  max={36500}
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
