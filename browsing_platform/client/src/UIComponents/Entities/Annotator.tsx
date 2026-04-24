import React, {useEffect, useMemo, useState} from 'react';
import {AnnotatableEntityType, IAnnotatableEntity, IMediaPart} from "../../types/entities";
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Stack,
    TextField,
    Typography
} from "@mui/material";
import {IQuickAccessData, ITagWithType} from "../../types/tags";
import TagSelector from "../Tags/TagSelector";
import InlineTagsDisplay from "../Tags/InlineTagsDisplay";
import QuickAccessBar from "../Tags/QuickAccessBar";
import {saveAnnotations as saveAnnotationsToServer} from "../../services/DataSaver";
import {fetchQuickAccessData} from "../../services/TagManagementService";
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
    const [quickAccessData, setQuickAccessData] = useState<IQuickAccessData>({individual_tags: [], type_dropdowns: []});

    useEffect(() => {
        if (!readonly) {
            fetchQuickAccessData(entityType).then(setQuickAccessData).catch(() => {});
        }
    }, [readonly, entityType]);

    const assignedTagIds = useMemo(() => new Set(tags.map(t => t.id)), [tags]);

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
        const existingTag = tags.find(t => t.id === qTag.id);
        if (existingTag) {
            setNoteModalTag({...existingTag});
            return;
        }
        const newTags = [...tags, {...qTag, assignment_notes: ""}];
        setTags(newTags);
        saveToServer(newTags);
        if (qTag.notes_recommended !== false) {
            setNoteModalTag({...qTag, assignment_notes: ""});
        }
    };

    if (readonly) {
        return <InlineTagsDisplay tags={tags}/>;
    }

    return <Stack gap={1}>
        <TagSelector
            selectedTags={tags}
            onChange={handleTagsChange}
            onChipClick={tag => setNoteModalTag({...tag})}
            label={`Tags on ${entityType} ${entity.id}`}
            entity={entityType}
        />
        <QuickAccessBar
            quickAccessData={quickAccessData}
            selectedTagIds={assignedTagIds}
            onSelect={handleQuickAccess}
        />

        <Dialog
            open={noteModalTag !== null}
            onClose={() => setNoteModalTag(null)}
            maxWidth="sm"
            fullWidth
        >
            <DialogTitle sx={{pb: 0}}>
                <Typography component="span" display="block" variant="subtitle2" color="text.secondary">
                    {noteModalTag?.tag_type_name ?? 'Tag'}
                </Typography>
                <Typography component="span" display="block" variant="h6">{noteModalTag?.name}</Typography>
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
