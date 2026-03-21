import React, {useEffect, useState} from 'react';
import {
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
    Typography,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import AddIcon from "@mui/icons-material/Add";
import TopNavBar from "../UIComponents/TopNavBar/TopNavBar";
import {ITagDetail, ITagHierarchyEntry, ITagType, ITagUsage} from "../types/tags";
import {ITagWithType} from "../types/tags";
import {
    addHierarchy,
    createTag,
    createTagType,
    deleteTag,
    deleteTagType,
    fetchTagChildren,
    fetchTagParents,
    fetchTagTypes,
    fetchTagUsage,
    fetchTags,
    removeHierarchy,
    updateTag,
    updateTagType,
} from "../services/TagManagementService";
import {lookupTags} from "../services/DataFetcher";
import Autocomplete from "@mui/material/Autocomplete";
import {toast} from "material-react-toastify";

const ENTITY_AFFINITY_OPTIONS = ["account", "post", "media", "media_part"];

/* ── Shared helpers ─────────────────────────────────────────────────────────── */

function UsageSummary({usage}: {usage: ITagUsage | null}) {
    if (!usage) return null;
    const total = usage.accounts + usage.posts + usage.media + usage.media_parts;
    if (total === 0) return <Typography variant="caption" color="text.secondary">Unused</Typography>;
    const parts = [];
    if (usage.accounts) parts.push(`${usage.accounts} acct`);
    if (usage.posts) parts.push(`${usage.posts} post`);
    if (usage.media) parts.push(`${usage.media} media`);
    if (usage.media_parts) parts.push(`${usage.media_parts} part`);
    return <Typography variant="caption" color="text.secondary">{parts.join(", ")}</Typography>;
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

/* ── Tab 2: Tags ────────────────────────────────────────────────────────────── */

function TagsTab() {
    const [tagTypes, setTagTypes] = useState<ITagType[]>([]);
    const [tags, setTags] = useState<ITagDetail[]>([]);
    const [selectedTypeId, setSelectedTypeId] = useState<number | null>(null);
    const [search, setSearch] = useState("");
    const [loading, setLoading] = useState(true);
    const [formOpen, setFormOpen] = useState(false);
    const [editTarget, setEditTarget] = useState<ITagDetail | null>(null);
    const [form, setForm] = useState<{name: string; description: string; tag_type_id: number | null; quick_access: boolean}>({
        name: "", description: "", tag_type_id: null, quick_access: false
    });
    const [usageMap, setUsageMap] = useState<Record<number, ITagUsage>>({});

    // Hierarchy state (only active while dialog is open for an existing tag)
    const [hierarchyParents, setHierarchyParents] = useState<ITagHierarchyEntry[]>([]);
    const [hierarchyChildren, setHierarchyChildren] = useState<ITagHierarchyEntry[]>([]);
    const [hierarchyLoading, setHierarchyLoading] = useState(false);
    const [addParentTag, setAddParentTag] = useState<ITagWithType | null>(null);
    const [addParentOptions, setAddParentOptions] = useState<ITagWithType[]>([]);
    const [addChildTag, setAddChildTag] = useState<ITagWithType | null>(null);
    const [addChildOptions, setAddChildOptions] = useState<ITagWithType[]>([]);

    const loadTypes = () => fetchTagTypes().then(setTagTypes);
    const loadTags = () => {
        setLoading(true);
        fetchTags({tag_type_id: selectedTypeId ?? undefined, q: search || undefined}).then(data => {
            setTags(data);
            setLoading(false);
        });
    };

    useEffect(() => { loadTypes(); }, []);
    useEffect(() => { loadTags(); }, [selectedTypeId, search]);

    const loadUsage = async (tagId: number) => {
        if (usageMap[tagId]) return;
        const u = await fetchTagUsage(tagId);
        setUsageMap(m => ({...m, [tagId]: u}));
    };

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
        if (t.id) loadHierarchy(t.id);
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

    return <Stack direction="row" gap={2} sx={{minHeight: 400}}>
        {/* Left sidebar: tag type filter */}
        <Stack sx={{width: 180, borderRight: '1px solid #e0e0e0', pr: 1}}>
            <Typography variant="caption" sx={{mb: 1, color: 'text.secondary'}}>Filter by type</Typography>
            <Button size="small" variant={selectedTypeId === null ? "contained" : "text"} onClick={() => setSelectedTypeId(null)}>All</Button>
            {tagTypes.map(tt => (
                <Button key={tt.id} size="small" variant={selectedTypeId === tt.id ? "contained" : "text"} onClick={() => setSelectedTypeId(tt.id ?? null)}>
                    {tt.name}
                </Button>
            ))}
        </Stack>
        {/* Right: tag table */}
        <Stack gap={1} sx={{flex: 1}}>
            <Stack direction="row" gap={1}>
                <TextField size="small" placeholder="Search tags…" value={search} onChange={e => setSearch(e.target.value)} sx={{flex: 1}}/>
                <Button variant="contained" startIcon={<AddIcon/>} onClick={openCreate}>New Tag</Button>
            </Stack>
            {loading ? <CircularProgress/> : (
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>Name</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Description</TableCell>
                            <TableCell>Quick Access</TableCell>
                            <TableCell>Usage</TableCell>
                            <TableCell/>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {tags.map(t => (
                            <TableRow key={t.id} onMouseEnter={() => t.id && loadUsage(t.id)}>
                                <TableCell>{t.name}</TableCell>
                                <TableCell>{t.tag_type_name && <Chip label={t.tag_type_name} size="small"/>}</TableCell>
                                <TableCell>{t.description}</TableCell>
                                <TableCell>{t.quick_access ? "✓" : ""}</TableCell>
                                <TableCell><UsageSummary usage={t.id ? usageMap[t.id] ?? null : null}/></TableCell>
                                <TableCell>
                                    <IconButton size="small" onClick={() => openEdit(t)}><EditIcon fontSize="small"/></IconButton>
                                    <IconButton size="small" color="error" onClick={() => handleDelete(t)}><DeleteIcon fontSize="small"/></IconButton>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            )}
        </Stack>

        <Dialog open={formOpen} onClose={() => setFormOpen(false)} maxWidth="sm" fullWidth>
            <DialogTitle>{editTarget ? "Edit Tag" : "New Tag"}</DialogTitle>
            <DialogContent>
                <Stack gap={2} sx={{mt: 1}}>
                    <TextField label="Name" value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} required/>
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
                            <Stack gap={0.5}>
                                <Typography variant="caption" color="text.secondary">Parents (supertags)</Typography>
                                <Stack direction="row" gap={0.5} flexWrap="wrap">
                                    {hierarchyParents.map(e => (
                                        <Chip
                                            key={e.super_tag_id}
                                            label={e.super_tag_name}
                                            size="small"
                                            onDelete={() => handleRemoveParent(e)}
                                        />
                                    ))}
                                    {hierarchyParents.length === 0 && <Typography variant="caption" color="text.secondary">None</Typography>}
                                </Stack>
                                <Stack direction="row" gap={1} alignItems="center">
                                    <Autocomplete
                                        sx={{flex: 1}}
                                        size="small"
                                        value={addParentTag}
                                        onChange={(_, v) => setAddParentTag(v)}
                                        onInputChange={async (_, v) => { if (v) setAddParentOptions(await lookupTags(v)); }}
                                        options={addParentOptions}
                                        getOptionLabel={o => o.name}
                                        isOptionEqualToValue={(a, b) => a.id === b.id}
                                        renderInput={params => <TextField {...params} label="Add parent" size="small"/>}
                                    />
                                    <Button size="small" variant="outlined" onClick={handleAddParent} disabled={!addParentTag}>Add</Button>
                                </Stack>
                            </Stack>

                            <Stack gap={0.5}>
                                <Typography variant="caption" color="text.secondary">Children (subtags)</Typography>
                                <Stack direction="row" gap={0.5} flexWrap="wrap">
                                    {hierarchyChildren.map(e => (
                                        <Chip
                                            key={e.sub_tag_id}
                                            label={e.sub_tag_name}
                                            size="small"
                                            onDelete={() => handleRemoveChild(e)}
                                        />
                                    ))}
                                    {hierarchyChildren.length === 0 && <Typography variant="caption" color="text.secondary">None</Typography>}
                                </Stack>
                                <Stack direction="row" gap={1} alignItems="center">
                                    <Autocomplete
                                        sx={{flex: 1}}
                                        size="small"
                                        value={addChildTag}
                                        onChange={(_, v) => setAddChildTag(v)}
                                        onInputChange={async (_, v) => { if (v) setAddChildOptions(await lookupTags(v)); }}
                                        options={addChildOptions}
                                        getOptionLabel={o => o.name}
                                        isOptionEqualToValue={(a, b) => a.id === b.id}
                                        renderInput={params => <TextField {...params} label="Add child" size="small"/>}
                                    />
                                    <Button size="small" variant="outlined" onClick={handleAddChild} disabled={!addChildTag}>Add</Button>
                                </Stack>
                            </Stack>
                        </>}
                    </>}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={() => setFormOpen(false)}>Cancel</Button>
                <Button variant="contained" onClick={handleSave}>Save</Button>
            </DialogActions>
        </Dialog>
    </Stack>;
}

/* ── Main Page ──────────────────────────────────────────────────────────────── */

export default function TagManagementPage() {
    const [tab, setTab] = useState(0);

    useEffect(() => {
        document.title = "Tags | Browsing Platform";
    }, []);

    return <div className="page-wrap">
        <TopNavBar>Tags</TopNavBar>
        <div className="page-content content-wrap">
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{mb: 2}}>
                <Tab label="Tag Types"/>
                <Tab label="Tags"/>
            </Tabs>
            <Divider sx={{mb: 2}}/>
            {tab === 0 && <TagTypesTab/>}
            {tab === 1 && <TagsTab/>}
        </div>
    </div>;
}
