import React, { useState, useEffect } from 'react';
import { getRepositories, searchRepository } from '../api';
import { Repository } from '../types';
import { Search as SearchIcon, Loader } from 'lucide-react';

export function Search() {
  const [query, setQuery] = useState('');
  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchRepositories = async () => {
      try {
        const repos = await getRepositories();
        setRepositories(repos);
        setError('');
      } catch (err) {
        setError('Failed to fetch repositories. Please try again later.');
        setRepositories([]);
      }
    };
    fetchRepositories();
  }, []);

  const handleSearch = async () => {
    if (!query || !selectedRepo) return;

    const [owner, name] = selectedRepo.split('/');
    setLoading(true);
    setError('');

    try {
      const response = await searchRepository(query, owner, name);
      setAnswer(response.summary);
    } catch (err) {
      setError('Failed to get response. Please try again.');
      setAnswer('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="card p-6 space-y-6">
        {error && (
          <div className="bg-red-900/50 border border-red-800 text-red-200 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="repository" className="block text-sm font-medium text-gray-300 mb-2">
            Select Repository
          </label>
          <select
            id="repository"
            className="input-base w-full p-2"
            value={selectedRepo}
            onChange={(e) => setSelectedRepo(e.target.value)}
          >
            {repositories.map((repo) => (
              <option key={`${repo.owner}/${repo.name}`} value={`${repo.owner}/${repo.name}`}>
                {repo.owner}/{repo.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="query" className="block text-sm font-medium text-gray-300 mb-2">
            Your Question
          </label>
          <div className="relative">
            <textarea
              id="query"
              className="input-base w-full p-3 pl-10 h-32"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask anything about the repository..."
            />
            <SearchIcon className="absolute left-3 top-3 text-gray-500" size={20} />
          </div>
          <div className="mt-1 text-sm text-gray-500">
            Press <kbd className="px-2 py-1 bg-gray-800 rounded text-xs">⌘K</kbd> to focus
          </div>
        </div>

        <button
          onClick={handleSearch}
          disabled={loading}
          className="btn-primary w-full flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader className="animate-spin" size={20} />
              Searching...
            </>
          ) : (
            <>
              <SearchIcon size={20} />
              Ask
            </>
          )}
        </button>

        {answer && (
          <div className="mt-6">
            <h3 className="text-lg font-medium text-gray-100 mb-2">Answer:</h3>
            <div className="bg-gray-800/50 rounded-lg p-4">
              <p className="text-gray-300 whitespace-pre-wrap">{answer}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}