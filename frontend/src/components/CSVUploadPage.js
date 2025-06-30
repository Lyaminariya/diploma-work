import React, { useState, useCallback } from 'react';
import axios from 'axios';
import styles from './CSVUploadPage.module.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const CSVUploadPage = () => {
    const [gameName, setGameName] = useState(''); // пользователь вводит имя игры

    const [playersFile, setPlayersFile] = useState(null);
    const [matchesFile, setMatchesFile] = useState(null);
    const [statsFile, setStatsFile] = useState(null);

    const [isLoading, setIsLoading] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [detailedErrors, setDetailedErrors] = useState(null);

    const handleFileChange = (setter) => (event) => {
        setter(event.target.files[0]);
        setMessage(''); // сбрасываем сообщения при выборе нового файла
        setError('');
        setDetailedErrors(null);
    };

    const handleSubmit = useCallback(async (event) => {
        event.preventDefault();

        const normalizedGameName = gameName.trim().toLowerCase();
        if (!normalizedGameName) {
            setError("Пожалуйста, введите название игры для импорта.");
            return;
        }

        setIsLoading(true);
        setMessage('');
        setError('');
        setDetailedErrors(null);

        if (!playersFile && !matchesFile && !statsFile) {
            setError('Пожалуйста, выберите хотя бы один файл для загрузки.');
            setIsLoading(false);
            return;
        }

        const formData = new FormData();
        if (playersFile) formData.append('players_csv', playersFile);
        if (matchesFile) formData.append('matches_csv', matchesFile);
        if (statsFile) formData.append('stats_csv', statsFile);

        formData.append('game_name', normalizedGameName);

        try {
            const response = await axios.post(`${API_BASE_URL}/api/import-csv/`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setMessage(response.data.message || 'Файлы успешно загружены и обработаны!');
            if(response.data.details) {
                console.log("Details from server:", response.data.details);
            }
            // Очистка после успешной загрузки
            setPlayersFile(null);
            setMatchesFile(null);
            setStatsFile(null);
            setGameName('');

            if (document.getElementById('playersFile')) document.getElementById('playersFile').value = '';
            if (document.getElementById('matchesFile')) document.getElementById('matchesFile').value = '';
            if (document.getElementById('statsFile')) document.getElementById('statsFile').value = '';

        } catch (err) {
            console.error("Ошибка загрузки CSV:", err.response || err.message);
            const errorData = err.response?.data;
            if (errorData) {
                setError(errorData.error || errorData.detail || 'Произошла ошибка при загрузке файлов.');
                if (errorData.row_errors) {
                    setDetailedErrors(errorData.row_errors);
                }
            } else {
                setError('Произошла ошибка при загрузке файлов. Сервер не отвечает или сетевая ошибка.');
            }
        } finally {
            setIsLoading(false);
        }
    }, [playersFile, matchesFile, statsFile, gameName]);

    return (
        <div className={styles.pageContainer}>
            <h1 className={styles.pageTitle}>Загрузка CSV данных</h1>

            {message && <p className={styles.successMessage}>{message}</p>}
            {error && <p className={styles.errorMessage}>{error}</p>}
            {detailedErrors && (
                 <div className={styles.detailedErrors}>
                    <h4>Ошибки в строках CSV:</h4>
                    <ul>
                        {Object.entries(detailedErrors).map(([fileName, errors]) => (
                           <li key={fileName}>
                                <strong>Файл "{fileName}":</strong>
                                {Array.isArray(errors) && errors.length > 0 ? (
                                    <ul>
                                        {errors.map((err, index) => (
                                            <li key={index}>
                                                Строка {err.row_number}: {JSON.stringify(err.errors)}
                                                {err.data ? ` (Данные: ${JSON.stringify(err.data)})` : ''}
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                     typeof errors === 'object' && errors.errors ?
                                     <p>Ошибка файла: {JSON.stringify(errors.errors)}</p> :
                                     <p>{typeof errors === 'object' ? JSON.stringify(errors) : String(errors)}</p>
                                )}
                           </li>
                        ))}
                    </ul>
                </div>
            )}

            <form onSubmit={handleSubmit} className={styles.uploadForm}>
                <div className={styles.formGroup}>
                    <label htmlFor="gameNameCsvInput">Название игры для импорта (например, cs2, dota2):</label>
                    <input
                        type="text"
                        id="gameNameCsvInput"
                        value={gameName}
                        onChange={(e) => setGameName(e.target.value)}
                        placeholder="Введите название игры"
                        className={styles.textInput}
                    />
                </div>

                <div className={styles.formGroup}>
                    <label htmlFor="playersFile">CSV файл с игроками (Players):</label>
                    <input
                        type="file"
                        id="playersFile"
                        accept=".csv"
                        onChange={handleFileChange(setPlayersFile)}
                    />
                    {playersFile && <p className={styles.fileName}>Выбран: {playersFile.name}</p>}
                </div>

                <div className={styles.formGroup}>
                    <label htmlFor="matchesFile">CSV файл с матчами (Matches):</label>
                    <input
                        type="file"
                        id="matchesFile"
                        accept=".csv"
                        onChange={handleFileChange(setMatchesFile)}
                    />
                     {matchesFile && <p className={styles.fileName}>Выбран: {matchesFile.name}</p>}
                </div>

                <div className={styles.formGroup}>
                    <label htmlFor="statsFile">CSV файл со статистикой игроков в матчах (PlayerMatchStats):</label>
                    <input
                        type="file"
                        id="statsFile"
                        accept=".csv"
                        onChange={handleFileChange(setStatsFile)}
                    />
                    {statsFile && <p className={styles.fileName}>Выбран: {statsFile.name}</p>}
                </div>

                <p className={styles.infoText}>
                    Убедитесь, что CSV файлы имеют правильные заголовки столбцов.
                    Название игры, введенное выше, будет использовано для всех загружаемых данных.
                    <br/>
                    <strong>Player:</strong> `puuid`, `username` (опц.), `rank` (опц.).
                    <br/>
                    <strong>Match:</strong> `game_match_id`, `match_timestamp` (ГГГГ-ММ-ДД ЧЧ:ММ:СС), `duration_seconds` (опц.), `map_name` (опц.), `game_mode` (опц.), `is_ranked` (опц., True/False), `rounds_played` (опц.).
                    <br/>
                    <strong>PlayerMatchStats:</strong> `player_puuid`, `match_game_id`, `won_match`, `kills`, `deaths`, `assists`, (и другие поля модели, например `unique_abilities_used`).
                </p>

                <button
                    type="submit"
                    disabled={isLoading || !gameName.trim() || (!playersFile && !matchesFile && !statsFile)}
                    className={styles.submitButton}
                >
                    {isLoading ? 'Загрузка...' : 'Загрузить и обработать'}
                </button>
            </form>
        </div>
    );
};

export default CSVUploadPage;