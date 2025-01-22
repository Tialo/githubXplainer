import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navigation } from './components/Navigation';
import { Search } from './pages/Search';
import { Repositories } from './pages/Repositories';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950">
        <Navigation />
        <Routes>
          <Route path="/" element={<Search />} />
          <Route path="/repositories" element={<Repositories />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;