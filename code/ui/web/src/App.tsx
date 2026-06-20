import { type DragEvent, useEffect, useState } from "react";

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

const FIELDS: [string, string][] = [
  ["claim_status", "Decision"],
  ["severity", "Severity"],
  ["issue_type", "Issue type"],
  ["object_part", "Object part"],
  ["evidence_standard_met", "Evidence sufficient"],
  ["valid_image", "Image usable"],
  ["risk_flags", "Risk flags"],
  ["supporting_image_ids", "Supporting images"],
  ["evidence_standard_met_reason", "Evidence note"],
  ["claim_status_justification", "Justification"],
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
  const [generating, setGenerating] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/api/claims?input=test`)
      .then((response) => response.json())
      .then((data) => {
        const list = data.claims as Claim[];
        setClaims(list);
        setSource((data.source as string) ?? "");
        if (list.length > 0) setSelected(list[0]);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
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
    setGenerating(true);
    setError("");
    const form = new FormData();
    if (uploadFile) form.append("file", uploadFile);
    fetch(`${API}/api/generate?input=test&strategy=two_stage`, { method: "POST", body: form })
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

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) setUploadFile(file);
  }

  return (
    <div className="app">
      <div className="appbar">
        <div className="appbar-inner">
          <div className="brand">
            <div className="logo">CR</div>
            <div>
              <h1>Claims Evidence Review</h1>
              <p className="sub">
                {loading
                  ? "Loading claims..."
                  : `Source: ${source || "claims.csv"} (${claims.length} claims)`}
              </p>
            </div>
          </div>
        </div>
      </div>

      <section className="dropzone-wrap">
        <div className="zone-label">
          <h2>Batch — generate predictions for a whole CSV</h2>
          <p>
            Upload a claims CSV; the pipeline runs every row and produces a downloadable
            output.csv. (Different from per-claim review below.)
          </p>
        </div>
        <label
          className={dragActive ? "dropzone active" : "dropzone"}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
        >
          <input
            type="file"
            accept=".csv"
            hidden
            onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
          />
          <div className="dz-inner">
            <svg
              className="dz-icon"
              width="46"
              height="46"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 16V4" />
              <path d="m6 10 6-6 6 6" />
              <path d="M4 20h16" />
            </svg>
            <p className="dz-title">Drag &amp; drop a claims CSV here</p>
            <p className="dz-sub">or click to browse</p>
            {uploadFile ? <p className="dz-file">Selected: {uploadFile.name}</p> : null}
          </div>
        </label>
      </section>

      <div className="container">
        <div className="zone-label">
          <h2>Review — verify one claim at a time</h2>
          <p>
            Browse the loaded dataset and run verification on a single selected claim. (Different
            from the batch CSV generator above.)
          </p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div className="layout">
          <aside className="panel queue">
            <div className="panel-head">
              <span>Claims Queue</span>
              <span className="count">{claims.length}</span>
            </div>
            <div className="queue-list">
              {claims.map((claim) => (
                <button
                  key={claim.index}
                  className={selected?.index === claim.index ? "qitem active" : "qitem"}
                  onClick={() => select(claim)}
                >
                  <span className={`tag ${claim.claim_object}`}>{claim.claim_object}</span>
                  <span className="qid">{claim.user_id}</span>
                  <span className="qmeta">{claim.image_ids.length} img</span>
                </button>
              ))}
            </div>
          </aside>

          <main className="panel detail">
            {selected ? (
              <>
                <div className="detail-head">
                  <div>
                    <div className="caseid">Claim · {selected.user_id}</div>
                    <span className={`tag ${selected.claim_object}`}>{selected.claim_object}</span>
                  </div>
                  <button
                    className="btn primary"
                    onClick={() => runVerification(selected)}
                    disabled={running}
                  >
                    {running ? (
                      <>
                        <span className="spinner" />
                        Reviewing
                      </>
                    ) : (
                      "Run verification"
                    )}
                  </button>
                </div>

                <section className="section">
                  <h3>Claim conversation</h3>
                  <div className="chat">
                    {parseTranscript(selected.user_claim).map((msg, i) => (
                      <div key={i} className={`bubble ${msg.role}`}>
                        <span className="speaker">{msg.speaker}</span>
                        <p>{msg.text}</p>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="section">
                  <h3>Submitted evidence</h3>
                  <div className="images">
                    {selected.image_paths.map((path, i) => (
                      <img key={path} src={imageUrl(path)} alt={selected.image_ids[i]} />
                    ))}
                  </div>
                </section>

                {prediction ? (
                  <section className="section">
                    <h3>Automated assessment</h3>
                    <div className="result">
                      {FIELDS.map(([key, label]) => (
                        <div className="row" key={key}>
                          <span className="k">{label}</span>
                          <span className="v">
                            {key === "claim_status" ? (
                              <span className={`badge ${prediction[key]}`}>
                                {(prediction[key] || "").replace(/_/g, " ")}
                              </span>
                            ) : (
                              prediction[key] || "-"
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </section>
                ) : null}
              </>
            ) : (
              <div className="empty">
                Select a claim from the queue to review its conversation, evidence, and run an
                automated assessment.
              </div>
            )}
          </main>
        </div>
      </div>

      <div className="genbar">
        <span className="genhint">
          {uploadFile
            ? `Will process the uploaded CSV: ${uploadFile.name}`
            : `Will process the loaded dataset (${source || "claims.csv"})`}
        </span>
        <button className="btn primary wide" onClick={generate} disabled={generating}>
          {generating ? (
            <>
              <span className="spinner" />
              Generating
            </>
          ) : (
            "Generate output.csv"
          )}
        </button>
      </div>
    </div>
  );
}
