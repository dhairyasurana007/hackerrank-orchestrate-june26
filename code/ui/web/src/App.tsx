import { useEffect, useState } from "react";

import "./App.css";

const API = (import.meta.env.VITE_API_URL as string) || "";

type Claim = {
  index: number;
  user_id: string;
  claim_object: string;
  user_claim: string;
  image_ids: string[];
  image_paths: string[];
  labels: Record<string, string>;
};
type Prediction = Record<string, string>;

const FIELDS = [
  "claim_status", "severity", "issue_type", "object_part",
  "evidence_standard_met", "valid_image", "risk_flags",
  "supporting_image_ids", "evidence_standard_met_reason", "claim_status_justification",
];

function imageUrl(path: string) {
  return `${API}/api/image?path=${encodeURIComponent(path)}`;
}

type Message = { role: "customer" | "agent"; speaker: string; text: string };

function parseTranscript(text: string): Message[] {
  return text
    .split("|")
    .map((turn) => turn.trim())
    .filter(Boolean)
    .map((turn) => {
      const idx = turn.indexOf(":");
      const speaker = idx >= 0 ? turn.slice(0, idx).trim() : "Support";
      const body = idx >= 0 ? turn.slice(idx + 1).trim() : turn;
      const role: "customer" | "agent" =
        speaker.toLowerCase() === "customer" ? "customer" : "agent";
      return { role, speaker, text: body };
    });
}

export function App() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selected, setSelected] = useState<Claim | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [generating, setGenerating] = useState(false);
  const [source, setSource] = useState("");

  useEffect(() => {
    fetch(`${API}/api/claims?input=test`)
      .then((response) => response.json())
      .then((data) => {
        setClaims(data.claims as Claim[]);
        setSource((data.source as string) ?? "");
      })
      .catch((err) => setError(String(err)));
  }, []);

  function select(claim: Claim) {
    setSelected(claim);
    setPrediction(null);
    setError("");
  }

  function runVerification(claim: Claim) {
    setRunning(true);
    setError("");
    fetch(`${API}/api/run?input=test&strategy=two_stage&index=${claim.index}`, { method: "POST" })
      .then((response) => response.json())
      .then((data) => setPrediction((data.predictions?.[0] as Prediction) ?? null))
      .catch((err) => setError(String(err)))
      .finally(() => setRunning(false));
  }

  function generate() {
    if (!uploadFile) return;
    setGenerating(true);
    setError("");
    const form = new FormData();
    form.append("file", uploadFile);
    fetch(`${API}/api/generate?strategy=two_stage`, { method: "POST", body: form })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "output.csv";
        link.click();
        URL.revokeObjectURL(url);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setGenerating(false));
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <h1>Evidence Review Dashboard</h1>
          <p className="sub">
            Loaded <strong>{source || "n/a"}</strong> · {claims.length} claims
          </p>
        </div>
        <div className="upload">
          <label className="filebtn">
            Choose CSV
            <input
              type="file"
              accept=".csv"
              hidden
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <span className={uploadFile ? "fname" : "fname muted"}>
            {uploadFile ? uploadFile.name : "no file selected"}
          </span>
          <button className="run" onClick={generate} disabled={!uploadFile || generating}>
            {generating ? (
              <>
                <span className="spinner" />
                Generating...
              </>
            ) : (
              "Generate output.csv"
            )}
          </button>
        </div>
      </header>
      {error ? <p className="error">{error}</p> : null}
      <div className="layout">
        <aside className="list">
          {claims.map((claim) => (
            <button
              key={claim.index}
              className={selected?.index === claim.index ? "claim active" : "claim"}
              onClick={() => select(claim)}
            >
              <span className={`tag ${claim.claim_object}`}>{claim.claim_object}</span>
              <span className="uid">{claim.user_id}</span>
            </button>
          ))}
        </aside>
        <main className="detail">
          {selected ? (
            <>
              <h2>
                <span className={`tag ${selected.claim_object}`}>{selected.claim_object}</span>
                {selected.user_id}
              </h2>
              <div className="chat">
                {parseTranscript(selected.user_claim).map((msg, i) => (
                  <div key={i} className={`bubble ${msg.role}`}>
                    <span className="speaker">{msg.speaker}</span>
                    <p>{msg.text}</p>
                  </div>
                ))}
              </div>
              <div className="images">
                {selected.image_paths.map((path, i) => (
                  <img key={path} src={imageUrl(path)} alt={selected.image_ids[i]} />
                ))}
              </div>
              <button className="run" onClick={() => runVerification(selected)} disabled={running}>
                {running ? (
                  <>
                    <span className="spinner" />
                    Running...
                  </>
                ) : (
                  "Run verification"
                )}
              </button>
              {prediction ? (
                <div className="prediction">
                  {FIELDS.map((field) => (
                    <div className="row" key={field}>
                      <span className="k">{field}</span>
                      <span className="v">
                        {field === "claim_status" ? (
                          <span className={`badge ${prediction[field]}`}>{prediction[field]}</span>
                        ) : (
                          prediction[field]
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <p className="empty">
              Select a claim to view its transcript, images, and run verification.
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
