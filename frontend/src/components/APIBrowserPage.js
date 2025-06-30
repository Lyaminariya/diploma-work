import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import styles from './APIBrowserPage.module.css';
import useAvailableGames from '../hooks/useAvailableGames';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const ITEMS_PER_PAGE = 10;

const ApiBrowserPage = () => {
    const {
        games: availableGames,
        selectedGame: gameName,
        setSelectedGame: setGameName,
        gamesLoading,
        gamesError
    } = useAvailableGames('valorant'); // valorant как игра по умолчанию

    const [puuid, setPuuid] = useState('');
    const [username, setUsername] = useState('');
    const [gameMatchIdForSearch, setGameMatchIdForSearch] = useState('');
    const [statPlayerPuuid, setStatPlayerPuuid] = useState('');
    const [statGameMatchId, setStatGameMatchId] = useState('');
    const [playerHistoryPuuid, setPlayerHistoryPuuid] = useState('');

    const [results, setResults] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const [listType, setListType] = useState('');
    const [listItems, setListItems] = useState([]);
    const [listOffset, setListOffset] = useState(0);
    const [listHasMore, setListHasMore] = useState(false);
    const [currentListPlayerPuuid, setCurrentListPlayerPuuid] = useState(null);

    const fetchData = useCallback(async (endpoint, params = {}, isPlayerHistory = false, forPlayerPuuid = null) => {
        setIsLoading(true);
        setError(null);
        const isPaginatedListEndpoint =
            (endpoint === '/api/players/' && params.limit !== undefined) ||
            (endpoint === '/api/matches/' && params.limit !== undefined) ||
            isPlayerHistory;
        const queryParams = new URLSearchParams(params);
        const fullUrl = `${API_BASE_URL}${endpoint}?${queryParams.toString()}`;

        if (isPaginatedListEndpoint) {
            setResults(null);
            let newListType = '';
            if (endpoint === '/api/players/') newListType = 'players';
            else if (endpoint === '/api/matches/') newListType = 'matches';
            else if (isPlayerHistory) newListType = 'playerMatchHistory';

            if (listType !== newListType || (isPlayerHistory && currentListPlayerPuuid !== forPlayerPuuid) || params.offset === 0) {
                setListItems([]);
                setListOffset(0);
                setListHasMore(false);
                if (isPlayerHistory) {
                    setCurrentListPlayerPuuid(forPlayerPuuid);
                } else {
                    setCurrentListPlayerPuuid(null);
                }
            }
            setListType(newListType);
        } else {
            setListItems([]);
            setListOffset(0);
            setListHasMore(false);
            setListType('');
            setResults(null);
            setCurrentListPlayerPuuid(null);
        }
        try {
            const response = await axios.get(fullUrl);
            if (isPaginatedListEndpoint) {
                if (response.data.results) {
                    setListItems(prevItems => (params.offset > 0 ? [...prevItems, ...response.data.results] : response.data.results));
                    setListHasMore(response.data.next !== null);
                    setListOffset(prevCurrentOffset => (params.offset > 0 ? prevCurrentOffset : 0) + response.data.results.length);
                } else {
                    setListItems(response.data);
                    setListHasMore(false);
                    setListOffset(response.data.length);
                }
            } else {
                 setResults(response.data);
            }
        } catch (err) {
            console.error("API Error:", err.response || err.message, "URL:", fullUrl);
            setError(err.response?.data?.detail || err.response?.data?.error || err.message || 'Произошла ошибка');
            setResults(null);
            setListItems([]);
            setListOffset(0);
            setListHasMore(false);
            setCurrentListPlayerPuuid(null);
        } finally {
            setIsLoading(false);
        }
    }, [listType, currentListPlayerPuuid, API_BASE_URL]);

    const handleGetPlayers = (isNextPage = false) => {
        const currentOffset = isNextPage ? listOffset : 0;
        fetchData('/api/players/', { game_name: gameName, limit: ITEMS_PER_PAGE, offset: currentOffset });
    };
    const handleGetMatches = (isNextPage = false) => {
        const currentOffset = isNextPage ? listOffset : 0;
        fetchData('/api/matches/', { game_name: gameName, limit: ITEMS_PER_PAGE, offset: currentOffset });
    };
    const handleGetPlayerMatchHistory = (isNextPage = false) => {
        if (!playerHistoryPuuid) {
            setError("Введите PUUID игрока для получения истории матчей.");
            setResults(null); setListItems([]); return;
        }
        const currentOffset = isNextPage && currentListPlayerPuuid === playerHistoryPuuid ? listOffset : 0;
        fetchData('/api/players/match-history/', { player_puuid: playerHistoryPuuid, game_name: gameName, limit: ITEMS_PER_PAGE, offset: currentOffset }, true, playerHistoryPuuid);
    };
    const renderListItem = (item, type) => {
         if (type === 'players') {
            return (
                <div key={item.puuid || item.id} className={styles.itemCard}>
                    <p><strong>Username:</strong> {item.username || 'N/A'} | <strong>PUUID:</strong> {item.puuid}</p>
                    <p><strong>Game:</strong> {item.game_name_display} ({item.game_name})</p>
                    <p><strong>Rank:</strong> {item.rank || 'N/A'}</p>
                </div>
            );
        }
        if (type === 'matches') {
            return (
                <div key={item.game_match_id || item.id} className={styles.itemCard}>
                    <p><strong>Game Match ID:</strong> {item.game_match_id}</p>
                    <p><strong>Game:</strong> {item.game_name_display} ({item.game_name})</p>
                    <p><strong>Map:</strong> {item.map_name || 'N/A'} | <strong>Mode:</strong> {item.game_mode || 'N/A'}</p>
                    <p><strong>Timestamp:</strong> {item.match_timestamp ? new Date(item.match_timestamp).toLocaleString() : 'N/A'}</p>
                    <p><strong>Ranked:</strong> {item.is_ranked === null ? 'N/A' : (item.is_ranked ? 'Yes' : 'No')}</p>
                </div>
            );
        }
        if (type === 'playerMatchHistory') {
            const match = item.match_info;
            if (!match) return <div key={item.id} className={styles.itemCard}><p>Ошибка: нет информации о матче</p></div>;
            return (
                <div key={item.id} className={styles.itemCard}>
                    <h4>Матч: {match.game_match_id} ({match.game_name_display})</h4>
                    <p><strong>Карта:</strong> {match.map_name || 'N/A'} | <strong>Режим:</strong> {match.game_mode || 'N/A'}</p>
                    <p><strong>Время:</strong> {match.match_timestamp ? new Date(match.match_timestamp).toLocaleString() : 'N/A'}</p>
                    <p><strong>Результат:</strong> {item.won_match ? 'Победа' : 'Поражение'}</p>
                    <p><strong>K/D/A:</strong> {item.kills}/{item.deaths}/{item.assists} (KDA: {item.kda?.toFixed(2)})</p>
                    <p><strong>Урон:</strong> {item.damage_dealt}</p>
                     {item.game_name === 'valorant' && (
                        <>
                            <p><strong>HS%:</strong> {item.headshot_rate?.toFixed(1)}%</p>
                            <p><strong>Навыки:</strong> {item.skills_used}, <strong>Ульты:</strong> {item.ultimates_used}</p>
                        </>
                    )}
                    {item.game_name === 'pubg' && (
                        <>
                            <p><strong>HS (rate):</strong> {item.headshot_rate?.toFixed(1)}%</p>
                            <p><strong>Бусты:</strong> {item.boosts_used}, <strong>Хилы:</strong> {item.heals_used}</p>
                        </>
                    )}
                    {item.game_name === 'cs2' && item.unique_abilities_used !== undefined && (
                         <p><strong>Исп. способностей:</strong> {item.unique_abilities_used}</p>
                    )}
                </div>
            );
        }
        return null;
    };


    return (
        <div className={styles.pageContainer}>
            <h1 className={styles.pageTitle}>API Браузер</h1>

            <div className={styles.section}>
                <h2 className={styles.sectionTitle}>Общий фильтр</h2>
                <div className={styles.formGroup} style={{ marginBottom: '20px', width:'auto' }}>
                    <label htmlFor="gameFilter">Выберите игру:</label>
                    {gamesLoading && <p>Загрузка списка игр...</p>}
                    {gamesError && <p className={styles.errorMessage}>{gamesError}</p>}
                    {!gamesLoading && !gamesError && (
                        <select
                            id="gameFilter"
                            value={gameName}
                            onChange={(e) => setGameName(e.target.value)}
                        >
                            {availableGames.map(game => (
                                <option key={game.value} value={game.value}>
                                    {game.label}
                                </option>
                            ))}
                        </select>
                    )}
                </div>
            </div>
            <div className={styles.section}>
                <h2 className={styles.sectionTitle}>Игроки</h2>
                <form onSubmit={(e) => { e.preventDefault(); handleGetPlayers(); }} className={styles.form}>
                    <button type="submit" disabled={isLoading || gamesLoading} className={styles.submitButton}>
                        {isLoading && listType === 'players' && listOffset === 0 ? 'Загрузка...' : 'Список игроков'}
                    </button>
                </form>

                <form onSubmit={(e) => { e.preventDefault(); fetchData('/api/players/by_puuid/', { puuid: puuid, game_name: gameName }); }} className={styles.form}>
                    <div className={styles.formGroup}>
                        <label htmlFor="puuid">Найти игрока по PUUID (для {availableGames.find(g=>g.value === gameName)?.label || gameName}):</label>
                        <input type="text" id="puuid" value={puuid} onChange={(e) => setPuuid(e.target.value)} placeholder="Player PUUID" />
                    </div>
                    <button type="submit" disabled={!puuid || isLoading || gamesLoading} className={styles.submitButton}>Найти по PUUID</button>
                </form>

                <form onSubmit={(e) => { e.preventDefault(); fetchData('/api/players/by_username/', { username: username, game_name: gameName }); }} className={styles.form}>
                    <div className={styles.formGroup}>
                        <label htmlFor="username">Найти игрока по Username (для {availableGames.find(g=>g.value === gameName)?.label || gameName}):</label>
                        <input type="text" id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Player Username" />
                    </div>
                    <button type="submit" disabled={!username || isLoading || gamesLoading} className={styles.submitButton}>Найти по Username</button>
                </form>

                <form onSubmit={(e) => { e.preventDefault(); handleGetPlayerMatchHistory(); }} className={styles.form}>
                     <div className={styles.formGroup}>
                        <label htmlFor="playerHistoryPuuid">История матчей игрока (PUUID) для {availableGames.find(g=>g.value === gameName)?.label || gameName}:</label>
                        <input
                            type="text"
                            id="playerHistoryPuuid"
                            value={playerHistoryPuuid}
                            onChange={(e) => setPlayerHistoryPuuid(e.target.value)}
                            placeholder="Введите PUUID игрока"
                        />
                    </div>
                    <button type="submit" disabled={!playerHistoryPuuid || isLoading || gamesLoading} className={styles.submitButton}>
                        {isLoading && listType === 'playerMatchHistory' && currentListPlayerPuuid === playerHistoryPuuid && listOffset === 0 ? 'Загрузка...' : 'История матчей'}
                    </button>
                </form>
            </div>

            <div className={styles.section}>
                <h2 className={styles.sectionTitle}>Матчи</h2>
                 <form onSubmit={(e) => { e.preventDefault(); handleGetMatches(); }} className={styles.form}>
                    <button type="submit" disabled={isLoading || gamesLoading} className={styles.submitButton}>
                         {isLoading && listType === 'matches' && listOffset === 0 ? 'Загрузка...' : 'Список матчей'}
                    </button>
                </form>

                <form onSubmit={(e) => { e.preventDefault(); fetchData('/api/matches/by_game_match_id/', { game_match_id: gameMatchIdForSearch, game_name: gameName }); }} className={styles.form}>
                    <div className={styles.formGroup}>
                        <label htmlFor="gameMatchIdForSearch">Найти матч по Game Match ID (для {availableGames.find(g=>g.value === gameName)?.label || gameName}):</label>
                        <input type="text" id="gameMatchIdForSearch" value={gameMatchIdForSearch} onChange={(e) => setGameMatchIdForSearch(e.target.value)} placeholder="In-game Match ID" />
                    </div>
                    <button type="submit" disabled={!gameMatchIdForSearch || isLoading || gamesLoading} className={styles.submitButton}>Найти по Game Match ID</button>
                </form>
            </div>

            <div className={styles.section}>
                <h2 className={styles.sectionTitle}>Статистика Игрока в Конкретном Матче</h2>
                <form onSubmit={(e) => { e.preventDefault(); fetchData('/api/player-match-stats/by_identifiers/', { player_puuid: statPlayerPuuid, game_match_id: statGameMatchId, game_name: gameName }); }} className={styles.form}>
                    <div className={styles.formGroup}>
                        <label htmlFor="statPlayerPuuid">Player PUUID (для {availableGames.find(g=>g.value === gameName)?.label || gameName}):</label>
                        <input type="text" id="statPlayerPuuid" value={statPlayerPuuid} onChange={(e) => setStatPlayerPuuid(e.target.value)} placeholder="Player PUUID" />
                    </div>
                    <div className={styles.formGroup}>
                        <label htmlFor="statGameMatchId">Game Match ID (для {availableGames.find(g=>g.value === gameName)?.label || gameName}):</label>
                        <input type="text" id="statGameMatchId" value={statGameMatchId} onChange={(e) => setStatGameMatchId(e.target.value)} placeholder="In-game Match ID" />
                    </div>
                    <button type="submit" disabled={!statPlayerPuuid || !statGameMatchId || isLoading || gamesLoading} className={styles.submitButton}>Получить Статистику</button>
                </form>
            </div>
            {isLoading && !listItems.length && !results && <p className={styles.loadingText}>Загрузка...</p>}
            {error && <p className={styles.errorMessage}>Ошибка: {error}</p>}

            {results && (
                <div className={styles.resultsContainer}>
                    <h3>Результат запроса:</h3>
                    <pre>{JSON.stringify(results, null, 2)}</pre>
                </div>
            )}

            {listItems.length > 0 && (
                <div className={styles.resultsContainer}>
                    <h3>
                        {listType === 'players' && `Список игроков (${availableGames.find(g=>g.value === gameName)?.label || gameName}):`}
                        {listType === 'matches' && `Список матчей (${availableGames.find(g=>g.value === gameName)?.label || gameName}):`}
                        {listType === 'playerMatchHistory' && `История матчей игрока PUUID: ${currentListPlayerPuuid || ''} (${availableGames.find(g=>g.value === gameName)?.label || gameName}):`}
                    </h3>
                    {listItems.map(item => renderListItem(item, listType))}
                    {listHasMore && (
                        <div className={styles.listControls} style={{justifyContent: 'center', marginTop: '15px'}}>
                            <button
                                onClick={() => {
                                    if (listType === 'players') handleGetPlayers(true);
                                    else if (listType === 'matches') handleGetMatches(true);
                                    else if (listType === 'playerMatchHistory') handleGetPlayerMatchHistory(true);
                                }}
                                disabled={isLoading || gamesLoading}
                            >
                                {isLoading ? 'Загрузка...' : 'Загрузить еще'}
                            </button>
                        </div>
                    )}
                </div>
            )}
             {!isLoading && !error && listType && listItems.length === 0 && !results && (
                <p className={styles.noDataText}>Нет данных для отображения списка.</p>
            )}
            {!isLoading && !error && !listType && !results &&
                 Object.values({puuid, username, gameMatchIdForSearch, statPlayerPuuid, statGameMatchId, playerHistoryPuuid}).some(v => v !== '') &&
                 (results === null && listItems.length === 0) &&
                (<p className={styles.noDataText}>Данные не найдены по вашему запросу.</p>
            )}
        </div>
    );
};

export default ApiBrowserPage;