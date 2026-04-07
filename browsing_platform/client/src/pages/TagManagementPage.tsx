import React, {useEffect, useState} from 'react';
import {Link, useSearchParams} from 'react-router';
import {
    Badge,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    List,
    ListItemButton,
    ListItemText,
    MenuItem,
    OutlinedInput,
    Select,
    Stack,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Tabs,
    TextField,
    Tooltip,
    Typography,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import AddIcon from "@mui/icons-material/Add";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import {ITagDetail, ITagHierarchyEntry, ITagType, ITagUsage, ITagWithType} from "../types/tags";
import {
    addHierarchy,
    createTag,
    createTagType,
    deleteTag,
    deleteTagType,
    fetchTagChildren,
    fetchTagParents,
    fetchTags,
    fetchTagTypeCounts,
    fetchTagTypes,
    fetchTagUsage,
    removeHierarchy,
    updateHierarchyNotes,
    updateTag,
    updateTagType,
} from "../services/TagManagementService";
import {lookupTags} from "../services/DataFetcher";
import Autocomplete from "@mui/material/Autocomplete";
import {toast} from "material-react-toastify";
import ImportTagsTab from "./TagManagement/ImportTagsTab";
import ImportAnnotationsTab from "./TagManagement/ImportAnnotationsTab";

const ENTITY_AFFINITY_OPTIONS = ["account", "post", "media", "media_part"];

/* ── Shared helpers ─────────────────────────────────────────────────────────── */

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

/* ── Tab 1: Tag Types ───────────────────────────────────────────────────────── */

function TagTypesTab() {
    const [tagTypes, setTagTypes] = useState<ITagType[]>([]);
    const [loading, setLoading] = useState(true);
    const [editTarget, setEditTarget] = useState<ITagType | null>(null);
    const [formOpen, setFormOpen] = useState(false);
    const [form, setForm] = useState<Omit<ITagType, "id">>({name: "", description: null, notes: null, entity_affinity: null});

    const load = () => {
        setLoading(true);
        fetchTagTypes().then(data => { setTagTypes(data); setLoading(false); });
    };
    useEffect(load, []);

    const openCreate = () => {
        setEditTarget(null);
        setForm({name: "", description: null, notes: null, entity_affinity: null});
        setFormOpen(true);
    };

    const openEdit = (tt: ITagType) => {
        setEditTarget(tt);
        setForm({name: tt.name, description: tt.description ?? null, notes: tt.notes ?? null, entity_affinity: tt.entity_affinity ?? null});
        setFormOpen(true);
    };

    const handleSave = async () => {
        try {
            if (editTarget?.id) {
                await updateTagType(editTarget.id, form);
            } else {
                await createTagType(form);
            }
            setFormOpen(false);
            load();
        } catch (e: any) {
            toast.error(e?.message || "Error saving tag type");
        }
    };

    const handleDelete = async (tt: ITagType) => {
        if (!tt.id) return;
        try {
            await deleteTagType(tt.id);
            load();
        } catch (e: any) {
            toast.error(e?.message || "Cannot delete tag type");
        }
    };

    if (loading) return <CircularProgress/>;

    return <Stack gap={2}>
        <Box>
            <Button variant="contained" startIcon={<AddIcon/>} onClick={openCreate}>New Tag Type</Button>
        </Box>
        <Table size="small">
            <TableHead>
                <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Entity Affinity</TableCell>
                    <TableCell/>
                </TableRow>
            </TableHead>
            <TableBody>
                {tagTypes.map(tt => (
                    <TableRow key={tt.id}>
                        <TableCell>{tt.name}</TableCell>
                        <TableCell>{tt.description}</TableCell>
                        <TableCell>
                            <Stack direction="row" gap={0.5} flexWrap="wrap">
                                {tt.entity_affinity?.map(e => <Chip key={e} label={e} size="small"/>)}
                            </Stack>
                        </TableCell>
                        <TableCell>
                            <IconButton size="small" onClick={() => openEdit(tt)}><EditIcon fontSize="small"/></IconButton>
                            <IconButton size="small" color="error" onClick={() => handleDelete(tt)}><DeleteIcon fontSize="small"/></IconButton>
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>

        <Dialog open={formOpen} onClose={() => setFormOpen(false)} maxWidth="sm" fullWidth>
            <DialogTitle>{editTarget ? "Edit Tag Type" : "New Tag Type"}</DialogTitle>
            <DialogContent>
                <Stack gap={2} sx={{mt: 1}}>
                    <TextField label="Name" value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} required/>
                    <TextField label="Description" value={form.description ?? ""} onChange={e => setForm(f => ({...f, description: e.target.value || null}))}/>
                    <TextField label="Notes" multiline value={form.notes ?? ""} onChange={e => setForm(f => ({...f, notes: e.target.value || null}))}/>
                    <FormControl>
                        <InputLabel>Entity Affinity</InputLabel>
                        <Select
                            multiple
                            value={form.entity_affinity ?? []}
                            onChange={e => setForm(f => ({...f, entity_affinity: e.target.value as string[] || null}))}
                            input={<OutlinedInput label="Entity Affinity"/>}
                            renderValue={(sel) => (
                                <Stack direction="row" gap={0.5} flexWrap="wrap">
                                    {(sel as string[]).map(v => <Chip key={v} label={v} size="small"/>)}
                                </Stack>
                            )}
                        >
                            {ENTITY_AFFINITY_OPTIONS.map(o => <MenuItem key={o} value={o}>{o}</MenuItem>)}
                        </Select>
                    </FormControl>
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={() => setFormOpen(false)}>Cancel</Button>
                <Button variant="contained" onClick={handleSave}>Save</Button>
            </DialogActions>
        </Dialog>
    </Stack>;
}

/* ── Hierarchy section (shared by Parents and Children panels) ──────────────── */

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
    onNoteUpdate: (entry: ITagHierarchyEntry, notes: string | null) => Promise<void>;
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
                            if (e.key === 'Enter') {
                                await onNoteUpdate(entries.find(x => x.super_tag_id === activeEditingNote.super_id && x.sub_tag_id === activeEditingNote.sub_id)!, activeEditingNote.notes || null);
                                setEntries(prev => prev.map(p => p.super_tag_id === activeEditingNote.super_id && p.sub_tag_id === activeEditingNote.sub_id ? {...p, notes: activeEditingNote.notes || null} : p));
                                setEditingNote(null);
                            } else if (e.key === 'Escape') { setEditingNote(null); }
                        }}
                        onBlur={async () => {
                            await onNoteUpdate(entries.find(x => x.super_tag_id === activeEditingNote.super_id && x.sub_tag_id === activeEditingNote.sub_id)!, activeEditingNote.notes || null);
                            setEntries(prev => prev.map(p => p.super_tag_id === activeEditingNote.super_id && p.sub_tag_id === activeEditingNote.sub_id ? {...p, notes: activeEditingNote.notes || null} : p));
                            setEditingNote(null);
                        }}
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

/* ── Tab 2: Tags ────────────────────────────────────────────────────────────── */

function TagsTab() {
    const [params, setParams] = useSearchParams();
    const selectedTypeId = params.get('type') ? Number(params.get('type')) : null;
    const setSelectedTypeId = (id: number | null) => {
        setPage(1);
        setParams(p => {
            const next = new URLSearchParams(p);
            if (id == null) next.delete('type'); else next.set('type', String(id));
            return next;
        });
    };

    const [tagTypes, setTagTypes] = useState<ITagType[]>([]);
    const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
    const [tags, setTags] = useState<ITagDetail[]>([]);
    const [search, setSearch] = useState("");
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const PAGE_SIZE = 50;
    const [formOpen, setFormOpen] = useState(false);
    const [editTarget, setEditTarget] = useState<ITagDetail | null>(null);
    const [form, setForm] = useState<{name: string; description: string; tag_type_id: number | null; quick_access: boolean}>({
        name: "", description: "", tag_type_id: null, quick_access: false
    });
    const [editUsage, setEditUsage] = useState<ITagUsage | null>(null);

    // Hierarchy state (only active while dialog is open for an existing tag)
    const [hierarchyParents, setHierarchyParents] = useState<ITagHierarchyEntry[]>([]);
    const [hierarchyChildren, setHierarchyChildren] = useState<ITagHierarchyEntry[]>([]);
    const [hierarchyLoading, setHierarchyLoading] = useState(false);
    const [addParentTag, setAddParentTag] = useState<ITagWithType | null>(null);
    const [addParentOptions, setAddParentOptions] = useState<ITagWithType[]>([]);
    const [addChildTag, setAddChildTag] = useState<ITagWithType | null>(null);
    const [addChildOptions, setAddChildOptions] = useState<ITagWithType[]>([]);
    const [editingNote, setEditingNote] = useState<{super_id: number; sub_id: number; notes: string} | null>(null);

    const loadTypes = () => {
        fetchTagTypes().then(setTagTypes);
        fetchTagTypeCounts().then(setTypeCounts).catch(() => {});
    };
    const loadTags = () => {
        setLoading(true);
        fetchTags({tag_type_id: selectedTypeId ?? undefined, q: search || undefined, page, page_size: PAGE_SIZE}).then(data => {
            setTags(data);
            setLoading(false);
        });
    };

    useEffect(() => { loadTypes(); }, []);
    useEffect(() => { loadTags(); }, [selectedTypeId, search, page]);

    const loadHierarchy = async (tagId: number) => {
        setHierarchyLoading(true);
        const [parents, children] = await Promise.all([fetchTagParents(tagId), fetchTagChildren(tagId)]);
        setHierarchyParents(parents);
        setHierarchyChildren(children);
        setHierarchyLoading(false);
    };

    const openCreate = () => {
        setEditTarget(null);
        setForm({name: "", description: "", tag_type_id: selectedTypeId, quick_access: false});
        setHierarchyParents([]);
        setHierarchyChildren([]);
        setAddParentTag(null);
        setAddChildTag(null);
        setFormOpen(true);
    };

    const openEdit = (t: ITagDetail) => {
        setEditTarget(t);
        setForm({name: t.name, description: t.description ?? "", tag_type_id: t.tag_type_id ?? null, quick_access: t.quick_access ?? false});
        setHierarchyParents([]);
        setHierarchyChildren([]);
        setAddParentTag(null);
        setAddChildTag(null);
        setEditUsage(null);
        if (t.id) {
            loadHierarchy(t.id);
            fetchTagUsage(t.id).then(setEditUsage);
        }
        setFormOpen(true);
    };

    const handleSave = async () => {
        try {
            if (editTarget?.id) {
                await updateTag(editTarget.id, {name: form.name, description: form.description || null, tag_type_id: form.tag_type_id, quick_access: form.quick_access});
            } else {
                await createTag({name: form.name, description: form.description || null, tag_type_id: form.tag_type_id, quick_access: form.quick_access});
            }
            setFormOpen(false);
            loadTags();
        } catch (e: any) {
            toast.error(e?.message || "Error saving tag");
        }
    };

    const handleDelete = async (t: ITagDetail) => {
        if (!t.id) return;
        try {
            await deleteTag(t.id);
            loadTags();
        } catch (e: any) {
            toast.error(e?.message || "Cannot delete tag");
        }
    };

    const handleToggleQuickAccess = async (t: ITagDetail) => {
        if (!t.id) return;
        const newValue = !t.quick_access;
        setTags(prev => prev.map(tag => tag.id === t.id ? {...tag, quick_access: newValue} : tag));
        try {
            await updateTag(t.id, {name: t.name, description: t.description ?? null, tag_type_id: t.tag_type_id ?? null, quick_access: newValue});
        } catch (e: any) {
            setTags(prev => prev.map(tag => tag.id === t.id ? {...tag, quick_access: !newValue} : tag));
            toast.error(e?.message || "Error updating quick access");
        }
    };

    const handleAddParent = async () => {
        if (!addParentTag || !editTarget?.id) return;
        try {
            await addHierarchy({super_tag_id: addParentTag.id, sub_tag_id: editTarget.id, notes: null});
            setAddParentTag(null);
            loadHierarchy(editTarget.id);
        } catch (e: any) {
            toast.error(e?.message || "Cannot add parent (may create a cycle)");
        }
    };

    const handleAddChild = async () => {
        if (!addChildTag || !editTarget?.id) return;
        try {
            await addHierarchy({super_tag_id: editTarget.id, sub_tag_id: addChildTag.id, notes: null});
            setAddChildTag(null);
            loadHierarchy(editTarget.id);
        } catch (e: any) {
            toast.error(e?.message || "Cannot add child (may create a cycle)");
        }
    };

    const handleRemoveParent = async (entry: ITagHierarchyEntry) => {
        await removeHierarchy(entry.super_tag_id, entry.sub_tag_id);
        if (editTarget?.id) loadHierarchy(editTarget.id);
    };

    const handleRemoveChild = async (entry: ITagHierarchyEntry) => {
        await removeHierarchy(entry.super_tag_id, entry.sub_tag_id);
        if (editTarget?.id) loadHierarchy(editTarget.id);
    };

    const totalCount = Object.values(typeCounts).reduce((a, b) => a + b, 0);

    return <Stack direction="row" gap={2} sx={{minHeight: 400}}>
        {/* Left sidebar: tag type filter */}
        <Stack sx={{width: 190, borderRight: '1px solid #e0e0e0', pr: 1, flexShrink: 0}}>
            <Typography variant="caption" sx={{mb: 0.5, color: 'text.secondary', fontWeight: 600, pl: 1}}>Filter by type</Typography>
            <List dense disablePadding>
                <ListItemButton
                    selected={selectedTypeId === null}
                    onClick={() => setSelectedTypeId(null)}
                    sx={{borderRadius: 1}}
                >
                    <ListItemText primary="All" primaryTypographyProps={{variant: 'body2'}}/>
                    <Badge badgeContent={totalCount} color="default" max={9999}
                           sx={{'& .MuiBadge-badge': {position: 'static', transform: 'none', ml: 1}}}/>
                </ListItemButton>
                {tagTypes.map(tt => (
                    <ListItemButton
                        key={tt.id}
                        selected={selectedTypeId === tt.id}
                        onClick={() => setSelectedTypeId(tt.id ?? null)}
                        sx={{borderRadius: 1}}
                    >
                        <ListItemText primary={tt.name} primaryTypographyProps={{variant: 'body2'}}/>
                        <Badge
                            badgeContent={typeCounts[String(tt.id)] ?? 0}
                            color="primary" max={9999}
                            sx={{'& .MuiBadge-badge': {position: 'static', transform: 'none', ml: 1}}}
                        />
                    </ListItemButton>
                ))}
                {typeCounts['null'] > 0 && (
                    <ListItemButton
                        selected={false}
                        disabled
                        sx={{borderRadius: 1}}
                    >
                        <ListItemText primary="(untyped)" primaryTypographyProps={{variant: 'body2', color: 'text.secondary'}}/>
                        <Badge badgeContent={typeCounts['null']} color="default" max={9999}
                               sx={{'& .MuiBadge-badge': {position: 'static', transform: 'none', ml: 1}}}/>
                    </ListItemButton>
                )}
            </List>
        </Stack>
        {/* Right: tag table */}
        <Stack gap={1} sx={{flex: 1}}>
            <Stack direction="row" gap={1}>
                <TextField size="small" placeholder="Search tags…" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} sx={{flex: 1}}/>
                <Button variant="contained" startIcon={<AddIcon/>} onClick={openCreate}>New Tag</Button>
            </Stack>
            {loading ? <CircularProgress/> : (
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>Name</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Description</TableCell>
                            <TableCell>Parents</TableCell>
                            <TableCell>Quick Access</TableCell>
                            <TableCell/>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {tags.map(t => (
                            <TableRow key={t.id}>
                                <TableCell>{t.name}</TableCell>
                                <TableCell>{t.tag_type_name && <Chip label={t.tag_type_name} size="small"/>}</TableCell>
                                <TableCell>{t.description}</TableCell>
                                <TableCell>
                                    <Stack direction="row" gap={0.5} flexWrap="wrap">
                                        {t.parents?.map(p => <Chip key={p.id} label={p.name} size="small" variant="outlined"/>)}
                                    </Stack>
                                </TableCell>
                                <TableCell padding="checkbox">
                                    <Checkbox
                                        checked={!!t.quick_access}
                                        size="small"
                                        onChange={() => handleToggleQuickAccess(t)}
                                    />
                                </TableCell>
                                <TableCell>
                                    <IconButton size="small" onClick={() => openEdit(t)}><EditIcon fontSize="small"/></IconButton>
                                    <IconButton size="small" color="error" onClick={() => handleDelete(t)}><DeleteIcon fontSize="small"/></IconButton>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            )}
            <Stack direction="row" justifyContent="center" alignItems="center" gap={2}>
                <Button size="small" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
                <Typography variant="caption">Page {page}</Typography>
                <Button size="small" disabled={tags.length < PAGE_SIZE} onClick={() => setPage(p => p + 1)}>Next</Button>
            </Stack>
        </Stack>

        <Dialog open={formOpen} onClose={() => setFormOpen(false)} maxWidth="sm" fullWidth>
            <DialogTitle>{editTarget ? "Edit Tag" : "New Tag"}</DialogTitle>
            <DialogContent>
                <Stack gap={2} sx={{mt: 1}}>
                    <TextField
                        label="Name"
                        value={form.name}
                        onChange={e => setForm(f => ({...f, name: e.target.value}))}
                        error={form.name.includes(',')}
                        helperText={form.name.includes(',') ? 'Tag name cannot contain commas' : undefined}
                        required
                    />
                    <TextField label="Description" value={form.description} onChange={e => setForm(f => ({...f, description: e.target.value}))}/>
                    <FormControl size="small">
                        <InputLabel>Tag Type</InputLabel>
                        <Select
                            value={form.tag_type_id ?? ""}
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

                    {/* Hierarchy — only shown when editing an existing tag */}
                    {editTarget?.id && <>
                        <Divider/>
                        <Typography variant="subtitle2">Hierarchy</Typography>
                        {hierarchyLoading ? <CircularProgress size={20}/> : <>
                            <HierarchyTagSection
                                label="Parents (supertags)"
                                entries={hierarchyParents}
                                getEntryId={e => e.super_tag_id}
                                getEntryTagName={e => e.super_tag_name}
                                editingNote={editingNote}
                                setEditingNote={setEditingNote}
                                onRemove={handleRemoveParent}
                                onNoteUpdate={(_, notes) => updateHierarchyNotes(editingNote!.super_id, editingNote!.sub_id, notes)}
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
                                onNoteUpdate={(_, notes) => updateHierarchyNotes(editingNote!.super_id, editingNote!.sub_id, notes)}
                                setEntries={setHierarchyChildren}
                                addTag={addChildTag}
                                setAddTag={setAddChildTag}
                                addOptions={addChildOptions}
                                setAddOptions={setAddChildOptions}
                                onAdd={handleAddChild}
                                addLabel="Add child"
                            />
                        </>}

                        <Divider/>
                        <Typography variant="subtitle2">Usage</Typography>
                        <UsageSummary usage={editUsage} tagId={editTarget.id}/>
                    </>}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={() => setFormOpen(false)}>Cancel</Button>
                <Button variant="contained" onClick={handleSave} disabled={form.name.includes(',') || !form.name.trim()}>Save</Button>
            </DialogActions>
        </Dialog>
    </Stack>;
}

/* ── Main Page ──────────────────────────────────────────────────────────────── */

const TAB_KEYS = ['types', 'tags', 'import-tags', 'import-annotations'];

export default function TagManagementPage() {
    const [params, setParams] = useSearchParams();
    const tab = Math.max(0, TAB_KEYS.indexOf(params.get('tab') ?? 'types'));

    const setTab = (v: number) => setParams(p => {
        const next = new URLSearchParams(p);
        next.set('tab', TAB_KEYS[v]);
        if (TAB_KEYS[v] !== 'tags') next.delete('type');
        return next;
    });

    useEffect(() => {
        document.title = "Tags | Browsing Platform";
    }, []);

    return <div className="page-wrap">
        <TopNavBar>Tags</TopNavBar>
        <div className="page-content content-wrap">
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{mb: 2}}>
                <Tab label="Tag Types"/>
                <Tab label="Tags"/>
                <Tab label="Import Tags"/>
                <Tab label="Import Annotations"/>
            </Tabs>
            <Divider sx={{mb: 2}}/>
            {tab === 0 && <TagTypesTab/>}
            {tab === 1 && <TagsTab/>}
            {tab === 2 && <ImportTagsTab/>}
            {tab === 3 && <ImportAnnotationsTab/>}
        </div>
    </div>;
}
