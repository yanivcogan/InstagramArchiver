/** djb2 hash → hue in [0, 360) */
export function tagTypeNameToHue(name: string): number {
    let hash = 5381;
    for (let i = 0; i < name.length; i++) {
        hash = (hash * 33) ^ name.charCodeAt(i);
    }
    return Math.abs(hash) % 360;
}

export function tagTypeNameToColor(name: string | null): { bg: string; text: string } {
    if(name === null){
        return {bg: "#e0e0e0", text: "#000"}
    }
    const hue = tagTypeNameToHue(name);
    return {
        bg: `hsl(${hue}, 55%, 85%)`,
        text: `hsl(${hue}, 55%, 25%)`,
    };
}
