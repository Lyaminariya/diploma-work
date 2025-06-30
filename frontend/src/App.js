import React, { useState } from 'react';
import DBSCANAnalysisPage from './components/DBSCANAnalysisPage';
import ApiBrowserPage from './components/APIBrowserPage';
import CSVUploadPage from './components/CSVUploadPage';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('csvUpload');

  return (
    <div className="App">
      <header className="App-header" style={{ backgroundColor: '#f0f0f0', padding: '10px 0', textAlign: 'center', marginBottom: '20px' }}>
        <nav>
          <button
            onClick={() => setCurrentPage('dbscan')}
            style={{background: currentPage === 'dbscan' ? '#e0e0e0' : 'white' }}
          >
            Анализ DBSCAN
          </button>
          <button
            onClick={() => setCurrentPage('apiBrowser')}
            style={{background: currentPage === 'apiBrowser' ? '#e0e0e0' : 'white' }}
          >
            API Браузер
          </button>
          <button
            onClick={() => setCurrentPage('csvUpload')}
            style={{background: currentPage === 'csvUpload' ? '#e0e0e0' : 'white' }}
          >
            Загрузка CSV
          </button>
        </nav>
      </header>
      <main style={{ padding: '0 20px' }}>
        {currentPage === 'dbscan' && <DBSCANAnalysisPage />}
        {currentPage === 'apiBrowser' && <ApiBrowserPage />}
        {currentPage === 'csvUpload' && <CSVUploadPage />}
      </main>
    </div>
  );
}

export default App;