import { useEffect, useState } from "react";

const API = (import.meta.env.VITE_API_URL as string) || "";

type Claim = {
  user_id: string;
  claim_object: string;
  user_claim: string;
  image_ids: string[];
  image_paths: string[];
  labels: Record<string, string>;
};

export function App() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selected, setSelected] = useState<Claim | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetch(`${API}/api/claims?input=test`)
      .then((response) => response.json())
      .then((data) => setClaims(data.claims as Claim[]))
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <main>
      <h1>Evidence Review Dashboard</h1>
      {error ? <p role="alert">{error}</p> : null}
      <p>{claims.length} claims</p>
      <ul>
        {claims.map((claim) => (
          <li key={claim.user_id + claim.image_paths.join()}>
            <button onClick={() => setSelected(claim)}>
              {claim.claim_object} - {claim.user_id}
            </button>
          </li>
        ))}
      </ul>
      {selected ? (
        <section>
          <h2>
            {selected.claim_object} ({selected.user_id})
          </h2>
          <p>{selected.user_claim}</p>
        </section>
      ) : null}
    </main>
  );
}
