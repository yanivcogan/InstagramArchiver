import {useEffect, useState} from 'react';
import {IArchiveSession, IExtractedEntitiesNested} from '../types/entities';

interface EntityPageState {
    data: IExtractedEntitiesNested | null;
    setData: React.Dispatch<React.SetStateAction<IExtractedEntitiesNested | null>>;
    loadingData: boolean;
    fetchError: string | null;
    sessions: IArchiveSession[] | null;
    loadingSessions: boolean;
    dbId: number | null;
    setDbId: React.Dispatch<React.SetStateAction<number | null>>;
}

export function useEntityPageState(
    apiRef: number | string | null,
    fetchFn: (ref: number | string) => Promise<IExtractedEntitiesNested>,
    fetchSessionsFn: (id: number) => Promise<IArchiveSession[]>,
    resolveDbId: (result: IExtractedEntitiesNested) => number | null,
    loadErrorMsg: string,
): EntityPageState {
    const [data, setData] = useState<IExtractedEntitiesNested | null>(null);
    const [loadingData, setLoadingData] = useState(apiRef !== null);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [sessions, setSessions] = useState<IArchiveSession[] | null>(null);
    const [loadingSessions, setLoadingSessions] = useState(false);
    const [dbId, setDbId] = useState<number | null>(typeof apiRef === 'number' ? apiRef : null);

    useEffect(() => {
        if (apiRef === null) return;
        setLoadingData(true);
        setLoadingSessions(true);
        setFetchError(null);
        const isByDbId = typeof apiRef === 'number';
        if (isByDbId) {
            setDbId(apiRef);
            fetchSessionsFn(apiRef).then(s => {
                setSessions(s);
                setLoadingSessions(false);
            }).catch(() => setLoadingSessions(false));
        }
        fetchFn(apiRef).then(result => {
            setData(result);
            setLoadingData(false);
            if (!isByDbId) {
                const resolvedId = resolveDbId(result);
                setDbId(resolvedId);
                if (resolvedId) {
                    fetchSessionsFn(resolvedId).then(s => {
                        setSessions(s);
                        setLoadingSessions(false);
                    }).catch(() => setLoadingSessions(false));
                } else {
                    setLoadingSessions(false);
                }
            }
        }).catch(err => {
            setFetchError(err?.message || loadErrorMsg);
            setLoadingData(false);
            setLoadingSessions(false);
        });
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [apiRef]);

    return {data, setData, loadingData, fetchError, sessions, loadingSessions, dbId, setDbId};
}
