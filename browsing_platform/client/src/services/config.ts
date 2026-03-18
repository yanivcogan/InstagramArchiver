const envEndpoint = import.meta.env.VITE_SERVER_ENDPOINT;
const serverPath = envEndpoint || "http://localhost:4444/";

const config = {serverPath}

export default config