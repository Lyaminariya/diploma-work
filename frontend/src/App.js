import React, { useState } from 'react';
import DBSCANAnalysisPage from './components/DBSCANAnalysisPage';
import ApiBrowserPage from './components/APIBrowserPage';
import PlayerComparisonPage from './components/PlayerComparisonPage';
import CSVUploadPage from './components/CSVUploadPage';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('playerComparison');

  const renderPage = () => {
    switch (currentPage) {
      case 'csvUpload':
        return <CSVUploadPage />;
      case 'dbscan':
        return <DBSCANAnalysisPage />;
      case 'apiBrowser':
        return <ApiBrowserPage />;
      case 'playerComparison':
        return <PlayerComparisonPage />;
      default:
        return <PlayerComparisonPage />;
    }
  };
  
  const getButtonStyle = (pageName) => ({
      margin: '0 5px', 
      padding: '8px 15px', 
      cursor: 'pointer', 
      border: '1px solid #ccc',
      borderRadius: '4px',
      background: currentPage === pageName ? '#e0e0e0' : 'white' 
  });

  return (
    <div className="App">
      <header className="App-header" style={{ backgroundColor: '#f0f0f0', padding: '10px 0', textAlign: 'center', marginBottom: '20px' }}>
        <nav>
          <button onClick={() => setCurrentPage('playerComparison')} style={getButtonStyle('playerComparison')}>
            Сравнение игроков
          </button>
          <button onClick={() => setCurrentPage('dbscan')} style={getButtonStyle('dbscan')}>
            Анализ DBSCAN
          </button>
          <button onClick={() => setCurrentPage('csvUpload')} style={getButtonStyle('csvUpload')}>
            Загрузка CSV
          </button>

          <button onClick={() => setCurrentPage('apiBrowser')} style={getButtonStyle('apiBrowser')}>
            API Браузер
          </button>
        </nav>
      </header>
      <main style={{ padding: '0 20px' }}>
        {renderPage()}
      </main>
    </div>
  );
}

export default App;