const envEndpoint = import.meta.env.VITE_SERVER_ENDPOINT;
const serverPath = envEndpoint || "http://localhost:4444/";

// console.log(`[config] serverPath: ${serverPath}`);

const config = {serverPath}

export default config