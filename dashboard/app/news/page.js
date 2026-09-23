// dashboard/app/news/page.js
"use client";

import { useEffect, useState } from "react";

function ArticleCard({ article }) {
  return (
    <div className="bg-white/10 backdrop-blur-lg rounded-xl border border-white/20 p-5 shadow-md hover:shadow-lg transition-shadow">
      <h2 className="text-xl font-semibold text-white mb-2">{article.title}</h2>
      <p className="text-sm text-white/80 mb-3 line-clamp-3">
        {article.summary || (article.content ? article.content.slice(0, 200) + "..." : "")}
      </p>
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-indigo-300 hover:text-indigo-200 underline"
      >
        Read full article →
      </a>
    </div>
  );
}

export default function NewsPage() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchNews() {
      try {
        const res = await fetch("/api/news/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setArticles(data.articles || []);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    fetchNews();
  }, []);

  return (
    <section className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-8 text-center">
          Route‑Related News
        </h1>
        {loading && (
          <p className="text-center text-white/70">Loading latest news...</p>
        )}
        {error && (
          <p className="text-center text-red-400">Failed to load news: {error}</p>
        )}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {articles.map((a, i) => (
            <ArticleCard key={i} article={a} />
          ))}
        </div>
      </div>
    </section>
  );
}
