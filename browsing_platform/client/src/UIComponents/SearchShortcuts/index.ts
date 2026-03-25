import {T_Search_Mode} from '../../services/DataFetcher';
import {SearchShortcutsProps} from './AccountSearchShortcuts';
import AccountSearchShortcuts from './AccountSearchShortcuts';
import {createDateRangeShortcut} from './DateRangeShortcut';
import MediaSearchShortcuts from './MediaSearchShortcuts';
import React from 'react';

export const SEARCH_SHORTCUTS: Partial<Record<T_Search_Mode, React.FC<SearchShortcutsProps>>> = {
    accounts: AccountSearchShortcuts,
    posts: createDateRangeShortcut('publication_date', 'posts', 'Published from', 'Published to'),
    media: MediaSearchShortcuts,
    archive_sessions: createDateRangeShortcut('archiving_timestamp', 'archive_sessions', 'Archived from', 'Archived to'),
};
