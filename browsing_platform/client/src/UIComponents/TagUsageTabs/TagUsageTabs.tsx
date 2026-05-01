import React, {useEffect, useMemo, useState} from 'react';
import {Link} from 'react-router';
import {Badge, Box, CircularProgress, Stack, Tab, Tabs, Typography} from '@mui/material';
import {ITagUsage, ITagWithType} from '../../types/tags';
import {E_ENTITY_TYPES} from '../../types/entities';
import {
    fetchTagsForSearchResults,
    ISearchQuery,
    searchData,
    SearchResult,
    T_Search_Mode,
} from '../../services/DataFetcher';
import {DefaultSearchResults, SEARCH_RESULT_RENDERERS} from '../SearchResults';

type TabConfig = {entity: E_ENTITY_TYPES; mode: T_Search_Mode; label: string; usageKey: keyof ITagUsage};

const TAB_CONFIG: TabConfig[] = [
    {entity: 'account', mode: 'accounts', label: 'Accounts', usageKey: 'accounts'},
    {entity: 'post',    mode: 'posts',    label: 'Posts',    usageKey: 'posts'},
    {entity: 'media',   mode: 'media',    label: 'Media',    usageKey: 'media'},
];

type TabState = {
    results: SearchResult[] | null;
    tagsMap: Record<number, ITagWithType[]>;
    loading: boolean;
    error: string | null;
};

function TabContent({state, mode, tagId}: {state: TabState | undefined; mode: T_Search_Mode; tagId: number}) {
    if (!state || state.loading || state.results === null) {
        return <Box sx={{py: 2, display: 'flex', justifyContent: 'center'}}><CircularProgress size={24}/></Box>;
    }
    if (state.error) {
        return <Typography color="error" variant="caption">{state.error}</Typography>;
    }
    if (state.results.length === 0) {
        return <Typography variant="caption" color="text.secondary">No results</Typography>;
    }
    const Renderer = SEARCH_RESULT_RENDERERS[mode] ?? DefaultSearchResults;
    return (
        <Stack gap={1}>
            <Renderer results={state.results} tagsMap={state.tagsMap}/>
            <Link to={`/search?sm=${mode}&t=${tagId}`} style={{fontSize: '0.75rem'}}>View all in Search →</Link>
        </Stack>
    );
}

export default function TagUsageTabs({tagId, usage, entityAffinity, refreshKey}: {
    tagId: number;
    usage: ITagUsage | null;
    entityAffinity: E_ENTITY_TYPES[] | null;
    refreshKey: number;
}) {
    const visibleTabs = useMemo(
        () => TAB_CONFIG.filter(t => entityAffinity === null || entityAffinity.includes(t.entity)),
        [entityAffinity]
    );

    const [activeTab, setActiveTab] = useState<string | null>(visibleTabs[0]?.mode ?? null);
    const [tabStates, setTabStates] = useState<Record<string, TabState>>({});

    // When visible tabs change (e.g. tag type edited), reset active tab
    useEffect(() => {
        setActiveTab(visibleTabs[0]?.mode ?? null);
    }, [visibleTabs]);

    // Clear all cached tab data when hierarchy changes
    useEffect(() => {
        setTabStates({});
    }, [refreshKey]);

    // Load (or reload) the active tab whenever it changes or hierarchy refreshes
    useEffect(() => {
        if (!activeTab) return;
        const controller = new AbortController();
        setTabStates(prev => ({...prev, [activeTab]: {results: null, tagsMap: {}, loading: true, error: null}}));
        const query: ISearchQuery = {
            search_mode: activeTab as T_Search_Mode,
            search_term: '',
            advanced_filters: null,
            page_number: 1,
            page_size: activeTab === 'media' ? 24 : 10,
            tag_ids: [tagId],
            tag_filter_mode: 'any',
        };
        searchData(query, {signal: controller.signal})
            .then(async results => {
                const ids = results.map(r => r.id).filter((id): id is number => id != null);
                const tagsMap = ids.length > 0 ? await fetchTagsForSearchResults(activeTab as T_Search_Mode, ids) : {};
                setTabStates(prev => ({...prev, [activeTab]: {results, tagsMap, loading: false, error: null}}));
            })
            .catch((e: any) => {
                if (e?.name === 'AbortError') return;
                setTabStates(prev => ({...prev, [activeTab]: {results: [], tagsMap: {}, loading: false, error: e?.message || 'Failed to load'}}));
            });
        return () => controller.abort();
    }, [activeTab, tagId, refreshKey]);

    if (visibleTabs.length === 0) {
        return (
            <Stack gap={0.5}>
                <Typography variant="subtitle2">Usage</Typography>
                {usage?.media_parts ? (
                    <Typography variant="caption" color="text.secondary">
                        {usage.media_parts} media {usage.media_parts === 1 ? 'part' : 'parts'} tagged (no search view available)
                    </Typography>
                ) : (
                    <Typography variant="caption" color="text.secondary">No searchable entities for this tag type.</Typography>
                )}
            </Stack>
        );
    }

    return (
        <Stack gap={1}>
            <Typography variant="subtitle2">Usage</Typography>
            <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}>
                {visibleTabs.map(t => (
                    <Tab key={t.mode} value={t.mode} label={
                        <Badge
                            badgeContent={usage ? usage[t.usageKey] : <CircularProgress size={8}/>}
                            color="primary"
                            max={9999}
                            showZero
                        >
                            <Box sx={{pr: 1.5}}>{t.label}</Box>
                        </Badge>
                    }/>
                ))}
            </Tabs>
            {visibleTabs.map(t => (
                <Box key={t.mode} hidden={activeTab !== t.mode} sx={{mt: 1}}>
                    <TabContent state={tabStates[t.mode]} mode={t.mode} tagId={tagId}/>
                </Box>
            ))}
        </Stack>
    );
}
