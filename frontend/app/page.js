'use client';

import { useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Home() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setSearched(false);

    try {
      const res = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Request failed (${res.status})`);
      }

      const data = await res.json();
      setResults(data.results);
      setSearched(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main>
      <h1>CVE Search</h1>
      <p className="subtitle">Search vulnerabilities using natural language</p>

      <form className="search-form" onSubmit={handleSubmit}>
        <input
          className="search-input"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "show me CVEs that involve remote code execution"'
        />
        <button className="search-btn" type="submit" disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {searched && (
        <p className="results-count">
          {results.length === 0
            ? 'No results found.'
            : `${results.length} result${results.length !== 1 ? 's' : ''} found`}
        </p>
      )}

      <div className="results">
        {results.map((cve) => (
          <div key={cve.cve_id} className="card">
            <div className="card-header">
              <span className="cve-id">{cve.cve_id}</span>
              {cve.score != null && (
                <span className="score-badge">
                  score {cve.score.toFixed(4)}
                </span>
              )}
            </div>
            <p className="description">{cve.description}</p>
            <div className="card-meta">
              <div className="meta-item">Published: <span>{cve.published?.slice(0, 10) ?? '—'}</span></div>
              <div className="meta-item">Status: <span>{cve.status ?? '—'}</span></div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
