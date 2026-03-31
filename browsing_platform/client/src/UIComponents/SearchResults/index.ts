import React from 'react';
import {SearchResult, T_Search_Mode} from '../../services/DataFetcher';
import {ITagWithType} from '../../types/tags';
import DefaultSearchResults from './DefaultSearchResults';
import MediaSearchResults from './MediaSearchResults';
import PostSearchResults from './PostSearchResults';
import ArchiveSessionSearchResults from './ArchiveSessionSearchResults';
import AccountSearchResults from './AccountSearchResults';

export interface SearchResultsProps {
    results: SearchResult[];
    tagsMap?: Record<number, ITagWithType[]>;
    selectedIds?: Set<number>;
    onToggleSelected?: (id: number) => void;
}

export const SEARCH_RESULT_RENDERERS: Partial<Record<T_Search_Mode, React.FC<SearchResultsProps>>> = {
    accounts: AccountSearchResults,
    posts: PostSearchResults,
    media: MediaSearchResults,
    archive_sessions: ArchiveSessionSearchResults,
};

export {DefaultSearchResults};
