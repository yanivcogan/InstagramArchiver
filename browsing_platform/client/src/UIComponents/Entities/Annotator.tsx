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
        fetchQuickAccessTags().then(setQuickAccessTags).catch(() => {});
    }, []);

    const saveToServer = async (newTags: ITagWithType[]) => {
        try {
            await saveAnnotationsToServer({...entity, tags: newTags} as IAnnotatableEntity, entityType as AnnotatableEntityType);
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
            onChipClick={tag => setNoteModalTag({...tag})}
        />
        <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            {quickAccessTags.map(qTag => (
                <Tooltip key={qTag.id} title={`Quick-add: ${qTag.tag_type_name ? `${qTag.tag_type_name} / ` : ""}${qTag.name}`} disableInteractive>
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
                        const updated = tags.map(t => t.id === noteModalTag.id ? {...t, assignment_notes: noteModalTag.assignment_notes ?? ""} : t);
                        setTags(updated);
                        saveToServer(updated);
                    }
                    setNoteModalTag(null);
                }}>Save</Button>
            </DialogActions>
        </Dialog>
    </Stack>;
}
