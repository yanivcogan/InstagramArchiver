import {useCallback, useState} from 'react';
import {T_Search_Mode} from '../services/DataFetcher';

const STORAGE_KEY = 'search_history';
const MAX_STORED = 30;

type SearchHistory = Partial<Record<T_Search_Mode, string[]>>;

function readHistory(): SearchHistory {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}');
    } catch {
        return {};
    }
}

export function useSearchHistory() {
    const [, setVersion] = useState(0);
    const bump = useCallback(() => setVersion(v => v + 1), []);

    const addSearch = useCallback((mode: T_Search_Mode, term: string) => {
        if (!term.trim()) return;
        const history = readHistory();
        const existing = history[mode] ?? [];
        const next = [term, ...existing.filter(t => t !== term)].slice(0, MAX_STORED);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({...history, [mode]: next}));
        bump();
    }, [bump]);

    const removeSearch = useCallback((mode: T_Search_Mode, term: string) => {
        const history = readHistory();
        const next = (history[mode] ?? []).filter(t => t !== term);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({...history, [mode]: next}));
        bump();
    }, [bump]);

    const getSuggestions = useCallback((mode: T_Search_Mode, prefix: string): string[] => {
        const lower = prefix.trim().toLowerCase();
        return (readHistory()[mode] ?? [])
            .filter(t => t.toLowerCase().startsWith(lower))
            .slice(0, 5);
    }, []);

    return {addSearch, removeSearch, getSuggestions};
}
