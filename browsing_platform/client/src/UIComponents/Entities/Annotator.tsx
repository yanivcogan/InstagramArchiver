import React, {useEffect, useState} from 'react';
import {AnnotatableEntityType, IAnnotatableEntity, IMediaPart} from "../../types/entities";
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Stack,
    TextField,
    Tooltip,
    Typography
} from "@mui/material";
import AddIcon from '@mui/icons-material/Add';
import {ITagWithType} from "../../types/tags";
import TagSelector from "../Tags/TagSelector";
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
    const [noteModalTag, setNoteModalTag] = useState<ITagWithType | null>(null);
    const [quickAccessTags, setQuickAccessTags] = useState<ITagWithType[]>([]);

    useEffect(() => {
        if (!readonly) {
            fetchQuickAccessTags().then(setQuickAccessTags).catch(() => {
            });
        }
    }, [readonly]);

    const saveToServer = async (newTags: ITagWithType[]) => {
        try {
            await saveAnnotationsToServer({
                ...entity,
                tags: newTags
            } as IAnnotatableEntity, entityType as AnnotatableEntityType);
            if (onSave) onSave();
        } catch {
            toast.error("Failed to save annotations.");
        }
    };

    const handleTagsChange = (newTags: ITagWithType[]) => {
        setTags(newTags);
        saveToServer(newTags);
    };

    const handleQuickAccess = (qTag: ITagWithType) => {
        const alreadyHas = tags.some(t => t.id === qTag.id);
        if (!alreadyHas) {
            const newTags = [...tags, {...qTag, assignment_notes: ""}];
            setTags(newTags);
            saveToServer(newTags);
        }
        // Open notes modal so the user can immediately annotate the quick-added tag
        setNoteModalTag({...qTag, assignment_notes: qTag.assignment_notes ?? ""});
    };

    if (readonly) {
        if (tags.length === 0) return null;
        return <Stack direction="row" gap={0.75} flexWrap="wrap" alignItems="baseline">
            <Typography variant="caption" color="text.secondary" sx={{fontWeight: 600}}>Tags:</Typography>
            {tags.map((tag, index) => (
                <Tooltip title={tag.tag_type_name} arrow disableInteractive>
                    <Typography key={index} component="span" variant="caption" sx={{
                        padding: '0.1em 0.4em',
                        backgroundColor: '#e0e0e0',
                        borderRadius: '4px',
                    }}>
                        {tag.name}
                        {tag.assignment_notes && (
                            <Typography component="span" variant="caption"
                                        sx={{ml: 0.5, color: 'text.secondary', fontStyle: 'italic'}}>
                                ({tag.assignment_notes})
                            </Typography>
                        )}
                    </Typography>
                </Tooltip>
            ))}
        </Stack>;
    }

    return <Stack gap={1}>
        <TagSelector
            selectedTags={tags}
            onChange={handleTagsChange}
            onChipClick={tag => setNoteModalTag({...tag})}
            label={`Tags on ${entityType} ${entity.id}`}
        />
        <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            {quickAccessTags.map(qTag => (
                <Tooltip key={qTag.id}
                         title={`Quick-add: ${qTag.tag_type_name ? `${qTag.tag_type_name} / ` : ""}${qTag.name}`}
                         disableInteractive>
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => handleQuickAccess(qTag)}
                        startIcon={<AddIcon/>}
                    >
                        {qTag.name}
                    </Button>
                </Tooltip>
            ))}
        </Stack>

        {/* Notes modal — opens when a tag chip is clicked */}
        <Dialog
            open={noteModalTag !== null}
            onClose={() => setNoteModalTag(null)}
            maxWidth="sm"
            fullWidth
        >
            <DialogTitle sx={{pb: 0}}>
                <Typography variant="subtitle2" color="text.secondary">
                    {noteModalTag?.tag_type_name ?? 'Tag'}
                </Typography>
                <Typography variant="h6">{noteModalTag?.name}</Typography>
            </DialogTitle>
            <DialogContent>
                <TextField
                    autoFocus
                    onFocus={(e) => {
                        const len = e.target.value.length;
                        e.target.setSelectionRange(len, len);
                    }}
                    multiline
                    fullWidth
                    rows={4}
                    placeholder="Notes about this tag assignment…"
                    value={noteModalTag?.assignment_notes ?? ""}
                    onChange={(e) => {
                        setNoteModalTag(curr => curr ? {...curr, assignment_notes: e.target.value} : null);
                    }}
                    sx={{mt: 1}}
                />
            </DialogContent>
            <DialogActions>
                <Button
                    color="error"
                    onClick={() => {
                        if (!noteModalTag) return;
                        handleTagsChange(tags.filter(t => t.id !== noteModalTag.id));
                        setNoteModalTag(null);
                    }}
                >
                    Remove tag
                </Button>
                <Button onClick={() => {
                    if (noteModalTag) {
                        const updated = tags.map(t => t.id === noteModalTag.id ? {
                            ...t,
                            assignment_notes: noteModalTag.assignment_notes ?? ""
                        } : t);
                        setTags(updated);
                        saveToServer(updated);
                    }
                    setNoteModalTag(null);
                }}>Save</Button>
            </DialogActions>
        </Dialog>
    </Stack>;
}
