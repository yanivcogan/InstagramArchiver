import React from 'react';
import {T_Search_Mode} from '../../services/DataFetcher';
import {SearchResultsProps} from './types';
import DefaultSearchResults from './DefaultSearchResults';
import MediaSearchResults from './MediaSearchResults';
import PostSearchResults from './PostSearchResults';
import ArchiveSessionSearchResults from './ArchiveSessionSearchResults';
import AccountSearchResults from './AccountSearchResults';

export const SEARCH_RESULT_RENDERERS: Partial<Record<T_Search_Mode, React.FC<SearchResultsProps>>> = {
    accounts: AccountSearchResults,
    posts: PostSearchResults,
    media: MediaSearchResults,
    archive_sessions: ArchiveSessionSearchResults,
};

export {DefaultSearchResults};
