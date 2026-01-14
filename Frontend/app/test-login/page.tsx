"use client";

import { useState } from "react";

export default function TestLoginPage() {
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setResult("");

    const form = e.currentTarget;
    const email = (form.elements.namedItem("email") as HTMLInputElement).value;
    const password = (form.elements.namedItem("password") as HTMLInputElement).value;

    console.log("Submitting:", { email, passwordLength: password.length });

    try {
      const res = await fetch("/api/test-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      setResult(JSON.stringify(data, null, 2));

      if (data.success) {
        // Redirect to dashboard
        window.location.href = "/admin/dashboard";
      }
    } catch (err: any) {
      setResult("Error: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: "40px", maxWidth: "400px", margin: "0 auto" }}>
      <h1>Test Login</h1>
      <form onSubmit={handleLogin}>
        <div style={{ marginBottom: "10px" }}>
          <label>Email:</label>
          <br />
          <input
            type="email"
            name="email"
            defaultValue="adam@saahomes.com"
            style={{ width: "100%", padding: "8px" }}
          />
        </div>
        <div style={{ marginBottom: "10px" }}>
          <label>Password:</label>
          <br />
          <input
            type="password"
            name="password"
            defaultValue="Vitzer0100!"
            style={{ width: "100%", padding: "8px" }}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          style={{ padding: "10px 20px", cursor: "pointer" }}
        >
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>

      {result && (
        <pre style={{ marginTop: "20px", background: "#f0f0f0", padding: "10px", overflow: "auto" }}>
          {result}
        </pre>
      )}
    </div>
  );
}
