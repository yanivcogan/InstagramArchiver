import papa from "papaparse";

const generateCSV:(data:any[][]) => string = (data: { [key: string]: any }[]) => {
    const data_copy: { [key: string]: any }[] = JSON.parse(JSON.stringify(data));
    data_copy.forEach((row) => {
        Array.from(Object.keys(row)).forEach((index) => {
            const cell = row[index];
            if (typeof cell === "object" && cell !== null) {
                row[index] = JSON.stringify(cell);
            }
        });
    })
    return papa.unparse(data_copy);
};

export const downloadCSV = (filename:string, content:string | any[][]) => {
    const csv = content instanceof Array ? generateCSV(content) : content;
    const blob = new Blob(["\uFEFF" + csv], {type: "text/csv;charset=utf-8,%EF%BB%BF"});
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename + ".csv";
    link.innerHTML = "Click here to download the file";
    document.body.appendChild(link);
    link.click();
    if(link.parentElement) {link.parentElement.removeChild(link)}
};