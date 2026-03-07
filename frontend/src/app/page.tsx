"use client";

import { useEffect, useState } from "react";
import { getAbout, AboutResponse } from "@/services/about";
import { getHealth } from "@/services/health";
import { getMembers, MembersResponse } from "@/services/members";
import LLMClient from "@/components/LLMClient";

interface HealthResponse {
  status: string;
  message: string;
}

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [about, setAbout] = useState<AboutResponse | null>(null);
  const [members, setMembers] = useState<MembersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch((err) => setError(err.message));
    getAbout().then(setAbout).catch((err) => setError(err.message));
    getMembers().then(setMembers).catch((err) => setError(err.message));
  }, []);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "sans-serif",
        backgroundColor: "#f5f5f5",
        color: "#333",
        padding: "2rem 1rem",
      }}
    >
      <h1 style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>PPL C - Equitek</h1>
      <p style={{ fontSize: "1.2rem", color: "#666", marginBottom: "2rem" }}>Excel Generator</p>

      <div
        style={{
          backgroundColor: "#fff",
          padding: "1.5rem 2rem",
          borderRadius: "8px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          marginBottom: "1rem",
          width: "100%",
          maxWidth: "720px",
        }}
      >
        <h2 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Backend Status</h2>
        {error && (
          <p style={{ color: "red" }}>
            Error: {error}
          </p>
        )}
        {health ? <p style={{ color: "green" }}>OK: {health.message}</p> : !error && <p>Loading...</p>}
      </div>

      {about && (
        <div
          style={{
            backgroundColor: "#fff",
            padding: "1.5rem 2rem",
            borderRadius: "8px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            marginBottom: "1rem",
            width: "100%",
            maxWidth: "720px",
          }}
        >
          <h2 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>About</h2>
          <p>Team: {about.team}</p>
          <p>Project: {about.project}</p>
        </div>
      )}

      {members && (
        <div
          style={{
            backgroundColor: "#fff",
            padding: "1.5rem 2rem",
            borderRadius: "8px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            width: "100%",
            maxWidth: "720px",
          }}
        >
          <h2 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>{members.group}</h2>
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {members.members.map((member) => (
              <li key={member.npm} style={{ marginBottom: "0.4rem" }}>
                {member.npm} - {member.name}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        style={{
          backgroundColor: "#fff",
          padding: "1.5rem 2rem",
          borderRadius: "8px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
          marginTop: "1rem",
          width: "100%",
          maxWidth: "720px",
        }}
      >
        <h2 style={{ fontSize: "1rem", marginBottom: "0.75rem" }}>LLM Generate JSON</h2>
        <LLMClient />
      </div>
    </main>
  );
}
