export const removeUndefinedValues = (obj: any) => {
    if (typeof obj === "object") {
        Object.keys(obj).forEach(key => obj[key] === undefined ? delete obj[key] : {});
    }
    return JSON.parse(JSON.stringify(obj, (key, value) => value === undefined ? null : value));
}

export function downloadTextFile(content: string, filename: string, mimeType: string): void {
    const blob = new Blob([content], {type: mimeType});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
