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
    <main style={{
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "sans-serif",
      backgroundColor: "#f5f5f5",
      color: "#333",
    }}>
      <h1 style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>PPL C - Equitek</h1>
      <p style={{ fontSize: "1.2rem", color: "#666", marginBottom: "2rem" }}>Excel Generator by Kelompok 7</p>

      <div style={{
        backgroundColor: "#fff",
        padding: "1.5rem 2rem",
        borderRadius: "8px",
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
      }}>
        <h2 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Backend Status</h2>
        {error && <p style={{ color: "red" }}>❌ {error}</p>}
        {data ? (
          <p style={{ color: "green" }}>✅ {data.message}</p>
        ) : (
          !error && <p>Loading...</p>
        )}
      </div>
    </main>
  );
}