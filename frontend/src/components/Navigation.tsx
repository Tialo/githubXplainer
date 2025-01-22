import React from 'react';
import { NavLink } from 'react-router-dom';
import { Search, GitFork } from 'lucide-react';

export function Navigation() {
  return (
    <nav className="bg-gray-900 border-b border-gray-800 py-4">
      <div className="container mx-auto px-4">
        <div className="flex items-center space-x-8">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `flex items-center space-x-2 text-gray-400 hover:text-gray-100 transition-colors duration-200 ${
                isActive ? 'text-blue-400 hover:text-blue-300' : ''
              }`
            }
          >
            <Search size={20} />
            <span>Ask githubXplainer</span>
          </NavLink>
          <NavLink
            to="/repositories"
            className={({ isActive }) =>
              `flex items-center space-x-2 text-gray-400 hover:text-gray-100 transition-colors duration-200 ${
                isActive ? 'text-blue-400 hover:text-blue-300' : ''
              }`
            }
          >
            <GitFork size={20} />
            <span>Repositories</span>
          </NavLink>
        </div>
      </div>
    </nav>
  );
}