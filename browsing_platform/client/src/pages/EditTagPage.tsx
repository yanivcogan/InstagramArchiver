import React, {useEffect, useState} from 'react';
import {Link, useNavigate, useParams} from 'react-router';
import {
    Autocomplete,
    Box,
    Button,
    Checkbox,
    CircularProgress,
    Divider,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    Stack,
    TextField,
    Tooltip,
    Chip,
    Typography,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import TopNavBar from '../UIComponents/TopNavBar/TopNavBar';
import {ITagDetail, ITagHierarchyEntry, ITagType, ITagUsage, ITagWithType} from '../types/tags';
import {
    fetchTag,
    fetchTagParents,
    fetchTagChildren,
    fetchTagTypes,
    fetchTagUsage,
    updateTag,
    addHierarchy,
    removeHierarchy,
    updateHierarchyNotes,
} from '../services/TagManagementService';
import {lookupTags} from '../services/DataFetcher';
import {toast} from 'material-react-toastify';

/* ── Usage summary ────────────────────────────────────────────────────────── */

function UsageSummary({usage, tagId}: {usage: ITagUsage | null; tagId: number}) {
    if (!usage) return <CircularProgress size={10}/>;
    const total = usage.accounts + usage.posts + usage.media + usage.media_parts;
    if (total === 0) return <Typography variant="caption" color="text.secondary">Unused</Typography>;
    const parts: React.ReactNode[] = [];
    if (usage.accounts) parts.push(
        <Link key="accounts" to={`/search?sm=accounts&t=${tagId}`} style={{fontSize: 'inherit'}}>
            {usage.accounts} {usage.accounts === 1 ? 'account' : 'accounts'}
        </Link>
    );
    if (usage.posts) parts.push(
        <Link key="posts" to={`/search?sm=posts&t=${tagId}`} style={{fontSize: 'inherit'}}>
            {usage.posts} {usage.posts === 1 ? 'post' : 'posts'}
        </Link>
    );
    if (usage.media) parts.push(
        <Link key="media" to={`/search?sm=media&t=${tagId}`} style={{fontSize: 'inherit'}}>
            {usage.media} media
        </Link>
    );
    if (usage.media_parts) parts.push(
        <span key="parts">{usage.media_parts} {usage.media_parts === 1 ? 'part' : 'parts'}</span>
    );
    return (
        <Typography variant="caption" color="text.secondary">
            {parts.reduce<React.ReactNode[]>((acc, el, i) => i === 0 ? [el] : [...acc, ', ', el], [])}
        </Typography>
    );
}

/* ── Hierarchy section ────────────────────────────────────────────────────── */

function HierarchyTagSection({
    label,
    entries,
    getEntryId,
    getEntryTagName,
    editingNote,
    setEditingNote,
    onRemove,
    onNoteUpdate,
    setEntries,
    addTag,
    setAddTag,
    addOptions,
    setAddOptions,
    onAdd,
    addLabel,
}: {
    label: string;
    entries: ITagHierarchyEntry[];
    getEntryId: (e: ITagHierarchyEntry) => number;
    getEntryTagName: (e: ITagHierarchyEntry) => string | null | undefined;
    editingNote: {super_id: number; sub_id: number; notes: string} | null;
    setEditingNote: React.Dispatch<React.SetStateAction<{super_id: number; sub_id: number; notes: string} | null>>;
    onRemove: (e: ITagHierarchyEntry) => void;
    onNoteUpdate: (notes: string | null) => Promise<void>;
    setEntries: React.Dispatch<React.SetStateAction<ITagHierarchyEntry[]>>;
    addTag: ITagWithType | null;
    setAddTag: React.Dispatch<React.SetStateAction<ITagWithType | null>>;
    addOptions: ITagWithType[];
    setAddOptions: React.Dispatch<React.SetStateAction<ITagWithType[]>>;
    onAdd: () => Promise<void>;
    addLabel: string;
}) {
    const activeEditingNote = editingNote && entries.some(e => e.super_tag_id === editingNote.super_id && e.sub_tag_id === editingNote.sub_id)
        ? editingNote : null;

    const commitNote = async () => {
        if (!activeEditingNote) return;
        await onNoteUpdate(activeEditingNote.notes || null);
        setEntries(prev => prev.map(p =>
            p.super_tag_id === activeEditingNote.super_id && p.sub_tag_id === activeEditingNote.sub_id
                ? {...p, notes: activeEditingNote.notes || null}
                : p
        ));
        setEditingNote(null);
    };

    return (
        <Stack gap={0.5}>
            <Typography variant="caption" color="text.secondary">{label}</Typography>
            <Stack direction="row" gap={0.5} flexWrap="wrap" alignItems="center">
                {entries.map(e => (
                    <Stack key={getEntryId(e)} direction="row" alignItems="center" gap={0.25}>
                        <Tooltip title={e.notes || ''} arrow disableInteractive>
                            <Chip label={getEntryTagName(e)} size="small" onDelete={() => onRemove(e)}/>
                        </Tooltip>
                        <Tooltip title="Edit note" arrow disableInteractive>
                            <IconButton size="small" sx={{p: 0.25}} onClick={() => setEditingNote({super_id: e.super_tag_id, sub_id: e.sub_tag_id, notes: e.notes ?? ''})}>
                                <EditIcon sx={{fontSize: '0.8rem'}}/>
                            </IconButton>
                        </Tooltip>
                    </Stack>
                ))}
                {entries.length === 0 && <Typography variant="caption" color="text.secondary">None</Typography>}
            </Stack>
            {activeEditingNote && (
                <Stack direction="row" gap={1} alignItems="center">
                    <TextField
                        size="small"
                        label="Note"
                        value={activeEditingNote.notes}
                        onChange={e => setEditingNote(n => n ? {...n, notes: e.target.value} : null)}
                        onKeyDown={async e => {
                            if (e.key === 'Enter') { await commitNote(); }
                            else if (e.key === 'Escape') { setEditingNote(null); }
                        }}
                        onBlur={commitNote}
                        autoFocus
                        sx={{flex: 1}}
                    />
                </Stack>
            )}
            <Stack direction="row" gap={1} alignItems="center">
                <Autocomplete
                    sx={{flex: 1}}
                    size="small"
                    value={addTag}
                    onChange={(_, v) => setAddTag(v)}
                    onInputChange={async (_, v) => { if (v) setAddOptions(await lookupTags(v)); }}
                    options={addOptions}
                    getOptionLabel={o => o.name}
                    isOptionEqualToValue={(a, b) => a.id === b.id}
                    renderInput={params => <TextField {...params} label={addLabel} size="small"/>}
                />
                <Button size="small" variant="outlined" onClick={onAdd} disabled={!addTag}>Add</Button>
            </Stack>
        </Stack>
    );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

export default function EditTagPage() {
    const {tag_id} = useParams<{tag_id: string}>();
    const navigate = useNavigate();
    const tagId = Number(tag_id);

    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [tagTypes, setTagTypes] = useState<ITagType[]>([]);
    const [form, setForm] = useState<{name: string; description: string; tag_type_id: number | null; quick_access: boolean; omit_from_tag_type_dropdown: boolean; notes_recommended: boolean}>({
        name: '', description: '', tag_type_id: null, quick_access: false, omit_from_tag_type_dropdown: false, notes_recommended: true,
    });
    const [usage, setUsage] = useState<ITagUsage | null>(null);
    const [hierarchyParents, setHierarchyParents] = useState<ITagHierarchyEntry[]>([]);
    const [hierarchyChildren, setHierarchyChildren] = useState<ITagHierarchyEntry[]>([]);
    const [addParentTag, setAddParentTag] = useState<ITagWithType | null>(null);
    const [addParentOptions, setAddParentOptions] = useState<ITagWithType[]>([]);
    const [addChildTag, setAddChildTag] = useState<ITagWithType | null>(null);
    const [addChildOptions, setAddChildOptions] = useState<ITagWithType[]>([]);
    const [editingNote, setEditingNote] = useState<{super_id: number; sub_id: number; notes: string} | null>(null);

    useEffect(() => {
        if (!tagId) return;
        setLoading(true);
        Promise.all([
            fetchTag(tagId),
            fetchTagTypes(),
            fetchTagParents(tagId),
            fetchTagChildren(tagId),
            fetchTagUsage(tagId),
        ]).then(([tag, types, parents, children, tagUsage]) => {
            setTagTypes(types);
            setForm({
                name: tag.name,
                description: tag.description ?? '',
                tag_type_id: tag.tag_type_id ?? null,
                quick_access: tag.quick_access ?? false,
                omit_from_tag_type_dropdown: tag.omit_from_tag_type_dropdown ?? false,
                notes_recommended: tag.notes_recommended ?? true,
            });
            setHierarchyParents(parents);
            setHierarchyChildren(children);
            setUsage(tagUsage);
            setLoading(false);
        }).catch((e: any) => {
            if (e?.status === 404) {
                setNotFound(true);
            } else {
                toast.error(e?.message || 'Failed to load tag');
            }
            setLoading(false);
        });
        document.title = 'Edit Tag | Browsing Platform';
    }, [tagId]);

    const loadHierarchy = async () => {
        try {
            const [parents, children] = await Promise.all([fetchTagParents(tagId), fetchTagChildren(tagId)]);
            setHierarchyParents(parents);
            setHierarchyChildren(children);
        } catch (e: any) {
            toast.error(e?.message || 'Failed to refresh hierarchy');
        }
    };

    const handleSave = async () => {
        try {
            await updateTag(tagId, {
                name: form.name,
                description: form.description || null,
                tag_type_id: form.tag_type_id,
                quick_access: form.quick_access,
                omit_from_tag_type_dropdown: form.omit_from_tag_type_dropdown,
                notes_recommended: form.notes_recommended,
            });
            navigate('/tags?tab=tags');
        } catch (e: any) {
            toast.error(e?.message || 'Error saving tag');
        }
    };

    const handleAddParent = async () => {
        if (!addParentTag) return;
        try {
            await addHierarchy({super_tag_id: addParentTag.id, sub_tag_id: tagId, notes: null});
            setAddParentTag(null);
            await loadHierarchy();
        } catch (e: any) {
            toast.error(e?.message || 'Cannot add parent (may create a cycle)');
        }
    };

    const handleAddChild = async () => {
        if (!addChildTag) return;
        try {
            await addHierarchy({super_tag_id: tagId, sub_tag_id: addChildTag.id, notes: null});
            setAddChildTag(null);
            await loadHierarchy();
        } catch (e: any) {
            toast.error(e?.message || 'Cannot add child (may create a cycle)');
        }
    };

    const handleRemoveParent = async (entry: ITagHierarchyEntry) => {
        try {
            await removeHierarchy(entry.super_tag_id, entry.sub_tag_id);
            await loadHierarchy();
        } catch (e: any) {
            toast.error(e?.message || 'Cannot remove parent');
        }
    };

    const handleRemoveChild = async (entry: ITagHierarchyEntry) => {
        try {
            await removeHierarchy(entry.super_tag_id, entry.sub_tag_id);
            await loadHierarchy();
        } catch (e: any) {
            toast.error(e?.message || 'Cannot remove child');
        }
    };

    if (loading) return (
        <div className="page-wrap">
            <TopNavBar>Edit Tag</TopNavBar>
            <div className="page-content content-wrap">
                <CircularProgress/>
            </div>
        </div>
    );

    if (notFound) return (
        <div className="page-wrap">
            <TopNavBar>Edit Tag</TopNavBar>
            <div className="page-content content-wrap">
                <Typography>Tag not found.</Typography>
                <Button onClick={() => navigate('/tags?tab=tags')}>Back to Tags</Button>
            </div>
        </div>
    );

    return (
        <div className="page-wrap">
            <TopNavBar>Edit Tag: {form.name}</TopNavBar>
            <div className="page-content content-wrap">
                <Stack gap={2} sx={{maxWidth: 600}}>
                    <TextField
                        label="Name"
                        value={form.name}
                        onChange={e => setForm(f => ({...f, name: e.target.value}))}
                        error={form.name.includes(',')}
                        helperText={form.name.includes(',') ? 'Tag name cannot contain commas' : undefined}
                        required
                    />
                    <TextField
                        label="Description"
                        value={form.description}
                        onChange={e => setForm(f => ({...f, description: e.target.value}))}
                    />
                    <FormControl size="small">
                        <InputLabel>Tag Type</InputLabel>
                        <Select
                            value={form.tag_type_id ?? ''}
                            label="Tag Type"
                            onChange={e => setForm(f => ({...f, tag_type_id: e.target.value ? Number(e.target.value) : null}))}
                        >
                            <MenuItem value=""><em>None</em></MenuItem>
                            {tagTypes.map(tt => <MenuItem key={tt.id} value={tt.id}>{tt.name}</MenuItem>)}
                        </Select>
                    </FormControl>
                    <FormControlLabel
                        control={<Checkbox checked={form.quick_access} onChange={e => setForm(f => ({...f, quick_access: e.target.checked}))}/>}
                        label="Quick access (show as shortcut button in annotator)"
                    />
                    <FormControlLabel
                        control={<Checkbox checked={form.notes_recommended} onChange={e => setForm(f => ({...f, notes_recommended: e.target.checked}))}/>}
                        label="Prompt for notes on quick-assign"
                    />
                    <FormControlLabel
                        control={<Checkbox checked={form.omit_from_tag_type_dropdown} onChange={e => setForm(f => ({...f, omit_from_tag_type_dropdown: e.target.checked}))}/>}
                        label="Exclude from type dropdown (when type has quick access)"
                    />

                    <Divider/>
                    <Typography variant="subtitle2">Hierarchy</Typography>
                    <HierarchyTagSection
                        label="Parents (supertags)"
                        entries={hierarchyParents}
                        getEntryId={e => e.super_tag_id}
                        getEntryTagName={e => e.super_tag_name}
                        editingNote={editingNote}
                        setEditingNote={setEditingNote}
                        onRemove={handleRemoveParent}
                        onNoteUpdate={notes => updateHierarchyNotes(editingNote!.super_id, editingNote!.sub_id, notes)}
                        setEntries={setHierarchyParents}
                        addTag={addParentTag}
                        setAddTag={setAddParentTag}
                        addOptions={addParentOptions}
                        setAddOptions={setAddParentOptions}
                        onAdd={handleAddParent}
                        addLabel="Add parent"
                    />
                    <HierarchyTagSection
                        label="Children (subtags)"
                        entries={hierarchyChildren}
                        getEntryId={e => e.sub_tag_id}
                        getEntryTagName={e => e.sub_tag_name}
                        editingNote={editingNote}
                        setEditingNote={setEditingNote}
                        onRemove={handleRemoveChild}
                        onNoteUpdate={notes => updateHierarchyNotes(editingNote!.super_id, editingNote!.sub_id, notes)}
                        setEntries={setHierarchyChildren}
                        addTag={addChildTag}
                        setAddTag={setAddChildTag}
                        addOptions={addChildOptions}
                        setAddOptions={setAddChildOptions}
                        onAdd={handleAddChild}
                        addLabel="Add child"
                    />

                    <Divider/>
                    <Typography variant="subtitle2">Usage</Typography>
                    <UsageSummary usage={usage} tagId={tagId}/>

                    <Box sx={{display: 'flex', gap: 1, pt: 1}}>
                        <Button variant="outlined" onClick={() => navigate('/tags?tab=tags')}>Cancel</Button>
                        <Button
                            variant="contained"
                            onClick={handleSave}
                            disabled={form.name.includes(',') || !form.name.trim()}
                        >
                            Save
                        </Button>
                    </Box>
                </Stack>
            </div>
        </div>
    );
}
