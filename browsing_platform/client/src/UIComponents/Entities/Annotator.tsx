import React, {useState} from 'react';
import {IAccount, IMedia, IMediaPart, IPost} from "../../types/entities";
import {Button, CircularProgress, Grow, Stack, Typography} from "@mui/material";
import {ITagWithType} from "../../types/tags";
import TextField from "@mui/material/TextField";
import TagSelector from "../Tags/TagSelector";
import SaveIcon from "@mui/icons-material/Save";
import {saveAccountAnnotations, saveMediaAnnotations, savePostAnnotations} from "../../services/DataSaver";
import {toast} from "material-react-toastify";

interface IProps {
    entity: IMedia | IPost | IAccount | IMediaPart
    entityType: "media" | "post" | "account" | "media_part"
    readonly: boolean,
    onSave?: () => void
}

interface IAnnotations {
    notes: string
    tags: ITagWithType[]
}

export default function EntityAnnotator({entity, entityType, readonly, onSave}: IProps) {
    const [annotations, setAnnotations] = useState<IAnnotations>({
        notes: entity.notes || "",
        tags: entity.tags || [],
    });
    const [unsavedChanges, setUnsavedChanges] = useState(false);
    const [awaitingSave, setAwaitingSave] = useState(false);

    const saveAnnotations = async () => {
        setAwaitingSave(true);
        const updatedEntity = {...entity, notes: annotations.notes, tags: annotations.tags};
        switch (entityType) {
            case "media":
                await saveMediaAnnotations(updatedEntity as IMedia);
                break;
            case "post":
                await savePostAnnotations(updatedEntity as IPost);
                break;
            case "account":
                await saveAccountAnnotations(updatedEntity as IAccount);
                break;
            case "media_part":
                break;
        }
        if (onSave) {
            onSave();
        }
        toast.success("Annotations saved successfully.");
        setAwaitingSave(false);
        setUnsavedChanges(false);
    };

    const {notes, tags} = annotations;

    if (readonly) {
        return <Stack gap={1}>
            <Typography variant={"h6"}>Notes</Typography>
            <Typography variant={"body2"}>{notes || "-"}</Typography>
            <Typography variant={"h6"}>Tags</Typography>
            {
                tags.length === 0
                    ? <Typography variant={"body2"}>-</Typography>
                    : <Stack direction={"row"} gap={1} flexWrap={"wrap"}>
                        {
                            tags.map((tag, index) => <Typography variant={"body2"} key={index} sx={{
                                padding: '0.2em 0.5em',
                                backgroundColor: '#e0e0e0',
                                borderRadius: '4px'
                            }}>{tag.name}</Typography>)
                        }
                    </Stack>
            }
        </Stack>
    } else {
        return <Stack gap={1}>
            <TextField
                label={"Notes"}
                multiline
                value={notes || ""}
                onChange={(e) => {
                    setAnnotations(curr => ({...curr, notes: e.target.value}));
                    setUnsavedChanges(true);
                }}
            />
            <TagSelector
                selectedTags={annotations.tags}
                onChange={(tags) => {
                    setAnnotations(curr => ({...curr, tags}));
                    setUnsavedChanges(true);
                }}
            />
            <Grow in={unsavedChanges} unmountOnExit>
                <Button
                    variant="contained"
                    startIcon={awaitingSave ? <CircularProgress size={20} color={"inherit"}/> : <SaveIcon/>}
                    onClick={saveAnnotations}
                    color={"success"}
                >
                    Save Annotations
                </Button>
            </Grow>
        </Stack>
    }
}
