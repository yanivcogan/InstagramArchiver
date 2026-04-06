import {SearchResult} from '../../services/DataFetcher';
import {ITagWithType} from '../../types/tags';

export interface SearchResultsProps {
    results: SearchResult[];
    tagsMap?: Record<number, ITagWithType[]>;
    selectedIds?: Set<number>;
    onToggleSelected?: (id: number) => void;
}
