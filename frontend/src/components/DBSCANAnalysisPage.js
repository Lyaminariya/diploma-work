import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Scatter } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    LinearScale,
    PointElement,
    LineElement,
    Tooltip,
    Legend,
    Title,
} from 'chart.js';
import styles from './DBSCANAnalysisPage.module.css';
import useAvailableGames from '../hooks/useAvailableGames';

ChartJS.register(
    LinearScale,
    PointElement,
    LineElement,
    Tooltip,
    Legend,
    Title
);

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const ITEMS_PER_PAGE = 15; // lля пагинации списка игроков в кластерах

const DBSCANAnalysisPage = () => {
    const {
        games: availableGames,
        selectedGame: gameName,
        setSelectedGame: setGameName,
        gamesLoading,
        gamesError
    } = useAvailableGames('valorant'); // valorant как игра по умолчанию

    const [eps, setEps] = useState('1.5');
    const [minSamples, setMinSamples] = useState('5');
    const [minMatches, setMinMatches] = useState('5');

    const [chartData, setChartData] = useState(null);
    const [analysisDetails, setAnalysisDetails] = useState(null);
    const [allClusteredPlayers, setAllClusteredPlayers] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [visiblePlayersCount, setVisiblePlayersCount] = useState({});

    const fetchData = useCallback(async () => {
        if (!gameName || gamesLoading) { // не запускаем, если игра не выбрана или список игр еще грузится
            if (gamesLoading) console.log("DBSCAN: Ожидание загрузки списка игр...");
            else if (!gameName) console.log("DBSCAN: Игра не выбрана.");
            setChartData(null); setAnalysisDetails(null); setAllClusteredPlayers(null);
            return;
        }

        setIsLoading(true);
        setError(null);
        setChartData(null);
        setAnalysisDetails(null);
        setAllClusteredPlayers(null);
        setVisiblePlayersCount({});

        try {
            const params = new URLSearchParams({
                game_name: gameName,
                eps: eps,
                min_samples: minSamples,
                min_matches: minMatches,
            });
            const response = await axios.get(`${API_BASE_URL}/api/stats/dbscan-analysis/?${params.toString()}`);
            const result = response.data;

            if (result.scatter_plot_data && result.scatter_plot_data.length > 0) {
                const scatterData = result.scatter_plot_data;
                const uniqueClusters = [...new Set(scatterData.map(d => d.cluster))].sort((a, b) => a - b);
                const colors = ['rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)',
                                'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
                                'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)'];
                const noiseColor = 'rgba(128, 128, 128, 0.5)';

                const datasets = uniqueClusters.map((clusterId, index) => {
                    const pointsInCluster = scatterData.filter(d => d.cluster === clusterId);
                    return {
                        label: clusterId === -1 ? `Шум (${pointsInCluster.length})` : `Кластер ${clusterId} (${pointsInCluster.length})`,
                        data: pointsInCluster.map(p => ({ x: p.x, y: p.y, username: p.username })),
                        backgroundColor: clusterId === -1 ? noiseColor : colors[index % colors.length],
                        borderColor: clusterId === -1 ? noiseColor.replace('0.5','1') : colors[index % colors.length].replace('0.7','1'),
                        pointRadius: clusterId === -1 ? 3 : 5,
                        pointHoverRadius: clusterId === -1 ? 4 : 7,
                    };
                });
                setChartData({ datasets });
            } else {
                 setChartData(null);
            }

            setAnalysisDetails(result.analysis_details);
            setAllClusteredPlayers(result.clustered_players);

            if (result.clustered_players) {
                const initialCounts = {};
                Object.keys(result.clustered_players).forEach(clusterId => {
                    initialCounts[clusterId] = ITEMS_PER_PAGE;
                });
                setVisiblePlayersCount(initialCounts);
            }

        } catch (err) {
            console.error("Ошибка при загрузке данных DBSCAN:", err.response || err.message);
            setError(err.response?.data?.error || err.response?.data?.detail || err.message || 'Произошла ошибка при загрузке данных.');
            setChartData(null);
            setAnalysisDetails(null);
            setAllClusteredPlayers(null);
        } finally {
            setIsLoading(false);
        }
    }, [gameName, eps, minSamples, minMatches, gamesLoading]); // gamesLoading в зависимостях

    useEffect(() => {
        if (gameName && !gamesLoading) {
             fetchData();
        }
    }, [fetchData, gameName, gamesLoading]);


    const handleSubmit = (event) => {
        event.preventDefault();
        fetchData();
    };

    const handleShowMore = (clusterId) => {
        setVisiblePlayersCount(prevCounts => ({
            ...prevCounts,
            [clusterId]: (prevCounts[clusterId] || 0) + ITEMS_PER_PAGE
        }));
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            title: {
                display: true,
                text: analysisDetails ? `DBSCAN: ${analysisDetails.game_name} (eps: ${analysisDetails.eps}, samples: ${analysisDetails.min_samples}, matches: ${analysisDetails.min_matches_per_player || minMatches})` : 'DBSCAN Результаты'
            },
            legend: { position: 'top', },
            tooltip: {
                callbacks: {
                    label: function (context) {
                        let label = context.dataset.label || '';
                        if (label) { label += ': '; }
                        const pointData = context.dataset.data[context.dataIndex];
                        if (pointData && pointData.username) {
                            label += `${pointData.username} (x: ${context.parsed.x?.toFixed(2)}, y: ${context.parsed.y?.toFixed(2)})`;
                        } else if (context.parsed?.x !== undefined) {
                            label += `(x: ${context.parsed.x?.toFixed(2)}, y: ${context.parsed.y?.toFixed(2)})`;
                        }
                        return label;
                    }
                }
            }
        },
        scales: {
            x: {
                type: 'linear', position: 'bottom',
                title: { display: true, text: analysisDetails?.x_axis_label || 'Ось X' }
            },
            y: {
                title: { display: true, text: analysisDetails?.y_axis_label || 'Ось Y' }
            }
        }
    };

    const renderTableCell = (value, toFixedDigits = 2) => {
        if (value === null || value === undefined || Number.isNaN(value)) return '-';
        if (typeof value === 'number') return value.toFixed(toFixedDigits);
        return value;
    };

    const tableColumns = analysisDetails?.features_used
        ? [
            { key: 'player_id', label: 'DB ID' },
            { key: 'puuid', label: 'PUUID'},
            { key: 'username', label: 'Username' },
            ...analysisDetails.features_used.map(feature => ({
                key: feature,
                label: feature.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
            }))
          ]
        : [
            { key: 'player_id', label: 'DB ID' },
            { key: 'puuid', label: 'PUUID'},
            { key: 'username', label: 'Username' }, { key: 'avg_kills', label: 'Avg Kills' },
            { key: 'avg_deaths', label: 'Avg Deaths' }, { key: 'avg_kda', label: 'Avg KDA' },
          ];


    return (
        <div className={styles.pageContainer}>
            <h1 className={styles.pageTitle}>Анализ кластеризации DBSCAN</h1>
            <form onSubmit={handleSubmit} className={styles.form}>
                <div className={styles.formGroup}>
                    <label htmlFor="gameNameDBSCAN">Игра:</label>
                    {gamesLoading && <p>Загрузка списка игр...</p>}
                    {gamesError && <p className={styles.errorMessage}>{gamesError}</p>}
                    {!gamesLoading && !gamesError && availableGames.length > 0 && (
                        <select
                            id="gameNameDBSCAN"
                            value={gameName}
                            onChange={(e) => setGameName(e.target.value)}
                            disabled={isLoading} // блокируем во время анализа
                        >
                            {availableGames.map(game => (
                                <option key={game.value} value={game.value}>
                                    {game.label}
                                </option>
                            ))}
                        </select>
                    )}
                     {!gamesLoading && !gamesError && availableGames.length === 0 && (
                        <p>Нет доступных игр для анализа.</p>
                    )}
                </div>
                <div className={styles.formGroup}>
                    <label htmlFor="eps">Eps:</label>
                    <input type="number" step="0.01" id="eps" value={eps} onChange={(e) => setEps(e.target.value)} />
                </div>
                <div className={styles.formGroup}>
                    <label htmlFor="minSamples">Min Samples:</label>
                    <input type="number" id="minSamples" value={minSamples} onChange={(e) => setMinSamples(e.target.value)} />
                </div>
                <div className={styles.formGroup}>
                    <label htmlFor="minMatches">Min Matches (на игрока):</label>
                    <input type="number" id="minMatches" value={minMatches} onChange={(e) => setMinMatches(e.target.value)} />
                </div>
                <button type="submit" disabled={isLoading || gamesLoading || !gameName} className={styles.submitButton}>
                    {isLoading ? 'Анализ...' : 'Анализировать'}
                </button>
            </form>

            {error && <p className={styles.errorMessage}>Ошибка анализа: {error}</p>}

            {analysisDetails && (
                <div className={styles.analysisDetails}>
                    <h3>Детали анализа:</h3>
                    <p><strong>Игра:</strong> {analysisDetails.game_name}</p>
                    <p><strong>Eps:</strong> {analysisDetails.eps}, <strong>Min Samples:</strong> {analysisDetails.min_samples}</p>
                    <p><strong>Мин. матчей на игрока:</strong> {analysisDetails.min_matches_per_player || minMatches}</p>
                    {analysisDetails.message && <p><strong>Сообщение от сервера:</strong> {analysisDetails.message}</p>}
                    <p><strong>Игроков проанализировано:</strong> {analysisDetails.total_players_analyzed}</p>
                    <p><strong>Найдено кластеров (без шума):</strong> {analysisDetails.clusters_found}</p>
                    <p><strong>Точек шума:</strong> {analysisDetails.noise_points}</p>
                    <p><strong>Использованные фичи для кластеризации:</strong> {analysisDetails.features_used?.join(', ')}</p>
                </div>
            )}

            {chartData && analysisDetails && analysisDetails.total_players_analyzed > 0 && (
                <div className={styles.chartContainer}>
                    <Scatter data={chartData} options={chartOptions} />
                </div>
            )}
            {!isLoading && analysisDetails && analysisDetails.total_players_analyzed === 0 && (
                 <p className={styles.noDataText}>Нет данных для отображения графика (0 игроков проанализировано для выбранных параметров).</p>
            )}
            {!chartData && !isLoading && analysisDetails && analysisDetails.total_players_analyzed > 0 && (
                <p className={styles.noDataText}>Нет данных для отображения графика (scatter_plot_data не получено или пустое).</p>
            )}


            {allClusteredPlayers && Object.keys(allClusteredPlayers).length > 0 && (
                <div>
                    <h2 className={styles.clustersSectionTitle}>Игроки по кластерам:</h2>
                    {Object.entries(allClusteredPlayers)
                        .sort(([a,],[b,]) => parseInt(a) - parseInt(b))
                        .map(([clusterId, players]) => (
                        <div key={clusterId} className={styles.clusterBlock}>
                            <h3 className={`${styles.clusterTitle} ${clusterId === '-1' || clusterId === -1 ? styles.clusterTitleNoise : ''}`}>
                                {clusterId === '-1' || clusterId === -1 ? `Шум (Noise) - ${players.length} игроков` : `Кластер ${clusterId} - ${players.length} игроков`}
                            </h3>
                            {players.length > 0 ? (
                                <>
                                    <table className={styles.playersTable}>
                                        <thead>
                                            <tr>
                                                {tableColumns.map(col => (
                                                    <th key={col.key}>{col.label}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {players.slice(0, visiblePlayersCount[clusterId] || ITEMS_PER_PAGE).map(player => (
                                                <tr key={player.player_id || player.puuid}> {}
    {tableColumns.map(col => (
        <td key={`${player.player_id || player.puuid}-${col.key}`}>
            {renderTableCell(player[col.key],)}
        </td>
    ))}
</tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    {players.length > (visiblePlayersCount[clusterId] || ITEMS_PER_PAGE) && (
                                        <button onClick={() => handleShowMore(clusterId)} className={styles.showMoreButton}>
                                            Показать еще {Math.min(ITEMS_PER_PAGE, players.length - (visiblePlayersCount[clusterId] || ITEMS_PER_PAGE))}
                                        </button>
                                    )}
                                </>
                            ) : (
                                <p>В этом кластере нет игроков.</p>
                            )}
                        </div>
                    ))}
                </div>
            )}
            {!isLoading && (!allClusteredPlayers || Object.keys(allClusteredPlayers).length === 0) && analysisDetails && analysisDetails.total_players_analyzed > 0 &&(
                <p className={styles.noDataText}>Нет данных о кластеризованных игроках.</p>
            )}
            {isLoading && <p className={styles.loadingText}>Загрузка данных анализа...</p>}
        </div>
    );
};

export default DBSCANAnalysisPage;