"use client";
import { useEffect, useState } from "react";
import { getHealth } from "@/services/health";

export default function Home() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <main style={{ padding: "2rem" }}>
      <h1>Excel Generator</h1>
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      {data ? (
        <pre>{JSON.stringify(data, null, 2)}</pre>
      ) : (
        <p>Loading...</p>
      )}
    </main>
  );
}