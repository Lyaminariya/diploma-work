import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Radar } from 'react-chartjs-2';
import styles from './PlayerComparisonPage.module.css';

import {
    Chart as ChartJS,
    RadialLinearScale,
    PointElement,
    LineElement,
    Filler,
    Tooltip,
    Legend,
    Title,
} from 'chart.js';

ChartJS.register(
    RadialLinearScale,
    PointElement,
    LineElement,
    Filler,
    Tooltip,
    Legend,
    Title
);

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const normalize = (value, min, max) => {
    if (max === min) return 0.5;
    const boundedValue = Math.max(min, Math.min(value, max));
    return (boundedValue - min) / (max - min);
};

const PlayerComparisonPage = () => {
    const [gameName, setGameName] = useState('valorant');
    const [searchType, setSearchType] = useState('puuid');
    const [playerIdentifier, setPlayerIdentifier] = useState('');
    const [comparisonRank, setComparisonRank] = useState('');

    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const [analysisData, setAnalysisData] = useState(null);
    const [chartData, setChartData] = useState(null);

    const performFetch = async (currentIdentifier, currentRank) => {
        if (!currentIdentifier) return;

        setIsLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                game_name: gameName,
                comparison_rank: currentRank,
            });
            if (searchType === 'puuid') {
                params.append('puuid', currentIdentifier);
            } else {
                params.append('username', currentIdentifier);
            }

            const response = await axios.get(`${API_BASE_URL}/api/stats/player-comparison/?${params.toString()}`);
            setAnalysisData(response.data);

            if (!currentRank && response.data?.target_player?.rank) {
                setComparisonRank(response.data.target_player.rank);
            }

        } catch (err) {
            console.error("API Error:", err);
            setError(err.response?.data?.error || err.message || 'Произошла ошибка');
            setAnalysisData(null);
            setChartData(null);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (analysisData && analysisData.target_player && comparisonRank) {
             performFetch(playerIdentifier, comparisonRank);
        }
    }, [comparisonRank]);

    useEffect(() => {
        if (!analysisData) {
            setChartData(null);
            return;
        }
        const { target_player, comparison_group } = analysisData;
        const boundaries = comparison_group?.stats_boundaries;
        if (!target_player?.stats || !boundaries) {
            setChartData(null);
            return;
        }
        const statsKeys = Object.keys(target_player.stats);
        const labels = statsKeys.map(key => {
            if (key === 'avg_deaths') return 'Deaths (inverted)';
            return key.replace(/avg_/g, '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        });
        const targetStatsNormalized = [];
        const comparisonStatsNormalized = [];
        statsKeys.forEach(key => {
            const boundary = boundaries[key];
            if (!boundary) return;
            const playerValue = target_player.stats[key];
            const groupAvgValue = boundary.avg;
            const normalizedPlayer = normalize(playerValue, boundary.min, boundary.max);
            const normalizedGroup = normalize(groupAvgValue, boundary.min, boundary.max);
            if (key === 'avg_deaths') {
                targetStatsNormalized.push(1 - normalizedPlayer);
                comparisonStatsNormalized.push(1 - normalizedGroup);
            } else {
                targetStatsNormalized.push(normalizedPlayer);
                comparisonStatsNormalized.push(normalizedGroup);
            }
        });
        setChartData({
            labels,
            datasets: [
                {
                    label: `${target_player.username} (Last ${target_player.matches_analyzed})`,
                    data: targetStatsNormalized,
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 2,
                },
                {
                    label: `Avg. Rank: ${comparison_group.rank} (${comparison_group.player_count} players)`,
                    data: comparisonStatsNormalized,
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                },
            ],
        });
    }, [analysisData]);

    const handleSubmit = (e) => {
        e.preventDefault();
        setAnalysisData(null);
        setChartData(null);
        performFetch(playerIdentifier, comparisonRank);
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {r: {angleLines: {display: true}, min: 0, max: 1, ticks: {stepSize: 0.2, backdropColor: 'rgba(255, 255, 255, 0.75)',}, pointLabels: {font: {size: 12,}},}},
        plugins: {legend: {position: 'top'}, title: {display: true, text: 'Сравнение производительности игрока (нормализованные значения)'}}
    };

    return (
        <div className={styles.pageContainer}>
            <h1 className={styles.pageTitle}>Сравнительный анализ игрока</h1>

            <form onSubmit={handleSubmit} className={styles.form}>
                <div className={styles.formGroup}>
                    <label htmlFor="gameName">Игра:</label>
                    <select id="gameName" value={gameName} onChange={(e) => setGameName(e.target.value)}>
                        <option value="valorant">Valorant</option>
                        <option value="pubg">PUBG</option>
                    </select>
                </div>
                <div className={styles.formGroup}>
                    <label>Тип поиска:</label>
                    <select value={searchType} onChange={e => setSearchType(e.target.value)}>
                        <option value="puuid">Игровой ID (PUUID)</option>
                        <option value="username">Никнейм</option>
                    </select>
                </div>
                <div className={styles.formGroup}>
                    <label htmlFor="playerIdentifier">Игрок:</label>
                    <input
                        type="text" // PUUID это строка, тип всегда text
                        id="playerIdentifier"
                        value={playerIdentifier}
                        onChange={(e) => setPlayerIdentifier(e.target.value)}
                        placeholder={searchType === 'puuid' ? 'Введите игровой ID (PUUID)' : 'Введите никнейм'}
                    />
                </div>
                <button type="submit" disabled={isLoading || !playerIdentifier} className={styles.submitButton}>
                    {isLoading ? 'Анализ...' : 'Анализировать'}
                </button>
            </form>

            {isLoading && !analysisData && <p className={styles.loadingText}>Загрузка данных...</p>}
            {error && <p className={styles.errorMessage}>Ошибка: {error}</p>}
            {analysisData && (
                <div className={styles.resultsContainer}>
                    <div className={styles.statsGrid}>
                        <div className={styles.statsCard}>
                            <h3>{analysisData.target_player.username} <span>({analysisData.target_player.rank || 'N/A'})</span></h3>
                            <p>Средние показатели за последние {analysisData.target_player.matches_analyzed} матчей:</p>
                            <ul>{analysisData.target_player.stats && Object.entries(analysisData.target_player.stats).map(([key, value]) => (<li key={key}><strong>{key.replace(/avg_/g,'').replace(/_/g, ' ')}:</strong> {value}</li>))}</ul>
                        </div>
                        <div className={styles.chartContainer}>
                            {chartData ? (<Radar key={`${analysisData.target_player.id}-${analysisData.comparison_group.rank || 'none'}`} data={chartData} options={chartOptions}/>) : (isLoading ? <p>Обновление диаграммы...</p> : <p>Нет данных для построения диаграммы.</p>)}
                        </div>
                        <div className={styles.statsCard}>
                             <h3>Сравнение с рангом</h3>
                             <div className={styles.formGroup}><label>Ранг для сравнения:</label><select value={comparisonRank} onChange={e => setComparisonRank(e.target.value)} disabled={!analysisData.available_ranks.length}><option value="">Выберите ранг</option>{analysisData.available_ranks.map(rank => (<option key={rank} value={rank}>{rank}</option>))}</select></div>
                             {analysisData.comparison_group.stats_boundaries ? (<>
                                    <p>Средние показатели для {analysisData.comparison_group.player_count} игроков ранга "{analysisData.comparison_group.rank}":</p>
                                    <ul>{Object.entries(analysisData.comparison_group.stats_boundaries).map(([key, value]) => (<li key={key}><strong>{key.replace(/avg_/g,'').replace(/_/g, ' ')}:</strong> {value.avg}</li>))}</ul>
                                </>) : (<p>Выберите ранг для отображения сравнительной статистики.</p>)}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default PlayerComparisonPage;