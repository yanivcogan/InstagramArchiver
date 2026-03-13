export const removeUndefinedValues = (obj: any) => {
    if (typeof obj === "object") {
        Object.keys(obj).forEach(key => obj[key] === undefined ? delete obj[key] : {});
    }
    return JSON.parse(JSON.stringify(obj, (key, value) => value === undefined ? null : value));
}
