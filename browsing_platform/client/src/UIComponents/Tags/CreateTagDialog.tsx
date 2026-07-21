import React, {useEffect, useState} from 'react';
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    InputLabel,
    MenuItem,
    Select,
    Stack,
    Typography,
} from "@mui/material";
import {toast} from "material-react-toastify";
import {ITagType, ITagWithType} from "../../types/tags";
import {E_ENTITY_TYPES} from "../../types/entities";
import {addHierarchy, createTag, fetchTagTypes, tagSaveErrorMessage} from "../../services/TagManagementService";
import TagSelector from "./TagSelector";
import TagNameField, {isValidTagName} from "./TagNameField";

interface IProps {
    open: boolean;
    initialName: string;
    entity?: E_ENTITY_TYPES;
    onClose: () => void;
    onCreated: (tag: ITagWithType) => void;
}

export default function CreateTagDialog({open, initialName, entity, onClose, onCreated}: IProps) {
    const [name, setName] = useState(initialName);
    const [tagTypeId, setTagTypeId] = useState<number | null>(null);
    const [parents, setParents] = useState<ITagWithType[]>([]);
    const [tagTypes, setTagTypes] = useState<ITagType[]>([]);
    const [loadingTypes, setLoadingTypes] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        (async () => {
            try {
                setTagTypes(await fetchTagTypes());
            } catch (e: any) {
                toast.error(e?.message || 'Failed to load tag types');
            } finally {
                setLoadingTypes(false);
            }
        })();
    }, []);

    // A media part shares its parent media's tag set (mirrors the server's normalize_entity_for_affinity).
    // An EMPTY affinity array means "compatible with nothing" server-side (JSON_CONTAINS on '[]'
    // never matches), so such types are excluded even when no entity is given.
    const normalizedEntity = entity === 'media_part' ? 'media' : entity;
    const compatibleTypes = tagTypes.filter(tt =>
        !tt.entity_affinity
        || (tt.entity_affinity.length > 0
            && (!normalizedEntity || tt.entity_affinity.includes(normalizedEntity))));

    const handleSave = async () => {
        setSaving(true);
        let created;
        try {
            created = await createTag({name: name.trim(), description: null, tag_type_id: tagTypeId});
        } catch (e: any) {
            toast.error(tagSaveErrorMessage(e, 'Failed to create tag'));
            setSaving(false);
            return;
        }
        const failedParents: string[] = [];
        for (const p of parents) {
            try {
                await addHierarchy({super_tag_id: p.id, sub_tag_id: created.id!, notes: null});
            } catch {
                failedParents.push(p.name);
            }
        }
        if (failedParents.length) {
            toast.warn(`Tag created, but could not link parent(s): ${failedParents.join(', ')}`);
        }
        const tt = tagTypes.find(t => t.id === tagTypeId);
        const now = new Date().toISOString();
        onCreated({
            id: created.id!,
            name: created.name,
            description: created.description ?? null,
            tag_type_id: tagTypeId,
            create_date: now,
            update_date: now,
            tag_type_name: tt?.name ?? null,
            tag_type_description: tt?.description ?? null,
            tag_type_notes: tt?.notes ?? null,
            tag_type_entity_affinity: tt?.entity_affinity ?? null,
            notes_recommended: created.notes_recommended,
        });
    };

    return (
        <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
            <DialogTitle>New Tag</DialogTitle>
            <DialogContent>
                <Stack gap={2} sx={{mt: 1}}>
                    <TagNameField value={name} onChange={setName} autoFocus/>
                    <FormControl size="small" required>
                        <InputLabel>Tag Type</InputLabel>
                        <Select
                            value={tagTypeId ?? ""}
                            label="Tag Type"
                            onChange={e => setTagTypeId(e.target.value ? Number(e.target.value) : null)}
                        >
                            {compatibleTypes.map(tt => <MenuItem key={tt.id} value={tt.id}>{tt.name}</MenuItem>)}
                        </Select>
                    </FormControl>
                    {!loadingTypes && compatibleTypes.length === 0 && (
                        <Typography variant="caption" color="error">
                            No tag types are compatible with {normalizedEntity ?? 'this context'}
                        </Typography>
                    )}
                    <TagSelector
                        selectedTags={parents}
                        onChange={setParents}
                        label="Parent tags (optional)"
                        disableCreate
                        disableDeletionCheck
                    />
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <Button
                    variant="contained"
                    onClick={handleSave}
                    disabled={saving || !isValidTagName(name) || tagTypeId == null}
                >Save</Button>
            </DialogActions>
        </Dialog>
    );
}
