import React, {useEffect, useRef, useState} from 'react';
import {AnnotatableEntityType, IAnnotatableEntity, IMediaPart} from "../../types/entities";
import {
    Box,
    Button,
    Collapse,
    IconButton,
    Stack,
    TextField,
    Tooltip,
    Typography
} from "@mui/material";
import {ITagWithType} from "../../types/tags";
import TagSelector from "../Tags/TagSelector";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {saveAnnotations as saveAnnotationsToServer} from "../../services/DataSaver";
import {fetchQuickAccessTags} from "../../services/TagManagementService";
import {toast} from "material-react-toastify";

interface IProps {
    entity: IAnnotatableEntity | IMediaPart
    entityType: AnnotatableEntityType | "media_part"
    readonly: boolean,
    onSave?: () => void
}

export default function EntityAnnotator({entity, entityType, readonly, onSave}: IProps) {
    const [tags, setTags] = useState<ITagWithType[]>(entity.tags || []);
    const [expandedNotes, setExpandedNotes] = useState<Set<number>>(
        () => new Set((entity.tags || []).filter(t => t.assignment_notes).map(t => t.id))
    );
    const [saveStatus, setSaveStatus] = useState<'idle' | 'pending' | 'saving'>('idle');
    const [quickAccessTags, setQuickAccessTags] = useState<ITagWithType[]>([]);
    const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const mountedRef = useRef(true);

    useEffect(() => {
        fetchQuickAccessTags().then(setQuickAccessTags).catch(() => {});
        return () => {
            mountedRef.current = false;
            if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        };
    }, []);

    const scheduleSave = (newTags: ITagWithType[]) => {
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        setSaveStatus('pending');
        saveTimerRef.current = setTimeout(async () => {
            if (!mountedRef.current) return;
            setSaveStatus('saving');
            try {
                await saveAnnotationsToServer({...entity, tags: newTags} as IAnnotatableEntity, entityType as AnnotatableEntityType);
                if (onSave) onSave();
            } catch {
                toast.error("Failed to save annotations.");
            }
            if (mountedRef.current) setSaveStatus('idle');
        }, 800);
    };

    const handleTagsChange = (newTags: ITagWithType[]) => {
        setTags(newTags);
        scheduleSave(newTags);
    };

    const updateTagNote = (tagId: number, note: string) => {
        const updated = tags.map(t => t.id === tagId ? {...t, assignment_notes: note} : t);
        setTags(updated);
        scheduleSave(updated);
    };

    const toggleNoteExpanded = (tagId: number) => {
        setExpandedNotes(curr => {
            const next = new Set(curr);
            if (next.has(tagId)) next.delete(tagId); else next.add(tagId);
            return next;
        });
    };

    const handleQuickAccess = (qTag: ITagWithType) => {
        const alreadyHas = tags.some(t => t.id === qTag.id);
        if (!alreadyHas) {
            const newTags = [...tags, {...qTag, assignment_notes: ""}];
            setTags(newTags);
            scheduleSave(newTags);
        }
        setExpandedNotes(curr => new Set([...curr, qTag.id]));
    };

    if (readonly) {
        return <Stack gap={1}>
            <Typography variant={"h6"}>Tags</Typography>
            {tags.length === 0
                ? <Typography variant={"body2"}>-</Typography>
                : <Stack gap={1}>
                    {tags.map((tag, index) => (
                        <Stack key={index} gap={0.5}>
                            <Typography variant={"body2"} sx={{
                                display: 'inline-block',
                                padding: '0.2em 0.5em',
                                backgroundColor: '#e0e0e0',
                                borderRadius: '4px',
                                width: 'fit-content',
                            }}>{tag.tag_type_name ? `${tag.tag_type_name} / ` : ""}{tag.name}</Typography>
                            {tag.assignment_notes && (
                                <Typography variant={"caption"} sx={{pl: 1, color: 'text.secondary'}}>
                                    {tag.assignment_notes}
                                </Typography>
                            )}
                        </Stack>
                    ))}
                </Stack>
            }
        </Stack>;
    }

    return <Stack gap={1}>
        <TagSelector
            selectedTags={tags}
            onChange={handleTagsChange}
        />
        {/* Per-tag notes */}
        {tags.length > 0 && (
            <Stack gap={0.5}>
                {tags.map((tag) => (
                    <Box key={tag.id} sx={{pl: 1, borderLeft: '2px solid #e0e0e0'}}>
                        <Stack direction="row" alignItems="center" gap={0.5}>
                            <Typography variant="caption" sx={{flex: 1, color: 'text.secondary'}}>
                                {tag.tag_type_name ? `${tag.tag_type_name} / ` : ""}{tag.name}
                            </Typography>
                            <Tooltip title={expandedNotes.has(tag.id) ? "Hide note" : "Add note"} disableInteractive>
                                <IconButton size="small" onClick={() => toggleNoteExpanded(tag.id)}>
                                    <ExpandMoreIcon fontSize="small" sx={{
                                        transform: expandedNotes.has(tag.id) ? 'rotate(180deg)' : 'rotate(0deg)',
                                        transition: 'transform 0.2s',
                                    }}/>
                                </IconButton>
                            </Tooltip>
                        </Stack>
                        <Collapse in={expandedNotes.has(tag.id)} unmountOnExit>
                            <TextField
                                size="small"
                                multiline
                                fullWidth
                                placeholder="Note for this tag…"
                                value={tag.assignment_notes ?? ""}
                                onChange={(e) => updateTagNote(tag.id, e.target.value)}
                                sx={{mt: 0.5}}
                            />
                        </Collapse>
                    </Box>
                ))}
            </Stack>
        )}
        <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            {quickAccessTags.map(qTag => (
                <Tooltip key={qTag.id} title={`Quick-add: ${qTag.tag_type_name ? `${qTag.tag_type_name} / ` : ""}${qTag.name}`} disableInteractive>
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => handleQuickAccess(qTag)}
                    >
                        {qTag.name}
                    </Button>
                </Tooltip>
            ))}
            {saveStatus !== 'idle' && (
                <Typography variant="caption" color="text.secondary" sx={{ml: 'auto'}}>
                    {saveStatus === 'pending' ? 'Unsaved…' : 'Saving…'}
                </Typography>
            )}
        </Stack>
    </Stack>;
}
