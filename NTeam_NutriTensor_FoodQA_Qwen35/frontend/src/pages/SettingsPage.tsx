import { useEffect, useState } from "react";
import { Download, LogOut } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { downloadBlob, errorMessage } from "../lib/export";
import {
  Button,
  ErrorNotice,
  Field,
  Modal,
  Toggle,
} from "../components/Primitives";

export default function SettingsPage() {
  const workspace = useWorkspace();
  const { api, connected, preferences, capabilities, toast } = workspace;
  const [base, setBase] = useState("");
  const [username, setUsername] = useState("owner");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState(preferences);
  const [eraseOpen, setEraseOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  useEffect(() => setDraft(preferences), [preferences]);
  const perform = async (action: () => Promise<unknown>) => {
    setPending(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };
  const signIn = () =>
    perform(async () => {
      await workspace.connect(base.trim(), password, username);
      setPassword("");
    });
  const exportData = (format: "json" | "csv") =>
    perform(async () =>
      downloadBlob(
        await api.exportData(format),
        `nutritensor-${format}.${format}`,
      ),
    );
  const erase = () =>
    perform(async () => {
      if (confirmation !== "DELETE") return;
      await api.erase();
      if (connected) window.location.reload();
      else {
        workspace.changed();
        setEraseOpen(false);
        setConfirmation("");
        toast("Browser data cleared", "success");
      }
    });
  return (
    <main className="workspace-page simple-page settings-simple">
      <h1>Settings</h1>
      <p className="simple-intro">Our local workspace.</p>
      <section className="simple-section">
        <h2>{connected ? "Connected" : "Sign in"}</h2>
        {connected ? (
          <>
            <p>ntemma</p>
            {/* <p className="fine-print">
              {capabilities?.vision
                ? "Image recognition supported by this checkpoint."
                : "Photo recognition unavailable. Use Enter food"}
            </p> */}
            <Button
              variant="secondary"
              loading={pending}
              onClick={() => void perform(workspace.disconnect)}
            >
              <LogOut size={16} /> Sign out
            </Button>
          </>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void signIn();
            }}
          >
            <Field label="Username">
              <input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                maxLength={32}
              />
            </Field>
            <Field label="Password">
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                maxLength={1024}
              />
            </Field>
            <details className="scan-details">
              <summary>Connection address</summary>
              <Field
                label="Server URL"
                hint="Leave empty when running this app from your local server."
              >
                <input
                  value={base}
                  onChange={(event) => setBase(event.target.value)}
                  placeholder="Same origin"
                  inputMode="url"
                />
              </Field>
            </details>
            <Button type="submit" loading={pending}>
              Sign in
            </Button>
            <p className="fine-print">
              Three local accounts maximum. models are runs on gpu. it have a electric bill.
              if our sir says so, it can be increased a littel upto 5.
            </p>
          </form>
        )}
        {error && <ErrorNotice message={error} />}
      </section>
      <section className="simple-section">
        <h2>Preferences</h2>
        <Field label="Science Day In">
          <select
            value={draft.timezone}
            onChange={(event) =>
              setDraft({ ...draft, timezone: event.target.value })
            }
          >
            <option value="Asia/Kolkata">India/SSPHS</option>
            {/* <option value="Asia/Dhaka"></option>
                <option value="UTC">UTC</option>
            <option value="Europe/London">London</option>
            <option value="America/New_York">New York</option> */}
          </select>
        </Field>
        {/* <Toggle
          checked={draft.reduced_motion}
          onChange={(value) => setDraft({ ...draft, reduced_motion: value })}
          label="Reduce motion"
          description="Keep result bubbles still."
        /> */}
        <Toggle
          checked={draft.save_images}
          onChange={(value) => setDraft({ ...draft, save_images: value })}
          label="Keep photos temporarily"
          description="Otherwise, the local server removes photos after analysis."
        />
        <Button
          loading={pending}
          onClick={() => void perform(() => workspace.savePreferences(draft))}
        >
          Save preferences
        </Button>
      </section>
      <details className="scan-details settings-advanced">
        <summary>Model & privacy</summary>
        <p>
          <strong>Models are engineered, not a toy</strong>The server checks the checkpoint architecture; names and
          weights always need review.
        </p>
        <dl>
          <div>
            <dt>Runtime</dt>
            <dd>{capabilities?.backend ?? "—"}</dd>
          </div>
          <div>
            <dt>Food records</dt>
            <dd>{capabilities?.catalog_count ?? "—"}</dd>
          </div>
          <div>
            <dt>Quantization</dt>
            <dd>{capabilities?.quantization ?? "—"}</dd>
          </div>
        </dl>
        <button
          className="scan-text-button"
          onClick={() => void perform(workspace.refreshCapabilities)}
        >
          Refresh model status
        </button>
        <div className="settings-data-actions">
          <Button
            variant="secondary"
            loading={pending}
            onClick={() => void exportData("json")}
          >
            <Download size={16} /> Export JSON
          </Button>
          <Button
            variant="secondary"
            loading={pending}
            onClick={() => void exportData("csv")}
          >
            Export CSV
          </Button>
          <Button variant="ghost" onClick={() => setEraseOpen(true)}>
            Delete data
          </Button>
        </div>
      </details>
      <Modal
        open={eraseOpen}
        onClose={() => setEraseOpen(false)}
        title="Delete your data?"
        description="This removes this account’s preferences and analyses. Export first if need a copy sir."
      >
        <Field label="Type DELETE to confirm">
          <input
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="off"
          />
        </Field>
        <div className="modal-footer">
          <Button variant="ghost" onClick={() => setEraseOpen(false)}>
            Keep data
          </Button>
          <Button
            disabled={confirmation !== "DELETE"}
            loading={pending}
            onClick={() => void erase()}
          >
            Delete data
          </Button>
        </div>
      </Modal>
    </main>
  );
}
