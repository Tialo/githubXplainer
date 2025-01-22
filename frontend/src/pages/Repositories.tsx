import React, { useState, useEffect } from 'react';
import { getRepositories, initializeRepository } from '../api';
import { Repository } from '../types';
import { GitFork, Plus, Loader } from 'lucide-react';

export function Repositories() {
  const [owner, setOwner] = useState('');
  const [name, setName] = useState('');
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    fetchRepositories();
  }, []);

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

  const handleAddRepository = async () => {
    if (!owner || !name) {
      setError('Please enter both owner and repository name.');
      return;
    }
    
    setLoading(true);
    setError('');

    try {
      await initializeRepository(owner, name);
      await fetchRepositories();
      setOwner('');
      setName('');
    } catch (err) {
      setError('Failed to add repository. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="card p-6">
        {error && (
          <div className="bg-red-900/50 border border-red-800 text-red-200 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <label htmlFor="owner" className="block text-sm font-medium text-gray-300 mb-2">
              Repository Owner
            </label>
            <input
              type="text"
              id="owner"
              className="input-base w-full p-2"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="e.g., facebook"
            />
          </div>
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
              Repository Name
            </label>
            <input
              type="text"
              id="name"
              className="input-base w-full p-2"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., react"
            />
          </div>
        </div>

        <button
          onClick={handleAddRepository}
          disabled={loading}
          className="btn-primary w-full flex items-center justify-center gap-2 mb-8"
        >
          {loading ? (
            <>
              <Loader className="animate-spin" size={20} />
              Adding Repository...
            </>
          ) : (
            <>
              <Plus size={20} />
              Add Repository
            </>
          )}
        </button>

        <div>
          <h2 className="text-xl font-semibold mb-4 text-gray-100">Available Repositories</h2>
          <div className="space-y-2">
            {repositories.map((repo) => (
              <div
                key={`${repo.owner}/${repo.name}`}
                className="p-4 bg-gray-800/50 rounded-lg flex items-center gap-3 hover:bg-gray-800 transition-colors duration-200"
              >
                <GitFork className="text-gray-400" size={20} />
                <span className="text-gray-300">
                  {repo.owner}/{repo.name}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}