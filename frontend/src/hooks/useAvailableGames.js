import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const useAvailableGames = (defaultGame = 'valorant') => {
    const [games, setGames] = useState([{ value: defaultGame, label: defaultGame.charAt(0).toUpperCase() + defaultGame.slice(1) }]); // Начальное значение
    const [selectedGame, setSelectedGame] = useState(defaultGame);
    const [gamesLoading, setGamesLoading] = useState(true);
    const [gamesError, setGamesError] = useState(null);

    useEffect(() => {
        const fetchGames = async () => {
            setGamesLoading(true);
            setGamesError(null);
            try {
                const response = await axios.get(`${API_BASE_URL}/api/available-games/`);
                if (response.data && response.data.length > 0) {
                    setGames(response.data);
                    // устанавливаем selectedGame в первое значение из списка, если defaultGame нет в списке,
                    // или оставляем defaultGame, если он есть.
                    const defaultGameExists = response.data.some(game => game.value === defaultGame);
                    if (!defaultGameExists) {
                        setSelectedGame(response.data[0].value);
                    } else {
                        setSelectedGame(defaultGame);
                    }
                } else {
                    // если список пуст, оставляем значение по умолчанию
                    setGames([{ value: defaultGame, label: defaultGame.charAt(0).toUpperCase() + defaultGame.slice(1) }]);
                    setSelectedGame(defaultGame);
                }
            } catch (err) {
                console.error("Failed to fetch available games:", err);
                setGamesError('Не удалось загрузить список игр.');
                // оставляем значение по умолчанию в случае ошибки
                 setGames([{ value: defaultGame, label: defaultGame.charAt(0).toUpperCase() + defaultGame.slice(1) }]);
                 setSelectedGame(defaultGame);
            } finally {
                setGamesLoading(false);
            }
        };

        fetchGames();
    }, [defaultGame]);

    return { games, selectedGame, setSelectedGame, gamesLoading, gamesError };
};

export default useAvailableGames;